#!/usr/bin/env python3
"""在达梦 10.168.56.103 创建并填充 NL-SQL 元数据表。

数据来源: config/FWBZ_strut.sql（表/列/类型/中文注释）
本机: python3.10 scripts/seed_meta_nl.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("COPYFILE_DISABLE", "1")

from app.core.dameng import close_dameng, execute_query, get_dameng_connection
from app.core.logger import get_logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_hephaestus_tables import CREATE_SQLS, INDEX_SQLS, TABLE_NAMES

logger = get_logger("seed_meta_nl")

STRUT = ROOT / "config" / "FWBZ_strut.sql"

TOPIC_RULES = [
    (("metering", "energy", "carbon", "coal", "price", "standard_coal"), "能耗"),
    (("alarm", "fault"), "告警"),
    (("device", "equipment", "gather"), "设备"),
    (("lighting",), "照明"),
    (("camera",), "视频"),
    (("door", "acs"), "门禁"),
    (("parking",), "停车"),
    (("flow", "exhibitor"), "客流"),
    (("fire",), "消防"),
    (("complaint",), "投诉"),
    (("activemeet", "active_meet"), "活动"),
    (("cold",), "冷源"),
    (("space", "building", "project"), "空间"),
    (("linkage", "patterning"), "联动"),
    (("ai_report", "sys_log", "log_"), "日志"),
]


def lit(value) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("'", "''")
    return "'" + text + "'"


def run(sql: str, *, commit: bool = True) -> None:
    conn = get_dameng_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        if commit and hasattr(conn, "commit"):
            conn.commit()
    finally:
        cur.close()


def commit() -> None:
    conn = get_dameng_connection()
    if hasattr(conn, "commit"):
        conn.commit()


def table_exists(name: str) -> bool:
    rows = execute_query(
        'SELECT COUNT(*) AS n FROM ALL_TABLES '
        "WHERE OWNER='FWBZ' AND TABLE_NAME=%s" % lit(name)
    )
    if not rows:
        rows = execute_query(
            "SELECT COUNT(*) AS n FROM USER_TABLES WHERE TABLE_NAME=%s" % lit(name)
        )
    if not rows:
        try:
            execute_query('SELECT 1 FROM "FWBZ"."%s" WHERE 1=0' % name)
            return True
        except Exception:
            return False
    n = list(rows[0].values())[0]
    return int(n or 0) > 0


def infer_topic(table: str) -> str | None:
    low = table.lower()
    for keys, topic in TOPIC_RULES:
        if any(k in low for k in keys):
            return topic
    return "综合"


def infer_grain(table: str) -> str | None:
    low = table.lower()
    for key, grain in (
        ("_data_year", "year"),
        ("_data_month", "month"),
        ("_data_day", "day"),
        ("_data_hour", "hour"),
        ("_data_minute", "minute"),
        ("_data_real", "real"),
        ("data_year", "year"),
        ("data_month", "month"),
        ("data_day", "day"),
        ("data_hour", "hour"),
        ("data_minute", "minute"),
        ("data_real", "real"),
        ("_year", "year"),
        ("_month", "month"),
        ("_day", "day"),
        ("_hour", "hour"),
    ):
        if key in low:
            return grain
    return None


def infer_role(col: str, is_pk: bool, is_fk: bool) -> str:
    if is_pk:
        return "pk"
    if is_fk:
        return "fk"
    low = col.lower()
    if low in {"time", "data_date", "start_date", "end_date", "executed_time"} or low.endswith("_time") or low.endswith("_date"):
        return "time"
    if low in {"value", "cost", "count", "amount", "energy", "power"} or "count" in low:
        return "metric"
    if low in {"status", "type", "level", "success_flag"}:
        return "status"
    if low in {"name", "title", "node_name"} or low.endswith("_name"):
        return "name"
    if low.endswith("_id") or low == "id":
        return "id"
    return "other"


def name_en_from(ident: str) -> str:
    return " ".join(p.capitalize() for p in ident.split("_") if p)


def parse_strut(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8")
    tables: dict[str, dict] = {}
    create_re = re.compile(
        r'CREATE TABLE "FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
        re.IGNORECASE | re.DOTALL,
    )
    col_re = re.compile(r'^\s*"(\w+)"\s+(.+?)\s*,?\s*$')
    tab_cmt = re.compile(r'COMMENT ON TABLE "FWBZ"\."(\w+)" IS \'((?:\\\'|[^\'])*)\';')
    col_cmt = re.compile(
        r'COMMENT ON COLUMN "FWBZ"\."(\w+)"\."(\w+)" IS \'((?:\\\'|[^\'])*)\';'
    )

    for m in create_re.finditer(text):
        tname = m.group(1)
        block = m.group(2)
        cols = []
        for line in block.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped or stripped.upper().startswith(
                ("PRIMARY", "UNIQUE", "CHECK", "CONSTRAINT", "INDEX", "FOREIGN")
            ):
                continue
            cm = col_re.match(stripped + ",")
            if not cm:
                cm = re.match(r'^\s*"(\w+)"\s+(.+)$', stripped)
            if not cm:
                continue
            col_name, rest = cm.group(1), cm.group(2).rstrip(",")
            not_null = "NOT NULL" in rest.upper()
            data_type = re.sub(r"\s+NOT\s+NULL", "", rest, flags=re.I).strip()
            cols.append(
                {"name": col_name, "data_type": data_type, "not_null": not_null}
            )
        tables[tname] = {
            "name": tname,
            "comment": "",
            "cols": cols,
            "col_comments": {},
        }

    for m in tab_cmt.finditer(text):
        if m.group(1) in tables:
            tables[m.group(1)]["comment"] = m.group(2)
    for m in col_cmt.finditer(text):
        tname, cname, cmt = m.group(1), m.group(2), m.group(3)
        if tname in tables:
            tables[tname]["col_comments"][cname] = cmt
    return tables


def resolve_fk_table(col: str, table_names: set[str]) -> str | None:
    if not col.lower().endswith("_id") or col.lower() == "id":
        return None
    base = col[: -3]
    candidates = []
    if base in table_names:
        candidates.append(base)
    alt = "table_" + base
    if alt in table_names:
        candidates.append(alt)
    # space_id -> space, venue_id -> table_venue_flow? skip fuzzy
    if len(candidates) == 1:
        return candidates[0]
    return None


SKIP_SYNONYM = {
    "主键", "自增主键", "创建人", "创建日期", "更新人", "更新日期",
    "所属部门", "排序", "排序字段",
}


def useful_phrase(text: str, physical: str) -> bool:
    phrase = (text or "").strip()
    if len(phrase) < 2:
        return False
    if phrase == physical or phrase == name_en_from(physical):
        return False
    if phrase in SKIP_SYNONYM:
        return False
    return any("\u4e00" <= ch <= "\u9fff" for ch in phrase)


def drop_legacy_tables() -> None:
    for name in ("meta_nl_synonym", "meta_nl_relation", "meta_nl_column", "meta_nl_table"):
        try:
            run('DROP TABLE "FWBZ"."%s"' % name)
            logger.info("已删除旧表 %s", name)
        except Exception:
            pass


def ensure_tables() -> None:
    drop_legacy_tables()
    for name in TABLE_NAMES:
        if table_exists(name):
            logger.info("表已存在: %s", name)
            continue
        logger.info("创建表: %s", name)
        ddl = [s for s in CREATE_SQLS if f'"{name}"' in s][0]
        run(ddl)
    for sql in INDEX_SQLS:
        try:
            run(sql)
        except Exception as exc:
            logger.info("索引跳过: %s", exc)


def truncate_meta() -> None:
    for name in ("hephaestus_meta_nl_synonym", "hephaestus_meta_nl_relation", "hephaestus_meta_nl_column", "hephaestus_meta_nl_table"):
        try:
            run('DELETE FROM "FWBZ"."%s"' % name)
            logger.info("已清空 %s", name)
        except Exception as exc:
            logger.warning("清空 %s 失败: %s", name, exc)


def seed() -> None:
    tables = parse_strut(STRUT)
    names = set(tables.keys())
    logger.info("解析到 %d 张业务表", len(tables))

    table_ids: dict[str, int] = {}
    tid = 0
    for tname, info in tables.items():
        tid += 1
        table_ids[tname] = tid
        low = tname.lower()
        enabled = "0" if any(x in low for x in ("temp", "251126", "_bak")) else "1"
        pks = ",".join(c["name"] for c in info["cols"] if c["name"].lower() == "id")
        cn = info["comment"] or name_en_from(tname)
        sql = (
            'INSERT INTO "FWBZ"."hephaestus_meta_nl_table" '
            '("id","schema_name","table_name","name_en","name_cn","aliases","topic",'
            '"description","pk_columns","time_grain","nl_enabled","priority") VALUES ('
            f"{tid},'FWBZ',{lit(tname)},{lit(name_en_from(tname))},{lit(cn)},NULL,"
            f"{lit(infer_topic(tname))},{lit(info['comment'] or None)},"
            f"{lit(pks or None)},{lit(infer_grain(tname))},{lit(enabled)},100)"
        )
        run(sql, commit=False)
    commit()
    logger.info("已写入 hephaestus_meta_nl_table %d 行", tid)

    cid = 0
    column_ids: dict[tuple[str, str], int] = {}
    for tname, info in tables.items():
        table_id = table_ids[tname]
        for col in info["cols"]:
            cid += 1
            cname = col["name"]
            column_ids[(tname, cname)] = cid
            is_pk = "1" if cname.lower() == "id" else "0"
            fk_to = resolve_fk_table(cname, names)
            is_fk = "1" if fk_to else "0"
            role = infer_role(cname, is_pk == "1", is_fk == "1")
            cn = info["col_comments"].get(cname) or name_en_from(cname)
            unit = "kWh" if cname.lower() == "value" and "metering" in tname.lower() else None
            if cname.lower() == "cost":
                unit = "元"
            sql = (
                'INSERT INTO "FWBZ"."hephaestus_meta_nl_column" '
                '("id","table_id","column_name","name_en","name_cn","aliases","data_type",'
                '"is_pk","is_fk","role","unit","enum_values","nl_enabled") VALUES ('
                f"{cid},{table_id},{lit(cname)},{lit(name_en_from(cname))},{lit(cn)},NULL,"
                f"{lit(col['data_type'])},{lit(is_pk)},{lit(is_fk)},{lit(role)},"
                f"{lit(unit)},NULL,'1')"
            )
            run(sql, commit=False)
    commit()
    logger.info("已写入 hephaestus_meta_nl_column %d 行", cid)

    rid = 0
    seen = set()
    for tname, info in tables.items():
        for col in info["cols"]:
            to_table = resolve_fk_table(col["name"], names)
            if not to_table or to_table == tname:
                continue
            to_cols = {c["name"] for c in tables[to_table]["cols"]}
            if "id" not in to_cols:
                continue
            key = (tname, col["name"], to_table, "id")
            if key in seen:
                continue
            seen.add(key)
            rid += 1
            desc = "%s.%s = %s.id" % (tname, col["name"], to_table)
            sql = (
                'INSERT INTO "FWBZ"."hephaestus_meta_nl_relation" '
                '("id","from_table_id","from_column","to_table_id","to_column",'
                '"join_type","description","nl_enabled") VALUES ('
                f"{rid},{table_ids[tname]},{lit(col['name'])},{table_ids[to_table]},"
                f"'id','LEFT',{lit(desc)},'1')"
            )
            run(sql, commit=False)
    commit()
    logger.info("已写入 hephaestus_meta_nl_relation %d 行", rid)

    sid = 0
    seen_syn: set[tuple[str, str, int]] = set()
    for tname, info in tables.items():
        phrase = (info["comment"] or "").strip()[:255]
        if useful_phrase(phrase, tname):
            key = (phrase, "table", table_ids[tname])
            if key not in seen_syn:
                seen_syn.add(key)
                sid += 1
                run(
                    'INSERT INTO "FWBZ"."hephaestus_meta_nl_synonym" '
                    '("id","phrase","target_type","target_id","weight") VALUES ('
                    f"{sid},{lit(phrase)},'table',{table_ids[tname]},2)",
                    commit=False,
                )
        for col in info["cols"]:
            phrase = (info["col_comments"].get(col["name"]) or "").strip()[:255]
            if not useful_phrase(phrase, col["name"]):
                continue
            col_id = column_ids[(tname, col["name"])]
            key = (phrase, "column", col_id)
            if key in seen_syn:
                continue
            seen_syn.add(key)
            sid += 1
            run(
                'INSERT INTO "FWBZ"."hephaestus_meta_nl_synonym" '
                '("id","phrase","target_type","target_id","weight") VALUES ('
                f"{sid},{lit(phrase)},'column',{col_id},1)",
                commit=False,
            )
    commit()
    logger.info("已写入 hephaestus_meta_nl_synonym %d 行", sid)


def main() -> None:
    if not STRUT.exists():
        raise SystemExit("找不到 %s" % STRUT)
    print("连接达梦并建表/灌数 ...")
    ensure_tables()
    truncate_meta()
    seed()
    n1 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_table"')
    n2 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_column"')
    n3 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_relation"')
    n4 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_synonym"')
    n5 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_chat_access_logs"')
    n6 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_rag_chunks"')
    print("完成: table=%s column=%s relation=%s synonym=%s logs=%s chunks=%s" % (
        list(n1[0].values())[0] if n1 else "?",
        list(n2[0].values())[0] if n2 else "?",
        list(n3[0].values())[0] if n3 else "?",
        list(n4[0].values())[0] if n4 else "?",
        list(n5[0].values())[0] if n5 else "?",
        list(n6[0].values())[0] if n6 else "?",
    ))
    close_dameng()


if __name__ == "__main__":
    main()
