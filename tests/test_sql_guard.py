"""SQL 安全门单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.sql_guard import validate


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg} | expected={expected!r} actual={actual!r}")


def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(msg)


# Case 1: 正常 SELECT 通过 + 自动补 LIMIT
r = validate("SELECT * FROM FWBZ.device")
assert_true(r.ok, "纯 SELECT 应通过")
assert_true("LIMIT" in r.sql.upper(), "应自动补 LIMIT")
print(f"  [1] OK | sql={r.sql!r}")

# Case 2: 已有 LIMIT 不重复加
r = validate("SELECT * FROM FWBZ.device LIMIT 10 OFFSET 0")
assert_true(r.ok)
assert_eq(r.sql.upper().count("LIMIT"), 1, "不应重复加 LIMIT")
print(f"  [2] OK | sql={r.sql!r}")

# Case 3: 拦截 DELETE / DROP / UPDATE / INSERT / TRUNCATE / ALTER / CREATE
for bad in [
    "DELETE FROM FWBZ.device",
    "DROP TABLE FWBZ.device",
    "UPDATE FWBZ.device SET name='x'",
    "INSERT INTO FWBZ.device VALUES (1)",
    "TRUNCATE TABLE FWBZ.device",
    "ALTER TABLE FWBZ.device ADD COLUMN x INT",
    "CREATE TABLE foo (id INT)",
    "GRANT SELECT ON FWBZ.device TO user1",
    "REVOKE SELECT ON FWBZ.device FROM user1",
]:
    r = validate(bad)
    assert_eq(r.ok, False, f"应拒绝: {bad!r}")
    print(f"  [3] OK | 拒绝 {bad[:30]!r} -> {r.reason!r}")

# Case 4: 拦截多语句 (中间分号)
r = validate("SELECT 1; DROP TABLE FWBZ.device")
assert_eq(r.ok, False, "中间分号应拒绝")
print(f"  [4] OK | 拦截多语句: {r.reason!r}")

# Case 5: 字符串里的分号不误判
r = validate("SELECT * FROM FWBZ.device WHERE name = 'a;b'")
assert_true(r.ok, "字符串里的分号不应误判")
print(f"  [5] OK | sql={r.sql!r}")

# Case 6: 列名含 create_time / drop_offline 不被误伤
r = validate("SELECT create_time, drop_offline FROM FWBZ.device")
assert_true(r.ok, "列名含 create_time 应正常")
print(f"  [6] OK | sql={r.sql!r}")

# Case 7: 聚合查询自动用 200 上限
r = validate("SELECT type, COUNT(*) FROM FWBZ.device GROUP BY type")
assert_true(r.ok)
assert_true("LIMIT 200" in r.sql, "聚合查询应自动 LIMIT 200")
print(f"  [7] OK | sql={r.sql!r}")

# Case 8: 明细查询自动用 500 上限
r = validate("SELECT * FROM FWBZ.device ORDER BY id")
assert_true(r.ok)
assert_true("LIMIT 500" in r.sql, "明细查询应自动 LIMIT 500")
print(f"  [8] OK | sql={r.sql!r}")

# Case 9: WITH ... SELECT 允许
r = validate("WITH t AS (SELECT * FROM FWBZ.device) SELECT * FROM t")
assert_true(r.ok, "WITH ... SELECT 应允许")
print(f"  [9] OK | sql={r.sql!r}")

# Case 10: 空 SQL
r = validate("")
assert_eq(r.ok, False)
r = validate("   ")
assert_eq(r.ok, False)
print(f"  [10] OK | 拒绝空 SQL: {r.reason!r}")

# Case 11: 末尾分号自动去
r = validate("SELECT * FROM FWBZ.device;")
assert_true(r.ok)
assert_eq(r.sql.rstrip().endswith(";"), False, "末尾分号应去掉")
print(f"  [11] OK | sql={r.sql!r}")

# Case 12: 自定义 limit 阈值
r = validate("SELECT * FROM FWBZ.device", detail_limit=100)
assert_true("LIMIT 100" in r.sql, "自定义 detail_limit 应生效")
print(f"  [12] OK | sql={r.sql!r}")

# Case 13: 已含 FETCH FIRST 不再补 LIMIT
r = validate("SELECT * FROM FWBZ.device FETCH FIRST 10 ROWS ONLY")
assert_true(r.ok)
print(f"  [13] OK | sql={r.sql!r}")

# Case 14: 已含 ROWNUM 不再补 LIMIT
r = validate("SELECT * FROM (SELECT t.*, ROWNUM rn FROM FWBZ.device t) WHERE rn <= 5")
assert_true(r.ok)
print(f"  [14] OK | sql={r.sql!r}")

# Case 15: 非 SELECT/WITH 前缀
r = validate("EXPLAIN SELECT * FROM FWBZ.device")
assert_eq(r.ok, False, "EXPLAIN 前缀不在白名单")
print(f"  [15] OK | 拒绝 EXPLAIN: {r.reason!r}")

print("\n[OK] SQL 安全门 15 个用例全部通过")
