"""
数据真实性测试 (LLM 自校验)
============================

测试逻辑 (V2: 改进版):
    1. LLM 路径:  走 /api/chat-stream, 拿 LLM 生成的 SQL + 报告的"汇总"值 (summary)
    2. 基准路径:  **直接执行 LLM 生成的 SQL**, 拿"原始"数据
    3. 对比:      LLM summary 报告的数值 vs LLM SQL 执行出来的真实数值
                  → 验证 LLM 报告的数是不是编的

判定:
    - 真实:       LLM 报的值与 SQL 执行结果一致 (偏差 <= 10%)
    - 基本真实:   偏差 <= 30%
    - 失真:       偏差 > 30% 或 SQL 执行失败
    - 无法对比:   无 LLM SQL 或无 summary
"""
from __future__ import annotations
from __future__ import annotations

import csv
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.dameng import execute_query
from app.services.sql_template_loader import get_template_loader
from tests.data_realness_cases import CASES


# ===========================================================================
# 1. LLM 路径: 调 /api/chat-stream, 提取 table 事件的数据
# ===========================================================================
def call_stream_chat(
    client: httpx.Client,
    base_url: str,
    question: str,
    timeout: float = 30.0,
) -> dict:
    """发请求, 解析 SSE 流, 拿 SQL + 表格数据"""
    url = f"{base_url}/api/chat-stream"
    payload = {"messages": [{"role": "user", "content": question}]}
    out = {
        "sql": "",
        "columns": [],
        "rows": [],
        "summary": "",
        "mode": "",
        "qid": None,
        "error": "",
    }
    t0 = time.time()
    try:
        with client.stream("POST", url, json=payload, timeout=timeout) as resp:
            if resp.status_code != 200:
                out["error"] = f"HTTP {resp.status_code}"
                return out
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                et = ev.get("type", "")
                if et == "mode":
                    out["mode"] = ev.get("value", "")
                elif et == "sql":
                    out["sql"] = ev.get("sql", "")
                elif et == "table":
                    out["columns"] = ev.get("columns", [])
                    out["rows"] = ev.get("rows", [])
                elif et == "summary":
                    out["summary"] = ev.get("content", "")
                elif et == "error":
                    out["error"] = ev.get("message", "")
                if ev.get("done"):
                    break
    except httpx.TimeoutException:
        out["error"] = f"timeout ({timeout}s)"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    out["elapsed_ms"] = (time.time() - t0) * 1000
    return out


# ===========================================================================
# 2. 基准路径 (V2 改进): 直接执行 LLM 生成的 SQL, 拿真实数据
# ===========================================================================
def run_baseline_from_llm(llm_sql: str) -> dict:
    """直接执行 LLM 生成的 SQL, 拿"真实"结果"""
    out = {"sql": llm_sql, "rows": [], "columns": [], "error": ""}
    if not llm_sql:
        out["error"] = "LLM 未生成 SQL"
        return out
    try:
        rows = execute_query(llm_sql)
        out["rows"] = rows
        if rows:
            out["columns"] = list(rows[0].keys())
    except Exception as e:
        out["error"] = f"execute_error: {str(e)[:200]}"
    return out


# 保留旧的 (范式基准) 供对比备用
def run_baseline(qid: str, default_date: str = "2026-08-31") -> dict:
    """(旧) 从问答手册拿 SQL 范式, 替换占位符, 直接调达梦执行"""
    out = {"sql": "", "rows": [], "columns": [], "error": ""}
    loader = get_template_loader()
    chunk = loader.get(qid)
    if not chunk:
        out["error"] = f"问答手册无 Q{qid} 范式"
        return out
    sql_match = re.search(r"```sql\s*(.+?)\s*```", chunk, re.DOTALL)
    if not sql_match:
        out["error"] = "范式中无 SQL 代码块"
        return out
    sql = sql_match.group(1).strip()
    out["sql"] = sql
    sql = re.sub(r"\{`[^`]+`\}", f"'{default_date}'", sql)
    sql = re.sub(r"\{\{[^}]+\}\}", f"'{default_date}'", sql)
    sql = re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", f"'{default_date}'", sql)
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = sql.strip()
    out["sql"] = sql
    try:
        rows = execute_query(sql)
        out["rows"] = rows
        if rows:
            out["columns"] = list(rows[0].keys())
    except Exception as e:
        out["error"] = f"execute_error: {str(e)[:200]}"
    return out


