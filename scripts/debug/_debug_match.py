"""debug: 看 qa_matcher 实际返回什么"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher

m = get_qa_matcher()
print(f"[匹配器] 共 {len(m.items)} 条 Q-ID, valid_qids={len(m.valid_qids)}")
print(f"[匹配器] prompt 模板长度: {len(m._prompt_template)} 字符")
print(f"[匹配器] 序列化后清单长度: {len(m._serialized)} 字符 (~{len(m._serialized)//4} tokens)")

# 试 3 条问题
test_qs = [
    "最近一周系统生成了哪些 AI 报告?",
    "今日总能耗多少?",
    "你好",
]
for q in test_qs:
    print(f"\n==========")
    print(f"问题: {q}")
    r = m.match(q)
    print(f"  best_qid: {r.best_qid}")
    print(f"  confidence: {r.best_confidence:.2f}")
    print(f"  matched: {r.matched}")
    print(f"  candidates: {r.candidates}")
    print(f"  raw: {r.raw_response[:200]}")
    print(f"  error: {r.error}")
    print(f"  elapsed: {r.elapsed_ms:.0f}ms")
