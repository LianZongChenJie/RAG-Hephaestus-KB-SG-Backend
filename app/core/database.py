"""PostgreSQL 数据库连接模块"""
import logging
from datetime import datetime
from typing import Optional

import asyncpg

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_pool: Optional[asyncpg.Pool] = None

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_access_logs (
    id              BIGSERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    access_time     TIMESTAMPTZ NOT NULL,
    token_count     INTEGER,
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    response        TEXT,
    model           VARCHAR(128),
    client_ip       VARCHAR(64),
    user_agent      TEXT
);
"""

_MIGRATE_COLUMNS_SQL = """
ALTER TABLE chat_access_logs ADD COLUMN IF NOT EXISTS client_ip VARCHAR(64);
ALTER TABLE chat_access_logs ADD COLUMN IF NOT EXISTS user_agent TEXT;
"""


async def init_db() -> None:
    """创建连接池并确保访问日志表存在"""
    global _pool
    db = settings.database
    _pool = await asyncpg.create_pool(
        host=db.host,
        port=db.port,
        user=db.user,
        password=db.password,
        database=db.name,
        min_size=db.min_size,
        max_size=db.max_size,
    )
    async with _pool.acquire() as conn:
        await conn.execute(_CREATE_TABLE_SQL)
        await conn.execute(_MIGRATE_COLUMNS_SQL)
    logger.info(
        "PostgreSQL ready: %s@%s:%s/%s",
        db.user, db.host, db.port, db.name
    )


async def close_db() -> None:
    """关闭数据库连接池"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def save_access_log(
    *,
    question: str,
    access_time: datetime,
    token_count: Optional[int],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    response: str,
    model: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """写入一条对话访问记录；失败只打日志，不影响主流程"""
    if _pool is None:
        logger.warning("DB pool not ready, skip access log")
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_access_logs
                    (question, access_time, token_count, prompt_tokens,
                     completion_tokens, response, model, client_ip, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                question,
                access_time,
                token_count,
                prompt_tokens,
                completion_tokens,
                response,
                model,
                client_ip,
                user_agent,
            )
    except Exception:
        logger.exception("failed to save chat access log")
