"""debug: TF-IDF 召回效果"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher
from app.services.keyword_matcher import KeywordMatcher

m = get_qa_matcher()
print(f"[QA] items={len(m.items)}")

# 转换 dict 解耦
items_dict = [
    {"q_id": it.q_id, "text": it.text, "domain": it.domain}
    for it in m.items
]
km = KeywordMatcher(items_dict)
print(f"[TF-IDF] doc_count={len(km._docs)}, vocab_size={len(km._df)}")

# 测试 1: 几个原题
print("\n=== 测试 1: 原题检索 ===")
for q in ["今日总能耗多少", "能耗", "告警", "摄像头"]:
    hits = km.top_k(q, k=3)
    print(f"\n[q={q!r}]")
    for h in hits:
        print(f"  {h['q_id']:5s} ({h['score']:.3f}) [{h['domain']}] {h['text']}")

# 测试 2: 改写问题
print("\n\n=== 测试 2: 改写/口语化 ===")
for q in [
    "今天园区电费花了多少",
    "3 号摄像头掉线了吗",
    "今天进园子多少人",
    "现在灯开着的有哪些回路",
    "上周生成了几份报告",
]:
    hits = km.top_k(q, k=3)
    print(f"\n[q={q!r}]")
    for h in hits:
        print(f"  {h['q_id']:5s} ({h['score']:.3f}) {h['text'][:50]}")

# 测试 3: 完全不沾边
print("\n\n=== 测试 3: 不沾边的 ===")
for q in ["你好", "今天天气", "Python 爬虫"]:
    hits = km.top_k(q, k=3, min_score=0.01)
    print(f"\n[q={q!r}] (min_score=0.01)")
    for h in hits:
        print(f"  {h['q_id']:5s} ({h['score']:.3f}) {h['text'][:50]}")
    if not hits:
        print("  (无候选)")
