"""对话访问日志：写入达梦 FWBZ.hephaestus_chat_access_logs。

接口名 init_db / close_db / save_access_log 保持不变，调用方无需改动。
写失败只打日志，不影响聊天主流程。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.core.dameng import execute_update, get_dameng_connection

logger = logging.getLogger(__name__)

_LOG_TABLE = 'FWBZ."hephaestus_chat_access_logs"'
_logs_ready = False

_INSERT_SQL = """
INSERT INTO FWBZ."hephaestus_chat_access_logs" (
    "question", "access_time", "token_count", "prompt_tokens",
    "completion_tokens", "response", "model", "client_ip", "user_agent"
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _clip(value: Optional[str], n: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= n else text[:n]


def _fmt_time(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _ping_log_table() -> None:
    conn = get_dameng_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM %s WHERE 1=0" % _LOG_TABLE)
    finally:
        cur.close()


def _commit() -> None:
    conn = get_dameng_connection()
    if hasattr(conn, "commit"):
        conn.commit()


def _save_access_log_sync(
    question: str,
    access_time: datetime,
    token_count: Optional[int],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    response: Optional[str],
    model: Optional[str],
    client_ip: Optional[str],
    user_agent: Optional[str],
) -> None:
    params = (
        question or "",
        _fmt_time(access_time),
        token_count,
        prompt_tokens,
        completion_tokens,
        response,
        _clip(model, 128),
        _clip(client_ip, 64),
        _clip(user_agent, 1000),
    )
    execute_update(_INSERT_SQL, params)
    _commit()


async def init_db() -> None:
    """探测达梦访问日志表（失败不影响主服务）"""
    global _logs_ready
    try:
        await asyncio.to_thread(_ping_log_table)
        _logs_ready = True
        logger.info("访问日志就绪: %s", _LOG_TABLE)
    except Exception as exc:
        _logs_ready = False
        logger.warning(
            "访问日志表不可用（不影响主服务）: %s",
            exc,
        )


async def close_db() -> None:
    """兼容旧接口；达梦连接由 close_dameng 在进程退出时关闭。"""
    global _logs_ready
    _logs_ready = False


async def save_access_log(
    *,
    question: str,
    access_time: datetime,
    token_count: Optional[int],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    response: Optional[str],
    model: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """写入一条对话访问记录；失败只打日志，不影响主流程"""
    if not _logs_ready:
        logger.warning("访问日志未就绪，跳过写入")
        return
    try:
        await asyncio.to_thread(
            _save_access_log_sync,
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
