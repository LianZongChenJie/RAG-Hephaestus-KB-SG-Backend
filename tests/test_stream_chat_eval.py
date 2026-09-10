"""
stream-chat 接口端到端评测脚本
==============================

测试用例构成:
    A 类 - 原题 (从 qa_matcher 自动生成, 80 条)
    B 类 - 同义改写 (~30 条, 验证 LLM 判匹配能力)
    C 类 - 扩写 (在原题上加时间/限定词, ~10 条)
    D 类 - 业务相关但不在清单 (~10 条, 边界)
    E 类 - 应走兜底 (~10 条, 闲聊/天气/非业务)

每个用例评估:
    - 实际 mode (db / llm)
    - 匹配 Q-ID 与预期是否一致
    - SQL 是否生成成功 (db 模式)
    - 端到端耗时

用法:
    python tests/test_stream_chat_eval.py
    python tests/test_stream_chat_eval.py --concurrency 4
    python tests/test_stream_chat_eval.py --filter A B
    python tests/test_stream_chat_eval.py --limit 5
    python tests/test_stream_chat_eval.py --output report.csv
    python tests/test_stream_chat_eval.py --url http://192.168.1.10:8000
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import httpx

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ===========================================================================
# 测试用例
# ===========================================================================
def build_a_cases() -> list[dict]:
    """A 类 - 原题, 从 qa_matcher 自动生成"""
    from app.services.qa_matcher import get_qa_matcher
    m = get_qa_matcher()
    cases = []
    for it in m.items:
        # 还原问号 (解析时被去掉了)
        q = it.text.rstrip("?？.。 ") + "?"
        cases.append({
            "category": "A_原题",
            "question": q,
            "expected_mode": "db",
            "expected_qid": it.q_id,
            "note": f"清单原题: {it.text}",
        })
    return cases


# B 类 - 同义改写 (30 条)
B_CASES = [
    {"category": "B_改写", "question": "今天园区电费花了多少", "expected_mode": "db", "expected_qid": "5.5", "note": "近义改写"},
    {"category": "B_改写", "question": "咱们用电用气用水情况", "expected_mode": "db", "expected_qid": "5.1", "note": "口语化"},
    {"category": "B_改写", "question": "帮我看看现在还有几条告警没处理", "expected_mode": "db", "expected_qid": "2.1", "note": "口语化"},
    {"category": "B_改写", "question": "X 设备最近报了几次警", "expected_mode": "db", "expected_qid": "2.4", "note": "变种问法"},
    {"category": "B_改写", "question": "摄像头掉线了哪些", "expected_mode": "db", "expected_qid": "9.1", "note": "口语化"},
    {"category": "B_改写", "question": "今天进园子多少人", "expected_mode": "db", "expected_qid": "13.1", "note": "口语化"},
    {"category": "B_改写", "question": "还有几个车位", "expected_mode": "db", "expected_qid": "12.1", "note": "简短问法"},
    {"category": "B_改写", "question": "现在灯开着的有哪些回路", "expected_mode": "db", "expected_qid": "6.1", "note": "变种问法"},
    {"category": "B_改写", "question": "上周生成了几份报告", "expected_mode": "db", "expected_qid": "1.1", "note": "时间变种"},
    {"category": "B_改写", "question": "昨天登录了几次系统", "expected_mode": "db", "expected_qid": "1.4", "note": "近义改写"},
    {"category": "B_改写", "question": "现在哪些设备没在工作", "expected_mode": "db", "expected_qid": "3.2", "note": "近义改写"},
    {"category": "B_改写", "question": "3 号设备跑了多少电", "expected_mode": "db", "expected_qid": "5.x", "note": "近义: 设备能耗"},
    {"category": "B_改写", "question": "园区能效咋样", "expected_mode": "db", "expected_qid": "5.x", "note": "宽泛问法"},
    {"category": "B_改写", "question": "今天的报警", "expected_mode": "db", "expected_qid": "2.2", "note": "简短问法"},
    {"category": "B_改写", "question": "哪些规则从来没触发过", "expected_mode": "db", "expected_qid": "2.6", "note": "近义: 死规则"},
    {"category": "B_改写", "question": "消防设备最近 24h 有离线的吗", "expected_mode": "db", "expected_qid": "2.7", "note": "变种问法"},
    {"category": "B_改写", "question": "分时电量尖峰平谷各多少", "expected_mode": "db", "expected_qid": "5.6", "note": "专业术语"},
    {"category": "B_改写", "question": "现在能介单价是啥", "expected_mode": "db", "expected_qid": "5.7", "note": "口语化"},
    {"category": "B_改写", "question": "今天用电折标煤多少", "expected_mode": "db", "expected_qid": "5.8", "note": "近义改写"},
    {"category": "B_改写", "question": "登录日志最近的", "expected_mode": "db", "expected_qid": "1.4", "note": "极简问法"},
    {"category": "B_改写", "question": "故障分析报告在哪", "expected_mode": "db", "expected_qid": "1.2", "note": "口语化"},
    {"category": "B_改写", "question": "慢接口 TOP10", "expected_mode": "db", "expected_qid": "18.1", "note": "运维专业词"},
    {"category": "B_改写", "question": "告警转工单完成情况", "expected_mode": "db", "expected_qid": "2.x", "note": "流程问法"},
    {"category": "B_改写", "question": "停车场现在空位", "expected_mode": "db", "expected_qid": "12.1", "note": "口语化"},
    {"category": "B_改写", "question": "今天投诉多少条", "expected_mode": "db", "expected_qid": "14.x", "note": "变种问法"},
    {"category": "B_改写", "question": "活动准备进度", "expected_mode": "db", "expected_qid": "15.x", "note": "简短问法"},
    {"category": "B_改写", "question": "BA 控制点最近趋势", "expected_mode": "db", "expected_qid": "8.2", "note": "专业术语"},
    {"category": "B_改写", "question": "联动策略今天触发了几次", "expected_mode": "db", "expected_qid": "7.2", "note": "近义改写"},
    {"category": "B_改写", "question": "跨域综合 / 接口心跳情况", "expected_mode": "db", "expected_qid": "18.x", "note": "跨域问法"},
    {"category": "B_改写", "question": "看门岗进出记录", "expected_mode": "db", "expected_qid": "10.x", "note": "近义改写"},
]


# C 类 - 扩写 (在原题上加时间/限定词)
C_CASES = [
    {"category": "C_扩写", "question": "今天 (2026-08-31) 全园区总用电量", "expected_mode": "db", "expected_qid": "5.1", "note": "加时间"},
    {"category": "C_扩写", "question": "最近 7 天的 AI 报告清单", "expected_mode": "db", "expected_qid": "1.1", "note": "加时间窗"},
    {"category": "C_扩写", "question": "2026 年 8 月各能介的能耗", "expected_mode": "db", "expected_qid": "5.1", "note": "具体日期"},
    {"category": "C_扩写", "question": "本月 (2026-08) 累计能耗", "expected_mode": "db", "expected_qid": "5.5", "note": "加时间"},
    {"category": "C_扩写", "question": "上周 (2026-08-24 ~ 30) 系统登录日志", "expected_mode": "db", "expected_qid": "1.4", "note": "加时间窗"},
    {"category": "C_扩写", "question": "金安桥场馆当前设备运行状态", "expected_mode": "db", "expected_qid": "3.x", "note": "加空间"},
    {"category": "C_扩写", "question": "近 24 小时未处理的紧急告警", "expected_mode": "db", "expected_qid": "2.1", "note": "加时间+等级"},
    {"category": "C_扩写", "question": "近 1 小时各空间温度趋势", "expected_mode": "db", "expected_qid": "8.2", "note": "加时间+空间"},
    {"category": "C_扩写", "question": "本月每日的电费 (按分时)", "expected_mode": "db", "expected_qid": "5.2", "note": "加维度"},
    {"category": "C_扩写", "question": "上季度碳排放总量", "expected_mode": "db", "expected_qid": "5.8", "note": "加时间"},
]


# D 类 - DB 相关但可能不在清单 (边界)
D_CASES = [
    {"category": "D_边界", "question": "统计所有 7 月份的电费", "expected_mode": "db", "expected_qid": "5.2", "note": "月度电费"},
    {"category": "D_边界", "question": "各楼层的平均温度", "expected_mode": "db", "expected_qid": "8.x", "note": "BA 域"},
    {"category": "D_边界", "question": "昨天 22 点到 24 点的报警", "expected_mode": "db", "expected_qid": "2.2", "note": "具体时段"},
    {"category": "D_边界", "question": "工单完成率最高的运维人员", "expected_mode": "db", "expected_qid": "2.x", "note": "TOP 排名"},
    {"category": "D_边界", "question": "近 30 天能耗最高的 10 个设备", "expected_mode": "db", "expected_qid": "5.x", "note": "TOP 排名"},
    {"category": "D_边界", "question": "金安桥 vs 其他场馆的能耗对比", "expected_mode": "db", "expected_qid": "5.1", "note": "多空间对比"},
    {"category": "D_边界", "question": "今天所有告警中按类型分布", "expected_mode": "db", "expected_qid": "2.3", "note": "分布统计"},
    {"category": "D_边界", "question": "我", "expected_mode": "llm", "expected_qid": None, "note": "单字问题"},
    {"category": "D_边界", "question": "你能干什么", "expected_mode": "llm", "expected_qid": None, "note": "能力问询"},
    {"category": "D_边界", "question": "查一下", "expected_mode": "llm", "expected_qid": None, "note": "无目标查询"},
]


# E 类 - 应走兜底 (闲聊/天气/非业务)
E_CASES = [
    {"category": "E_兜底", "question": "今天北京天气怎么样", "expected_mode": "llm", "expected_qid": None, "note": "天气"},
    {"category": "E_兜底", "question": "你好", "expected_mode": "llm", "expected_qid": None, "note": "寒暄"},
    {"category": "E_兜底", "question": "帮我写个 Python 爬虫", "expected_mode": "llm", "expected_qid": None, "note": "编程任务"},
    {"category": "E_兜底", "question": "今天有什么新闻", "expected_mode": "llm", "expected_qid": None, "note": "新闻"},
    {"category": "E_兜底", "question": "你是谁", "expected_mode": "llm", "expected_qid": None, "note": "自我介绍"},
    {"category": "E_兜底", "question": "明天会下雨吗", "expected_mode": "llm", "expected_qid": None, "note": "天气"},
    {"category": "E_兜底", "question": "介绍下你自己", "expected_mode": "llm", "expected_qid": None, "note": "自我介绍"},
    {"category": "E_兜底", "question": "谢谢", "expected_mode": "llm", "expected_qid": None, "note": "寒暄"},
    {"category": "E_兜底", "question": "讲个笑话", "expected_mode": "llm", "expected_qid": None, "note": "闲聊"},
    {"category": "E_兜底", "question": "推荐一部电影", "expected_mode": "llm", "expected_qid": None, "note": "闲聊"},
]


# ===========================================================================
# SSE 解析
# ===========================================================================
# 匹配 mode 事件 message 字段中的 Q-ID 和 置信度
# 例: "匹配到标准问题 Q5.5 (置信度 92%), 正在生成查询..."
_QID_RE = re.compile(r"Q(\d+\.\d+)")
_CONF_RE = re.compile(r"置信度\s*(\d+)%")


@dataclass
class EvalResult:
    """单条用例的评测结果"""
    category: str
    question: str
    expected_mode: str
    expected_qid: Optional[str]
    actual_mode: str = ""           # db / llm
    actual_qid: Optional[str] = None
    actual_confidence: float = 0.0
    sql_generated: str = ""
    table_row_count: int = 0
    chart_generated: bool = False
    summary: str = ""
    error: str = ""
    elapsed_ms: float = 0.0
    note: str = ""


def call_stream_chat(
    client: httpx.Client,
    base_url: str,
    question: str,
    timeout: float = 30.0,
) -> dict:
    """
    发 POST /api/chat-stream, 解析 SSE 流, 返回解析结果
    返回 dict 含: mode, qid, confidence, sql, table_rows, has_chart, summary, error, elapsed_ms
    """
    url = f"{base_url}/api/chat-stream"
    payload = {"messages": [{"role": "user", "content": question}]}

    t0 = time.time()
    out = {
        "mode": "",
        "qid": None,
        "confidence": 0.0,
        "sql": "",
        "table_rows": 0,
        "has_chart": False,
        "summary": "",
        "error": "",
        "elapsed_ms": 0.0,
    }

    try:
        with client.stream("POST", url, json=payload, timeout=timeout) as resp:
            if resp.status_code != 200:
                out["error"] = f"HTTP {resp.status_code}"
                out["elapsed_ms"] = (time.time() - t0) * 1000
                return out

            for line in resp.iter_lines():
                if not line:
                    continue
                # SSE: "data: {...}"
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                ev_type = ev.get("type", "")

                if ev_type == "mode":
                    val = ev.get("value", "")
                    if val in ("db", "llm"):
                        out["mode"] = val
                    msg = ev.get("message", "") or ""
                    if not out["qid"]:
                        m = _QID_RE.search(msg)
                        if m:
                            out["qid"] = m.group(1)
                    if not out["confidence"]:
                        m = _CONF_RE.search(msg)
                        if m:
                            out["confidence"] = int(m.group(1)) / 100.0

                elif ev_type == "sql":
                    out["sql"] = ev.get("sql", "")

                elif ev_type == "table":
                    rows = ev.get("rows", [])
                    out["table_rows"] = len(rows) if isinstance(rows, list) else 0

                elif ev_type == "chart":
                    out["has_chart"] = True

                elif ev_type == "summary":
                    out["summary"] = ev.get("content", "")

                elif ev_type == "error":
                    out["error"] = ev.get("message", "")

                elif ev_type == "message":
                    # 兜底分支的流式 token, 拼到 summary 里
                    if not out["summary"]:
                        out["summary"] = ""
                    out["summary"] += ev.get("content", "")

                # done 事件标志着流结束
                if ev.get("done"):
                    break

    except httpx.TimeoutException:
        out["error"] = f"timeout ({timeout}s)"
    except httpx.ConnectError as e:
        out["error"] = f"connect: {e}"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"

    out["elapsed_ms"] = (time.time() - t0) * 1000
    return out


# ===========================================================================
# 评估逻辑
# ===========================================================================
def evaluate_case(case: dict, response: dict) -> EvalResult:
    """评估单条用例"""
    actual_qid = response.get("qid")
    # Q-ID 兼容匹配: 5.x 匹配 5.1/5.2/...
    expected = case["expected_qid"]
    expected_match = False
    if expected is None:
        expected_match = actual_qid is None
    elif expected.endswith(".x"):
        # 域级匹配: 5.x 命中 5.1/5.2/... 都算对
        prefix = expected.rstrip(".x")
        expected_match = actual_qid is not None and actual_qid.startswith(prefix + ".")
    else:
        expected_match = (actual_qid == expected)

    return EvalResult(
        category=case["category"],
        question=case["question"],
        expected_mode=case["expected_mode"],
        expected_qid=expected,
        actual_mode=response.get("mode", ""),
        actual_qid=actual_qid,
        actual_confidence=response.get("confidence", 0.0),
        sql_generated=response.get("sql", "")[:200],
        table_row_count=response.get("table_rows", 0),
        chart_generated=response.get("has_chart", False),
        summary=response.get("summary", "")[:200],
        error=response.get("error", ""),
        elapsed_ms=response.get("elapsed_ms", 0.0),
        note=case.get("note", ""),
    )


def run_one(client: httpx.Client, base_url: str, case: dict) -> EvalResult:
    """运行单条用例"""
    resp = call_stream_chat(client, base_url, case["question"])
    return evaluate_case(case, resp)


# ===========================================================================
# 报告
# ===========================================================================
def print_summary(results: list[EvalResult]) -> None:
    """打印分类汇总"""
    print("\n" + "=" * 80)
    print(" 评测汇总")
    print("=" * 80)

    # 按 category 分组
    by_cat: dict[str, list[EvalResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    for cat in sorted(by_cat.keys()):
        rs = by_cat[cat]
        total = len(rs)
        mode_match = sum(1 for r in rs if r.actual_mode == r.expected_mode)
        qid_match = sum(1 for r in rs if _qid_match(r))
        sql_ok = sum(1 for r in rs if r.sql_generated and not r.error)
        has_data = sum(1 for r in rs if r.table_row_count > 0)
        errored = sum(1 for r in rs if r.error)
        avg_ms = sum(r.elapsed_ms for r in rs) / total if total else 0

        print(f"\n[{cat}] 共 {total} 条")
        print(f"  模式命中: {mode_match}/{total} ({mode_match/total*100:.0f}%)")
        if cat.startswith("A") or cat.startswith("B") or cat.startswith("C") or cat.startswith("D"):
            print(f"  Q-ID 匹配: {qid_match}/{total} ({qid_match/total*100:.0f}%)")
        print(f"  SQL 生成成功: {sql_ok}/{total}")
        print(f"  有数据返回: {has_data}/{total}")
        print(f"  错误: {errored}/{total}")
        print(f"  平均耗时: {avg_ms:.0f}ms")


def _qid_match(r: EvalResult) -> bool:
    """评估 Q-ID 匹配: 考虑 .x 通配"""
    exp = r.expected_qid
    act = r.actual_qid
    if exp is None:
        return act is None
    if exp.endswith(".x"):
        prefix = exp.rstrip(".x")
        return act is not None and act.startswith(prefix + ".")
    return act == exp


def print_failures(results: list[EvalResult], limit: int = 20) -> None:
    """打印失败用例详情"""
    print("\n" + "=" * 80)
    print(f" 失败用例详情 (最多 {limit} 条)")
    print("=" * 80)

    failures = [
        r for r in results
        if r.actual_mode != r.expected_mode
        or (not _qid_match(r) and r.expected_qid is not None)
        or r.error
    ]

    if not failures:
        print("\n[OK] 全部通过!")
        return

    for r in failures[:limit]:
        print(f"\n[FAIL] [{r.category}] {r.question[:60]}")
        print(f"  预期: mode={r.expected_mode}, qid={r.expected_qid}")
        print(f"  实际: mode={r.actual_mode}, qid={r.actual_qid}, conf={r.actual_confidence:.0%}")
        if r.error:
            print(f"  错误: {r.error[:100]}")
        elif r.expected_mode == "db" and not r.sql_generated:
            print(f"  SQL: <未生成>")
        if r.note:
            print(f"  备注: {r.note}")


def save_csv(results: list[EvalResult], path: str) -> None:
    """保存为 CSV 报告"""
    fieldnames = list(asdict(results[0]).keys()) if results else []
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    print(f"\n[CSV] 报告已保存: {path} ({len(results)} 条)")


# ===========================================================================
# Markdown 报告
# ===========================================================================
def _qid_in_expected(actual: Optional[str], expected: Optional[str]) -> bool:
    """Q-ID 命中判定 (支持 .x 通配)"""
    if expected is None:
        return actual is None
    if expected.endswith(".x"):
        prefix = expected.rstrip(".x")
        return actual is not None and actual.startswith(prefix + ".")
    return actual == expected


def _category_label(category: str) -> str:
    """A_原题 -> A 类 (清单原题, 应命中 Q-ID)"""
    mapping = {
        "A_原题": "清单原题",
        "B_改写": "改写问题",
        "C_扩写": "扩写问题",
        "D_边界": "边界问题",
        "E_兜底": "非业务兜底",
    }
    return mapping.get(category, category)


def _verdict_symbol(r: EvalResult) -> str:
    """生成 markdown 用的判定符号"""
    mode_ok = r.actual_mode == r.expected_mode
    qid_ok = _qid_in_expected(r.actual_qid, r.expected_qid)
    if r.error and r.expected_mode == "db":
        return "❌ 错误"
    if mode_ok and qid_ok:
        return "✅ 通过"
    if mode_ok and not qid_ok:
        return "⚠️ 模式对,Q-ID 错"
    return "❌ 模式错"


def save_markdown(results: list[EvalResult], path: str, csv_path: str = "") -> None:
    """生成 markdown 格式的测试记录文档

    结构:
        # 测试总览
        ## 1. 评测概览
        ## 2. 分类汇总
        ## 3. 用例详情
            ### 3.1 清单原题 (A 类)
                #### Q1.1 业务域 - 业务子域
                    ##### 3.1.1 测试用例 1
                    ##### 3.1.2 测试用例 2
            ...
        ## 4. 失败用例
        ## 5. 附录
    """
    # 按 category 分组
    by_cat: dict[str, list[EvalResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    # 全局统计
    total = len(results)
    mode_correct = sum(1 for r in results if r.actual_mode == r.expected_mode)
    qid_correct = sum(1 for r in results if _qid_in_expected(r.actual_qid, r.expected_qid))
    errored = sum(1 for r in results if r.error)
    avg_ms = sum(r.elapsed_ms for r in results) / total if total else 0
    max_ms = max((r.elapsed_ms for r in results), default=0)
    min_ms = min((r.elapsed_ms for r in results), default=0)

    lines: list[str] = []
    lines.append("# stream-chat 接口功能测试报告\n")
    lines.append(f"> **测试时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"> **测试范围**: `/api/chat-stream` 端到端功能  ")
    lines.append(f"> **服务地址**: `http://localhost:8000`  ")
    lines.append(f"> **测试类型**: 单元 + 集成 + 兜底 (5 大类, {total} 条用例)  ")
    lines.append(f"> **报告生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")

    # 1. 总览
    lines.append("## 1. 评测概览\n")
    lines.append("| 指标 | 值 |")
    lines.append("|------|------|")
    lines.append(f"| **总用例数** | {total} |")
    lines.append(f"| **模式命中** (db/llm 与预期一致) | **{mode_correct}** / {total} ({mode_correct/total*100:.1f}%) |")
    lines.append(f"| **Q-ID 命中** (含 .x 通配) | **{qid_correct}** / {total} ({qid_correct/total*100:.1f}%) |")
    lines.append(f"| **错误数** | {errored} / {total} |")
    lines.append(f"| **平均耗时** | {avg_ms:.0f} ms |")
    lines.append(f"| **最快** | {min_ms:.0f} ms |")
    lines.append(f"| **最慢** | {max_ms:.0f} ms |")
    lines.append("")

    # 2. 分类汇总
    lines.append("## 2. 分类汇总\n")
    lines.append("| 类别 | 用例数 | 模式命中 | Q-ID 命中 | 平均耗时 | 错误数 |")
    lines.append("|------|--------|----------|-----------|----------|--------|")
    for cat in sorted(by_cat.keys()):
        rs = by_cat[cat]
        n = len(rs)
        mc = sum(1 for r in rs if r.actual_mode == r.expected_mode)
        qc = sum(1 for r in rs if _qid_in_expected(r.actual_qid, r.expected_qid))
        am = sum(r.elapsed_ms for r in rs) / n
        ec = sum(1 for r in rs if r.error)
        lines.append(f"| **{_category_label(cat)}** ({cat}) | {n} | {mc}/{n} | {qc}/{n} | {am:.0f} ms | {ec}/{n} |")
    lines.append("")

    # 3. 用例详情 (按 category)
    lines.append("## 3. 用例详情\n")
    cat_order = ["A_原题", "B_改写", "C_扩写", "D_边界", "E_兜底"]
    case_idx = 0
    for cat in cat_order:
        if cat not in by_cat:
            continue
        rs = by_cat[cat]
        lines.append(f"### 3.{cat_order.index(cat)+1} {_category_label(cat)} ({cat}) — {len(rs)} 条\n")
        for r in rs:
            case_idx += 1
            verdict = _verdict_symbol(r)
            lines.append(f"#### 用例 {case_idx} — {verdict}\n")
            lines.append(f"- **提问**: {r.question}")
            if r.note:
                lines.append(f"- **备注**: {r.note}")
            lines.append(f"- **预期模式**: `{r.expected_mode}` | **预期 Q-ID**: `{r.expected_qid or 'null'}`")
            lines.append(f"- **实际模式**: `{r.actual_mode or '空'}` | **实际 Q-ID**: `{r.actual_qid or 'null'}` | **置信度**: {r.actual_confidence:.0%}")
            lines.append(f"- **耗时**: {r.elapsed_ms:.0f} ms")
            if r.error:
                lines.append(f"- **错误**: `{r.error[:200]}`")
            if r.sql_generated:
                lines.append("- **生成 SQL** (前 200 字符):")
                lines.append("  ```sql")
                lines.append(f"  {r.sql_generated}")
                lines.append("  ```")
            if r.table_row_count > 0:
                lines.append(f"- **表格行数**: {r.table_row_count}")
            if r.chart_generated:
                lines.append(f"- **图表**: ✅")
            if r.summary:
                lines.append(f"- **回复摘要**: {r.summary}")
            lines.append("")

    # 4. 失败用例汇总
    lines.append("## 4. 失败 / 异常用例\n")
    failed = [
        r for r in results
        if r.actual_mode != r.expected_mode
        or not _qid_in_expected(r.actual_qid, r.expected_qid)
        or r.error
    ]
    if not failed:
        lines.append("🎉 全部通过!\n")
    else:
        lines.append(f"共 **{len(failed)}** 条失败/异常, 详情如下:\n")
        for i, r in enumerate(failed, 1):
            lines.append(f"**{i}. [{_category_label(r.category)}]** {r.question}")
            lines.append(f"   - 预期: mode=`{r.expected_mode}` qid=`{r.expected_qid}`")
            lines.append(f"   - 实际: mode=`{r.actual_mode}` qid=`{r.actual_qid}` conf={r.actual_confidence:.0%}")
            if r.error:
                lines.append(f"   - 错误: `{r.error[:150]}`")
            lines.append("")

    # 5. 附录
    lines.append("## 5. 附录\n")
    lines.append("### 5.1 测试用例分类说明\n")
    lines.append("- **A_原题**: 从 `config/FWBZ问题清单.md` 解析出的 80 条标准问题")
    lines.append("- **B_改写**: 标准问题的同义改写 / 口语化变种 (~30 条)")
    lines.append("- **C_扩写**: 在原题基础上加时间/限定词的扩展 (~10 条)")
    lines.append("- **D_边界**: 业务相关但可能不在清单的边界问题 (~10 条)")
    lines.append("- **E_兜底**: 与问题清单无关的闲聊/非业务问题 (~10 条)")
    lines.append("")
    lines.append("### 5.2 评估规则\n")
    lines.append("- **模式命中**: 实际 mode (db/llm) 与预期一致")
    lines.append("- **Q-ID 命中**: 实际 Q-ID 与预期完全一致, 或预期是 `5.x` 这种通配, 实际命中该域内任一子项")
    lines.append("- **错误**: 接口返回错误 (timeout / ConnectError / SSE error 事件等)")
    lines.append("")
    if csv_path:
        lines.append("### 5.3 完整数据\n")
        lines.append(f"CSV 报告: `{csv_path}` (含每条用例的完整 SQL / 摘要 / 耗时)")
    lines.append("")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[Markdown] 报告已保存: {path} ({len(results)} 条, {len(content)} 字符)")


# ===========================================================================
# 主流程
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(description="stream-chat 端到端评测")
    parser.add_argument("--url", default="http://localhost:8000", help="服务 base URL")
    parser.add_argument("--concurrency", type=int, default=1, help="并发数")
    parser.add_argument("--filter", nargs="+", default=["A", "B", "C", "D", "E"],
                        help="跑哪几类 (A/B/C/D/E)")
    parser.add_argument("--limit", type=int, default=0, help="每类最多跑几条 (0=全部)")
    parser.add_argument("--output", default="", help="CSV 报告输出路径 (实时 flush)")
    parser.add_argument("--output-md", default="", help="Markdown 测试记录文档路径")
    parser.add_argument("--batch", type=int, default=0, help="当前批次号 (1-based, 0=不分批)")
    parser.add_argument("--batch-total", type=int, default=1, help="总批数")
    args = parser.parse_args()

    # 1. 构造用例
    print("\n[1] 构造测试用例...")
    all_cases: list[dict] = []
    if "A" in args.filter:
        all_cases.extend(build_a_cases())
    if "B" in args.filter:
        all_cases.extend(B_CASES)
    if "C" in args.filter:
        all_cases.extend(C_CASES)
    if "D" in args.filter:
        all_cases.extend(D_CASES)
    if "E" in args.filter:
        all_cases.extend(E_CASES)

    if args.limit > 0:
        # 按类限制
        by_cat: dict[str, list[dict]] = {}
        for c in all_cases:
            by_cat.setdefault(c["category"][0], []).append(c)
        all_cases = []
        for cat_letter, cs in by_cat.items():
            all_cases.extend(cs[:args.limit])

    # 分批: 把 all_cases 切成 N 份, 只跑第 args.batch 份
    if args.batch > 0 and args.batch_total > 1:
        per_batch = (len(all_cases) + args.batch_total - 1) // args.batch_total
        start = (args.batch - 1) * per_batch
        end = min(start + per_batch, len(all_cases))
        all_cases = all_cases[start:end]
        print(f"  [分批] 第 {args.batch}/{args.batch_total} 批, 跑 {start+1}-{end} 条 (共 {len(all_cases)} 条)")

    print(f"  共 {len(all_cases)} 条用例")

    # 2. 跑测试
    print(f"\n[2] 跑测试 (并发={args.concurrency}, url={args.url})")
    results: list[EvalResult] = []
    csv_file = None
    csv_writer = None
    if args.output:
        # 实时写 CSV (每跑完一条立即 flush, 避免被 kill 后丢数据)
        import csv as _csv
        csv_file = open(args.output, "w", encoding="utf-8-sig", newline="")
        csv_writer = _csv.DictWriter(csv_file, fieldnames=list(asdict(EvalResult(
            category="", question="", expected_mode="", expected_qid=None,
        )).keys()))
        csv_writer.writeheader()
        csv_file.flush()

    def save_one(r: EvalResult) -> None:
        if csv_writer:
            csv_writer.writerow(asdict(r))
            csv_file.flush()

    with httpx.Client() as client:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {
                ex.submit(run_one, client, args.url, c): c
                for c in all_cases
            }
            done_count = 0
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                save_one(r)  # 立即写盘
                done_count += 1
                # 进度条
                if done_count % 5 == 0 or done_count == len(all_cases):
                    pct = done_count / len(all_cases) * 100
                    print(f"  进度: {done_count}/{len(all_cases)} ({pct:.0f}%)")

    if csv_file:
        csv_file.close()

    # 3. 汇总
    print_summary(results)
    print_failures(results, limit=30)

    # 4. 保存 CSV
    if args.output:
        save_csv(results, args.output)

    # 5. 保存 Markdown 报告
    if args.output_md:
        csv_ref = args.output if args.output else ""
        save_markdown(results, args.output_md, csv_path=csv_ref)


if __name__ == "__main__":
    main()
