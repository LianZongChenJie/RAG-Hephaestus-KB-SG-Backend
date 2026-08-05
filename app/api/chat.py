"""聊天流式接口"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatMessage, ChatStreamRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["聊天"])


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
    access_time = datetime.now(timezone.utc)
    question = chat_service.get_last_user_question(body.messages)
    client_ip = _client_ip(request)
    user_agent = request.headers.get("user-agent")
    payload = chat_service.build_payload(body)

    return StreamingResponse(
        chat_service.stream_chat(
            payload,
            question=question,
            access_time=access_time,
            client_ip=client_ip,
            user_agent=user_agent,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
