"""
RAG 增强版 chat 流式接口
=========================

POST /api/chat-rag-stream

请求:
    {
      "query": "今日能耗多少?",
      "history": [{"role":"user","content":"..."}]  # 可选
    }

响应 (SSE):
    event: stage
    data: {"stage":"rewrite","status":"running"}
    ...
    event: token
    data: {"text":"今日全园区..."}
    ...
    event: done
    data: {"trace":{...},"elapsed_ms":1234}
"""
from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.logger import get_logger
from app.services.stream_chat_v2 import StreamChatV2

router = APIRouter(prefix="/api", tags=["RAG聊天"])
log = get_logger("chat_rag")


class ChatRagRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


@router.post("/chat-rag-stream")
async def chat_rag_stream(request: Request, body: ChatRagRequest) -> StreamingResponse:
    """RAG 增强版流式 chat"""
    start = time.time()
    svc = StreamChatV2()

    async def gen():
        try:
            async for chunk in svc.handle(body.query, body.history):
                yield chunk
        except Exception as e:
            log.exception(f"chat-rag-stream 异常: {e}")
            err = json.dumps({"text": f"内部错误: {e}"}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n"
            yield "event: done\ndata: {}\n\n"
        finally:
            duration = (time.time() - start) * 1000
            log.info(f"chat-rag 完成: q='{body.query[:50]}' dur={duration:.0f}ms")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat-rag-health")
async def chat_rag_health() -> dict:
    """健康检查: 向量库 + 嵌入服务"""
    from app.core.vector_store import get_vector_store
    from app.core.embedder import get_embedder

    vs = get_vector_store(embedding_dim=1024)
    emb = get_embedder()
    info = {
        "vector_store": "ok" if vs else "down",
        "chunk_count": vs.count() if vs else 0,
        "embedder_model": emb.model,
    }
    # 测试嵌入
    vec = emb.embed("test")
    info["embedder"] = "ok" if vec else "down"
    if vec:
        info["embedding_dim"] = len(vec)
    return info
