"""
FWBZ 问题清单评测脚本
======================

用现有 chat_service 对问题清单中的题目做端到端测试, 评估:
    1. 能否被识别为 DB 相关(关键词路由)
    2. 能否生成 SQL
    3. SQL 是否合法(通过安全门)
    4. 能否在达梦上执行成功
    5. 返回数据是否合理(非空/字段对得上)

用法:
    python tests/eval_question_list.py
    python tests/eval_question_list.py --limit 20   # 只跑前 20 题
    python tests/eval_question_list.py --skip-db    # 不真跑 DB, 只测到 SQL 生成
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# 路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 关闭 chat_service 启动时疯狂的日志
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
# 强制所有 chat / dameng 相关 logger 调高
for name in ("chat", "dameng", "sql_schema_parser", "rag", "eval"):
    logging.getLogger(name).setLevel(logging.WARNING)
log = logging.getLogger("eval")
log.setLevel(logging.INFO)

from app.core.dameng import execute_query
from app.services.chat_service import ChatService
from app.services.sql_guard import validate

# 跑通库内的 16 张核心表名(用于 SQL 合法性的轻校验)
KNOWN_TABLES = {
    "ai_report_history", "alarm_category", "alarm_level", "alarm_record",
    "alarm_rule_point", "alarm_rules",
    "building_control_point", "building_control_point_history",
    "camera_info", "carbon_emission_factor", "data_amend_log",
    "data_day", "data_hour", "data_minute", "data_month", "data_real", "data_year",
    "device", "device_attribute", "device_attribute_config",
    "device_attribute_data", "device_attribute_history",
    "device_model", "device_model_attribute", "device_static_data",
    "device_static_data_config",
    "energy_analysis_benchmark", "energy_analysis_chart", "energy_analysis_config",
    "energy_attribute_management", "energy_flow_diagram_config",
    "energy_medium_manage", "energy_price", "energy_pricing_config",
    "equipment_category", "gather_rule_config",
    "lighting_area", "lighting_circuit", "lighting_operation_log",
    "lighting_plan", "lighting_plan_execution_time",
    "linkage_front_point", "linkage_rear_point", "linkage_strategy",
    "log_point_execute_record", "log_strategy_execute_record",
    "metering_point", "metering_point_cost_data_day",
    "metering_point_cost_data_hour", "metering_point_cost_data_month",
    "metering_point_cost_data_year",
    "metering_point_data_day", "metering_point_data_hour",
    "metering_point_data_month", "metering_point_data_year",
    "metering_point_rel",
    "patterning_execution_time", "patterning_point",
    "patterning_related", "patterning_strategy",
    "project", "role_data_permission", "space",
    "standard_coal_coefficient", "sys_log",
    "table_acs_device",
    "table_activeMeet_info", "table_activeMeet_preparation_info",
    "table_activeMeet_preparation_type", "table_activeMeet_report",
    "table_activeMeets_device_type",
    "table_camera_group", "table_camera_info", "table_camera_resource",
    "table_cold_source_history",
    "table_complaint_info", "table_complaint_record",
    "table_complaint_status", "table_complaint_type",
    "table_door_event", "table_door_resource",
    "table_event_notify", "table_event_type",
    "table_fire_alarm_record",
    "table_http_system", "table_interface_history", "table_interface_info",
    "table_mqtt_history", "table_page_info",
    "table_parking_count", "table_parking_record",
    "table_patrol_plan", "table_patrolHistory", "table_patrol_history",
    "table_person_recognition", "table_personnel_statistics",
    "table_plan_camera", "table_protocol_type_info",
    "table_region_resource",
    "table_smoke_detector", "table_smoke_detector_type",
    "table_tagid_info",
    "table_venue_flow_hour", "table_venue_info",
    "table_visitor_flow",
    "unit_management",
}


# ---------------------------------------------------------------------------
# 读取问题清单
# ---------------------------------------------------------------------------
def load_questions(path: Path) -> list[tuple[str, str]]:
    """读 FWBZ问题清单.md, 返回 [(q_id, question), ...]"""
    text = path.read_text(encoding="utf-8")
    questions: list[tuple[str, str]] = []
    section = ""
    section_re = __import__("re").compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", __import__("re").MULTILINE)
    item_re = __import__("re").compile(r"^(\d+)\.\s+(.+?)\s*$", __import__("re").MULTILINE)
    for line in text.splitlines():
        m = section_re.match(line)
        if m:
            section = m.group(2).strip()
            continue
        m = item_re.match(line)
        if m and section and "问题" not in line and not line.startswith("---"):
            q = m.group(2).strip()
            if q and not q.startswith("**") and not q.startswith("A"):
                qid = f"{section[:4]}_{m.group(1)}"
                questions.append((qid, q))
    return questions


# ---------------------------------------------------------------------------
# 单题评测
# ---------------------------------------------------------------------------
def eval_one(svc: ChatService, question: str, skip_db: bool) -> dict:
    """对一道题做端到端评测, 返回详细报告"""
    t0 = time.time()
    out: dict = {
        "question": question,
        "is_db_related": None,
        "sql_generated": None,
        "guard_ok": None,
        "guard_reason": None,
        "exec_ok": None,
        "exec_error": None,
        "row_count": 0,
        "sample_row": None,
        "elapsed_ms": 0,
    }
    try:
        # 1. 路由判断
        out["is_db_related"] = svc._detect_db_related(question)
        if not out["is_db_related"]:
            out["exec_error"] = "未识别为 DB 相关(关键词未命中)"
            out["elapsed_ms"] = int((time.time() - t0) * 1000)
            return out

        # 2. 生成 SQL
        sql = svc._generate_sql(question)
        if not sql:
            out["exec_error"] = "LLM 未能生成 SQL"
            out["elapsed_ms"] = int((time.time() - t0) * 1000)
            return out
        out["sql_generated"] = sql

        # 3. 安全门
        g = validate(sql, allowed_tables=KNOWN_TABLES)
        out["guard_ok"] = g.ok
        out["guard_reason"] = g.reason
        if not g.ok:
            out["exec_error"] = f"安全门拒绝: {g.reason}"
            out["elapsed_ms"] = int((time.time() - t0) * 1000)
            return out

        # 4. 执行(可选)
        if not skip_db:
            try:
                rows, err = svc._execute_sql(g.sql)
                if err:
                    out["exec_ok"] = False
                    out["exec_error"] = err[:200]
                else:
                    out["exec_ok"] = True
                    out["row_count"] = len(rows) if rows else 0
                    if rows:
                        out["sample_row"] = dict(list(rows[0].items())[:5])
            except Exception as e:
                out["exec_ok"] = False
                out["exec_error"] = f"执行异常: {e}"
        else:
            out["exec_ok"] = "skipped"

    except Exception as e:
        out["exec_error"] = f"评测异常: {e}"
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="跑多少题(默认 20)")
    ap.add_argument("--skip-db", action="store_true", help="不真跑 DB")
    ap.add_argument("--out", default="tests/eval_report.json", help="报告输出路径")
    ap.add_argument("--questions", default="config/FWBZ问题清单.md")
    args = ap.parse_args()

    qpath = ROOT / args.questions
    if not qpath.exists():
        log.error(f"问题清单不存在: {qpath}")
        return 1

    all_q = load_questions(qpath)
    log.info(f"问题清单共 {len(all_q)} 题; 跑前 {args.limit} 题")
    sampled = all_q[:args.limit]

    svc = ChatService()
    log.info("ChatService 初始化完成, 开始评测...")

    results = []
    for i, (qid, q) in enumerate(sampled, 1):
        log.info(f"[{i}/{len(sampled)}] {qid}: {q[:50]}")
        r = eval_one(svc, q, args.skip_db)
        r["qid"] = qid
        results.append(r)
        # 打印简表
        status = "✓" if r["exec_ok"] is True else (
            "跳过" if r["exec_ok"] == "skipped" else "✗"
        )
        reason = r["exec_error"] or f"{r['row_count']} 行"
        log.info(f"    {status}  {reason[:80]}")

    # 汇总统计
    total = len(results)
    n_db = sum(1 for r in results if r["is_db_related"])
    n_sql = sum(1 for r in results if r["sql_generated"])
    n_guard = sum(1 for r in results if r["guard_ok"] is True)
    n_exec = sum(1 for r in results if r["exec_ok"] is True)
    n_skip = sum(1 for r in results if r["exec_ok"] == "skipped")

    log.info("=" * 60)
    log.info(f"DB 路由命中: {n_db}/{total}")
    log.info(f"生成 SQL:     {n_sql}/{total}")
    log.info(f"安全门通过:   {n_guard}/{total}")
    if args.skip_db:
        log.info(f"DB 执行:      跳过")
    else:
        log.info(f"DB 执行成功:  {n_exec}/{total}")
    log.info("=" * 60)

    # 写报告
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "total": total,
                "n_db": n_db,
                "n_sql": n_sql,
                "n_guard": n_guard,
                "n_exec": n_exec,
                "n_skip": n_skip,
                "skip_db": args.skip_db,
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    log.info(f"报告已写入: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
