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

settings = get_settings()
logger = get_logger("dameng")

# 达梦连接（同步模式）
_dm_conn = None

# Schema 缓存：table_name (lower) -> set of column_names (lower)
# 从 config/FWBZ_strut.sql 解析，只读一次
_schema_cache: Dict[str, Set[str]] = {}
_schema_loaded = False


def _load_schema_from_file() -> Dict[str, Set[str]]:
    """解析 config/FWBZ_strut.sql，构建表名→列名集合的映射"""
    global _schema_cache, _schema_loaded
    if _schema_loaded:
        return _schema_cache

    # __file__ = app/core/dameng.py → parent.parent = app/ → parent.parent.parent = 项目根目录
    schema_file = Path(__file__).parent.parent.parent / "config" / "FWBZ_strut.sql"
    if not schema_file.exists():
        logger.warning(f"Schema 文件不存在: {schema_file}")
        _schema_loaded = True
        return _schema_cache

    try:
        content = schema_file.read_text(encoding='utf-8')
        # 匹配 CREATE TABLE "FWBZ"."table_name" ( ... );
        # 支持多行括号内容
        table_pattern = re.compile(
            r'CREATE\s+TABLE\s+"FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
            re.IGNORECASE | re.DOTALL
        )
        for match in table_pattern.finditer(content):
            table_name = match.group(1).lower()
            block = match.group(2)
            # 提取所有 "column_name" （排除 PRIMARY KEY、CONSTRAINT 等）
            # 排除行首含 KEY/CONSTRAINT/INDEX/UNIQUE/CHECK 的行
            cols: Set[str] = set()
            for line in block.splitlines():
                line = line.strip()
                # 跳过约束关键字行
                if re.match(r'^(PRIMARY|UNIQUE|CHECK|CONSTRAINT|INDEX|FOREIGN)', line, re.IGNORECASE):
                    continue
                for col_match in re.finditer(r'"(\w+)"', line):
                    cols.add(col_match.group(1).lower())
            _schema_cache[table_name] = cols

        logger.info(f"已从 {schema_file} 加载 {len(_schema_cache)} 个表的 schema 缓存")
        _schema_loaded = True
    except Exception as e:
        logger.warning(f"Schema 文件解析失败: {e}，使用空缓存")
        _schema_loaded = True

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
    验证 SQL 中各子句（SELECT/WHERE/ORDER BY/GROUP BY 等）的列名是否真实存在于表结构中。
    FROM 子句里的表名和 JOIN 子句中的表名不参与验证（只验证真正的列引用）。

    Returns:
        (is_valid, error_message, invalid_columns)
    """
    try:
        table_cols = _load_schema_from_file()
        if not table_cols:
            return True, None, []

        # 1. 找 FROM 子句中所有被引用的表（用于列名归属判断）
        from_match = re.search(
            r'FROM\s+(.+?)(?=\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|\s+OFFSET|\s+UNION|,|\s*$)',
            sql, re.IGNORECASE | re.DOTALL
        )
        table_names: Set[str] = set()
        if from_match:
            from_clause = from_match.group(1)
            for m in re.finditer(r'FWBZ\."(\w+)"|"(\w+)"|(?<![.\w"])(\w+)(?=\s*(?:LEFT|RIGHT|INNER|OUTER|JOIN|WHERE|GROUP|ORDER|LIMIT|ON|,|$|\s*$))', from_clause, re.IGNORECASE):
                t = (m.group(1) or m.group(2) or m.group(3) or '').strip().lower()
                if t and t in table_cols:
                    table_names.add(t)
            for m in re.finditer(r'(?:JOIN|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN)\s+(?:FWBZ\.)?"?(\w+)"?', from_clause, re.IGNORECASE):
                t = m.group(1).strip().lower()
                if t in table_cols:
                    table_names.add(t)

        # 过滤掉 schema 名本身（只有表名才参与列验证）
        table_names = {t for t in table_names if t in table_cols}

        if not table_names:
            return True, None, []

        # 2. 只从真正需要验证列名的子句中提取标识符
        # 排除 FROM 和 JOIN 子句（那里是表名，不是列名）
        # 只验证：SELECT 列表、WHERE、GROUP BY、HAVING、ORDER BY、LIMIT/OFFSET
        SELECT_KW = r'SELECT\s+(.+?)\s+FROM\b'
        WHERE_KW = r'WHERE\s+(.+?)(?=\s+GROUP|\s+ORDER|\s+HAVING|\s+LIMIT|\s+OFFSET|\s+UNION|\s*$)'
        GROUP_KW = r'GROUP\s+BY\s+(.+?)(?=\s+HAVING|\s+ORDER|\s+LIMIT|\s+OFFSET|\s+UNION|\s*$)'
        HAVING_KW = r'HAVING\s+(.+?)(?=\s+GROUP|\s+ORDER|\s+LIMIT|\s+OFFSET|\s+UNION|\s*$)'
        ORDER_KW = r'ORDER\s+BY\s+(.+?)(?=\s+LIMIT|\s+OFFSET|\s+UNION|\s*$)'

        clause_texts: List[str] = []
        for pattern in [SELECT_KW, WHERE_KW, GROUP_KW, HAVING_KW, ORDER_KW]:
            for m in re.finditer(pattern, sql, re.IGNORECASE | re.DOTALL):
                clause_texts.append(m.group(1))

        # 3. 只从这些子句文本中提取双引号标识符
        #    先去掉 AS "别名" 形式（别名不是列名，不参与验证）
        validated_ids: List[str] = []
        for clause in clause_texts:
            clause_clean = re.sub(r'\s+AS\s+"[^"]*"', '', clause, flags=re.IGNORECASE)
            clause_clean = re.sub(r'\s+AS\s+\'[^\']*\'', '', clause_clean, flags=re.IGNORECASE)
            validated_ids.extend(re.findall(r'"([^"]+)"', clause_clean))

        if not validated_ids:
            return True, None, []

        # 4. 排除肯定不是列名的标识符
        non_cols = {schema.lower(), 'fwbz', 'and', 'or', 'select', 'from', 'where',
                     'order', 'group', 'by', 'limit', 'offset', 'having',
                     'join', 'left', 'right', 'inner', 'outer', 'on',
                     'as', 'in', 'is', 'null', 'not', 'like', 'between'}

        invalid_cols: List[str] = []
        for col_name in validated_ids:
            col_lower = col_name.lower()
            if col_lower in non_cols:
                continue

            # 如果它本身就是一个真实存在的表名，说明是从 FROM 子句被误提取的，跳过
            if col_lower in table_cols:
                continue

            col_exists = any(col_lower in cols for cols in [table_cols.get(t) for t in table_names])
            if not col_exists:
                owner = '?'
                for t, cols in table_cols.items():
                    if col_lower in cols:
                        owner = f'"{t}"'
                        break
                invalid_cols.append(f'"{col_name}"（该列在表 {owner} 中不存在）')

        if invalid_cols:
            return False, f"检测到不存在的列名: {', '.join(invalid_cols)}", invalid_cols
        return True, None, []

    except Exception as e:
        logger.warning(f"列名验证失败: {e}，跳过验证")
        return True, None, []


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
