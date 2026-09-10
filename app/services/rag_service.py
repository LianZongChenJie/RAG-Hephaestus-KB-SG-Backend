"""
RAG 召回服务
============

提供:
    - RagService.retrieve(query): 三路召回, 返回 SQL 范式 + DDL + 候选问题
    - 内置缓存 (LRU, 5min TTL, 进程内)

召回策略:
    1. 嵌入用户 query
    2. 三路并行检索
       a. question  (top-3, 用于候选问题展示)
       b. sql_template (top-2, 用于 SQL 范式)
       c. schema (top-3, 用于 DDL 提示)
    3. 取 SQL 范式中提到的表名, 再去 schema 补全
    4. 按 score 过滤 (min_score 默认 0.5)
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.embedder import OllamaEmbedder, get_embedder
from app.core.vector_store import (
    PgVectorStore,
    RagSearchHit,
    get_vector_store,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 召回结果
# ---------------------------------------------------------------------------
@dataclass
class RetrievalResult:
    query: str
    questions: list[RagSearchHit] = field(default_factory=list)
    sql_templates: list[RagSearchHit] = field(default_factory=list)
    schema_chunks: list[RagSearchHit] = field(default_factory=list)
    cached: bool = False
    elapsed_ms: float = 0.0

    def to_prompt_context(self) -> str:
        """拼成一段可塞进 LLM prompt 的 context"""
        sections: list[str] = []

        if self.questions:
            sections.append("【候选问题(top-3)】")
            for i, h in enumerate(self.questions, 1):
                sections.append(f"{i}. [{h.chunk_id}] {h.content}")

        if self.sql_templates:
            sections.append("\n【相关 SQL 范式(top-2, 仅供参照)】")
            for h in self.sql_templates:
                sections.append(f"--- {h.chunk_id} ---\n{h.content}")

        if self.schema_chunks:
            sections.append("\n【相关表 DDL(务必用真实字段名)】")
            for h in self.schema_chunks:
                sections.append(h.content)

        return "\n".join(sections)


# ---------------------------------------------------------------------------
# 简单 LRU + TTL 缓存 (进程内, 适合单实例部署)
# ---------------------------------------------------------------------------
class _TTLCache:
    def __init__(self, ttl_sec: int = 300, max_size: int = 512):
        self.ttl = ttl_sec
        self.max = max_size
        self._data: dict[str, tuple[float, RetrievalResult]] = {}

    def _key(self, query: str) -> str:
        return hashlib.md5(query.strip().lower().encode()).hexdigest()

    def get(self, query: str) -> Optional[RetrievalResult]:
        k = self._key(query)
        item = self._data.get(k)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > self.ttl:
            self._data.pop(k, None)
            return None
        # 标记缓存命中
        val.cached = True
        return val

    def set(self, query: str, val: RetrievalResult) -> None:
        if len(self._data) >= self.max:
            # 简单 LRU: 删最早的
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])
            self._data.pop(oldest[0], None)
        self._data[self._key(query)] = (time.time(), val)


# ---------------------------------------------------------------------------
# 召回服务
# ---------------------------------------------------------------------------
class RagService:
    def __init__(
        self,
        store: Optional[PgVectorStore] = None,
        embedder: Optional[OllamaEmbedder] = None,
        min_score: float = 0.45,
        cache_ttl: int = 300,
    ):
        self.store = store or get_vector_store(embedding_dim=1024)
        self.embedder = embedder or get_embedder()
        self.min_score = min_score
        self._cache = _TTLCache(ttl_sec=cache_ttl)

    def available(self) -> bool:
        """向量库是否可用; 不可用时调用方应走兜底"""
        return self.store is not None

    def retrieve(
        self,
        query: str,
        top_k_q: int = 3,
        top_k_sql: int = 2,
        top_k_schema: int = 3,
    ) -> RetrievalResult:
        """
        三路召回
        """
        # 1. 查缓存
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        # 2. 嵌入
        vec = self.embedder.embed(query)
        if not vec or self.store is None:
            return RetrievalResult(query=query)

        # 3. 三路检索
        questions = self.store.search(
            vec, type_filter=["question"], top_k=top_k_q, min_score=self.min_score
        )
        sql_templates = self.store.search(
            vec, type_filter=["sql_template"], top_k=top_k_sql, min_score=self.min_score
        )

        # 4. schema: 先看 sql_templates 提到的表, 再用问题向量去补
        schema_chunks: list[RagSearchHit] = []
        # 提取 SQL 范式中出现的表名
        referenced_tables = set()
        for h in sql_templates:
            referenced_tables.update(_extract_tables(h.content))
        for h in questions:
            referenced_tables.update(_extract_tables(h.content))
        # 先按表名精确查
        for tbl in referenced_tables:
            tbl_hits = self.store.search(
                vec, type_filter=["schema"], topic=None, top_k=1, min_score=0.0
            )
            # 用 chunk_id 前缀匹配
            for hit in tbl_hits:
                if hit.chunk_id == f"TBL_{tbl.lower()}":
                    schema_chunks.append(hit)
                    break
        # 不够再用向量补
        if len(schema_chunks) < top_k_schema:
            extra = self.store.search(
                vec, type_filter=["schema"], top_k=top_k_schema, min_score=self.min_score
            )
            for h in extra:
                if h not in schema_chunks:
                    schema_chunks.append(h)
        schema_chunks = schema_chunks[:top_k_schema]

        result = RetrievalResult(
            query=query,
            questions=questions,
            sql_templates=sql_templates,
            schema_chunks=schema_chunks,
            cached=False,
            elapsed_ms=0.0,
        )
        # 5. 写缓存
        self._cache.set(query, result)
        return result


# ---------------------------------------------------------------------------
# 辅助: 从 chunk 文本里粗略抽表名
# ---------------------------------------------------------------------------
_TABLE_RE = re.compile(
    r"(?:FROM|JOIN|INTO|UPDATE)\s+[`\"\[]?(?:FWBZ\.)?(\w+)[`\"\]]?",
    re.IGNORECASE
)


def _extract_tables(text: str) -> set[str]:
    return {m.group(1).lower() for m in _TABLE_RE.finditer(text or "")}


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_singleton: Optional[RagService] = None


def get_rag_service() -> Optional[RagService]:
    """获取 RAG 召回服务单例; 失败时返回 None"""
    global _singleton
    if _singleton is not None:
        return _singleton
    try:
        _singleton = RagService()
        return _singleton
    except Exception as e:
        logger.warning(f"RAG 初始化失败: {e}")
        return None
