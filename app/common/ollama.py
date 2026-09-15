"""LLM 客户端：默认 Ollama，本机可用 OpenAI 兼容公有云（阿里云 Token Plan 等）。"""
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from app.common.config import get_settings

settings = get_settings()


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _first_int(*values: Any) -> Optional[int]:
    for value in values:
        n = _as_int(value)
        if n is not None:
            return n
    return None


def parse_llm_usage(data: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
    """从 Ollama / OpenAI 兼容响应里取出 prompt、completion token。"""
    if not isinstance(data, dict):
        return None, None
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt = _first_int(
        usage.get("prompt_tokens"),
        usage.get("input_tokens"),
        data.get("prompt_eval_count"),
        data.get("prompt_tokens"),
    )
    completion = _first_int(
        usage.get("completion_tokens"),
        usage.get("output_tokens"),
        data.get("eval_count"),
        data.get("completion_tokens"),
    )
    total = _first_int(usage.get("total_tokens"), data.get("total_tokens"))
    if prompt is None and completion is None and total is not None:
        return total, 0
    if prompt is not None and completion is None and total is not None:
        completion = max(total - prompt, 0)
    elif completion is not None and prompt is None and total is not None:
        prompt = max(total - completion, 0)
    return prompt, completion


class OllamaClient:
    """Ollama / OpenAI 兼容客户端，对外仍输出 Ollama 形态的 chunk。"""

    def __init__(self):
        cfg = settings.ollama
        self.chat_url = cfg.chat_url
        self.tags_url = cfg.tags_url
        self.model = cfg.model
        self.timeout = cfg.timeout
        self.num_gpu = cfg.num_gpu
        self.keep_alive = cfg.keep_alive
        self.think = cfg.think
        self.provider = getattr(cfg, "provider", "ollama") or "ollama"
        self.api_key = getattr(cfg, "api_key", "") or ""
        self.base_url = (getattr(cfg, "base_url", "") or "").rstrip("/")
        self.reset_usage()

    def reset_usage(self) -> None:
        self._usage_prompt = 0
        self._usage_completion = 0

    def add_usage(
        self,
        prompt: Optional[int] = None,
        completion: Optional[int] = None,
        *,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if data:
            parsed_prompt, parsed_completion = parse_llm_usage(data)
            if prompt is None:
                prompt = parsed_prompt
            if completion is None:
                completion = parsed_completion
        if prompt:
            self._usage_prompt += int(prompt)
        if completion:
            self._usage_completion += int(completion)

    def usage_snapshot(
        self,
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        prompt = self._usage_prompt or None
        completion = self._usage_completion or None
        total = (self._usage_prompt + self._usage_completion) or None
        return prompt, completion, total

    def _use_openai(self) -> bool:
        return self.provider in ("openai", "openai_compat", "cloud", "dashscope", "token_plan")

    def _openai_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _openai_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _openai_body(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        stream: bool,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
            "enable_thinking": bool(self.think),
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if stream:
            # 否则 OpenAI 兼容流式（含阿里云 Token Plan）最后一包才带 usage
            body["stream_options"] = {"include_usage": True}
        return body

    def _messages_from_payload(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        return list(payload.get("messages") or [])

    def _temp_from_payload(self, payload: Dict[str, Any], default: float = 0.6) -> float:
        opts = payload.get("options") or {}
        return float(opts.get("temperature", default))

    def _max_tokens_from_payload(self, payload: Dict[str, Any]) -> Optional[int]:
        opts = payload.get("options") or {}
        n = opts.get("num_predict")
        return int(n) if n else None

    def _content_from_openai(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()

    def build_chat_payload(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        num_ctx: int,
        stream: bool = True,
    ) -> Dict[str, Any]:
        """构建聊天请求 payload（Ollama 形态，OpenAI 路径会再转换）"""
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
        return {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "format": "json",
            "options": {
                "num_gpu": self.num_gpu,
                "temperature": 0.3,
                "num_ctx": settings.model_defaults.num_ctx,
                "num_predict": settings.model_defaults.num_predict,
            },
        }

    def build_report_payload(
        self,
        messages: List[Dict[str, str]],
        num_predict: int = None,
    ) -> Dict[str, Any]:
        if num_predict is None:
            num_predict = settings.model_defaults.num_predict_report
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
                "num_predict": num_predict,
            },
        }

    async def stream_chat(
        self,
        payload: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        if self._use_openai():
            async for chunk in self._stream_openai(payload):
                yield chunk
            return

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", self.chat_url, json=payload) as response:
                if response.status_code != 200:
                    text = await response.aread()
                    yield {"error": f"Ollama 返回 {response.status_code}: {text.decode('utf-8', errors='replace')}"}
                    yield {"done": True}
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        if chunk.get("done"):
                            self.add_usage(data=chunk)
                        yield chunk
                    except json.JSONDecodeError:
                        continue

    async def _stream_openai(self, payload: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        body = self._openai_body(
            self._messages_from_payload(payload),
            temperature=self._temp_from_payload(payload),
            stream=True,
            max_tokens=self._max_tokens_from_payload(payload),
            json_mode=payload.get("format") == "json",
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", self._openai_url(), headers=self._openai_headers(), json=body
            ) as response:
                if response.status_code != 200:
                    text = await response.aread()
                    yield {"error": f"公有云 LLM 返回 {response.status_code}: {text.decode('utf-8', errors='replace')}"}
                    yield {"done": True}
                    return
                usage_data: Dict[str, Any] = {}
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line or line == "[DONE]":
                        if line == "[DONE]":
                            p, c = parse_llm_usage({"usage": usage_data})
                            self.add_usage(prompt=p, completion=c)
                            yield {
                                "done": True,
                                "prompt_eval_count": p,
                                "eval_count": c,
                            }
                            return
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("usage"):
                        usage_data = data["usage"]
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {})
                    content = delta.get("content") or ""
                    finish = choices[0].get("finish_reason")
                    if content:
                        yield {"message": {"content": content}, "done": False}
                    if finish and data.get("usage"):
                        # 部分网关把 usage 和 finish 放在同一包
                        usage_data = data["usage"]
                p, c = parse_llm_usage({"usage": usage_data})
                self.add_usage(prompt=p, completion=c)
                yield {
                    "done": True,
                    "prompt_eval_count": p,
                    "eval_count": c,
                }

    async def chat(self, payload: Dict[str, Any]) -> str:
        if self._use_openai():
            return await self._chat_openai(payload)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.chat_url, json=payload)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"Ollama 返回 {response.status_code}",
                    request=response.request,
                    response=response,
                )
            result = response.json()
            self.add_usage(data=result)
            return result.get("message", {}).get("content", "")

    async def _chat_openai(self, payload: Dict[str, Any]) -> str:
        body = self._openai_body(
            self._messages_from_payload(payload),
            temperature=self._temp_from_payload(payload, 0.3),
            stream=False,
            max_tokens=self._max_tokens_from_payload(payload),
            json_mode=payload.get("format") == "json",
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self._openai_url(), headers=self._openai_headers(), json=body
            )
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"公有云 LLM 返回 {response.status_code}: {response.text[:300]}",
                    request=response.request,
                    response=response,
                )
            data = response.json()
            self.add_usage(data=data)
            return self._content_from_openai(data)

    async def chat_for_report(self, payload: Dict[str, Any]) -> str:
        import logging
        logger = logging.getLogger("app.common.ollama")
        if self._use_openai():
            content = await self._chat_openai(payload)
            logger.info("chat_for_report content 长度: %s", len(content))
            return content
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.chat_url, json=payload)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"Ollama 返回 {response.status_code}",
                    request=response.request,
                    response=response,
                )
            body_bytes = response.read()
            logger.info("chat_for_report 原始字节: %s", len(body_bytes))
            result = json.loads(body_bytes)
            self.add_usage(data=result)
            content = result.get("message", {}).get("content", "")
            logger.info("chat_for_report content 长度: %s", len(content))
            return content

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> str:
        """同步调用 LLM，返回完整回复（SQL 生成、检测等）"""
        if self._use_openai():
            body = self._openai_body(
                messages,
                temperature=temperature,
                stream=False,
                max_tokens=settings.model_defaults.num_predict,
                json_mode=json_mode,
            )
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self._openai_url(), headers=self._openai_headers(), json=body
                )
                if response.status_code != 200:
                    raise httpx.HTTPStatusError(
                        message=f"公有云 LLM 返回 {response.status_code}: {response.text[:300]}",
                        request=response.request,
                        response=response,
                    )
                data = response.json()
                self.add_usage(data=data)
                return self._content_from_openai(data)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "num_gpu": self.num_gpu,
                "temperature": temperature,
                "num_ctx": settings.model_defaults.num_ctx,
                "num_predict": settings.model_defaults.num_predict,
            },
        }
        if json_mode:
            payload["format"] = "json"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.chat_url, json=payload)
            if response.status_code != 200:
                raise httpx.HTTPStatusError(
                    message=f"Ollama 返回 {response.status_code}",
                    request=response.request,
                    response=response,
                )
            result = response.json()
            self.add_usage(data=result)
            return result.get("message", {}).get("content", "")

    async def check_health(self) -> tuple[bool, Optional[str], bool]:
        if self._use_openai():
            return await self._check_openai_health()
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

    async def _check_openai_health(self) -> tuple[bool, Optional[str], bool]:
        if not self.api_key or not self.base_url:
            return False, "未配置公有云 base_url / api_key", False
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    f"{self.base_url}/models",
                    headers=self._openai_headers(),
                )
            if r.status_code != 200:
                return False, f"models 接口状态 {r.status_code}", False
            ids = [m.get("id") or "" for m in (r.json().get("data") or [])]
            ready = self.model in ids or any(i.startswith(self.model) for i in ids)
            return True, f"openai-compat models={len(ids)}", ready
        except httpx.ConnectError:
            return False, "公有云 LLM 不可达", False
        except Exception as exc:
            return False, str(exc), False