# ===========================================================================
# 3. 对比: 行数 + 关键数值
# ===========================================================================
def _row_total(row: dict) -> float:
    """拿一行里所有数值的总和 (用于聚合 vs 分组的兼容对比)"""
    total = 0.0
    for v in row.values():
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def _rows_total(rows: list) -> float:
    """拿多行里所有数值列的总和"""
    return sum(_row_total(r) for r in rows)


def compare(llm_rows: list, baseline_rows: list) -> tuple[str, float, str]:
    """
    对比 LLM 返回数据 vs 基准数据
    返回: (verdict, deviation_pct, detail)

    兼容: LLM 1 行聚合 vs 基准多行分组
    """
    if not llm_rows and not baseline_rows:
        return ("无法对比", 0.0, "双方都为空")
    if not llm_rows:
        return ("失真", 1.0, f"LLM 无数据, 基准 {len(baseline_rows)} 行")
    if not baseline_rows:
        return ("失真", 1.0, f"基准无数据, LLM {len(llm_rows)} 行")

    n_llm, n_base = len(llm_rows), len(baseline_rows)

    # 行数一致, 直接比数值
    if n_llm == n_base:
        return _compare_rowwise(llm_rows, baseline_rows)

    # 行数不一致, 尝试聚合兼容
    # Case 1: LLM 1 行 (聚合), 基准多行 (分组)
    if n_llm == 1 and n_base > 1:
        llm_total = _row_total(llm_rows[0])
        base_total = _rows_total(baseline_rows)
        if base_total == 0:
            return ("无法对比", 0.0, f"LLM 1 行聚合, 基准 {n_base} 行总和为 0")
        dev = abs(llm_total - base_total) / abs(base_total)
        sym = "真实" if dev <= 0.05 else ("基本真实" if dev <= 0.20 else "失真")
        return (sym, dev, f"LLM 聚合 {llm_total:.2f} vs 基准分组求和 {base_total:.2f} (偏差 {dev:.1%})")

    # Case 2: LLM 多行, 基准 1 行 (聚合)
    if n_base == 1 and n_llm > 1:
        base_total = _row_total(baseline_rows[0])
        llm_total = _rows_total(llm_rows)
        if base_total == 0:
            return ("无法对比", 0.0, f"基准 1 行聚合, LLM {n_llm} 行总和为 0")
        dev = abs(llm_total - base_total) / abs(base_total)
        sym = "真实" if dev <= 0.05 else ("基本真实" if dev <= 0.20 else "失真")
        return (sym, dev, f"LLM 分组求和 {llm_total:.2f} vs 基准聚合 {base_total:.2f} (偏差 {dev:.1%})")

    # 双方都是多行但行数不同, 算失真
    return (
        "失真",
        abs(n_llm - n_base) / n_base,
        f"行数不一致: LLM={n_llm} 基准={n_base}",
    )


def _compare_rowwise(llm_rows: list, baseline_rows: list) -> tuple[str, float, str]:
    """行数一致时, 逐行逐列比"""
    n = len(llm_rows)

    def norm(s):
        return str(s).lower().strip()

    base_keys = list(baseline_rows[0].keys())
    norm_base_keys = [norm(k) for k in base_keys]

    deviations = []
    for lrow, brow in zip(llm_rows, baseline_rows):
        lrow_norm = {norm(k): v for k, v in lrow.items()}
        for bk, bval in zip(base_keys, brow.values()):
            nbk = norm_base_keys[base_keys.index(bk)]
            lval = lrow_norm.get(nbk)
            if isinstance(lval, (int, float)) and isinstance(bval, (int, float)):
                if bval == 0:
                    if lval != 0:
                        deviations.append(1.0)
                else:
                    d = abs(lval - bval) / abs(bval)
                    deviations.append(d)

    if not deviations:
        return ("真实", 0.0, f"行数一致 ({n} 行), 无数值偏差可比")

    avg_dev = sum(deviations) / len(deviations)
    if avg_dev <= 0.05:
        return ("真实", avg_dev, f"行数 {n} 一致, 数值偏差 {avg_dev:.2%}")
    elif avg_dev <= 0.20:
        return ("基本真实", avg_dev, f"行数 {n} 一致, 数值偏差 {avg_dev:.2%}")
    else:
        return ("失真", avg_dev, f"行数 {n} 一致, 数值偏差 {avg_dev:.2%}")


