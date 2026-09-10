"""验证 QA 匹配器 + Q-ID 索引 是否能正常加载"""
from app.services.qa_matcher import get_qa_matcher
from app.services.sql_template_loader import get_template_loader

m = get_qa_matcher()
print(f"[问题清单] 加载 {len(m.items)} 条")
print("前 5 条:")
for it in m.items[:5]:
    print(f"  {it.q_id} | [{it.domain}] {it.text}")
print("后 5 条:")
for it in m.items[-5:]:
    print(f"  {it.q_id} | [{it.domain}] {it.text}")

t = get_template_loader()
qids = t.all_qids()
print(f"\n[Q-ID 索引] 共 {len(qids)} 条")
print(f"前 5 个 Q-ID: {qids[:5]}")
print(f"Q5.1 标题: {t.get_title('5.1')}")
sample = t.get("5.1") or ""
print(f"Q5.1 块长度: {len(sample)} 字符")
print("Q5.1 前 200 字:")
print(sample[:200])

print(f"\n[可用性] matcher.available() = {m.available()}")
