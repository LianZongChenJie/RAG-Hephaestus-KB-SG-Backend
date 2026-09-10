"""
pgvector 向量库封装
===================

提供:
    - PgVectorStore: 同步的 pgvector 客户端（避免与 asyncpg 冲突）
    - 数据模型: RagChunk

设计要点:
    1. 用 psycopg3 同步连接（pgvector 官方推荐）
    2. 不复用项目里的 asyncpg，避免类型/扩展干扰
    3. 表结构在首次启动时自动创建
    4. HNSW 索引自动建，召回毫秒级
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import psycopg
from pgvector.psycopg import register_vector

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class RagChunk:
    """RAG 索引中的一个 chunk 单元"""
    chunk_id: str                       # 唯一 ID, 如 'Q2.3' / 'TBL_alarm_record' / 'SQL_5.1'
    type: str                           # question / sql_template / schema
    topic: Optional[str] = None         # 10 大类目, 如 '能耗' / '告警'
    title: Optional[str] = None         # 简短标题
    content: str = ""                   # 原始文本
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None  # 向量; 写入时必传, 检索结果中由 sql 计算

    def to_db_tuple(self) -> tuple:
        return (
            self.chunk_id,
            self.type,
            self.topic,
            self.title,
            self.content,
            json.dumps(self.metadata, ensure_ascii=False) if self.metadata else None,
            self.embedding,
        )


@dataclass
class RagSearchHit:
    """召回命中"""
    chunk_id: str
    type: str
    topic: Optional[str]
    title: Optional[str]
    content: str
    metadata: dict[str, Any]
    score: float                        # 0~1, 越大越相似


# ---------------------------------------------------------------------------
# 向量库
# ---------------------------------------------------------------------------
class PgVectorStore:
    """
    同步 pgvector 客户端。
    复用 config.yaml 里 database 段的连接信息。
    """

    _CREATE_EXT_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

    _CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        id          BIGSERIAL PRIMARY KEY,
        chunk_id    TEXT UNIQUE NOT NULL,
        type        VARCHAR(32) NOT NULL,
        topic       VARCHAR(64),
        title       TEXT,
        content     TEXT NOT NULL,
        metadata    JSONB,
        embedding   VECTOR(1024),
        created_at  TIMESTAMPTZ DEFAULT now(),
        updated_at  TIMESTAMPTZ DEFAULT now()
    );
    """

    _CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_rag_chunks_type
        ON rag_chunks (type);
    CREATE INDEX IF NOT EXISTS idx_rag_chunks_topic
        ON rag_chunks (topic);
    CREATE INDEX IF NOT EXISTS idx_rag_chunks_hnsw
        ON rag_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """

    def __init__(self, embedding_dim: int = 1024, connect_timeout: int = 10):
        self.embedding_dim = embedding_dim
        self.connect_timeout = connect_timeout
        self._dsn = self._build_dsn()
        self._init_schema()

    # ----- DSN 构造 -----
    def _build_dsn(self) -> str:
        db = settings.database
        # 跟 config.yaml 一致
        return (
            f"host={db.host} port={db.port} user={db.user} "
            f"password={db.password} dbname={db.name} "
            f"connect_timeout={self.connect_timeout}"
        )

    # ----- 初始化 -----
    def _init_schema(self) -> None:
        """确保 extension + 表 + 索引存在"""
        try:
            with psycopg.connect(self._dsn, autocommit=True) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute(self._CREATE_EXT_SQL)
                    # 维度由 embedding_dim 决定, 重写表的 embedding 类型
                    cur.execute(self._CREATE_TABLE_SQL.replace(
                        "VECTOR(1024)", f"VECTOR({self.embedding_dim})"
                    ))
                    cur.execute(self._CREATE_INDEX_SQL)
            logger.info(
                f"pgvector 初始化完成: {settings.database.host}:"
                f"{settings.database.port}/{settings.database.name}, dim={self.embedding_dim}"
            )
        except Exception as e:
            logger.error(f"pgvector 初始化失败: {e}")
            raise

    # ----- 上下文管理器 -----
    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn, autocommit=False)
        register_vector(conn)
        return conn

    # ----- 写入 -----
    def upsert(self, chunks: list[RagChunk]) -> int:
        """批量 upsert, 返回成功条数"""
        if not chunks:
            return 0
        sql = """
        INSERT INTO rag_chunks (chunk_id, type, topic, title, content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            type      = EXCLUDED.type,
            topic     = EXCLUDED.topic,
            title     = EXCLUDED.title,
            content   = EXCLUDED.content,
            metadata  = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            updated_at = now();
        """
        rows = [c.to_db_tuple() for c in chunks]
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.executemany(sql, rows)
                conn.commit()
            logger.info(f"upsert {len(chunks)} chunks OK")
            return len(chunks)
        except Exception as e:
            logger.error(f"upsert 失败: {e}")
            raise

    def delete_by_id(self, chunk_id: str) -> bool:
        sql = "DELETE FROM rag_chunks WHERE chunk_id = %s;"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (chunk_id,))
                ok = cur.rowcount > 0
            conn.commit()
        return ok

    def clear(self) -> int:
        """清空全部 chunks (用于重建索引)"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE rag_chunks RESTART IDENTITY;")
            conn.commit()
        logger.warning("rag_chunks 表已清空")
        return 0

    def count(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM rag_chunks;")
                return cur.fetchone()[0]

    # ----- 检索 -----
    def search(
        self,
        vec: list[float],
        type_filter: Optional[list[str]] = None,
        topic: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[RagSearchHit]:
        """
        余弦相似度检索
        type_filter: 限定 chunk 类型, 如 ['sql_template', 'question']
        topic:       限定主题, 如 '能耗'
        min_score:   最低相似度阈值 (0~1), 低于此分的丢弃
        """
        if not vec:
            return []

        sql = """
        SELECT chunk_id, type, topic, title, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM   rag_chunks
        WHERE  (%s::text[] IS NULL OR type = ANY(%s))
          AND  (%s::text   IS NULL OR topic = %s)
          AND  (1 - (embedding <=> %s::vector)) >= %s
        ORDER  BY embedding <=> %s::vector
        LIMIT  %s;
        """
        params = (
            vec,
            type_filter, type_filter,
            topic, topic,
            vec, min_score,
            vec, top_k,
        )
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    hits: list[RagSearchHit] = []
                    for row in cur.fetchall():
                        meta = row[5]
                        if isinstance(meta, str):
                            try:
                                meta = json.loads(meta)
                            except Exception:
                                meta = {}
                        elif meta is None:
                            meta = {}
                        hits.append(RagSearchHit(
                            chunk_id=row[0],
                            type=row[1],
                            topic=row[2],
                            title=row[3],
                            content=row[4],
                            metadata=meta or {},
                            score=float(row[6]),
                        ))
            return hits
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []


# ---------------------------------------------------------------------------
# 全局单例 (惰性初始化, 失败也不让进程起不来)
# ---------------------------------------------------------------------------
_singleton: Optional[PgVectorStore] = None
_init_failed = False


def get_vector_store(embedding_dim: int = 1024) -> Optional[PgVectorStore]:
    """
    获取向量库单例。
    若 PG 不可达, 返回 None, 调用方应走兜底分支。
    """
    global _singleton, _init_failed
    if _singleton is not None:
        return _singleton
    if _init_failed:
        return None
    try:
        _singleton = PgVectorStore(embedding_dim=embedding_dim)
        return _singleton
    except Exception as e:
        logger.warning(f"向量库初始化失败, RAG 模式将降级: {e}")
        _init_failed = True
        return None
