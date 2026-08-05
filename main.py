"""
FastAPI 后端：代理 Ollama Chat API，提供 SSE 流式对话与 CORS。
访问记录（问题、时间、token、返回内容）写入 PostgreSQL。
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List, Literal, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db import close_db, init_db, save_access_log

# ---------- 配置常量（按需修改） ----------
HOST = "0.0.0.0"
PORT = 8000
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
MODEL_NAME = "qwen3.5:9b"
OLLAMA_TIMEOUT = 300.0
# 仅已下载的 9B + 全 GPU 极速；勿与 27B 同时 loaded
OLLAMA_NUM_GPU = 99
OLLAMA_KEEP_ALIVE = "24h"
DEFAULT_NUM_CTX = 2048
DEFAULT_TEMPERATURE = 0.6
# Qwen3.5 默认会先生成大量 thinking，体感极慢且 GPU 利用率看起来很低；关闭后直接出正文
OLLAMA_THINK = False
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Hephaestus Chat Proxy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    messages: List[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0, le=2)
    num_ctx: int = Field(default=DEFAULT_NUM_CTX, ge=512, le=8192)


def _last_user_question(messages: List[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            return msg.content
    return messages[-1].content


def _client_ip(request: Request) -> Optional[str]:
    """优先取代理头中的真实 IP，否则用直连 peer。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 可能是 "client, proxy1, proxy2"
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _ollama_payload(body: ChatStreamRequest) -> dict[str, Any]:
    """仅 qwen3.5:9b，固定 GPU offload；默认关闭 thinking 以降低延迟。"""
    logger.info(
        "chat-stream model=%s num_gpu=%s num_ctx=%s think=%s",
        MODEL_NAME,
        OLLAMA_NUM_GPU,
        body.num_ctx,
        OLLAMA_THINK,
    )
    return {
        "model": MODEL_NAME,
        "messages": [m.model_dump() for m in body.messages],
        "stream": True,
        "think": OLLAMA_THINK,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_gpu": OLLAMA_NUM_GPU,
            "temperature": body.temperature,
            "num_ctx": body.num_ctx,
        },
    }


async def _stream_ollama(
    payload: dict[str, Any],
    *,
    question: str,
    access_time: datetime,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    读取 Ollama NDJSON 流，转为 SSE。
    约定：每条 SSE 为 data: {"content":"<增量文本>"}\n\n
    与 frontend/src/api/chat.js 解析格式一致。
    流结束后将问题 / 时间 / token / 完整回复 / 客户端信息写入数据库。
    """
    response_parts: list[str] = []
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            async with client.stream(
                "POST", OLLAMA_CHAT_URL, json=payload
            ) as response:
                if response.status_code != 200:
                    text = await response.aread()
                    err = text.decode("utf-8", errors="replace")
                    yield f'data: {json.dumps({"error": f"Ollama 返回 {response.status_code}: {err}"}, ensure_ascii=False)}\n\n'
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("done"):
                        prompt_tokens = chunk.get("prompt_eval_count")
                        completion_tokens = chunk.get("eval_count")
                        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                        break

                    message = chunk.get("message") or {}
                    delta = message.get("content") or ""
                    if delta:
                        response_parts.append(delta)
                        sse = f"data: {json.dumps({'content': delta}, ensure_ascii=False)}\n\n"
                        yield sse
                        # 尽快刷到客户端，避免 ASGI/代理合并缓冲
                        await asyncio.sleep(0)

    except httpx.ConnectError:
        yield f'data: {json.dumps({"error": "无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用"}, ensure_ascii=False)}\n\n'
    except httpx.ReadTimeout:
        yield f'data: {json.dumps({"error": "Ollama 响应超时，请稍后重试"}, ensure_ascii=False)}\n\n'
    except Exception as exc:
        logger.exception("stream error")
        yield f'data: {json.dumps({"error": f"服务异常: {exc}"}, ensure_ascii=False)}\n\n'
    finally:
        reply = "".join(response_parts)
        total: Optional[int] = None
        if prompt_tokens is not None or completion_tokens is not None:
            total = (prompt_tokens or 0) + (completion_tokens or 0)
        await save_access_log(
            question=question,
            access_time=access_time,
            token_count=total,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            response=reply,
            model=MODEL_NAME,
            client_ip=client_ip,
            user_agent=user_agent,
        )


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """健康检查，并探测 Ollama 是否可达。"""
    ollama_ok = False
    detail: Optional[str] = None
    model_ready = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(OLLAMA_TAGS_URL)
            ollama_ok = r.status_code == 200
            if ollama_ok:
                tags = r.json().get("models") or []
                model_ready = any(
                    (m.get("name") or "") == MODEL_NAME
                    or (m.get("name") or "").startswith(f"{MODEL_NAME}-")
                    for m in tags
                )
            if not ollama_ok:
                detail = f"tags 接口状态 {r.status_code}"
    except httpx.ConnectError:
        detail = "Ollama 未启动或不可达"
    except Exception as exc:
        detail = str(exc)

    return {
        "ok": True,
        "ollama": ollama_ok,
        "model": MODEL_NAME,
        "model_ready": model_ready,
        "mode": "qwen9b-gpu-fast",
        "detail": detail,
    }


@app.post("/api/chat-stream")
async def chat_stream(request: Request, body: ChatStreamRequest) -> StreamingResponse:
    """转发对话至 Ollama，SSE 流式返回增量 content。"""
    access_time = datetime.now(timezone.utc)
    question = _last_user_question(body.messages)
    client_ip = _client_ip(request)
    user_agent = request.headers.get("user-agent")
    payload = _ollama_payload(body)
    return StreamingResponse(
        _stream_ollama(
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
