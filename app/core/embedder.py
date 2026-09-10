"""
Ollama Embedding 客户端
=======================

调用本地 Ollama 服务的 /api/embeddings 接口。
默认模型: bge-m3 (1024 维, 中文友好)。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaEmbedder:
    """
    Ollama 嵌入客户端 (同步)。

    用法:
        emb = OllamaEmbedder()                # 默认 bge-m3
        vec = emb.embed("今日能耗多少?")        # -> list[float], 1024 维
    """

    DEFAULT_MODEL = "bge-m3"
    DEFAULT_DIM = 1024

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.model = model
        # 复用 ollama.chat_url 拼出 base_url
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            chat_url = settings.ollama.chat_url.rstrip("/")
            # /api/chat -> base
            self.base_url = chat_url[: -len("/api/chat")] if chat_url.endswith("/api/chat") else chat_url
        self.timeout = timeout

    def embed(self, text: str) -> Optional[list[float]]:
        """对单段文本嵌入; 失败返回 None"""
        if not text or not text.strip():
            return None
        url = f"{self.base_url}/api/embeddings"
        payload = {"model": self.model, "prompt": text.strip()}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            vec = data.get("embedding")
            if not vec:
                logger.warning(f"Ollama embed 返回空: {data}")
                return None
            return list(vec)
        except Exception as e:
            logger.error(f"Ollama embed 失败: {e}")
            return None

    def embed_batch(self, texts: list[str], show_progress: bool = True) -> list[Optional[list[float]]]:
        """批量嵌入, 顺序串行 (避免 OOM)"""
        results: list[Optional[list[float]]] = []
        n = len(texts)
        for i, t in enumerate(texts, 1):
            results.append(self.embed(t))
            if show_progress and i % 20 == 0:
                logger.info(f"  嵌入进度 {i}/{n}")
        ok = sum(1 for v in results if v is not None)
        logger.info(f"嵌入完成: {ok}/{n} 成功")
        return results

    @staticmethod
    def dim_of(model: str) -> int:
        """常见模型维度查表; 实际应取 embed 返回的 vec 长度"""
        return {
            "bge-m3": 1024,
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
            "text-embedding-3-small": 1536,
        }.get(model, OllamaEmbedder.DEFAULT_DIM)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_singleton: Optional[OllamaEmbedder] = None


def get_embedder(model: Optional[str] = None) -> OllamaEmbedder:
    global _singleton
    if _singleton is None or (model and model != _singleton.model):
        _singleton = OllamaEmbedder(model=model or OllamaEmbedder.DEFAULT_MODEL)
    return _singleton
