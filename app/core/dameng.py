"""达梦数据库连接模块"""
import importlib
import logging
import os
import re
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

# 强制 UTF-8 避免 dmPython 在中文 Windows 上用 GBK 编码导致特殊字符报错
os.environ['NLS_LANG'] = '.UTF8'

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.sql_schema_parser import parse_schema_from_file

settings = get_settings()
logger = get_logger("dameng")

# 达梦连接（同步模式）
_dm_conn = None

# Schema 缓存：table_name (lower) -> set of column_names (lower)
# 解析逻辑收敛在 app.core.sql_schema_parser，这里只做进程内单次缓存
_schema_cache: Dict[str, Set[str]] = {}
_schema_loaded = False


def _load_schema_from_file() -> Dict[str, Set[str]]:
    """从 sql_schema_parser 加载 schema，进程内只解析一次。"""
    global _schema_cache, _schema_loaded
    if _schema_loaded:
        return _schema_cache

    _schema_cache = parse_schema_from_file()
    _schema_loaded = True
    if _schema_cache:
        logger.info(f"已加载 {len(_schema_cache)} 个表的 schema 缓存")
    return _schema_cache


def get_table_columns(table_name: str) -> Set[str]:
    """获取指定表的列名集合（已转小写）"""
    cache = _load_schema_from_file()
    return cache.get(table_name.lower(), set())


def get_dameng_connection():
    """获取达梦数据库连接（同步）"""
    global _dm_conn

    if _dm_conn is not None:
        try:
            # 测试连接是否有效
            cursor = _dm_conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.close()
            return _dm_conn
        except Exception:
            _dm_conn = None

    # 尝试多个可能的达梦驱动模块名
    module_names = ["dmpython", "dmPython", "dmoes", "dmodb"]
    dm_module = None

    for module_name in module_names:
        try:
            dm_module = importlib.import_module(module_name)
            logger.info("成功导入达梦驱动模块: %s", module_name)
            break
        except ImportError:
            continue

    if dm_module is None:
        logger.error("未找到达梦驱动模块，请执行: pip install dmpython")
        raise ImportError("未找到达梦驱动模块")

    try:
        _dm_conn = dm_module.connect(
            host=settings.dameng.host,
            port=settings.dameng.port,
            user=settings.dameng.user,
            password=settings.dameng.password,
            schema=settings.dameng.schema,
        )
        logger.info("达梦数据库连接成功: %s@%s:%s/%s",
            settings.dameng.user, settings.dameng.host,
            settings.dameng.port, settings.dameng.schema)
        return _dm_conn
    except Exception as exc:
        logger.error("达梦数据库连接失败: %s", exc)
        raise


def close_dameng():
    """关闭达梦数据库连接"""
    global _dm_conn
    if _dm_conn is not None:
        try:
            _dm_conn.close()
        except Exception:
            pass
        _dm_conn = None
        logger.info("达梦数据库连接已关闭")


