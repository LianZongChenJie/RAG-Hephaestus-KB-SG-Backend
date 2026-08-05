"""聊天服务 - SSE 流式对话处理"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncIterator, List, Optional

import httpx

from app.core.config import get_settings
from app.core.database import save_access_log
from app.core.ollama import OllamaClient
from app.schemas.chat import ChatMessage, ChatStreamRequest

logger = logging.getLogger(__name__)
settings = get_settings()


class ChatService:
    """聊天服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def get_last_user_question(self, messages: List[ChatMessage]) -> str:
        """获取最后一个用户问题"""
        for msg in reversed(messages):
            if msg.role == "user" and msg.content.strip():
                return msg.content
        return messages[-1].content

    def build_payload(self, body: ChatStreamRequest) -> dict[str, Any]:
        """构建 Ollama 请求 payload"""
        logger.info(
            "chat-stream model=%s num_gpu=%s num_ctx=%s think=%s",
            self.ollama.model,
            self.ollama.num_gpu,
            body.num_ctx,
            self.ollama.think,
        )
        return self.ollama.build_chat_payload(
            messages=[m.model_dump() for m in body.messages],
            temperature=body.temperature,
            num_ctx=body.num_ctx,
        )

    async def stream_chat(
        self,
        payload: dict[str, Any],
        *,
        question: str,
        access_time: datetime,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        执行流式对话，产出 SSE 格式数据。
        结束后自动写入访问日志。
        """
        response_parts: list[str] = []
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None

        try:
            async for chunk in self.ollama.stream_chat(payload):
                if chunk.get("done"):
                    prompt_tokens = chunk.get("prompt_eval_count")
                    completion_tokens = chunk.get("eval_count")
                    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                    break

                message = chunk.get("message") or {}
                delta = message.get("content") or ""
                if delta:
                    response_parts.append(delta)
                    yield f"data: {json.dumps({'content': delta}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0)  # 刷新缓冲区

        except httpx.ConnectError:
            yield f'data: {json.dumps({"error": "无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用"}, ensure_ascii=False)}\n\n'
        except httpx.ReadTimeout:
            yield f'data: {json.dumps({"error": "Ollama 响应超时，请稍后重试"}, ensure_ascii=False)}\n\n'
        except Exception as exc:
            logger.exception("stream error")
            yield f'data: {json.dumps({"error": f"服务异常: {exc}"}, ensure_ascii=False)}\n\n'
        finally:
            reply = "".join(response_parts)
            total = None
            if prompt_tokens is not None or completion_tokens is not None:
                total = (prompt_tokens or 0) + (completion_tokens or 0)
            await save_access_log(
                question=question,
                access_time=access_time,
                token_count=total,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response=reply,
                model=self.ollama.model,
                client_ip=client_ip,
                user_agent=user_agent,
            )
