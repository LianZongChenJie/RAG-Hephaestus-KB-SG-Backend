"""Ollama 客户端封装"""
import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()


class OllamaClient:
    """Ollama API 客户端"""

    def __init__(self):
        self.chat_url = settings.ollama.chat_url
        self.tags_url = settings.ollama.tags_url
        self.model = settings.ollama.model
        self.timeout = settings.ollama.timeout
        self.num_gpu = settings.ollama.num_gpu
        self.keep_alive = settings.ollama.keep_alive
        self.think = settings.ollama.think

    def build_chat_payload(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        num_ctx: int,
        stream: bool = True,
    ) -> Dict[str, Any]:
        """构建聊天请求 payload"""
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "num_gpu": self.num_gpu,
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }

    def build_sql_payload(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """构建 SQL 生成请求 payload（低温度保证准确性）"""
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "num_gpu": self.num_gpu,
                "temperature": 0.3,
                "num_ctx": settings.model_defaults.num_ctx,
                "num_predict": 2048,
            },
        }

    async def stream_chat(
        self,
        payload: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天，返回解析后的 chunk"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", self.chat_url, json=payload) as response:
                if response.status_code != 200:
                    text = await response.aread()
                    yield {"error": f"Ollama 返回 {response.status_code}: {text.decode('utf-8', errors='replace')}"}
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        yield chunk
                    except json.JSONDecodeError:
                        continue

    async def chat(self, payload: Dict[str, Any]) -> str:
        """非流式聊天，返回完整回复"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.chat_url, json=payload)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"Ollama 返回 {response.status_code}",
                    request=response.request,
                    response=response,
                )
            result = response.json()
            return result.get("message", {}).get("content", "")

    async def chat_for_report(self, payload: Dict[str, Any]) -> str:
        """非流式聊天，返回完整回复（同步方式，确保完整读取，用于AI报告生成）"""
        import logging
        logger = logging.getLogger("app.core.ollama")
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.chat_url, json=payload)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"Ollama 返回 {response.status_code}",
                    request=response.request,
                    response=response,
                )
            body_bytes = response.read()
            logger.warning(f"chat_for_report 读取原始字节长度: {len(body_bytes)}")
            result = json.loads(body_bytes)
            content = result.get("message", {}).get("content", "")
            logger.warning(f"chat_for_report content 长度: {len(content)}")
            return content

    async def check_health(self) -> tuple[bool, Optional[str], bool]:
        """检查 Ollama 健康状态"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(self.tags_url)
                ollama_ok = r.status_code == 200
                model_ready = False
                detail = None

                if ollama_ok:
                    tags = r.json().get("models") or []
                    model_ready = any(
                        (m.get("name") or "") == self.model
                        or (m.get("name") or "").startswith(f"{self.model}-")
                        for m in tags
                    )
                else:
                    detail = f"tags 接口状态 {r.status_code}"

                return ollama_ok, detail, model_ready
        except httpx.ConnectError:
            return False, "Ollama 未启动或不可达", False
        except Exception as exc:
            return False, str(exc), False