@contextmanager
def dameng_cursor() -> Iterator[Any]:
    """获取达梦数据库游标的上下文管理器"""
    conn = get_dameng_connection()
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def execute_query(sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """
    执行查询SQL并返回结果

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        查询结果列表，每行是一个字典
    """
    logger.info("=" * 80)
    logger.info(">>> 执行SQL查询 >>>")
    logger.info("SQL: %s", sql)
    if params:
        logger.info("参数: %s", params)
    logger.info("-" * 80)

    try:
        with dameng_cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取所有结果
            rows = cursor.fetchall()

            logger.info("返回 %d 行数据", len(rows))
            if rows:
                logger.info("示例数据: %s", dict(zip(columns, rows[0])))
            logger.info(">>> SQL执行成功 <<<")

            # 转换为字典列表
            return [dict(zip(columns, row)) for row in rows]
    except ImportError as exc:
        logger.warning("达梦驱动未安装: %s", exc)
        return []
    except Exception as exc:
        logger.error("=" * 80)
        logger.error(">>> SQL执行失败 <<<")
        logger.error("SQL: %s", sql)
        if params:
            logger.error("参数: %s", params)
        logger.error("错误: %s", exc)
        logger.error("堆栈: %s", traceback.format_exc())
        logger.error("=" * 80)
        return []


def execute_scalar(sql: str, params: Optional[Tuple] = None) -> Any:
    """
    执行查询SQL并返回第一行第一列的值

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        标量值
    """
    with dameng_cursor() as cursor:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        row = cursor.fetchone()
        return row[0] if row else None


def validate_sql_columns(sql: str, schema: str = "FWBZ") -> Tuple[bool, Optional[str], List[str]]:
    """
    严格验证 SQL 中所有表引用和列引用的合法性 (P0 重构版)。

    关键修复 (P0 修的 bug):
        1. 识别 FROM/JOIN 的表别名 (e.g. "r" = alarm_rules), 避免误判
        2. 排除 SELECT 列表 AS 别名 (e.g. COUNT(*) AS "cnt")
        3. 排除 ON 条件里的表别名引用

    验证规则:
        1. 【表白名单】FROM/JOIN 的真实表必须在 schema 中
        2. 【列白名单】对每个列引用:
           - qualified "alias"."col":  解析 alias → 真实表 → col 必须在该表
           - bare "col":  必须在查询涉及的所有表的列并集里
        3. SELECT 列表的 AS 别名 不参与校验

    Returns:
        (is_valid, error_message, invalid_items)
    """
    try:
        table_cols = _load_schema_from_file()
        if not table_cols:
            return True, None, []

        # ========== 步骤 1: 解析 FROM/JOIN 的表+别名映射 ==========
        alias_to_table: dict[str, str] = {}  # alias.lower() -> table.lower() 或 "__subquery__"
        sql_keywords_skip = {
            "select", "from", "where", "group", "order", "having", "limit",
            "offset", "union", "with", "on", "as", "join", "inner", "left",
            "right", "outer", "full", "cross", "and", "or", "not", "in",
            "is", "null", "like", "between", "exists", "case", "when",
            "then", "else", "end", "set", "values", "into", "update",
        }

        # 1a) 匹配 FROM/JOIN 物理表
        from_table_pattern = re.compile(
            r'\b(?:FROM|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN)\s+'
            r'(?:(?:"?FWBZ"?\s*\.\s*)?)?"?([A-Za-z_]\w*)"?'
            r'(?:\s+(?:AS\s+)?"?([A-Za-z_]\w*)"?)?',
            re.IGNORECASE,
        )
        for m in from_table_pattern.finditer(sql):
            table = m.group(1)
            alias = m.group(2)
            if not table:
                continue
            tl = table.lower()
            if tl in sql_keywords_skip:
                continue
            if not alias or alias.lower() in sql_keywords_skip:
                al = tl
            else:
                al = alias.lower()
            alias_to_table[al] = tl

        # 1b) 匹配 FROM/JOIN (subquery) [AS] alias
        # 用 Python 字符串扫描 (跳过嵌套括号)
        sub_start_pattern = re.compile(r'\b(?:FROM|JOIN)\s*\(', re.IGNORECASE)
        for m in sub_start_pattern.finditer(sql):
            # 找配对的 )
            depth = 1
            i = m.end()
            while i < len(sql) and depth > 0:
                c = sql[i]
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if i >= len(sql):
                continue
            # i 指向 ) 之后, 找 AS alias 或 alias
            j = i + 1
            while j < len(sql) and sql[j] in ' \t':
                j += 1
            rest = sql[j:]
            am = re.match(r'(?:AS\s+)?"?([A-Za-z_]\w*)"?\b', rest, re.IGNORECASE)
            if am and am.group(1).lower() not in sql_keywords_skip:
                alias_to_table[am.group(1).lower()] = "__subquery__"

        # ========== 步骤 2: 提取 SELECT 列表的 AS 别名 (跳过校验) ==========
        # 用字符串扫描 (不依赖正则) 找顶层 SELECT 列表, 跳过嵌套括号
        # (避免 EXTRACT 内的 FROM 干扰)
        select_aliases: set[str] = set()
        select_clause = _extract_top_select(sql)
        if select_clause:
            for m in re.finditer(
                r'\bAS\s+(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z_]\w*))',
                select_clause,
                re.IGNORECASE,
            ):
                alias = m.group(1) or m.group(2) or m.group(3)
                if alias and alias.lower() not in sql_keywords_skip:
                    select_aliases.add(alias.lower())

        # ========== 步骤 3: 校验表 (按真实表名, 不查别名; 子查询占位排除) ==========
        real_tables = {t for t in alias_to_table.values() if t != "__subquery__"}
        invalid_items: List[str] = []
        for t in real_tables:
            if t not in table_cols:
                invalid_items.append(f'表 "{t}" 不在数据库 schema 中（臆造表名）')
        if invalid_items:
            error_detail = "; ".join(invalid_items[:10])
            if len(invalid_items) > 10:
                error_detail += f" ...（共 {len(invalid_items)} 个问题）"
            return False, f"表引用不合法: {error_detail}", invalid_items

        if not real_tables:
            # 纯子查询, 没有物理表, 直接放行 (列无法静态校验)
            return True, None, []

        # ========== 步骤 4: 提取所有列引用 ==========
        # qualified 引用: "X"."Y"  → (X, Y)
        # bare 引用:     "Y"  (在非字符串字面量中)
        qualified_refs: List[Tuple[str, str]] = []
        bare_refs: List[str] = []

        # 先扫 qualified: 格式 "X"."Y"
        for qm in re.finditer(r'"([^"]+)"\s*\.\s*"([^"]+)"', sql):
            left, right = qm.group(1), qm.group(2)
            # 过滤: 不在 alias_to_table 里的可能是字符串, 跳过
            ll = left.lower()
            if ll in alias_to_table or ll in real_tables:
                qualified_refs.append((ll, right.lower()))

        # 再扫 bare: 所有 "X" 形式, 排除:
        #   - SQL 关键字
        #   - alias_to_table 的 key (别名)
        #   - 真实表名
        #   - SELECT 列表的 AS 别名
        #   - 函数参数 (EXTRACT/CONVERT/CAST 等的特定参数是关键字, 不是列)
        exclude_bare = (
            sql_keywords_skip
            | set(alias_to_table.keys())
            | real_tables
            | select_aliases
        )
        # 还要排除 schema 名 "fwbz"
        exclude_bare.add("fwbz")
        exclude_bare.add(schema.lower())
        # EXTRACT 第一个参数是日期部分关键字 (YEAR/MONTH/DAY/HOUR/MINUTE/SECOND/EPOCH/TIMEZONE 等)
        # CAST/CONVERT 第一个参数是类型关键字
        # TRUNC 第一个参数是时间字段
        for kw in [
            "year", "month", "day", "hour", "minute", "second",
            "epoch", "timezone_hour", "timezone_minute",
            "date", "time", "timestamp", "interval",
            "char", "varchar", "varchar2", "nvarchar", "text", "number",
            "int", "integer", "bigint", "smallint", "tinyint",
            "decimal", "numeric", "float", "double", "real",
            "binary", "varbinary", "blob", "clob",
        ]:
            exclude_bare.add(kw)

        for bm in re.finditer(r'"([^"]+)"', sql):
            bare = bm.group(1).lower()
            if bare in exclude_bare:
                continue
            # 排除 qualified 引用的右值
            if any(bare == c for _, c in qualified_refs):
                continue
            # 排除明显是函数包裹的 (粗略: 如果前面是 . 跳过, 因为 . 后是列)
            # 实际上 qualified regex 已经先匹配, 这里不需要
            bare_refs.append(bare)

        # ========== 步骤 5: 校验列 ==========
        invalid_cols: List[str] = []
        for table_alias, col_name in qualified_refs:
            # 真实表 (子查询占位的话直接跳过列校验)
            real_t = alias_to_table.get(table_alias, table_alias)
            if real_t == "__subquery__":
                # 子查询的列无法静态校验, 跳过
                continue
            if real_t not in real_tables:
                continue
            if col_name not in table_cols.get(real_t, set()):
                invalid_cols.append(
                    f'"{table_alias}"."{col_name}"（列 "{col_name}" 不在表 "{real_t}" 中）'
                )

        for col_name in bare_refs:
            # 裸列: 必须在查询涉及的所有表的列并集里
            owners = [t for t in real_tables if col_name in table_cols.get(t, set())]
            if not owners:
                # 整个 schema 都找不到 → 臆造
                schema_owners = [t for t, cols in table_cols.items() if col_name in cols]
                if schema_owners:
                    owners_str = ", ".join(f'"{t}"' for t in schema_owners[:3])
                    invalid_cols.append(
                        f'"{col_name}"（该列存在于 {owners_str} 等表，但不在当前查询中）'
                    )
                else:
                    invalid_cols.append(f'"{col_name}"（不在 schema 中，属于臆造列名）')

        if invalid_cols:
            error_detail = "; ".join(invalid_cols[:10])
            if len(invalid_cols) > 10:
                error_detail += f" ...（共 {len(invalid_cols)} 个问题列）"
            return False, f"列引用不合法: {error_detail}", invalid_cols

        return True, None, []

    except Exception as e:
        logger.warning(f"列名验证失败: {e}，跳过验证")
        return True, None, []


def _extract_top_select(sql: str) -> Optional[str]:
    """
    提取顶层 SELECT 列表内容 (从 SELECT 之后到 FROM <表名> 之前)。
    跳过嵌套括号内的 FROM (如 EXTRACT("EPOCH" FROM (...)) 不会干扰)。
    """
    sql_lower = sql.lower()
    m = re.search(r'\bSELECT\b', sql, re.IGNORECASE)
    if not m:
        return None
    i = m.end()
    depth = 0
    in_str: Optional[str] = None  # 当前是否在字符串字面量里 (' 或 ")
    while i < len(sql):
        c = sql[i]
        if in_str:
            # 在字符串里, 找匹配的结束符 (达梦里 '' 是转义)
            if c == in_str:
                # 看下一个字符是不是同一个引号 (转义)
                if i + 1 < len(sql) and sql[i + 1] == in_str:
                    i += 2
                    continue
                in_str = None
            i += 1
            continue
        if c in ("'", '"'):
            in_str = c
            i += 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif depth == 0 and sql_lower[i:i + 4] == 'from':
            # 检查 FROM 后面是表名 (字母/引号/方括号), 不是 ( 用于 EXTRACT
            j = i + 4
            while j < len(sql) and sql[j] in ' \t':
                j += 1
            if j < len(sql) and sql[j] in ('"', '[', 'A', 'B', 'C', 'D', 'E', 'F',
                                            'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N',
                                            'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',
                                            'W', 'X', 'Y', 'Z', '_', 'a', 'b', 'c',
                                            'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k',
                                            'l', 'm', 'n', 'o', 'p', 'q', 'r', 's',
                                            't', 'u', 'v', 'w', 'x', 'y', 'z'):
                return sql[m.end():i].strip()
        i += 1
    return None


def health_check() -> bool:
    """检查达梦数据库连接是否正常"""
    try:
        result = execute_scalar('SELECT 1 FROM DUAL')
        return result == 1
    except Exception as exc:
        logger.warning("达梦数据库健康检查失败: %s", exc)
        return False


# ==================== 异步查询支持 ====================

import asyncio
from concurrent.futures import ThreadPoolExecutor

# 全局线程池，用于执行同步数据库操作
_db_executor: Optional[ThreadPoolExecutor] = None


def _get_db_executor() -> ThreadPoolExecutor:
    """获取数据库操作专用线程池"""
    global _db_executor
    if _db_executor is None:
        _db_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="db_query_")
    return _db_executor