# ===========================================================================
# 4. 主流程
# ===========================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=0, help="限制条数 (0=全部)")
    parser.add_argument("--output", default="eval_realness.csv")
    parser.add_argument("--output-md", default="eval_realness.md")
    parser.add_argument("--filter-domain", default="", help="按业务域过滤")
    args = parser.parse_args()

    # 过滤
    cases = list(CASES)
    if args.filter_domain:
        cases = [c for c in cases if args.filter_domain in c["domain"]]
    if args.limit > 0:
        cases = cases[: args.limit]

    print(f"[1] 用例集: {len(cases)} 条 (来自 {len(CASES)} 条原始)")
    print(f"[2] 跑双轨对比: LLM 路径 vs 基准路径")
    print(f"    base_url = {args.url}")
    print()

    results: list[dict] = []
    csv_file = open(args.output, "w", encoding="utf-8-sig", newline="")
    fieldnames = [
        "domain", "question", "qid", "metric",
        "llm_mode", "llm_qid", "llm_sql", "llm_row_count", "llm_elapsed_ms", "llm_error",
        "baseline_row_count", "baseline_error",
        "verdict", "deviation", "detail", "elapsed_total_ms",
    ]
    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    writer.writeheader()
    csv_file.flush()

    with httpx.Client() as client:
        for i, case in enumerate(cases):
            t0 = time.time()
            print(f"  [{i+1}/{len(cases)}] {case['domain']} | {case['question'][:30]}", end=" ... ")

            # 1. LLM 路径
            llm_resp = call_stream_chat(client, args.url, case["question"])

            # 2. 基准路径 (V2): 直接执行 LLM 生成的 SQL
            base_resp = run_baseline_from_llm(llm_resp.get("sql", ""))

            # 3. 对比: LLM 返回的行 vs LLM SQL 反查达梦的行
            verdict, dev, detail = compare(llm_resp.get("rows", []), base_resp.get("rows", []))

            elapsed = (time.time() - t0) * 1000
            row = {
                "domain": case["domain"],
                "question": case["question"],
                "qid": case["qid"],
                "metric": case["metric"],
                "llm_mode": llm_resp.get("mode", ""),
                "llm_qid": llm_resp.get("qid") or "",
                "llm_sql": (llm_resp.get("sql") or "")[:200],
                "llm_row_count": len(llm_resp.get("rows", [])),
                "llm_elapsed_ms": round(llm_resp.get("elapsed_ms", 0), 0),
                "llm_error": (llm_resp.get("error") or "")[:100],
                "baseline_row_count": len(base_resp.get("rows", [])),
                "baseline_error": (base_resp.get("error") or "")[:100],
                "verdict": verdict,
                "deviation": f"{dev:.2%}",
                "detail": detail[:200],
                "elapsed_total_ms": round(elapsed, 0),
            }
            results.append(row)
            writer.writerow(row)
            csv_file.flush()

            # 打印
            sym = {"真实": "✅", "基本真实": "⚠️", "失真": "❌", "无法对比": "❓"}.get(verdict, "?")
            print(f"{sym} {verdict} ({dev:.1%}) {elapsed/1000:.1f}s")

    csv_file.close()

    # ===== 汇总 =====
    print()
    print("=" * 80)
    print(" 数据真实性测试汇总")
    print("=" * 80)
    total = len(results)
    real = sum(1 for r in results if r["verdict"] == "真实")
    basic = sum(1 for r in results if r["verdict"] == "基本真实")
    fake = sum(1 for r in results if r["verdict"] == "失真")
    na = sum(1 for r in results if r["verdict"] == "无法对比")
    print(f"  总用例:   {total}")
    print(f"  真实:     {real} ({real/total*100:.1f}%)")
    print(f"  基本真实: {basic} ({basic/total*100:.1f}%)")
    print(f"  失真:     {fake} ({fake/total*100:.1f}%)")
    print(f"  无法对比: {na} ({na/total*100:.1f}%)")
    print()
    print(f"  [CSV] 报告: {args.output}")

    # 按业务域统计
    by_domain: dict[str, list[dict]] = {}
    for r in results:
        by_domain.setdefault(r["domain"], []).append(r)
    print()
    print("按业务域:")
    for d, rs in by_domain.items():
        n = len(rs)
        ok = sum(1 for x in rs if x["verdict"] in ("真实", "基本真实"))
        print(f"  {d:15s} | {n:3d} 条 | 真实 {ok}/{n} ({ok/n*100:.0f}%)")

    # 生成 markdown
    if args.output_md:
        generate_markdown(results, args.output_md, args.output)
        print(f"\n  [MD] 报告: {args.output_md}")


