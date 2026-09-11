"""本地跑 match() 完整流程, 不调 Ollama / 不调 达梦
验证: TF-IDF 召回 + 阈值过滤 + best_qid 分配
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.qa_matcher import get_qa_matcher

m = get_qa_matcher()
print(f"items={len(m.items)}, valid_qids={len(m.valid_qids)}, "
      f"keyword_matcher={'OK' if m._keyword_matcher else 'None'}")

# 测试用例
test_cases = []
# A 类 80 原题
for it in m.items:
    test_cases.append({
        "q": it.text + "?",
        "expected": it.q_id,
        "type": "原题",
    })
# B 类 30 改写
B = [
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
for q, exp in B:
    test_cases.append({"q": q, "expected": exp, "type": "改写"})
# E 类 兜底
E = [
    ("今天北京天气怎么样", None),
    ("你好", None),
    ("帮我写个 Python 爬虫", None),
    ("今天有什么新闻", None),
    ("你是谁", None),
    ("讲个笑话", None),
]
for q, exp in E:
    test_cases.append({"q": q, "expected": exp, "type": "兜底"})

# 跑评估
t0 = time.time()
type_stats = {}
mismatches = []
total = len(test_cases)
matched_correct = 0
mode_correct = 0

for tc in test_cases:
    r = m.match(tc["q"])
    actual_qid = r.best_qid
    actual_mode = "db" if actual_qid else "llm"
    expected = tc["expected"]
    expected_mode = "db" if expected else "llm"

    # 域级通配判定
    def hit(a, e):
        if e is None:
            return a is None
        if e.endswith(".x"):
            return a is not None and a.startswith(e.rstrip(".x") + ".")
        return a == e

    correct = hit(actual_qid, expected)
    mode_ok = actual_mode == expected_mode

    if correct:
        matched_correct += 1
    if mode_ok:
        mode_correct += 1
    if not correct or not mode_ok:
        mismatches.append({
            "q": tc["q"],
            "expected": expected,
            "actual_qid": actual_qid,
            "actual_mode": actual_mode,
            "actual_conf": r.best_confidence,
            "type": tc["type"],
        })

    t = tc["type"]
    type_stats.setdefault(t, {"total": 0, "qid_hit": 0, "mode_hit": 0})
    type_stats[t]["total"] += 1
    if correct:
        type_stats[t]["qid_hit"] += 1
    if mode_ok:
        type_stats[t]["mode_hit"] += 1

elapsed = (time.time() - t0) * 1000

print(f"\n=== 评估结果 ({total} 条, 耗时 {elapsed:.0f}ms = {elapsed/total:.2f}ms/条) ===")
for t, st in type_stats.items():
    print(f"  [{t}] {st['qid_hit']}/{st['total']} Q-ID ({st['qid_hit']/st['total']*100:.0f}%) | "
          f"{st['mode_hit']}/{st['total']} 模式 ({st['mode_hit']/st['total']*100:.0f}%)")
print(f"  [TOTAL] {matched_correct}/{total} Q-ID ({matched_correct/total*100:.1f}%) | "
      f"{mode_correct}/{total} 模式 ({mode_correct/total*100:.1f}%)")

print(f"\n=== 失败用例 ({len(mismatches)} 条) ===")
for m in mismatches[:30]:
    print(f"  [{m['type']}] {m['q'][:40]}")
    print(f"    预期: {m['expected']} -> mode={m['expected'] and 'db' or 'llm'}")
    print(f"    实际: {m['actual_qid']} (conf={m['actual_conf']:.3f}) -> mode={m['actual_mode']}")
