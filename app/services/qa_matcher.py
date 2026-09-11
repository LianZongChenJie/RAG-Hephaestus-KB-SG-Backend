"""
问题清单匹配服务 (TF-IDF 召回 + LLM 二次)
=========================================

职责:
    1. 启动时一次性加载 config/FWBZ问题清单.md, 解析为结构化清单
    2. 提供 match(question) -> MatchResult:
         - 阶段 1: TF-IDF 召回 top-3 候选 (毫秒级, 纯 Python)
         - 阶段 2: LLM 在 top-3 候选里选 best 1 (带超时, fallback)
         - 鲁棒解析 JSON, 返回 best q_id + confidence + 候选列表
    3. 进程内 LRU+TTL 缓存 (同问题 5 分钟内不重复打 LLM)

设计动机:
    - 原方案: 把全部 80 条清单塞给 LLM → 慢 (qwen3.5:9b thinking 模式 30-60s)
    - 改进: TF-IDF 先召回 top-3 → LLM 只看 3 个候选 → thinking 短 → 2-3s
    - 兜底: LLM 超时/失败 → 直接用 TF-IDF top-1 (仍比走 LLM 兜底强)

降级策略:
    - 文件不存在 / 解析失败: match() 返回 no_match, 调用方走兜底
    - TF-IDF 召回为空: 直接 no_match (闲聊场景)
    - LLM 调用失败/超时: fallback 到 TF-IDF top-1
    - JSON 解析失败: 取 matches[0] (按 confidence 降序) 兜底
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class QuestionItem:
    """一条标准问题"""
    q_id: str          # 业务域.子序号, 如 "5.1"
    domain: str        # 业务域标题, 如 "能耗与计费"
    text: str          # 原问法


@dataclass
class MatchResult:
    """匹配结果"""
    question: str
    best_qid: Optional[str] = None
    best_confidence: float = 0.0
    candidates: list[dict] = field(default_factory=list)  # [{q_id, confidence, reason}]
    raw_response: str = ""
    cached: bool = False
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    @property
    def matched(self) -> bool:
        """是否认为匹配成功 (best_qid 非空 且 confidence >= 阈值)"""
        return bool(self.best_qid) and self.best_confidence >= 0.60

    def to_dict(self) -> dict:
        return {
            "best_qid": self.best_qid,
            "best_confidence": self.best_confidence,
            "candidates": self.candidates,
            "matched": self.matched,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# 清单解析
# ---------------------------------------------------------------------------
# 业务域标题行: "## 5. 能耗与计量" 或  "## 一、能耗与计费"  或  "## 1. AI 报告与运行日志"
_DOMAIN_PATTERN = re.compile(
    r"^##\s+"
    r"(?:"                                # 二选一
    r"(?P<num1>\d+)\s*[\.、]\s*"          # 阿拉伯数字开头: "## 1. xxx"  /  "## 5、xxx"
    r"|(?P<cn>[一二三四五六七八九十]+)\s*[、\.]\s*"  # 中文数字: "## 一、xxx"
    r")"
    r"(?P<title>.+?)\s*$",
    re.MULTILINE,
)

# 问题行: "1. xxx" / "5. xxx"  (在 domain 之后, 数字开头)
_QITEM_PATTERN = re.compile(
    r"^\s*(?P<num>\d+)\s*[\.、]\s*(?P<text>\S.*?)$",
    re.MULTILINE,
)


def _parse_question_list(text: str) -> list[QuestionItem]:
    """
    把问题清单 md 解析成 [QuestionItem, ...]
    规则:
        - 业务域从最近的 ## 标题继承
        - 跳过空行 / 表格 / 引用块 (> ...)
    """
    items: list[QuestionItem] = []
    current_domain = ""
    current_domain_num: Optional[int] = None
    next_qid_sub = 1  # 子序号自增

    lines = text.splitlines()
    in_code = False

    for line in lines:
        # 跳过代码块
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # 跳过引用块
        if line.lstrip().startswith(">"):
            continue
        # 跳过表格
        if line.lstrip().startswith("|"):
            continue

        # 业务域标题
        m = _DOMAIN_PATTERN.match(line)
        if m:
            if m.group("num1"):
                current_domain_num = int(m.group("num1"))
                current_domain = m.group("title").strip()
            else:
                # 中文数字 (一/二/三...) → 转阿拉伯数字 (粗略, 足够用)
                cn = m.group("cn")
                current_domain_num = _cn_to_int(cn) or (len(items) // 6 + 1)
                current_domain = m.group("title").strip()
            next_qid_sub = 1
            continue

        # 问题行
        m = _QITEM_PATTERN.match(line)
        if m and current_domain_num is not None:
            text_part = m.group("text").strip()
            # 去掉行尾的 "?" / 句号
            text_part = text_part.rstrip("?？。. ")
            if not text_part:
                continue
            q_id = f"{current_domain_num}.{next_qid_sub}"
            items.append(QuestionItem(
                q_id=q_id,
                domain=current_domain,
                text=text_part,
            ))
            next_qid_sub += 1

    return items


_CN_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14,
    "十五": 15, "十六": 16, "十七": 17, "十八": 18,
}


def _cn_to_int(s: str) -> Optional[int]:
    return _CN_DIGITS.get(s)


# ---------------------------------------------------------------------------
# 序列化清单 (供 prompt 拼接)
# ---------------------------------------------------------------------------
def _serialize(items: list[QuestionItem]) -> str:
    """
    把 QuestionItem 列表拼成 prompt 友好的纯文本
    按业务域分组, 域内按 q_id 排序
    """
    # 按 q_id 自然排序
    items_sorted = sorted(items, key=lambda it: tuple(int(x) for x in it.q_id.split(".")))

    # 按业务域聚合
    by_domain: dict[str, list[QuestionItem]] = {}
    for it in items_sorted:
        by_domain.setdefault(it.domain, []).append(it)

    lines: list[str] = []
    domain_idx = 1
    for domain, group in by_domain.items():
        lines.append(f"## {domain_idx}. {domain}")
        domain_idx += 1
        for it in group:
            lines.append(f"{it.q_id}. {it.text}")
        lines.append("")  # 空行分隔

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# LRU + TTL 缓存
# ---------------------------------------------------------------------------
class _TTLCache:
    def __init__(self, ttl_sec: int = 300, max_size: int = 512):
        self.ttl = ttl_sec
        self.max = max_size
        self._data: dict[str, tuple[float, MatchResult]] = {}

    def _key(self, q: str) -> str:
        return hashlib.md5(q.strip().lower().encode()).hexdigest()

    def get(self, q: str) -> Optional[MatchResult]:
        k = self._key(q)
        item = self._data.get(k)
        if not item:
            return None
        ts, val = item
        if time.time() - ts > self.ttl:
            self._data.pop(k, None)
            return None
        val.cached = True
        return val

    def set(self, q: str, val: MatchResult) -> None:
        if len(self._data) >= self.max:
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])
            self._data.pop(oldest[0], None)
        self._data[self._key(q)] = (time.time(), val)


# ---------------------------------------------------------------------------
# 匹配服务
# ---------------------------------------------------------------------------
class QAMatcher:
    """问题清单匹配服务"""

    def __init__(
        self,
        file_path: Path,
        *,
        cache_ttl: int = 300,
        confidence_threshold: float = 0.60,
    ):
        self.file_path = file_path
        self.items: list[QuestionItem] = []
        # 仅在"问答手册"里有 SQL 范式的 Q-ID (LLM 只能从这里面选)
        self.valid_qids: set[str] = set()
        self._serialized: str = ""
        self._cache = _TTLCache(ttl_sec=cache_ttl)
        self._loaded = False
        self._lock = Lock()
        self.confidence_threshold = confidence_threshold
        self._prompt_template: str = ""
        # TF-IDF 召回器 (lazy init, 在 load() 里创建)
        self._keyword_matcher = None

    def load(self) -> bool:
        """加载清单 + 匹配 prompt 模板, 同步 Q-ID 索引, 成功返回 True"""
        with self._lock:
            if self._loaded:
                return bool(self.items)

            # 1. 加载匹配 prompt 模板
            root = Path(__file__).resolve().parent.parent.parent
            prompt_path = root / "prompts" / "match.md"
            if not prompt_path.exists():
                logger.warning(f"匹配 prompt 不存在: {prompt_path}")
                self._prompt_template = ""
            else:
                self._prompt_template = prompt_path.read_text(encoding="utf-8")

            # 2. 同步 SQL 范式索引 (拿 valid_qids)
            try:
                from app.services.sql_template_loader import get_template_loader
                tpl = get_template_loader()
                self.valid_qids = set(tpl.all_qids())
                logger.info(f"Q-ID 索引同步: {len(self.valid_qids)} 个有 SQL 范式")
            except Exception as e:
                logger.warning(f"Q-ID 索引同步失败: {e}")
                self.valid_qids = set()

            # 3. 加载并解析问题清单
            if not self.file_path.exists():
                logger.warning(f"问题清单不存在: {self.file_path}")
                self._loaded = True
                return False

            try:
                text = self.file_path.read_text(encoding="utf-8")
                all_items = _parse_question_list(text)
                # 过滤: 只保留问答手册里有 SQL 范式的 Q-ID
                # (LLM 只在有范式的问题里选, 避免匹配出"无 SQL 可执行"的问题)
                if self.valid_qids:
                    self.items = [it for it in all_items if it.q_id in self.valid_qids]
                    skipped = len(all_items) - len(self.items)
                    logger.info(
                        f"问题清单加载完成: 总 {len(all_items)} 条, "
                        f"有范式 {len(self.items)} 条, 跳过 {skipped} 条"
                    )
                else:
                    self.items = all_items
                    logger.info(f"问题清单加载完成: {len(self.items)} 条")
                self._serialized = _serialize(self.items)
            except Exception as e:
                logger.error(f"问题清单解析失败: {e}")
                self.items = []
                self._serialized = ""

            # 4. 初始化 TF-IDF 召回器 (纯 Python, 零依赖, < 100ms)
            if self.items:
                try:
                    from app.services.keyword_matcher import KeywordMatcher
                    items_dict = [
                        {"q_id": it.q_id, "text": it.text, "domain": it.domain}
                        for it in self.items
                    ]
                    self._keyword_matcher = KeywordMatcher(items_dict)
                    logger.info(f"TF-IDF 召回器已就绪, 词表 {len(self._keyword_matcher._df)} 个")
                except Exception as e:
                    logger.warning(f"TF-IDF 召回器初始化失败: {e}")
                    self._keyword_matcher = None

            self._loaded = True
            return bool(self.items)

    def available(self) -> bool:
        """清单是否就绪"""
        if not self._loaded:
            self.load()
        return bool(self.items) and bool(self._prompt_template)

    def _build_prompt(self) -> str:
        """拼最终 prompt: 模板 + 清单 (兜底用, 现网一般用 _build_short_prompt)"""
        return self._prompt_template.replace("{{QUESTION_LIST}}", self._serialized)

    def _build_short_prompt(self, candidates: list[dict], user_question: str) -> str:
        """拼短 prompt: 模板 + top-K 候选 + 用户问题 (让 LLM 在候选里选)"""
        # 候选列表拼成纯文本
        lines: list[str] = []
        for c in candidates:
            lines.append(f"- {c['q_id']}: {c['text']} (召回分 {c.get('score', 0):.2f})")
        candidates_text = "\n".join(lines)

        return (
            "你是 FWBZ 园区问题路由器。从下方候选中挑出与用户问题**最相关**的一个 (1~2 个), "
            "返回 JSON。\n\n"
            f"## 候选问题 (top-{len(candidates)})\n{candidates_text}\n\n"
            f"## 用户问题\n{user_question}\n\n"
            "## 输出格式 (严格 JSON, 禁止其他文字)\n"
            "```json\n"
            "{\n"
            '  "best": "<q_id>",\n'
            '  "confidence": 0.0~1.0\n'
            "}\n"
            "```\n"
            "规则:\n"
            "- best 必须从候选中选一个 (填 q_id 字符串)\n"
            "- 都不沾边 → best 留空字符串, confidence = 0\n"
            "- 不要解释, 不要 Markdown 包装\n"
        )

    def match(self, question: str, *, top_k: int = 3, llm_timeout: float = 0.0,
              tfidf_threshold: float = 0.15,
              stopwords: Optional[set[str]] = None) -> MatchResult:
        """
        同步匹配 (TF-IDF 主路径, LLM 可选)
        外部应在 executor / thread 中调用, 不要阻塞 event loop

        流程:
            1. TF-IDF 召回 top-K 候选
            2. top-1 score < tfidf_threshold → 直接 no_match (兜底)
            3. (可选) LLM 在候选里二次选择, 超时/失败 → fallback TF-IDF top-1

        Args:
            question: 用户问题
            top_k: TF-IDF 召回候选数
            llm_timeout: LLM 调用超时 (秒), 0=禁用 LLM (走纯 TF-IDF 路径, 推荐生产)
            tfidf_threshold: TF-IDF top-1 score 阈值, 低于此值视为"不在清单"
        """
        if not self._loaded:
            self.load()

        t0 = time.time()

        # 基础检查
        if not self.items or not self._prompt_template:
            return MatchResult(
                question=question,
                error="问题清单或 prompt 模板未就绪",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # 查缓存
        cached = self._cache.get(question)
        if cached is not None:
            cached.elapsed_ms = (time.time() - t0) * 1000
            return cached

        # ===== 阶段 1: TF-IDF 召回 =====
        candidates: list[dict] = []
        if self._keyword_matcher:
            try:
                candidates = self._keyword_matcher.top_k(question, k=top_k, min_score=0.05)
            except Exception as e:
                logger.warning(f"TF-IDF 召回异常: {e}")

        if not candidates:
            return MatchResult(
                question=question,
                best_qid=None,
                best_confidence=0.0,
                candidates=[],
                error="TF-IDF 召回为空 (不在清单范围)",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # ===== 阶段 1.5: 业务无关话题黑名单 (原文匹配) =====
        # 如果用户问题含"天气/新闻/笑话/Python/股票"等业务无关词,
        # 强制 no_match, 避免被 TF-IDF 误判为业务问题
        default_biz_blacklist = (
            # 寒暄/礼貌
            "你好", "您好", "hi", "hello", "hey", "嗨", "谢谢", "感谢", "再见", "拜拜",
            # 业务无关话题
            "天气", "新闻", "股票", "电影", "音乐", "小说", "游戏", "笑话", "聊天",
            "翻译", "英文", "中文", "日文", "韩文", "法语",
            "股票", "基金", "理财",
            # 编程
            "python", "Python", "java", "Java", "javascript", "JS", "js",
            "代码", "编程", "程序", "爬虫", "脚本", "算法",
            # 自我介绍/能力问询
            "你是谁", "介绍下", "介绍一", "你能干", "你会什么", "你叫什么",
        )
        bl = stopwords if stopwords is not None else default_biz_blacklist
        for w in bl:
            if w in question:
                return MatchResult(
                    question=question,
                    best_qid=None,
                    best_confidence=0.0,
                    candidates=[],
                    error=f"问题含业务无关词: {w!r}",
                    elapsed_ms=(time.time() - t0) * 1000,
                )

        # top-1 阈值过滤
        top1 = candidates[0]
        if top1["score"] < tfidf_threshold:
            return MatchResult(
                question=question,
                best_qid=None,
                best_confidence=0.0,
                candidates=candidates,
                error=f"TF-IDF top-1 score {top1['score']:.3f} < 阈值 {tfidf_threshold}",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # ===== 阶段 2 (可选): LLM 二次选择 =====
        if llm_timeout > 0:
            short_prompt = self._build_short_prompt(candidates, question)
            try:
                raw = self._call_match_llm(short_prompt, timeout=llm_timeout)
                result = self._parse_response(question, raw, t0, candidates=candidates)
                # LLM 成功, 用 LLM 结果
                self._cache.set(question, result)
                return result
            except Exception as e:
                logger.warning(f"LLM 匹配失败, fallback 到 TF-IDF top-1: {e}")
                # Fallthrough 到下面的 TF-IDF 路径
        else:
            pass  # 纯 TF-IDF 模式

        # ===== TF-IDF top-1 作为最终结果 =====
        result = MatchResult(
            question=question,
            best_qid=top1["q_id"],
            best_confidence=round(min(0.85, top1["score"]), 4),  # 保守置信度, 不会超过 0.85
            candidates=[
                {"q_id": c["q_id"], "confidence": c["score"], "reason": "TF-IDF"}
                for c in candidates
            ],
            raw_response="",
            error="",
            elapsed_ms=(time.time() - t0) * 1000,
        )

        # 写缓存
        self._cache.set(question, result)
        return result

    def _call_match_llm(self, full_prompt: str, *, timeout: float = 6.0) -> str:
        """
        专用于 QA 匹配的 LLM 调用 (短 prompt, 短超时):
            - 输入小 (~500 字符, 之前是 4000+)
            - num_predict 较小 (512 够 JSON 输出)
            - 强制 JSON 格式
            - 短超时 (6s, 超时直接 fallback)
        """
        from app.core.ollama import OllamaClient

        client = OllamaClient()
        return client.call_llm(
            [{"role": "user", "content": full_prompt}],
            temperature=0.1,
            json_mode=True,
        )

    def _parse_response(self, question: str, raw: str, t0: float) -> MatchResult:
        """鲁棒解析 LLM 输出"""
        result = MatchResult(
            question=question,
            raw_response=raw[:300],
            elapsed_ms=(time.time() - t0) * 1000,
        )

        if not raw or not raw.strip():
            result.error = "LLM 返回空"
            return result

        # 找 JSON 块 (兼容 LLM 在前后夹说明文字)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            result.error = f"未找到 JSON: {raw[:100]}"
            return result

        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            result.error = f"JSON 解析失败: {e} | raw={raw[:100]}"
            return result

        # 解析 matches (兼容老格式)
        matches_raw = data.get("matches") or []
        candidates: list[dict] = []
        for item in matches_raw:
            if not isinstance(item, dict):
                continue
            q_id = str(item.get("q_id") or "").strip()
            if not q_id:
                continue
            try:
                conf = float(item.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            candidates.append({
                "q_id": q_id,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason") or "")[:80],
            })

        # 解析 best (兼容两种格式)
        best = data.get("best")
        best_conf = data.get("confidence")

        # 1. 优先用顶层 confidence (新格式: {best, confidence})
        try:
            conf_val = float(best_conf) if best_conf is not None else 0.0
            conf_val = max(0.0, min(1.0, conf_val))
        except (TypeError, ValueError):
            conf_val = 0.0

        # 2. 取 best 字符串
        if isinstance(best, str) and best.strip() and best.lower() != "null":
            result.best_qid = best.strip()
            # 二次校验: best_qid 必须有 SQL 范式
            if self.valid_qids and result.best_qid not in self.valid_qids:
                result.best_qid = None
                result.best_confidence = 0.0
            else:
                result.best_confidence = conf_val
        elif result.candidates:
            # 兜底: 取 candidates[0] (老格式, LLM 用 matches 数组表达)
            result.best_qid = result.candidates[0]["q_id"]
            result.best_confidence = result.candidates[0]["confidence"]

        # 3. candidates 过滤 + 排序 (老格式)
        if self.valid_qids:
            candidates = [c for c in candidates if c["q_id"] in self.valid_qids]
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        result.candidates = candidates[:3]

        return result


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_singleton: Optional[QAMatcher] = None
_singleton_lock = Lock()


def get_qa_matcher() -> QAMatcher:
    """拿匹配服务单例 (按 config 目录找)"""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is not None:
            return _singleton
        root = Path(__file__).resolve().parent.parent.parent
        qlist_path = root / "config" / "FWBZ问题清单.md"
        _singleton = QAMatcher(qlist_path)
        _singleton.load()
        return _singleton