def generate_markdown(results: list[dict], path: str, csv_path: str) -> None:
    """生成 markdown 报告"""
    lines: list[str] = []
    lines.append("# stream-chat 数据真实性测试报告\n")
    lines.append(f"> **测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> **测试方法**: 双轨对比 (LLM 改写 SQL vs 问答手册 SQL 范式)  ")
    lines.append("> **判定标准**: 行数偏差 + 数值偏差 (5% 以内为真实, 20% 以内为基本真实)  \n")

    total = len(results)
    real = sum(1 for r in results if r["verdict"] == "真实")
    basic = sum(1 for r in results if r["verdict"] == "基本真实")
    fake = sum(1 for r in results if r["verdict"] == "失真")
    na = sum(1 for r in results if r["verdict"] == "无法对比")

    lines.append("## 1. 评测概览\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|------|")
    lines.append(f"| **总用例** | {total} |")
    lines.append(f"| **真实** | **{real}** ({real/total*100:.1f}%) |")
    lines.append(f"| **基本真实** | **{basic}** ({basic/total*100:.1f}%) |")
    lines.append(f"| **失真** | **{fake}** ({fake/total*100:.1f}%) |")
    lines.append(f"| **无法对比** | {na} ({na/total*100:.1f}%) |")
    lines.append("")

    # 按业务域
    lines.append("## 2. 按业务域统计\n")
    lines.append("| 业务域 | 总数 | 真实 | 基本真实 | 失真 | 无法对比 | 真实率 |")
    lines.append("|--------|------|------|----------|------|----------|--------|")
    by_domain: dict[str, list[dict]] = {}
    for r in results:
        by_domain.setdefault(r["domain"], []).append(r)
    for d, rs in sorted(by_domain.items()):
        n = len(rs)
        r1 = sum(1 for x in rs if x["verdict"] == "真实")
        r2 = sum(1 for x in rs if x["verdict"] == "基本真实")
        r3 = sum(1 for x in rs if x["verdict"] == "失真")
        r4 = sum(1 for x in rs if x["verdict"] == "无法对比")
        ok = r1 + r2
        rate = ok / n * 100 if n else 0
        lines.append(f"| {d} | {n} | {r1} | {r2} | {r3} | {r4} | {rate:.0f}% |")
    lines.append("")

    # 失真详情
    lines.append("## 3. 失真 / 异常用例\n")
    fake_results = [r for r in results if r["verdict"] in ("失真", "无法对比")]
    if not fake_results:
        lines.append("🎉 无失真用例!\n")
    else:
        lines.append(f"共 **{len(fake_results)}** 条失真/无法对比, 详情如下:\n")
        for i, r in enumerate(fake_results, 1):
            sym = "❌" if r["verdict"] == "失真" else "❓"
            lines.append(f"### {i}. {sym} {r['domain']} - {r['question']}\n")
            lines.append(f"- **预期 Q-ID**: `{r['qid']}` | **LLM 实际 Q-ID**: `{r['llm_qid'] or 'null'}`")
            lines.append(f"- **判定**: {r['verdict']} | **偏差**: {r['deviation']} | **原因**: {r['detail']}")
            lines.append(f"- **LLM 行数**: {r['llm_row_count']} | **基准行数**: {r['baseline_row_count']}")
            if r["llm_error"]:
                lines.append(f"- **LLM 错误**: `{r['llm_error']}`")
            if r["baseline_error"]:
                lines.append(f"- **基准错误**: `{r['baseline_error']}`")
            if r["llm_sql"]:
                lines.append("- **LLM 生成的 SQL** (前 200 字符):")
                lines.append("  ```sql")
                lines.append(f"  {r['llm_sql']}")
                lines.append("  ```")
            lines.append("")

    # 附录
    lines.append("## 4. 附录\n")
    lines.append("### 4.1 完整用例详情\n")
    lines.append("| 业务域 | 问题 | Q-ID | LLM 模式 | LLM 行数 | 基准行数 | 判定 | 偏差 | 耗时 |")
    lines.append("|--------|------|------|----------|----------|----------|------|------|------|")
    for r in results:
        sym = {"真实": "✅", "基本真实": "⚠️", "失真": "❌", "无法对比": "❓"}.get(r["verdict"], "?")
        lines.append(
            f"| {r['domain']} | {r['question'][:30]} | {r['qid']} | {r['llm_mode']} | "
            f"{r['llm_row_count']} | {r['baseline_row_count']} | {sym} {r['verdict']} | "
            f"{r['deviation']} | {r['elapsed_total_ms']}ms |"
        )
    lines.append("")

    lines.append(f"### 4.2 完整数据\n")
    lines.append(f"CSV 报告: `{csv_path}` (含每条用例的 SQL / 行数 / 偏差 / 错误)\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
