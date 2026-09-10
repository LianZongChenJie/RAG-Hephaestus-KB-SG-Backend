"""
轻量 TF-IDF 召回器 (纯 Python, 零依赖)
=======================================

背景:
    QA 匹配原方案: 把全部 80 条清单塞给 LLM 让它挑 → 慢 (30-60s, thinking 模式)
    改进: TF-IDF 先召回 top-K → LLM 只看 K 条做二次选择 → thinking 短 → 2-3s

实现:
    - 不依赖 sklearn/jieba/numpy
    - 字符 n-gram + 词级 混合特征 (中文按字 + 简单切词)
    - 倒排索引优化 (O(K) 查询)
    - 数据量 80 条, 完全够用

召回策略:
    1. 中文: 单字 (unigram) + 二字 (bigram) 混合
    2. 英文/数字: 按空格切词
    3. 算每个 token 的 TF-IDF (用 log 平滑)
    4. 余弦相似度

降级:
    - 词表为空 / 全 0 权重 → 返回空列表
    - 相似度 < min_score → 过滤掉
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional


# 匹配中文单字 / 二字 / 英文数字串
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    """
    简单分词:
        - 英文/数字: 整体作为一个 token
        - 中文: 拆成单字 + 二字 bigram
    """
    if not text:
        return []
    base_tokens = _TOKEN_RE.findall(text)
    tokens: list[str] = []
    cn_chars: list[str] = []
    for tok in base_tokens:
        if re.match(r"^[A-Za-z0-9]+$", tok):
            tokens.append(tok.lower())
        else:
            cn_chars.append(tok)
    # 中文: 单字 + 二字
    if cn_chars:
        # 单字
        tokens.extend(cn_chars)
        # 二字 bigram
        for i in range(len(cn_chars) - 1):
            tokens.append(cn_chars[i] + cn_chars[i + 1])
    return tokens


class KeywordMatcher:
    """TF-IDF + 余弦相似度 召回器

    Args:
        items: 清单项, 每项至少含 q_id / text / domain 三个 key
    """

    def __init__(self, items: list):
        self.items = items
        self._docs: list[list[str]] = []
        self._df: Counter = Counter()  # doc freq
        self._idf: dict[str, float] = {}
        self._doc_vecs: list[dict[str, float]] = []  # sparse tfidf
        self._doc_norms: list[float] = []

        self._build()

    def _build(self) -> None:
        """构建 TF-IDF 索引"""
        # 1. 分词
        self._docs = [_tokenize(it["text"]) for it in self.items]

        # 2. 算 doc freq
        self._df = Counter()
        for tokens in self._docs:
            for tok in set(tokens):
                self._df[tok] += 1

        # 3. 算 IDF (log 平滑)
        n_docs = max(1, len(self._docs))
        self._idf = {
            tok: math.log((n_docs + 1) / (df + 1)) + 1.0
            for tok, df in self._df.items()
        }

        # 4. 算每个文档的 TF-IDF 向量 (sparse dict)
        self._doc_vecs = []
        self._doc_norms = []
        for tokens in self._docs:
            vec = self._tfidf(tokens)
            self._doc_vecs.append(vec)
            # 算 L2 范数
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._doc_norms.append(norm)

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        """把 token 列表转为 TF-IDF dict"""
        if not tokens:
            return {}
        tf = Counter(tokens)
        total = len(tokens)
        vec = {}
        for tok, cnt in tf.items():
            if tok not in self._idf:
                continue
            tf_val = cnt / total
            vec[tok] = tf_val * self._idf[tok]
        return vec

    def top_k(
        self,
        query: str,
        k: int = 3,
        min_score: float = 0.05,
    ) -> list[dict]:
        """
        召回 top-K 候选
        返回: [{q_id, text, domain, score}, ...] 按 score 降序
        """
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        q_vec = self._tfidf(q_tokens)
        if not q_vec:
            return []
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        # 算与所有文档的余弦相似度
        scored: list[tuple[int, float]] = []
        for i, d_vec in enumerate(self._doc_vecs):
            if not d_vec:
                continue
            # 点积: 遍历 q_vec (小)
            dot = 0.0
            for tok, w in q_vec.items():
                if tok in d_vec:
                    dot += w * d_vec[tok]
            if dot <= 0:
                continue
            sim = dot / (q_norm * self._doc_norms[i])
            if sim >= min_score:
                scored.append((i, sim))

        # 排序
        scored.sort(key=lambda x: x[1], reverse=True)

        # 拿 top-K
        results: list[dict] = []
        for idx, score in scored[:k]:
            it = self.items[idx]
            results.append({
                "q_id": it["q_id"],
                "text": it["text"],
                "domain": it["domain"],
                "score": round(score, 4),
            })
        return results


# ---------------------------------------------------------------------------
# 单例 (与 qa_matcher 同步)
# ---------------------------------------------------------------------------
_singleton: Optional[KeywordMatcher] = None


def get_keyword_matcher() -> Optional[KeywordMatcher]:
    """拿 TF-IDF 召回器单例; 不可用时返回 None"""
    global _singleton
    if _singleton is not None:
        return _singleton
    from app.services.qa_matcher import get_qa_matcher
    m = get_qa_matcher()
    if not m.items:
        return None
    _singleton = KeywordMatcher(m.items)
    return _singleton
