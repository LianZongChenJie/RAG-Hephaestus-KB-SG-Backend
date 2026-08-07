"""达梦数据库连接模块"""
import importlib
import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

# 强制 UTF-8 避免 dmPython 在中文 Windows 上用 GBK 编码导致特殊字符报错
os.environ['NLS_LANG'] = '.UTF8'

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 达梦连接（同步模式）
_dm_conn = None


def get_dameng_connection():
    """获取达梦数据库连接（同步）"""
    global _dm_conn

    if _dm_conn is not None:
        try:
            # 测试连接是否有效
            _dm_conn.cursor().execute("SELECT 1")
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
            charset='utf-8',
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
    logger.info("=" * 60)
    logger.info("执行SQL: %s", sql)
    if params:
        logger.info("参数: %s", params)

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

            # 转换为字典列表
            return [dict(zip(columns, row)) for row in rows]
    except ImportError as exc:
        logger.warning("达梦驱动未安装: %s", exc)
        return []
    except Exception as exc:
        logger.error("SQL执行失败: %s", exc)
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


def health_check() -> bool:
    """检查达梦数据库连接是否正常"""
    try:
        result = execute_scalar('SELECT 1 FROM DUAL')
        return result == 1
    except Exception as exc:
        logger.warning("达梦数据库健康检查失败: %s", exc)
        return False


def execute_update(sql: str, params: Optional[Tuple] = None) -> int:
    """
    执行INSERT/UPDATE/DELETE SQL并返回影响的行数

    Args:
        sql: SQL语句
        params: 参数元组

    Returns:
        影响的行数
    """
    logger.info("执行更新SQL: %s", sql)
    if params:
        logger.info("参数: %s", params)

    try:
        with dameng_cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
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
        logger.error("SQL执行失败: %s", exc)
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
    logger.info("执行INSERT SQL: %s", sql)
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
            return result[0] if result else 0
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
        logger.error("INSERT执行失败: %s", exc)
        raise
