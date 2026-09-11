"""debug: 看 E 类问题 top-1 实际是什么 + 停用词过滤是否生效"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher
from app.services.keyword_matcher import _tokenize

m = get_qa_matcher()

E_QUERIES = [
    "今天北京天气怎么样",
    "帮我写个 Python 爬虫",
    "今天有什么新闻",
    "你是谁",
    "讲个笑话",
    "你好",
]

for q in E_QUERIES:
    print(f"\n[q={q!r}]")
    candidates = m._keyword_matcher.top_k(q, k=3, min_score=0.05)
    if not candidates:
        print("  (无候选)")
        continue
    for c in candidates:
        print(f"  top: {c['q_id']} ({c['score']:.3f}) text={c['text']!r}")
    top1 = candidates[0]
    top1_tokens = set(_tokenize(top1["text"]))
    q_tokens = set(_tokenize(q))
    sw = {"你好", "天气", "新闻", "笑话", "python", "爬虫", "你是"}
    overlap = (q_tokens & top1_tokens) - sw
    print(f"  q_tokens: {q_tokens}")
    print(f"  top1_tokens: {top1_tokens}")
    print(f"  交集去停用词: {overlap}")
    print(f"  停用词过滤触发: {not overlap}")
