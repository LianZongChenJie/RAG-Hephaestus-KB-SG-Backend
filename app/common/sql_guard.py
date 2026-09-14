"""
达梦 SQL 安全门
================

职责:
    在 LLM 生成的 SQL 提交到达梦执行前, 做 4 件事:
        1. 白名单: 只允许 SELECT
        2. 黑名单: 拦截 DDL/DML/控制类关键字
        3. 防多语句: 禁止 ; 串接
        4. 自动 LIMIT: 没有分页时按场景兜底(明细 500 / 聚合 200)

设计原则:
    - 零依赖, 纯字符串正则, 不解析 AST
    - 失败保守: 拿不准就拒绝 (返回 ok=False)
    - 与 chat_service._generate_sql 里的 14 项修复解耦:
      这里只做"粗筛", 仍允许下游做"细修"

返回:
    GuardResult(ok: bool, sql: str, reason: str)
        - ok=True:  sql 是清洗后的最终 SQL
        - ok=False: sql 是原始 SQL, reason 给出拒绝原因
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# 禁用关键字 (独立 DDL/DML/控制类)
#   用 \b 词边界匹配, 避免误伤列名 (如 create_time)
# ---------------------------------------------------------------------------
_FORBIDDEN_KEYWORDS = frozenset({
    "insert", "update", "delete", "drop", "truncate",
    "alter", "create", "rename", "grant", "revoke",
    "exec", "execute", "merge", "call", "lock",
    "commit", "rollback", "savepoint",
})

# 允许的前缀: 必须是 SELECT / WITH ... SELECT
_ALLOWED_PREFIX = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


@dataclass
class GuardResult:
    """安全门结果"""
    ok: bool
    sql: str
    reason: str = ""


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def validate(
    sql: str,
    *,
    detail_limit: int = 500,
    aggregate_limit: int = 200,
) -> GuardResult:
    """
    校验 LLM 生成的 SQL 是否可执行

    Args:
        sql: 待校验的 SQL 字符串
        detail_limit: 明细查询 (无 GROUP BY) 的 LIMIT 兜底
        aggregate_limit: 聚合查询 (有 GROUP BY) 的 LIMIT 兜底

    Returns:
        GuardResult(ok, sql, reason)
    """
    if not sql or not sql.strip():
        return GuardResult(ok=False, sql=sql or "", reason="SQL 为空")

    # 1. 前缀白名单
    s = sql.strip().rstrip(";").strip()
    if not _ALLOWED_PREFIX.match(s):
        return GuardResult(
            ok=False,
            sql=sql,
            reason="非 SELECT/WITH 语句, 已拒绝",
        )

    # 2. 多语句拦截 (除末尾分号外, 中间不能有分号)
    #    注意: 字符串字面量里的 ';' 不应被算作多语句, 这里粗略判断
    #    若 LLM 在 'select 1;select 2' 这种, 拒绝
    body_no_strings = _strip_string_literals(s)
    if ";" in body_no_strings:
        return GuardResult(
            ok=False,
            sql=sql,
            reason="禁止多语句 (检测到中间分号)",
        )

    # 3. 黑名单关键字
    lowered = body_no_strings.lower()
    for kw in _FORBIDDEN_KEYWORDS:
        # \b 词边界, 避免误伤 create_time / drop_offline_flag 这类列名
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            return GuardResult(
                ok=False,
                sql=sql,
                reason=f"禁用关键字: {kw.upper()}",
            )

    # 4. 自动补 LIMIT (如果没有 LIMIT/FETCH/ROWNUM 分页)
    if not re.search(r"\b(LIMIT|FETCH\s+FIRST|ROWNUM)\b", s, re.IGNORECASE):
        has_group_by = bool(re.search(r"\bGROUP\s+BY\b", s, re.IGNORECASE))
        cap = aggregate_limit if has_group_by else detail_limit
        s = s.rstrip() + f" LIMIT {cap} OFFSET 0"

    return GuardResult(ok=True, sql=s, reason="")


# ---------------------------------------------------------------------------
# 工具: 把字符串字面量替换为空格, 避免里面的 ; 误判
# ---------------------------------------------------------------------------
def _strip_string_literals(sql: str) -> str:
    """把单引号字符串里的内容替换成空格, 用于关键字/分号检测"""
    out = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        # 单引号字符串
        if c == "'":
            out.append(c)
            i += 1
            while i < n:
                ch = sql[i]
                if ch == "'":
                    out.append(ch)
                    i += 1
                    # 转义 ''
                    if i < n and sql[i] == "'":
                        out.append(sql[i])
                        i += 1
                        continue
                    break
                out.append(" ")
                i += 1
            continue
        # 双引号标识符, 原样保留 (达梦里是标识符, 不用清)
        if c == '"':
            out.append(c)
            i += 1
            while i < n and sql[i] != '"':
                out.append(sql[i])
                i += 1
            if i < n:
                out.append(sql[i])
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)
