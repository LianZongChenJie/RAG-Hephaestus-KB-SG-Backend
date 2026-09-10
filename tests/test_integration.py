"""
集成测试 (不调 Ollama)
========================
验证:
    1. 三个新模块能正常加载
    2. 问题清单 / 问答手册 能解析
    3. valid_qids 同步正确
    4. chat_service.py:stream_chat 改造后能正常 import
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg} | expected={expected!r} actual={actual!r}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# 1. 加载 qa_matcher
# ---------------------------------------------------------------------------
print("\n[1] 加载 qa_matcher")
from app.services.qa_matcher import get_qa_matcher
m = get_qa_matcher()
assert_true(m.available(), "qa_matcher 应可用")
print(f"  [OK] 加载 {len(m.items)} 条 Q-ID, valid_qids={len(m.valid_qids)} 个")

# valid_qids 是问答手册全集(86), items 是清单 ∩ 范式集
item_qids = {it.q_id for it in m.items}
assert_true(item_qids.issubset(m.valid_qids), "items 应是 valid_qids 的子集")
missing = m.valid_qids - item_qids  # 问答手册有但清单没列
print(f"  [OK] items={len(item_qids)} ⊆ valid_qids={len(m.valid_qids)}")
if missing:
    print(f"  [INFO] 清单未覆盖 (问答手册有但清单无): {sorted(missing)}")

# 检查至少 5 条样例
print(f"  [OK] 样例:")
for it in m.items[:3]:
    print(f"      {it.q_id} | [{it.domain}] {it.text}")


# ---------------------------------------------------------------------------
# 2. 加载 sql_template_loader
# ---------------------------------------------------------------------------
print("\n[2] 加载 sql_template_loader")
from app.services.sql_template_loader import get_template_loader
t = get_template_loader()
qids = t.all_qids()
assert_true(len(qids) > 50, "Q-ID 索引应 > 50")
print(f"  [OK] 共 {len(qids)} 个 Q-ID")
print(f"  [OK] 前 10 个: {qids[:10]}")

# 抽查 Q5.1 / Q5.2 / Q5.3 (能耗域是核心)
for qid in ["5.1", "5.2", "5.3", "9.1"]:
    assert_true(t.has(qid), f"{qid} 应有")
    chunk = t.get(qid)
    assert_true(len(chunk) > 50, f"{qid} chunk 长度应 > 50")
    assert_true("SELECT" in chunk, f"{qid} 应含 SELECT")
    print(f"  [OK] {qid} 标题='{t.get_title(qid)}', 块长 {len(chunk)}")


# ---------------------------------------------------------------------------
# 3. chat_service 整套 import 不报错
# ---------------------------------------------------------------------------
print("\n[3] 验证 chat_service 改造后能 import")
try:
    from app.services.chat_service import ChatService
    svc = ChatService()
    assert_true(hasattr(svc, "stream_chat"), "应保留 stream_chat 方法")
    assert_true(hasattr(svc, "_generate_sql"), "应保留 _generate_sql 方法")
    # 新签名: 接受 sql_template / qid
    import inspect
    sig = inspect.signature(svc._generate_sql)
    assert_true("sql_template" in sig.parameters, "_generate_sql 应有 sql_template 参数")
    assert_true("qid" in sig.parameters, "_generate_sql 应有 qid 参数")
    print(f"  [OK] ChatService 实例化成功")
    print(f"  [OK] _generate_sql 签名: {sig}")
except Exception as e:
    raise AssertionError(f"chat_service 加载失败: {e}")


# ---------------------------------------------------------------------------
# 4. sql_guard 在 chat_service 中的引用
# ---------------------------------------------------------------------------
print("\n[4] 验证 _execute_sql 已集成 sql_guard")
import re
with open(Path(__file__).resolve().parent.parent / "app" / "services" / "chat_service.py", encoding="utf-8") as f:
    src = f.read()

assert_true("from app.core.sql_guard import validate" in src, "_execute_sql 应引用 sql_guard")
assert_true("guard = guard_validate(sql)" in src, "应调用 guard_validate")
print(f"  [OK] _execute_sql 已集成 sql_guard.validate")


# ---------------------------------------------------------------------------
# 5. _generate_sql 的 template_section 拼接
# ---------------------------------------------------------------------------
print("\n[5] 验证 _generate_sql 已支持 template_section")
assert_true("template_section" in src, "应有 template_section 变量")
assert_true("template_section + retry_hint" in src, "template_section 应拼到 ollama 调用")
print(f"  [OK] _generate_sql 已支持 template_section")


# ---------------------------------------------------------------------------
# 6. stream_chat 已用 QA 匹配替代 _detect_db_related
# ---------------------------------------------------------------------------
print("\n[6] 验证 stream_chat 流程")
assert_true("from app.services.qa_matcher import get_qa_matcher" in src, "应 import qa_matcher")
assert_true("matcher.match" in src, "应调用 matcher.match")
assert_true("template_loader.get" in src, "应调用 template_loader.get")
# 兜底分支
assert_true("兜底分支" in src, "应有兜底分支")
assert_true("stream_summary['fallback_reason']" in src, "应记录 fallback 原因")
print(f"  [OK] stream_chat 已用 QA 匹配 + 问答手册 范式")


# ---------------------------------------------------------------------------
# 7. SSE 事件协议保持
# ---------------------------------------------------------------------------
print("\n[7] 验证 SSE 事件协议未破坏")
sse_events = ["'mode'", "'sql'", "'table'", "'chart'", "'summary'", "'message'", "'error'", "'done'"]
for ev in sse_events:
    assert_true(ev in src, f"SSE 事件 {ev} 应保留")
print(f"  [OK] 8 种 SSE 事件 type 全部保留")


print("\n[ALL OK] 集成测试 7 项全部通过")
