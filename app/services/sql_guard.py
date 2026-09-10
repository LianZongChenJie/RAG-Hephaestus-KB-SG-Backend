"""
SQL 安全门
==========

对 LLM 生成的 SQL 做静态校验, 阻断一切破坏性操作。
仅允许 SELECT 查询, 强制 LIMIT, 禁止多语句。

设计:
    1. 关键字白名单: 仅 SELECT
    2. 黑名单: DDL/DML 及危险关键字
    3. 强制 LIMIT / FETCH FIRST
    4. 单语句检查 (无分号)
    5. 字段名白名单 (基于 schema 可选, 由调用方传入)
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 关键字
# ---------------------------------------------------------------------------
FORBIDDEN_KEYWORDS = {
    # DDL
    "drop", "create", "alter", "truncate", "rename",
    # DML (写)
    "insert", "update", "delete", "merge",
    # 权限
    "grant", "revoke",
    # 事务 & 系统
    "commit", "rollback", "savepoint",
    # 函数执行
    "exec", "execute", "call",
    # 其他危险
    "xp_", "sp_",
    # 备份/还原
    "backup", "restore", "load",
}

ALLOWED_PREFIX = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
COMMENT_LINE = re.compile(r"--[^\n]*")
COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


# ---------------------------------------------------------------------------
# 校验结果
# ---------------------------------------------------------------------------
@dataclass
class GuardResult:
    ok: bool
    sql: str                          # 校验后 (可能追加了 LIMIT) 的 SQL
    reason: str = ""                  # 失败原因
    risk_level: str = "low"           # low / medium / high

    def to_dict(self) -> dict:
        return {"ok": self.ok, "sql": self.sql, "reason": self.reason, "risk_level": self.risk_level}


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def validate(
    sql: str,
    *,
    max_rows: int = 1000,
    allowed_tables: set[str] | None = None,
) -> GuardResult:
    """
    校验 LLM 生成的 SQL。

    Args:
        sql: 待校验 SQL
        max_rows: 强制 LIMIT 上限
        allowed_tables: 允许的表名集合 (None 表示不校验表名)

    Returns:
        GuardResult
    """
    if not sql or not sql.strip():
        return GuardResult(False, "", "SQL 为空", "high")

    # 1. 去注释, 防止注释绕过
    cleaned = COMMENT_BLOCK.sub(" ", sql)
    cleaned = COMMENT_LINE.sub(" ", cleaned)
    cleaned = cleaned.strip()
    # 去掉结尾分号
    cleaned = cleaned.rstrip(";").rstrip()

    # 2. 必须是 SELECT / WITH 开头 (WITH CTE 也允许)
    if not ALLOWED_PREFIX.match(cleaned):
        return GuardResult(False, sql, "SQL 必须以 SELECT 开头", "high")

    # 3. 多语句检查 (去掉字符串字面量后, 不应再含分号)
    if ";" in _strip_strings(cleaned):
        return GuardResult(False, sql, "禁止多语句", "high")

    # 4. 黑名单关键词
    body = _strip_strings(cleaned)
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", body, re.IGNORECASE):
            return GuardResult(False, sql, f"禁止使用关键字: {kw.upper()}", "high")

    # 5. 强制 LIMIT / FETCH
    has_limit = bool(re.search(r"\bFETCH\s+FIRST\b", body, re.IGNORECASE))
    has_limit2 = bool(re.search(r"\bLIMIT\s+\d+", body, re.IGNORECASE))
    has_rownum = bool(re.search(r"\bROWNUM\s*<\s*=", body, re.IGNORECASE))
    if not (has_limit or has_limit2 or has_rownum):
        cleaned = cleaned.rstrip() + f"\nFETCH FIRST {max_rows} ROWS ONLY"
    else:
        # 校验 LIMIT 不超过 max_rows
        m = re.search(r"\bLIMIT\s+(\d+)", body, re.IGNORECASE)
        if m and int(m.group(1)) > max_rows:
            cleaned = re.sub(r"\bLIMIT\s+\d+", f"LIMIT {max_rows}", cleaned, flags=re.IGNORECASE)
        m2 = re.search(r"\bFETCH\s+FIRST\s+(\d+)", body, re.IGNORECASE)
        if m2 and int(m2.group(1)) > max_rows:
            cleaned = re.sub(
                r"\bFETCH\s+FIRST\s+\d+",
                f"FETCH FIRST {max_rows} ROWS ONLY",
                cleaned, flags=re.IGNORECASE
            )

    # 6. 表名白名单 (可选)
    if allowed_tables:
        referenced = _extract_tables(body)
        illegal = referenced - {t.lower() for t in allowed_tables}
        if illegal:
            return GuardResult(
                False, sql,
                f"引用了未授权的表: {sorted(illegal)}", "high"
            )

    return GuardResult(True, cleaned, "", "low")


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------
def _strip_strings(sql: str) -> str:
    """去掉字符串字面量, 避免 'drop' 之类的字符串绕过。
    支持 '' 转义的单引号嵌套 (PostgreSQL/DM 风格)。"""
    out = []
    i = 0
    in_str = False
    n = len(sql)
    while i < n:
        c = sql[i]
        if in_str:
            if c == "'" and i + 1 < n and sql[i + 1] == "'":
                # '' 转义: 跳过两个引号
                i += 2
                continue
            if c == "'":
                in_str = False
                i += 1
                continue
            i += 1
        else:
            if c == "'":
                in_str = True
                i += 1
                continue
            out.append(c)
            i += 1
    return "".join(out)


def _extract_tables(sql: str) -> set[str]:
    """
    从 SQL 中粗略提取表名 (FROM / JOIN 后的标识符)。
    仅供白名单校验参考, 不替代 SQL 解析器。
    自动跳过 schema 前缀 (FWBZ. / "FWBZ".)
    跳过函数调用 (FROM TRUNC(...) 之类)
    """
    tables: set[str] = set()
    # 匹配 FROM/JOIN 等关键字 + 紧跟的可选 schema.table
    # 关键: 第一个 token 不能是 '(' (即函数调用)
    pattern = re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+"
        r"(?!\()"                              # 后面跟 '(' 就是函数, 跳过
        r"(?:[`\"\[]?(\w+)[`\"\]]?\.)?[`\"\[]?(\w+)[`\"\]]?",
        re.IGNORECASE
    )
    for m in pattern.finditer(sql):
        schema = (m.group(1) or "").lower()
        table = (m.group(2) or "").lower()
        # 跳过常见 SQL 关键字(防误判)
        if table in {"select", "where", "order", "group", "having", "limit", "fetch",
                     "extract", "year", "month", "day", "hour", "minute", "second",
                     "date", "time", "timestamp", "interval", "current", "sysdate",
                     "trunc", "round", "concat", "coalesce", "nvl", "decode", "case",
                     "when", "then", "else", "end", "as", "and", "or", "not", "null",
                     "true", "false", "is", "in", "between", "like", "exists",
                     "distinct", "all", "any", "union", "intersect", "except",
                     "with", "from", "join", "inner", "left", "right", "outer",
                     "cross", "on", "using", "values", "set", "into"}:
            continue
        if schema in {"fwbz", "public", "dbo"}:
            tables.add(table)
        elif not schema:
            tables.add(table)
        else:
            tables.add(table)
    return tables


# ---------------------------------------------------------------------------
# 攻击用例 (供测试参考)
# ---------------------------------------------------------------------------
ATTACK_CASES = [
    # (sql, should_pass, label)
    ("SELECT * FROM alarm_record", True, "正常查询"),
    ("DROP TABLE alarm_record", False, "DROP"),
    ("DELETE FROM alarm_record WHERE id=1", False, "DELETE"),
    ("UPDATE device SET name='x'", False, "UPDATE"),
    ("INSERT INTO device VALUES (1)", False, "INSERT"),
    ("SELECT 1; DROP TABLE device", False, "多语句"),
    ("SELECT * FROM device -- WHERE 1=1; DROP", True, "注释里有 DROP 也算 OK"),
    ("SELECT * FROM v$session", True, "系统视图 (允许)"),
    ("SELECT * FROM information_schema.tables", True, "字典视图 (允许)"),
    ("SELECT * FROM device UNION SELECT * FROM alarm_record", True, "UNION"),
    ("WITH x AS (SELECT 1) SELECT * FROM x", True, "CTE"),
    ("EXEC sp_helpdb", False, "EXEC"),
    ("CALL some_proc()", False, "CALL"),
    ("SELECT pg_sleep(999)", True, "慢函数 (业务侧超时控制)"),
    ("SELECT * FROM device LIMIT 99999", True, "LIMIT 自动缩到 max_rows"),
]


if __name__ == "__main__":
    # 简单自测
    print("=" * 60)
    print(f"{'用例':<45} {'通过':<6} {'结果'}")
    print("-" * 60)
    fail = 0
    for sql, should_pass, label in ATTACK_CASES:
        r = validate(sql)
        passed = (r.ok == should_pass)
        if not passed:
            fail += 1
        flag = "OK " if passed else "FAIL"
        print(f"{label:<45} {flag:<6} ok={r.ok}  {r.reason[:30]}")
    print("=" * 60)
    print(f"自测失败: {fail} / {len(ATTACK_CASES)}")
