"""评估纯 TF-IDF top-1 准确率 (在 80 原题 + 30 改写上)"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher
from app.services.keyword_matcher import KeywordMatcher

m = get_qa_matcher()
items_dict = [
    {"q_id": it.q_id, "text": it.text, "domain": it.domain}
    for it in m.items
]
km = KeywordMatcher(items_dict)

# 测试用例
test_cases = []

# A 类: 80 个原题
for it in m.items:
    test_cases.append({
        "q": it.text + "?",
        "expected_qid": it.q_id,
        "type": "原题",
    })

# B 类: 改写 (从 test_stream_chat_eval.py 抄过来)
B_CASES = [
    ("今天园区电费花了多少", "5.5"),
    ("咱们用电用气用水情况", "5.1"),
    ("帮我看看现在还有几条告警没处理", "2.1"),
    ("X 设备最近报了几次警", "2.4"),
    ("摄像头掉线了哪些", "9.1"),
    ("今天进园子多少人", "13.1"),
    ("还有几个车位", "12.1"),
    ("现在灯开着的有哪些回路", "6.1"),
    ("上周生成了几份报告", "1.1"),
    ("昨天登录了几次系统", "1.4"),
    ("现在哪些设备没在工作", "3.2"),
    ("3 号设备跑了多少电", "5.x"),
    ("园区能效咋样", "5.x"),
    ("今天的报警", "2.2"),
    ("哪些规则从来没触发过", "2.6"),
    ("消防设备最近 24h 有离线的吗", "2.7"),
    ("分时电量尖峰平谷各多少", "5.6"),
    ("现在能介单价是啥", "5.7"),
    ("今天用电折标煤多少", "5.8"),
    ("登录日志最近的", "1.4"),
    ("故障分析报告在哪", "1.2"),
    ("慢接口 TOP10", "18.1"),
    ("告警转工单完成情况", "2.x"),
    ("停车场现在空位", "12.1"),
    ("今天投诉多少条", "14.x"),
    ("活动准备进度", "15.x"),
    ("BA 控制点最近趋势", "8.2"),
    ("联动策略今天触发了几次", "7.2"),
    ("跨域综合 / 接口心跳情况", "18.x"),
    ("看门岗进出记录", "10.x"),
]
for q, exp in B_CASES:
    test_cases.append({"q": q, "expected_qid": exp, "type": "改写"})

# 跑评估
t0 = time.time()
top1_correct = 0
top3_correct = 0
type_stats = {}
mismatches = []

for i, tc in enumerate(test_cases):
    hits = km.top_k(tc["q"], k=3, min_score=0.05)
    top1 = hits[0]["q_id"] if hits else None
    top3 = {h["q_id"] for h in hits}
    expected = tc["expected_qid"]

    # 域级通配
    def matches(actual, exp):
        if actual is None:
            return exp is None
        if exp.endswith(".x"):
            return actual.startswith(exp.rstrip(".x") + ".")
        return actual == exp

    if matches(top1, expected):
        top1_correct += 1
    else:
        mismatches.append({
            "q": tc["q"],
            "expected": expected,
            "top1": top1,
            "top3": sorted(top3),
            "type": tc["type"],
        })

    if any(matches(qid, expected) for qid in top3):
        top3_correct += 1

    # 按类型统计
    t = tc["type"]
    type_stats.setdefault(t, {"total": 0, "top1_hit": 0, "top3_hit": 0})
    type_stats[t]["total"] += 1
    if matches(top1, expected):
        type_stats[t]["top1_hit"] += 1
    if any(matches(qid, expected) for qid in top3):
        type_stats[t]["top3_hit"] += 1

elapsed = time.time() - t0
total = len(test_cases)

print(f"=== TF-IDF 评估结果 (耗时 {elapsed*1000:.0f}ms / {total} 条, 平均 {elapsed/total*1000:.1f}ms/条) ===")
print()
for t, st in type_stats.items():
    print(f"[{t}] {st['top1_hit']}/{st['total']} top-1 ({st['top1_hit']/st['total']*100:.1f}%) | "
          f"{st['top3_hit']}/{st['total']} top-3 ({st['top3_hit']/st['total']*100:.1f}%)")
print()
print(f"[总计] {top1_correct}/{total} top-1 ({top1_correct/total*100:.1f}%) | "
      f"{top3_correct}/{total} top-3 ({top3_correct/total*100:.1f}%)")

print(f"\n=== 失败详情 (前 20 条) ===")
for m in mismatches[:20]:
    print(f"  [{m['type']}] {m['q'][:50]}")
    print(f"    预期: {m['expected']}, 实际 top-1: {m['top1']}, top-3: {m['top3']}")