async def execute_query_async(sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """
    异步执行查询SQL（在线程池中执行，不阻塞事件循环）

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        查询结果列表，每行是一个字典
    """
    loop = asyncio.get_event_loop()
    executor = _get_db_executor()
    return await loop.run_in_executor(executor, execute_query, sql, params)


def execute_update(sql: str, params: Optional[Tuple] = None) -> int:
    """
    执行INSERT/UPDATE/DELETE SQL并返回影响的行数

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        影响的行数
    """
    logger.info(">>> 执行更新SQL >>>")
    logger.info("SQL: %s", sql)
    if params:
        logger.info("参数: %s", params)

    try:
        with dameng_cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            logger.info(">>> 更新成功，影响 %d 行 <<<", cursor.rowcount)
            return cursor.rowcount
    except Exception as exc:
        # 编码错误时，尝试将特殊 Unicode 字符替换后重试
        if params and ('gbk' in str(exc).lower() or 'codec' in str(exc).lower()):
            safe_params = tuple(
                str(p).replace('\u00b3', '^3') if isinstance(p, str) else p
                for p in params
            )
            logger.warning("参数编码异常，已自动替换特殊字符后重试: %s", exc)
            with dameng_cursor() as cursor:
                cursor.execute(sql, safe_params)
                return cursor.rowcount
        logger.error("=" * 80)
        logger.error(">>> SQL执行失败 <<<")
        logger.error("SQL: %s", sql)
        if params:
            logger.error("参数: %s", params)
        logger.error("错误: %s", exc)
        logger.error("=" * 80)
        raise


def execute_insert_return_id(sql: str, params: Optional[Tuple] = None) -> int:
    """
    执行INSERT SQL并返回自增ID

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        新插入记录的自增ID
    """
    logger.info(">>> 执行INSERT SQL >>>")
    logger.info("SQL: %s", sql)
    if params:
        logger.info("参数: %s", params)

    try:
        with dameng_cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            # 获取最后插入的ID
            cursor.execute("SELECT LAST_INSERT_ID()")
            result = cursor.fetchone()
            new_id = result[0] if result else 0
            logger.info(">>> 插入成功，新记录ID: %d <<<", new_id)
            return new_id
    except Exception as exc:
        # 编码错误时，尝试将特殊 Unicode 字符替换后重试
        if params and ('gbk' in str(exc).lower() or 'codec' in str(exc).lower()):
            safe_params = tuple(
                str(p).replace('\u00b3', '^3') if isinstance(p, str) else p
                for p in params
            )
            logger.warning("INSERT参数编码异常，已自动替换特殊字符后重试: %s", exc)
            with dameng_cursor() as cursor:
                cursor.execute(sql, safe_params)
                cursor.execute("SELECT LAST_INSERT_ID()")
                result = cursor.fetchone()
                return result[0] if result else 0
        logger.error("=" * 80)
        logger.error(">>> INSERT执行失败 <<<")
        logger.error("SQL: %s", sql)
        if params:
            logger.error("参数: %s", params)
        logger.error("错误: %s", exc)
        logger.error("=" * 80)
        raise
