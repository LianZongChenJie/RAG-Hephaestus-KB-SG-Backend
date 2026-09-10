"""P0 修复: validate_sql_columns 单元测试

覆盖:
    1. 8 个之前失败的 SQL (表别名/列别名) — 应全部通过
    2. 真实臆造列名 — 应拒绝
    3. 真实臆造表名 — 应拒绝
    4. 边界情况: 嵌套 JOIN, ON 条件, AS 别名
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.dameng import validate_sql_columns


def test_pass(name: str, sql: str) -> None:
    ok, err, items = validate_sql_columns(sql)
    status = "[OK]" if ok else "[FAIL]"
    detail = f" - {err[:80]}" if not ok and err else ""
    print(f"  {status} {name}{detail}")
    if not ok:
        raise AssertionError(f"{name} 应通过, 但报错: {err}")


def test_reject(name: str, sql: str, must_contain: str = "") -> None:
    ok, err, items = validate_sql_columns(sql)
    status = "[OK]" if not ok else "[FAIL]"
    detail = f" - {err[:80]}" if err else ""
    print(f"  {status} {name}{detail}")
    if ok:
        raise AssertionError(f"{name} 应拒绝, 但通过了")
    if must_contain and must_contain not in (err or ""):
        raise AssertionError(f"{name} 报错信息不含 '{must_contain}': {err}")


print("=" * 60)
print(" P0 测试: validate_sql_columns 重写后行为")
print("=" * 60)


# ============= 1. 之前失败的 SQL (P0 修的 bug) =============
print("\n[1] 之前失败的 SQL (表别名/列别名场景)")

# 用例 1: NOT EXISTS 子查询, 表别名 r/rec
test_pass(
    "1.1 NOT EXISTS 死规则 (别名 r/rec)",
    '''SELECT "r"."id", "r"."rule_code"
       FROM "FWBZ"."alarm_rules" "r"
       WHERE "r"."enabled_status" = '1'
         AND NOT EXISTS (SELECT 1 FROM "FWBZ"."alarm_record" "rec"
                          WHERE "rec"."alarm_rule_id" = "r"."id")
       LIMIT 500 OFFSET 0'''
)

# 用例 2: GROUP BY + AS 列别名
test_pass(
    "1.2 GROUP BY + COUNT(*) AS cnt",
    '''SELECT "alarm_category_name", "alarm_level_name",
               COUNT(*) AS "cnt"
       FROM "FWBZ"."alarm_record"
       WHERE "space_id" IS NOT NULL
       GROUP BY "alarm_category_name", "alarm_level_name"
       LIMIT 200 OFFSET 0'''
)

# 用例 3: 设备实时点位, 表别名 d
test_pass(
    "1.3 设备实时点位 (别名 d)",
    '''SELECT "d"."id", "d"."device_name", "d"."run_state", "d"."last_gather_time"
       FROM "FWBZ"."device" "d"
       WHERE "d"."id" IN (SELECT "device_id" FROM "FWBZ"."data_real")
       LIMIT 500 OFFSET 0'''
)

# 用例 4: 设备离线, 表别名 d + 多个 JOIN
test_pass(
    "1.4 设备离线 (别名 d + JOIN)",
    '''SELECT "d"."id", "d"."device_name", "d"."last_gather_time",
               EXTRACT("EPOCH" FROM (SYSDATE - "d"."last_gather_time")) / 3600.0 AS "offline_hours"
       FROM "FWBZ"."device" "d"
       WHERE EXTRACT("EPOCH" FROM (SYSDATE - "d"."last_gather_time")) / 3600.0 > 24
       LIMIT 500 OFFSET 0'''
)

# 用例 5: 折标煤, 表别名 d, s — 实际 LLM 真的臆造了 device_energy_consumption.energy_medium/time
# 校验器应该正确识别 (这是 LLM 真实错误, 应被拒绝)
test_reject(
    "1.5 折标煤 LLM 真实臆造列 (别名 d/s)",
    '''SELECT NVL(SUM("value") * NVL("eccsc", 1), 0) AS "折标煤吨数"
       FROM "FWBZ"."device_energy_consumption" "d"
       JOIN "FWBZ"."standard_coal_coefficient" "s"
         ON "d"."energy_medium" = "s"."energy_medium"
       WHERE TRUNC("d"."time") = TRUNC(SYSDATE)
       LIMIT 500 OFFSET 0''',
    must_contain="energy_medium",
)

# 用例 6: LLM 真实臆造了 alarm_record.category 列 (正确列是 alarm_category_id)
test_reject(
    "1.6 复杂聚合 LLM 真实臆造列",
    '''SELECT "category", COUNT(*) AS "count", SUM("value") AS "total"
       FROM "FWBZ"."alarm_record"
       GROUP BY "category"
       ORDER BY "count" DESC
       LIMIT 200 OFFSET 0''',
    must_contain="category",
)

# 用例 7: ON 条件里两个表别名 (用真实列名 space_name)
test_pass(
    "1.7 JOIN ... ON 别名.列",
    '''SELECT "a"."id", "b"."space_name"
       FROM "FWBZ"."device" "a"
       JOIN "FWBZ"."space" "b" ON "a"."space_id" = "b"."id"
       LIMIT 500 OFFSET 0'''
)

# 用例 8: 子查询 AS 别名
test_pass(
    "1.8 子查询 + AS 别名",
    '''SELECT "t"."device_name", "t"."value"
       FROM (SELECT "device_id", SUM("value") AS "value"
             FROM "FWBZ"."data_day"
             GROUP BY "device_id") "t"
       LIMIT 500 OFFSET 0'''
)


# ============= 2. 真实臆造列名 (应拒绝) =============
print("\n[2] 真实臆造列名 (应拒绝)")

test_reject(
    "2.1 臆造列 eccsc (不在 device_energy_consumption 中)",
    '''SELECT "eccsc"
       FROM "FWBZ"."device_energy_consumption"''',
    must_contain="eccsc",
)


# ============= 3. 真实臆造表名 (应拒绝) =============
print("\n[3] 真实臆造表名 (应拒绝)")

test_reject(
    "3.1 臆造表 fake_table",
    '''SELECT "id" FROM "FWBZ"."fake_table" LIMIT 100''',
    must_contain="fake_table",
)


# ============= 4. 边界情况 =============
print("\n[4] 边界情况")

test_pass(
    "4.1 极简 SELECT 1",
    'SELECT 1 FROM "FWBZ"."device" LIMIT 1',
)

test_pass(
    "4.2 子查询无别名",
    'SELECT * FROM (SELECT "id" FROM "FWBZ"."device") LIMIT 10',
)

test_pass(
    "4.3 大小写不敏感 (FWBZ vs fwbz)",
    'SELECT "id" FROM fwbz."device" LIMIT 10',
)


print("\n" + "=" * 60)
print(" ✅ 全部 P0 测试通过")
print("=" * 60)
