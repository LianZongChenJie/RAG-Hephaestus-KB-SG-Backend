"""
RAG 增强版 stream-chat 服务
============================

跟现有 ChatService 并存, 通过 /api/chat-rag-stream 路由调用。
完整流程:
    1. Query 重写
    2. 缓存检查
    3. 意图分类
    4. RAG 三路召回
    5. LLM 生成 SQL
    6. SQL 安全门
    7. 达梦执行
    8. LLM 包装
    9. SSE 流式输出
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx

from app.core.config import get_settings
from app.core.dameng import execute_query
from app.core.embedder import get_embedder
from app.core.ollama import OllamaClient
from app.core.vector_store import get_vector_store
from app.services.rag_service import RagService, get_rag_service
from app.services.sql_guard import validate

settings = get_settings()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt 加载 (一次性)
# ---------------------------------------------------------------------------
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    p = _PROMPTS_DIR / name
    if not p.exists():
        logger.warning(f"Prompt 文件不存在: {p}")
        return ""
    return p.read_text(encoding="utf-8")


PROMPTS = {
    "rewrite": _load_prompt("rewrite.md"),
    "intent": _load_prompt("intent.md"),
    "sql_gen": _load_prompt("sql_gen.md"),
    "wrap": _load_prompt("wrap.md"),
    "fallback": _load_prompt("fallback.md"),
}


# ---------------------------------------------------------------------------
# SSE 事件工具
# ---------------------------------------------------------------------------
def sse(event: str, data: dict | str) -> str:
    """构造一个 SSE 事件"""
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {data}\n\n"


# ---------------------------------------------------------------------------
# 阶段结果(供调用方回溯)
# ---------------------------------------------------------------------------
@dataclass
class StageTrace:
    rewrite: Optional[str] = None
    intent: Optional[str] = None
    intent_conf: float = 0.0
    retrieval: dict = field(default_factory=dict)
    sql: Optional[str] = None
    sql_explain: Optional[str] = None
    row_count: int = 0
    error: Optional[str] = None
    fallback: bool = False


# ---------------------------------------------------------------------------
# 流式服务
# ---------------------------------------------------------------------------
class StreamChatV2:
    """
    RAG 增强的流式 chat 服务。

    用法:
        svc = StreamChatV2()
        async for chunk in svc.handle("今日能耗多少?"):
            yield chunk  # SSE 字符串
    """

    def __init__(self):
        self.ollama = OllamaClient()
        self.rag = get_rag_service()
        self.trace = StageTrace()

    # ---------- 工具方法 ----------
    async def _ollama_chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        stream: bool = False,
        json_mode: bool = False,
    ) -> str:
        """单次 Ollama 调用, 返回完整内容"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        url = settings.ollama.chat_url
        payload = self.ollama.build_chat_payload(
            messages,
            temperature=temperature,
            num_ctx=settings.model_defaults.num_ctx,
            stream=stream,
        )
        if json_mode:
            payload["format"] = "json"

        timeout = settings.ollama.timeout
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama 调用失败: {e}")
            return ""

    # ---------- 阶段 1: Query 重写 ----------
    async def _stage_rewrite(self, query: str, history: list[dict]) -> str:
        if not history or not PROMPTS["rewrite"]:
            return query
        sys = PROMPTS["rewrite"]
        user = f"历史: {history[-3:]}\n当前: {query}\n改写后:"
        out = await self._ollama_chat(sys, user, temperature=0.2, json_mode=False)
        out = (out or "").strip()
        # 简单防御: 如果包含换行/序号, 取第一行
        out = out.split("\n")[0].strip()
        return out or query

    # ---------- 阶段 2: 意图分类 ----------
    async def _stage_intent(self, query: str) -> tuple[Optional[str], float]:
        if not PROMPTS["intent"]:
            return None, 0.0
        sys = PROMPTS["intent"]
        out = await self._ollama_chat(sys, query, temperature=0.1, json_mode=True)
        out = (out or "").strip()
        try:
            # 鲁棒解析: 找 JSON
            m = re.search(r"\{.*?\}", out, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                intent = d.get("intent")
                conf = float(d.get("confidence", 0))
                return (intent if conf >= 0.6 else None), conf
        except Exception as e:
            logger.warning(f"意图分类解析失败: {e} | raw={out[:100]}")
        return None, 0.0

    # ---------- 阶段 3: RAG 召回 ----------
    async def _stage_retrieval(self, query: str):
        if not self.rag or not self.rag.available():
            return None
        # 同步检索放线程池
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.rag.retrieve, query)

    # ---------- 阶段 4: SQL 生成 ----------
    async def _stage_sql_gen(
        self,
        query: str,
        retrieval_ctx: str,
    ) -> dict:
        sys = PROMPTS["sql_gen"]
        user = f"{retrieval_ctx}\n\n【用户问题】\n{query}\n\n【输出 JSON】"
        out = await self._ollama_chat(sys, user, temperature=0.2, json_mode=True)
        out = (out or "").strip()
        try:
            m = re.search(r"\{.*\}", out, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            logger.warning(f"SQL 解析失败: {e} | raw={out[:200]}")
        return {"sql": "", "explain": f"SQL 解析失败: {out[:80]}"}

    # ---------- 阶段 5: 安全门 ----------
    def _stage_guard(self, sql: str) -> tuple[bool, str, str]:
        r = validate(sql)
        return r.ok, r.sql, r.reason

    # ---------- 阶段 6: 执行 ----------
    async def _stage_execute(self, sql: str) -> tuple[list, Optional[str]]:
        loop = asyncio.get_running_loop()
        try:
            rows = await asyncio.wait_for(
                loop.run_in_executor(None, execute_query, sql),
                timeout=15.0,
            )
            return rows or [], None
        except Exception as e:
            return [], str(e)

    # ---------- 阶段 7: 包装 ----------
    async def _stage_wrap(self, query: str, sql: str, rows: list) -> str:
        sys = PROMPTS["wrap"]
        # 截断数据, 避免 prompt 爆炸
        sample = rows[:30] if rows else []
        user = (
            f"问题: {query}\n"
            f"SQL: {sql}\n"
            f"命中行数: {len(rows)}\n"
            f"数据: {json.dumps(sample, ensure_ascii=False, default=str)}\n"
        )
        out = await self._ollama_chat(sys, user, temperature=0.5, json_mode=False)
        return (out or "查询完成,但 LLM 包装失败。").strip()

    # ---------- 主流程 ----------
    async def handle(
        self,
        query: str,
        history: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        """生成 SSE 事件流"""
        t0 = time.time()
        history = history or []

        # 1. 重写
        yield sse("stage", {"stage": "rewrite", "status": "running"})
        rewritten = await self._stage_rewrite(query, history)
        self.trace.rewrite = rewritten
        yield sse("stage", {"stage": "rewrite", "status": "done", "result": rewritten})

        # 2. 意图分类
        yield sse("stage", {"stage": "intent", "status": "running"})
        intent, conf = await self._stage_intent(rewritten)
        self.trace.intent = intent
        self.trace.intent_conf = conf
        yield sse("stage", {
            "stage": "intent", "status": "done",
            "result": intent, "confidence": conf,
        })

        if intent is None:
            # 走兜底
            self.trace.fallback = True
            self.trace.error = "无法识别意图"
            yield sse("fallback", {"reason": "未匹配到任何业务类目"})
            fallback_text = PROMPTS["fallback"] or "本系统暂时无法回答这个问题,请换种问法试试。"
            # 流式输出兜底
            for line in fallback_text.split("\n\n"):
                yield sse("token", {"text": line + "\n\n"})
            yield sse("done", {"trace": self.trace.__dict__, "elapsed_ms": int((time.time() - t0) * 1000)})
            return

        # 3. 召回
        yield sse("stage", {"stage": "retrieval", "status": "running"})
        retrieval = await self._stage_retrieval(rewritten)
        if retrieval is None:
            yield sse("warning", {"msg": "向量库不可用, 使用规则兜底"})
        ctx = retrieval.to_prompt_context() if retrieval else ""
        self.trace.retrieval = {
            "q_count": len(retrieval.questions) if retrieval else 0,
            "sql_count": len(retrieval.sql_templates) if retrieval else 0,
            "schema_count": len(retrieval.schema_chunks) if retrieval else 0,
            "cached": retrieval.cached if retrieval else False,
        }
        yield sse("stage", {"stage": "retrieval", "status": "done", "result": self.trace.retrieval})

        # 4. SQL 生成
        yield sse("stage", {"stage": "sql_gen", "status": "running"})
        gen = await self._stage_sql_gen(rewritten, ctx)
        sql = (gen.get("sql") or "").strip()
        self.trace.sql = sql
        self.trace.sql_explain = gen.get("explain")
        yield sse("stage", {
            "stage": "sql_gen", "status": "done",
            "sql": sql, "explain": gen.get("explain"),
        })

        if not sql:
            # 兜底
            self.trace.fallback = True
            self.trace.error = "LLM 未生成 SQL"
            yield sse("fallback", {"reason": "未生成 SQL"})
            yield sse("token", {"text": PROMPTS["fallback"] or "无法生成查询语句,请换种问法。"})
            yield sse("done", {"trace": self.trace.__dict__, "elapsed_ms": int((time.time() - t0) * 1000)})
            return

        # 5. SQL 安全门
        ok, safe_sql, reason = self._stage_guard(sql)
        yield sse("stage", {
            "stage": "guard", "status": "ok" if ok else "blocked",
            "reason": reason, "final_sql": safe_sql,
        })
        if not ok:
            self.trace.fallback = True
            self.trace.error = f"SQL 不通过安全门: {reason}"
            yield sse("fallback", {"reason": reason})
            yield sse("token", {"text": f"生成的 SQL 未能通过安全检查({reason}),已拦截。请换个问法。"})
            yield sse("done", {"trace": self.trace.__dict__, "elapsed_ms": int((time.time() - t0) * 1000)})
            return

        # 6. 执行
        yield sse("stage", {"stage": "execute", "status": "running"})
        rows, err = await self._stage_execute(safe_sql)
        if err:
            self.trace.fallback = True
            self.trace.error = f"执行失败: {err}"
            yield sse("stage", {"stage": "execute", "status": "error", "error": err})
            yield sse("token", {"text": f"查询执行失败: {err[:100]}"})
            yield sse("done", {"trace": self.trace.__dict__, "elapsed_ms": int((time.time() - t0) * 1000)})
            return
        self.trace.row_count = len(rows)
        yield sse("stage", {"stage": "execute", "status": "done", "row_count": len(rows)})

        # 7. LLM 包装
        yield sse("stage", {"stage": "wrap", "status": "running"})
        text = await self._stage_wrap(rewritten, safe_sql, rows)
        yield sse("stage", {"stage": "wrap", "status": "done"})

        # 流式吐 token
        for line in text.split("\n\n"):
            yield sse("token", {"text": line + "\n\n"})

        # 8. 完成
        yield sse("done", {
            "trace": self.trace.__dict__,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "row_count": len(rows),
        })
