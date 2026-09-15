"""聊天流式接口"""
import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.chat.schemas import ChatMessage, ChatStreamRequest
from app.chat.chat_service import ChatService, _one_line
from app.common.database import beijing_now
from app.common.logger import get_logger

router = APIRouter(prefix="/api", tags=["聊天"])
log = get_logger("access")


def _client_ip(request: Request) -> Optional[str]:
    """优先取代理头中的真实 IP，否则用直连 peer。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return None


@router.post("/chat-stream")
async def chat_stream(
    request: Request,
    body: ChatStreamRequest,
) -> StreamingResponse:
    """
    转发对话至 Ollama，SSE 流式返回增量 content。
    """
    chat_service = ChatService()
    access_time = beijing_now()
    question = chat_service.get_last_user_question(body.messages)
    client_ip = _client_ip(request)
    user_agent = request.headers.get("user-agent")
    payload = chat_service.build_payload(body)

    start_time = time.time()

    # 回调：流式结束后记日志
    async def on_summary(summary: dict):
        duration = time.time() - start_time
        prompt_tokens, completion_tokens, token_count = (
            chat_service.ollama.usage_snapshot()
        )
        log.info(
            "chat-stream ip=%s duration_ms=%s mode=%s qid=%s rows=%s "
            "tokens=%s prompt=%s completion=%s error=%s q=%s sql=%s",
            client_ip or "unknown",
            round(duration * 1000, 2),
            summary.get("mode"),
            summary.get("qid"),
            summary.get("row_count"),
            token_count,
            prompt_tokens,
            completion_tokens,
            summary.get("error"),
            (question or "")[:80],
            _one_line(summary.get("sql"), 160),
        )

    return StreamingResponse(
        chat_service.stream_chat(
            payload,
            question=question,
            access_time=access_time,
            client_ip=client_ip,
            user_agent=user_agent,
            on_summary=on_summary,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
