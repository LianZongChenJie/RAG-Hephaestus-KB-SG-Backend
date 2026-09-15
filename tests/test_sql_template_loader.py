"""问答手册 SQL 抽出：无占位符可直接执行，有 {{变量}} 需模型改写。"""
from app.chat.sql_template_loader import (
    extract_sql_from_chunk,
    get_template_loader,
)


def test_extract_plain_select():
    chunk = """**Q7.1 请查看并介绍设备信息**
```sql
SELECT d."id", d."device_name"
FROM "FWBZ"."device" d
LIMIT 500
```
"""
    sql = extract_sql_from_chunk(chunk)
    assert sql is not None
    assert sql.startswith("SELECT")
    assert "device" in sql
    assert "{{" not in sql


def test_extract_skips_placeholder_sql():
    chunk = """**Q6.3 x**
```sql
SELECT * FROM "FWBZ"."table_venue_info" vi
WHERE vi."venue_name" = '{{venue_name}}'
```
"""
    assert extract_sql_from_chunk(chunk) is None


def test_handbook_matches_question_list_qids():
    from app.chat.qa_matcher import _parse_question_list
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    items = _parse_question_list(
        (root / "config" / "FWBZ保障平台问题清单.md").read_text(encoding="utf-8")
    )
    loader = get_template_loader()
    qids = [it.q_id for it in items]
    assert qids, "问题清单不应为空"
    missing = [qid for qid in qids if not loader.has(qid)]
    assert not missing, f"手册缺 Q-ID: {missing}"
    sql = loader.get_executable_sql("2.1")
    assert sql is not None and "metering_point" in sql
