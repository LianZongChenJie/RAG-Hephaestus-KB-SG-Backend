#!/usr/bin/env python3
"""从达梦 FWBZ 真实库结构灌 NL-SQL 元数据表。

这次要固化的是：关注哪些表/字段，以及它们之间真实的业务对应关系。
达梦几乎没有声明 FOREIGN KEY，那只是建表时没落约束，不等于没有关联。

来源：
- 物理列/注释/主键：ALL_TABLES 等数据字典（不读 FWBZ_strut.sql）
- 重点表、JOIN、枚举：问答手册里已订正的 SQL
- 其余业务外键：列名对应（space_id、category_id、index_code 等）写入
  hephaestus_meta_nl_relation

本机: python3.10 scripts/seed_meta_nl.py
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("COPYFILE_DISABLE", "1")

from app.common.dameng import close_dameng, execute_query, get_dameng_connection
from app.common.logger import get_logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from create_hephaestus_tables import CREATE_SQLS, INDEX_SQLS, TABLE_NAMES

logger = get_logger("seed_meta_nl")

SCHEMA = "FWBZ"
HANDBOOK = ROOT / "config" / "FWBZ保障平台问答手册.md"
SKIP_TABLE_PREFIXES = ("hephaestus_",)

# 手册章节号 → 保障平台菜单名
MENU_TOPICS = {
    "2": "智慧能源",
    "3": "韧性安全",
    "4": "照明控制",
    "5": "会展服务",
    "6": "场馆运营",
    "7": "设备管理",
    "8": "故障告警",
    "9": "物联网",
    "11": "AI运行报告",
}

# 清单尚未出题、但同菜单相关的表（次优先）
MENU_RELATED = (
    ("lighting_", "照明控制"),
    ("alarm_", "故障告警"),
    ("table_activemeet", "会展服务"),
    ("table_exhibitor", "会展服务"),
    ("table_camera", "韧性安全"),
    ("table_door", "韧性安全"),
    ("table_acs", "韧性安全"),
    ("gather_", "物联网"),
    ("table_interface", "物联网"),
    ("table_mqtt", "物联网"),
    ("table_http_system", "物联网"),
    ("ai_report", "AI运行报告"),
    ("cold_source", "智慧能源"),
    ("metering_", "智慧能源"),
    ("energy_", "智慧能源"),
    ("building_control", "智慧能源"),
    ("data_day", "智慧能源"),
    ("data_hour", "智慧能源"),
    ("data_month", "智慧能源"),
    ("data_year", "智慧能源"),
    ("data_real", "智慧能源"),
    ("data_minute", "智慧能源"),
    ("device_model", "设备管理"),
    ("equipment_category", "设备管理"),
)

# 不在保障平台菜单内
OFF_MENU_MARKERS = (
    "table_parking",
    "table_fire",
    "table_complaint",
    "table_patrol",
    "sys_",
    "qrtz_",
)

# 手册写明现网为空，禁止当 NL 事实表
EMPTY_FACT_TABLES = {
    "metering_point_data_day",
    "metering_point_data_hour",
    "metering_point_data_month",
    "metering_point_data_year",
}

# 手册 SQL 里写清的业务别名（表）
TABLE_ALIASES = {
    "device": "楼控设备,电表设备,暖通设备",
    "cold_source_device": "冷源设备",
    "data_day": "能耗计量数据,日能耗",
    "metering_point": "能源计量规则,计量点",
    "metering_point_rel": "计量点关联",
    "energy_analysis_config": "能源优化",
    "table_door_resource": "门禁,门禁点,安防设备",
    "table_acs_device": "门禁控制器,安防设备",
    "table_camera_resource": "摄像头,安防设备",
    "lighting_circuit": "照明回路,照明设备",
    "lighting_area": "照明区域",
    "table_venue_flow_hour": "场馆客流",
    "table_venue_info": "场馆",
    "table_activeMeet_info": "场馆排期,活动",
    "alarm_record": "报警,告警",
    "device_model": "设备模型",
    "equipment_category": "设备类别",
    "cold_source_equipment_category": "冷源类别",
    "space": "空间位置",
}

# 手册 CASE / device_type / 在线口径
COLUMN_OVERLAY: dict[tuple[str, str], dict] = {
    ("device", "device_type"): {
        "role": "dim",
        "enum_values": "1=电表设备,2=楼控设备",
        "aliases": "设备类型,楼控,电表",
    },
    ("device", "run_state"): {"role": "status", "aliases": "运行状态,在线情况"},
    ("device", "category_id"): {"role": "fk", "aliases": "设备类别"},
    ("device", "space_id"): {"role": "fk", "aliases": "空间位置"},
    ("data_day", "value"): {"role": "metric", "unit": "kWh", "aliases": "能耗,用电量"},
    ("data_day", "time"): {"role": "time"},
    ("data_day", "device_id"): {"role": "fk"},
    ("metering_point", "category_id"): {"role": "fk", "aliases": "设备类别"},
    ("metering_point", "space_id"): {"role": "fk", "aliases": "空间位置"},
    ("metering_point", "node_name"): {"role": "name", "aliases": "计量点,服贸会区域总耗电"},
    ("cold_source_device", "category_id"): {"role": "fk", "aliases": "冷源类别"},
    ("cold_source_device", "status"): {"role": "status"},
    ("table_camera_resource", "online"): {
        "role": "status",
        "enum_values": "1=在线,0=离线",
        "aliases": "在线情况",
    },
    ("table_camera_resource", "camera_type"): {
        "role": "dim",
        "enum_values": "0=枪机,1=半球,2=快球,3=带云台枪机",
        "aliases": "设备类型",
    },
    ("table_camera_resource", "region_name"): {"role": "dim", "aliases": "空间位置"},
    ("table_door_resource", "door_state"): {
        "role": "status",
        "enum_values": "3=离线,其他非空=在线",
        "aliases": "在线情况,门状态",
    },
    ("table_door_resource", "region_name"): {"role": "dim", "aliases": "空间位置"},
    ("table_door_resource", "parent_index_code"): {"role": "fk", "aliases": "门禁控制器"},
    ("table_acs_device", "online"): {
        "role": "status",
        "enum_values": "1=在线,0=离线",
        "aliases": "在线情况",
    },
    ("table_acs_device", "dev_type_desc"): {"role": "dim", "aliases": "设备类型"},
    ("table_acs_device", "region_name"): {"role": "dim", "aliases": "空间位置"},
    ("lighting_circuit", "status"): {"role": "status"},
    ("lighting_circuit", "all_duration"): {"role": "metric", "aliases": "照明能耗,时长"},
    ("lighting_circuit", "area_id"): {"role": "fk", "aliases": "照明区域"},
    ("lighting_area", "area_name"): {"role": "dim", "aliases": "空间位置,照明区域"},
    ("equipment_category", "category_name"): {"role": "dim", "aliases": "设备类别"},
    ("cold_source_equipment_category", "category_name"): {
        "role": "dim",
        "aliases": "冷源类别",
    },
    ("device_model", "category_id"): {"role": "fk"},
    ("alarm_record", "alarm_status"): {"role": "status"},
    ("alarm_record", "alarm_level_name"): {"role": "dim", "aliases": "告警等级"},
    ("alarm_record", "alarm_category_name"): {"role": "dim", "aliases": "告警类别"},
    ("alarm_record", "space_name"): {"role": "dim", "aliases": "空间位置"},
    ("table_venue_flow_hour", "today_in_count"): {"role": "metric"},
    ("table_venue_flow_hour", "today_now_count"): {"role": "metric"},
    ("table_venue_flow_hour", "max_count"): {"role": "metric"},
    ("table_venue_flow_hour", "venue_id"): {"role": "fk"},
    ("table_activeMeet_info", "venue_id"): {"role": "fk"},
    ("table_venue_info", "venue_name"): {"role": "dim", "aliases": "场馆"},
}

TOPIC_RULES = [
    (("metering", "energy", "carbon", "coal", "price", "standard_coal"), "智慧能源"),
    (("cold",), "智慧能源"),
    (("lighting",), "照明控制"),
    (("camera", "door", "acs"), "韧性安全"),
    (("alarm", "fault"), "故障告警"),
    (("activemeet", "active_meet", "exhibitor"), "会展服务"),
    (("venue_flow", "venue_info"), "场馆运营"),
    (("gather", "interface", "mqtt", "http_system"), "物联网"),
    (("ai_report",), "AI运行报告"),
    (("device_model", "equipment_category"), "设备管理"),
    (("device",), "设备管理"),
    (("space", "building", "project"), "空间"),
    (("linkage", "patterning"), "联动"),
]

_DIM_COLS = {
    "category_name",
    "region_name",
    "area_name",
    "space_name",
    "venue_name",
    "device_type",
    "camera_type",
    "dev_type_desc",
}
_STATUS_COLS = {
    "status",
    "online",
    "door_state",
    "run_state",
    "alarm_status",
    "type",
    "level",
    "success_flag",
    "comstat",
}
_METRIC_COLS = {
    "value",
    "cost",
    "count",
    "amount",
    "energy",
    "power",
    "cnt",
    "all_duration",
}

_SECTION_RE = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$", re.M)
_SQL_FENCE = re.compile(r"```sql\s*(.*?)\s*```", re.I | re.S)
_TABLE_ALIAS_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+"FWBZ"\."([^"]+)"(?:\s+(?:AS\s+)?([A-Za-z_][\w]*))?',
    re.I,
)
_JOIN_TYPE_RE = re.compile(
    r'\b((?:LEFT|INNER|RIGHT|FULL)(?:\s+OUTER)?\s+JOIN|JOIN)\s+"FWBZ"\."([^"]+)"',
    re.I,
)
_EQ_RE = re.compile(
    r'([A-Za-z_][\w]*)\."([^"]+)"\s*=\s*([A-Za-z_][\w]*)\."([^"]+)"',
)


@dataclass
class HandbookGold:
    tables: dict[str, set[str]] = field(default_factory=dict)  # lower -> topics
    aliases: dict[str, list[str]] = field(default_factory=dict)  # lower -> phrases
    joins: list[tuple[str, str, str, str, str]] = field(default_factory=list)
    # from_table, from_col, to_table, to_col, join_type  （原名大小写按手册）


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
        "SELECT COUNT(*) AS n FROM ALL_TABLES "
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


def _skip_table(name: str) -> bool:
    low = (name or "").lower()
    return any(low.startswith(p) for p in SKIP_TABLE_PREFIXES)


def name_en_from(ident: str) -> str:
    return " ".join(p.capitalize() for p in ident.split("_") if p)


def infer_topic(table: str) -> str:
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
    if low in _DIM_COLS:
        return "dim"
    if (
        low in {"time", "data_date", "start_date", "end_date", "executed_time"}
        or low.endswith("_time")
        or low.endswith("_date")
    ):
        return "time"
    if low in _METRIC_COLS or "count" in low:
        return "metric"
    if low in _STATUS_COLS or low.endswith("_status") or "state" in low:
        return "status"
    if low in {"name", "title", "node_name"} or low.endswith("_name"):
        return "name"
    if low.endswith("_id") or low == "id":
        return "id"
    return "other"


def _format_data_type(row: dict) -> str:
    dt = str(row.get("DATA_TYPE") or "").strip() or "UNKNOWN"
    upper = dt.upper()
    if upper in {"VARCHAR", "VARCHAR2", "CHAR", "CHARACTER"}:
        n = row.get("CHAR_LENGTH") or row.get("DATA_LENGTH")
        if n:
            return f"{dt}({int(n)})"
    if upper in {"NUMBER", "DECIMAL", "NUMERIC", "DEC"}:
        p, s = row.get("DATA_PRECISION"), row.get("DATA_SCALE")
        if p not in (None, ""):
            if s not in (None, "", 0):
                return f"{dt}({int(p)},{int(s)})"
            return f"{dt}({int(p)})"
    return dt


def _alias_map(sql: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for table, alias in _TABLE_ALIAS_RE.findall(sql):
        key = (alias or table).strip()
        if key:
            mapping[key] = table
            mapping[key.lower()] = table
    return mapping


def _join_types(sql: str) -> dict[str, str]:
    types: dict[str, str] = {}
    for raw, table in _JOIN_TYPE_RE.findall(sql):
        kind = raw.upper().replace(" OUTER", "").split()[0]
        if kind == "JOIN":
            kind = "INNER"
        types[table] = kind if kind in {"LEFT", "INNER", "RIGHT", "FULL"} else "LEFT"
    return types


def _normalize_join(
    t1: str, c1: str, t2: str, c2: str, join_types: dict[str, str]
) -> tuple[str, str, str, str, str]:
    """FK 侧 → PK 侧；JOIN 类型取被引入的表。"""
    c1l, c2l = c1.lower(), c2.lower()
    if c2l == "id" and c1l != "id":
        from_t, from_c, to_t, to_c = t1, c1, t2, c2
    elif c1l == "id" and c2l != "id":
        from_t, from_c, to_t, to_c = t2, c2, t1, c1
    elif c1l.endswith("_id") and not c2l.endswith("_id"):
        from_t, from_c, to_t, to_c = t1, c1, t2, c2
    elif c2l.endswith("_id") and not c1l.endswith("_id"):
        from_t, from_c, to_t, to_c = t2, c2, t1, c1
    else:
        from_t, from_c, to_t, to_c = t1, c1, t2, c2
    jtype = join_types.get(to_t) or join_types.get(from_t) or "LEFT"
    return from_t, from_c, to_t, to_c, jtype


def parse_handbook_sql_joins(sql: str) -> list[tuple[str, str, str, str, str]]:
    aliases = _alias_map(sql)
    join_types = _join_types(sql)
    out: list[tuple[str, str, str, str, str]] = []
    seen = set()
    for a1, c1, a2, c2 in _EQ_RE.findall(sql):
        t1 = aliases.get(a1) or aliases.get(a1.lower())
        t2 = aliases.get(a2) or aliases.get(a2.lower())
        if not t1 or not t2 or t1 == t2:
            continue
        item = _normalize_join(t1, c1, t2, c2, join_types)
        key = (item[0].lower(), item[1].lower(), item[2].lower(), item[3].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def parse_handbook_tables(sql: str) -> list[str]:
    seen = []
    found = set()
    for table, _alias in _TABLE_ALIAS_RE.findall(sql):
        if table not in found:
            found.add(table)
            seen.append(table)
    return seen


def load_handbook_gold(path: Path | None = None) -> HandbookGold:
    """解析保障平台问答手册 SQL：重点表、章节 topic、JOIN。"""
    gold = HandbookGold()
    text = (path or HANDBOOK).read_text(encoding="utf-8")
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        menu_no = m.group(1)
        topic = MENU_TOPICS.get(menu_no) or m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        for fence in _SQL_FENCE.findall(chunk):
            sql = fence.strip()
            for table in parse_handbook_tables(sql):
                gold.tables.setdefault(table.lower(), set()).add(topic)
            for join in parse_handbook_sql_joins(sql):
                key = (
                    join[0].lower(),
                    join[1].lower(),
                    join[2].lower(),
                    join[3].lower(),
                )
                if any(
                    (j[0].lower(), j[1].lower(), j[2].lower(), j[3].lower()) == key
                    for j in gold.joins
                ):
                    continue
                gold.joins.append(join)
    for tname, aliases in TABLE_ALIASES.items():
        gold.aliases[tname.lower()] = [p.strip() for p in aliases.split(",") if p.strip()]
    logger.info(
        "问答手册金标: %d 张重点表, %d 条 JOIN",
        len(gold.tables),
        len(gold.joins),
    )
    return gold


def _match_name(name: str, pool: Iterable[str]) -> str | None:
    low = name.lower()
    for item in pool:
        if item.lower() == low:
            return item
    return None


def _pick_topic(tname: str, topics: set[str]) -> str:
    """同表出现在多个菜单时，按表名归到更具体的业务域。"""
    if len(topics) == 1:
        return next(iter(topics))
    low = tname.lower()
    if "cold" in low and "智慧能源" in topics:
        return "智慧能源"
    if any(k in low for k in ("acs", "door", "camera")) and "韧性安全" in topics:
        return "韧性安全"
    if "lighting" in low and "照明控制" in topics:
        return "照明控制"
    if any(k in low for k in ("venue", "activemeet")) and "场馆运营" in topics:
        return "场馆运营"
    if "设备管理" in topics:
        return "设备管理"
    return sorted(topics)[0]


def classify_table(tname: str, gold: HandbookGold) -> tuple[str, str | None, int, str]:
    """topic, aliases, priority, nl_enabled。priority 越小越优先。"""
    low = tname.lower()
    aliases = ",".join(gold.aliases[low]) if gold.aliases.get(low) else None
    if any(low.startswith(p) or p in low for p in OFF_MENU_MARKERS):
        return infer_topic(tname), aliases, 900, "0"
    if low in EMPTY_FACT_TABLES or any(x in low for x in ("temp", "251126", "_bak")):
        return infer_topic(tname), aliases, 800, "0"
    if low in gold.tables:
        topics = gold.tables[low]
        topic = _pick_topic(tname, topics)
        extra = [t for t in topics if t != topic]
        if extra:
            alias_parts = [aliases] if aliases else []
            alias_parts.extend(extra)
            aliases = ",".join(p for p in alias_parts if p)
        return topic, aliases, 10, "1"

    for marker, topic in MENU_RELATED:
        if low.startswith(marker) or marker in low:
            return topic, aliases, 40, "1"

    return infer_topic(tname), aliases, 200, "1"


def column_overlay(tname: str, cname: str) -> dict:
    return COLUMN_OVERLAY.get((tname, cname)) or COLUMN_OVERLAY.get(
        (tname.lower(), cname.lower())
    ) or {}


def load_fwbz_schema() -> dict[str, dict]:
    """从达梦数据字典读取 FWBZ 业务表结构（表/列/注释/主键/外键）。"""
    owner = lit(SCHEMA)
    table_rows = execute_query(
        "SELECT TABLE_NAME FROM ALL_TABLES "
        f"WHERE OWNER={owner} ORDER BY TABLE_NAME"
    )
    col_rows = execute_query(
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, DATA_LENGTH, "
        "DATA_PRECISION, DATA_SCALE, NULLABLE, COLUMN_ID, CHAR_LENGTH "
        "FROM ALL_TAB_COLUMNS "
        f"WHERE OWNER={owner} ORDER BY TABLE_NAME, COLUMN_ID"
    )
    tab_cmt_rows = execute_query(
        "SELECT TABLE_NAME, COMMENTS FROM ALL_TAB_COMMENTS "
        f"WHERE OWNER={owner}"
    )
    col_cmt_rows = execute_query(
        "SELECT TABLE_NAME, COLUMN_NAME, COMMENTS FROM ALL_COL_COMMENTS "
        f"WHERE OWNER={owner}"
    )
    pk_rows = execute_query(
        "SELECT acc.TABLE_NAME, acc.COLUMN_NAME "
        "FROM ALL_CONSTRAINTS ac "
        "INNER JOIN ALL_CONS_COLUMNS acc "
        "  ON ac.OWNER = acc.OWNER AND ac.CONSTRAINT_NAME = acc.CONSTRAINT_NAME "
        f"WHERE ac.OWNER={owner} AND ac.CONSTRAINT_TYPE='P'"
    )
    fk_rows = execute_query(
        "SELECT acc.TABLE_NAME AS from_table, acc.COLUMN_NAME AS from_column, "
        "       r.TABLE_NAME AS to_table, r.COLUMN_NAME AS to_column "
        "FROM ALL_CONSTRAINTS ac "
        "INNER JOIN ALL_CONS_COLUMNS acc "
        "  ON ac.OWNER = acc.OWNER AND ac.CONSTRAINT_NAME = acc.CONSTRAINT_NAME "
        "INNER JOIN ALL_CONS_COLUMNS r "
        "  ON ac.R_OWNER = r.OWNER AND ac.R_CONSTRAINT_NAME = r.CONSTRAINT_NAME "
        f"WHERE ac.OWNER={owner} AND ac.CONSTRAINT_TYPE='R'"
    )

    tables: dict[str, dict] = {}
    for row in table_rows or []:
        tname = str(row.get("TABLE_NAME") or "").strip()
        if not tname or _skip_table(tname):
            continue
        tables[tname] = {
            "name": tname,
            "comment": "",
            "cols": [],
            "col_comments": {},
            "pk_columns": [],
            "fks": [],
        }

    tab_cmt = {
        str(r.get("TABLE_NAME") or ""): str(r.get("COMMENTS") or "").strip()
        for r in (tab_cmt_rows or [])
    }
    for tname, info in tables.items():
        info["comment"] = tab_cmt.get(tname) or ""

    for row in col_rows or []:
        tname = str(row.get("TABLE_NAME") or "").strip()
        cname = str(row.get("COLUMN_NAME") or "").strip()
        if tname not in tables or not cname:
            continue
        tables[tname]["cols"].append(
            {
                "name": cname,
                "data_type": _format_data_type(row),
                "not_null": str(row.get("NULLABLE") or "Y").upper() == "N",
            }
        )

    for row in col_cmt_rows or []:
        tname = str(row.get("TABLE_NAME") or "").strip()
        cname = str(row.get("COLUMN_NAME") or "").strip()
        if tname in tables and cname:
            comment = str(row.get("COMMENTS") or "").strip()
            if comment:
                tables[tname]["col_comments"][cname] = comment

    for row in pk_rows or []:
        tname = str(row.get("TABLE_NAME") or "").strip()
        cname = str(row.get("COLUMN_NAME") or "").strip()
        if tname in tables and cname and cname not in tables[tname]["pk_columns"]:
            tables[tname]["pk_columns"].append(cname)

    for row in fk_rows or []:
        ft = str(row.get("from_table") or "").strip()
        fc = str(row.get("from_column") or "").strip()
        tt = str(row.get("to_table") or "").strip()
        tc = str(row.get("to_column") or "").strip() or "id"
        if ft in tables and tt in tables and fc:
            tables[ft]["fks"].append((fc, tt, tc))

    logger.info(
        "从达梦读取 FWBZ 业务表 %d 张（已排除 Hephaestus 表）",
        len(tables),
    )
    return tables


# 列名 → 目标表.列。达梦无 FK 约束，按保障平台真实口径固化。
# category_id / parent_index_code 随所在表变化，见 resolve_business_fk。
COLUMN_FK_MAP = {
    "space_id": ("space", "id"),
    "model_id": ("device_model", "id"),
    "venue_id": ("table_venue_info", "id"),
    "device_id": ("device", "id"),
    "device_category_id": ("equipment_category", "id"),
    "metering_point_id": ("metering_point", "id"),
}


def resolve_fk_table(col: str, table_names: set[str]) -> str | None:
    """仅按列名 xxx_id ≈ 表名 猜测；对不上业务表（如 category_id）时不要用。"""
    if not col.lower().endswith("_id") or col.lower() == "id":
        return None
    base = col[:-3]
    candidates = []
    hit = _match_name(base, table_names)
    if hit:
        candidates.append(hit)
    hit = _match_name("table_" + base, table_names)
    if hit and hit not in candidates:
        candidates.append(hit)
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_business_fk(
    table: str, col: str, table_names: set[str]
) -> tuple[str, str] | None:
    """识别真实对应关系（与手册 JOIN 同口径）。返回 (to_table, to_col)。"""
    low_t = table.lower()
    low_c = col.lower()
    if low_c in {"id", "create_by", "update_by", "sys_org_code"}:
        return None
    if low_c == "category_id":
        target = (
            "cold_source_equipment_category"
            if "cold_source" in low_t
            else "equipment_category"
        )
        hit = _match_name(target, table_names)
        return (hit, "id") if hit else None
    if low_c == "area_id" and "lighting" in low_t:
        hit = _match_name("lighting_area", table_names)
        return (hit, "id") if hit else None
    if low_c == "config_id" and "energy_analysis" in low_t:
        hit = _match_name("energy_analysis_config", table_names)
        return (hit, "id") if hit else None
    if low_c == "parent_index_code" and "door" in low_t:
        hit = _match_name("table_acs_device", table_names)
        return (hit, "index_code") if hit else None
    mapped = COLUMN_FK_MAP.get(low_c)
    if mapped:
        hit = _match_name(mapped[0], table_names)
        if hit and hit.lower() != low_t:
            return hit, mapped[1]
        return None
    guessed = resolve_fk_table(col, table_names)
    if guessed and guessed.lower() != low_t:
        return guessed, "id"
    return None


SKIP_SYNONYM = {
    "主键",
    "自增主键",
    "创建人",
    "创建日期",
    "更新人",
    "更新日期",
    "所属部门",
    "排序",
    "排序字段",
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
    for name in (
        "hephaestus_meta_nl_synonym",
        "hephaestus_meta_nl_relation",
        "hephaestus_meta_nl_column",
        "hephaestus_meta_nl_table",
    ):
        try:
            run('DELETE FROM "FWBZ"."%s"' % name)
            logger.info("已清空 %s", name)
        except Exception as exc:
            logger.warning("清空 %s 失败: %s", name, exc)


def _col_names(info: dict) -> dict[str, str]:
    return {c["name"].lower(): c["name"] for c in info["cols"]}


def seed() -> None:
    gold = load_handbook_gold()
    tables = load_fwbz_schema()
    names = set(tables.keys())
    gold_fk = {
        (j[0].lower(), j[1].lower()) for j in gold.joins
    }
    logger.info("灌入 %d 张业务表（手册重点 %d）", len(tables), len(gold.tables))

    table_ids: dict[str, int] = {}
    tid = 0
    enabled_n = 0
    for tname, info in tables.items():
        tid += 1
        table_ids[tname] = tid
        topic, aliases, priority, enabled = classify_table(tname, gold)
        if enabled == "1":
            enabled_n += 1
        pks = ",".join(info.get("pk_columns") or [])
        if not pks:
            pks = ",".join(c["name"] for c in info["cols"] if c["name"].lower() == "id")
        cn = info["comment"] or name_en_from(tname)
        sql = (
            'INSERT INTO "FWBZ"."hephaestus_meta_nl_table" '
            '("id","schema_name","table_name","name_en","name_cn","aliases","topic",'
            '"description","pk_columns","time_grain","nl_enabled","priority") VALUES ('
            f"{tid},'FWBZ',{lit(tname)},{lit(name_en_from(tname))},{lit(cn)},"
            f"{lit(aliases)},{lit(topic)},{lit(info['comment'] or None)},"
            f"{lit(pks or None)},{lit(infer_grain(tname))},{lit(enabled)},{priority})"
        )
        run(sql, commit=False)
    commit()
    logger.info("已写入 hephaestus_meta_nl_table %d 行（nl_enabled=1 共 %d）", tid, enabled_n)

    cid = 0
    column_ids: dict[tuple[str, str], int] = {}
    for tname, info in tables.items():
        table_id = table_ids[tname]
        for col in info["cols"]:
            cid += 1
            cname = col["name"]
            column_ids[(tname, cname)] = cid
            declared_pk = cname in (info.get("pk_columns") or [])
            is_pk = "1" if declared_pk or cname.lower() == "id" else "0"
            declared_fk = next(
                (item for item in info.get("fks") or [] if item[0] == cname),
                None,
            )
            overlay = column_overlay(tname, cname)
            biz = resolve_business_fk(tname, cname, names)
            fk_to = declared_fk[1] if declared_fk else (biz[0] if biz else None)
            is_fk = (
                "1"
                if fk_to
                or overlay.get("role") == "fk"
                or (tname.lower(), cname.lower()) in gold_fk
                else "0"
            )
            role = overlay.get("role") or infer_role(cname, is_pk == "1", is_fk == "1")
            cn = info["col_comments"].get(cname) or overlay.get("aliases") or name_en_from(
                cname
            )
            if isinstance(cn, str) and "," in cn:
                cn = info["col_comments"].get(cname) or name_en_from(cname)
            unit = overlay.get("unit")
            if unit is None and cname.lower() == "value" and "metering" in tname.lower():
                unit = "kWh"
            if cname.lower() == "cost":
                unit = "元"
            dtype = col["data_type"]
            col_enabled = "0" if dtype.upper().split("(")[0] in {
                "CLOB",
                "TEXT",
                "BLOB",
                "LONGVARCHAR",
            } else "1"
            sql = (
                'INSERT INTO "FWBZ"."hephaestus_meta_nl_column" '
                '("id","table_id","column_name","name_en","name_cn","aliases","data_type",'
                '"is_pk","is_fk","role","unit","enum_values","nl_enabled") VALUES ('
                f"{cid},{table_id},{lit(cname)},{lit(name_en_from(cname))},{lit(cn)},"
                f"{lit(overlay.get('aliases'))},{lit(dtype)},{lit(is_pk)},{lit(is_fk)},"
                f"{lit(role)},{lit(unit)},{lit(overlay.get('enum_values'))},{lit(col_enabled)})"
            )
            run(sql, commit=False)
    commit()
    logger.info("已写入 hephaestus_meta_nl_column %d 行", cid)

    rid = 0
    seen = set()

    def add_relation(
        from_table: str,
        from_col: str,
        to_table: str,
        to_col: str,
        join_type: str = "LEFT",
    ) -> None:
        nonlocal rid
        ft = _match_name(from_table, tables)
        tt = _match_name(to_table, tables)
        if not ft or not tt or ft == tt:
            return
        from_map = _col_names(tables[ft])
        to_map = _col_names(tables[tt])
        fc = from_map.get(from_col.lower())
        tc = to_map.get(to_col.lower())
        if not fc or not tc:
            logger.warning(
                "关联列不存在，跳过: %s.%s = %s.%s",
                from_table,
                from_col,
                to_table,
                to_col,
            )
            return
        key = (ft.lower(), fc.lower(), tt.lower(), tc.lower())
        if key in seen:
            return
        seen.add(key)
        rid += 1
        kind = (join_type or "LEFT").upper()
        if kind not in {"LEFT", "INNER"}:
            kind = "LEFT"
        desc = "%s.%s = %s.%s" % (ft, fc, tt, tc)
        sql = (
            'INSERT INTO "FWBZ"."hephaestus_meta_nl_relation" '
            '("id","from_table_id","from_column","to_table_id","to_column",'
            '"join_type","description","nl_enabled") VALUES ('
            f"{rid},{table_ids[ft]},{lit(fc)},{table_ids[tt]},"
            f"{lit(tc)},{lit(kind)},{lit(desc)},'1')"
        )
        run(sql, commit=False)

    for from_t, from_c, to_t, to_c, jtype in gold.joins:
        add_relation(from_t, from_c, to_t, to_c, jtype)
    handbook_n = rid
    for tname, info in tables.items():
        for from_col, to_table, to_col in info.get("fks") or []:
            add_relation(tname, from_col, to_table, to_col)
        for col in info["cols"]:
            biz = resolve_business_fk(tname, col["name"], names)
            if biz:
                add_relation(tname, col["name"], biz[0], biz[1])
    commit()
    logger.info(
        "已写入 hephaestus_meta_nl_relation %d 行（手册 JOIN %d，其余为业务外键）",
        rid,
        handbook_n,
    )

    sid = 0
    seen_syn: set[tuple[str, str, int]] = set()

    def add_syn(phrase: str, target_type: str, target_id: int, weight: int) -> None:
        nonlocal sid
        phrase = (phrase or "").strip()[:255]
        if not useful_phrase(phrase, ""):
            return
        key = (phrase, target_type, target_id)
        if key in seen_syn:
            return
        seen_syn.add(key)
        sid += 1
        run(
            'INSERT INTO "FWBZ"."hephaestus_meta_nl_synonym" '
            '("id","phrase","target_type","target_id","weight") VALUES ('
            f"{sid},{lit(phrase)},{lit(target_type)},{target_id},{weight})",
            commit=False,
        )

    for tname, info in tables.items():
        tid_ = table_ids[tname]
        add_syn(info["comment"], "table", tid_, 2)
        for phrase in gold.aliases.get(tname.lower()) or []:
            add_syn(phrase, "table", tid_, 3)
        for topic in gold.tables.get(tname.lower()) or []:
            add_syn(topic, "table", tid_, 2)
        for col in info["cols"]:
            col_id = column_ids[(tname, col["name"])]
            add_syn(info["col_comments"].get(col["name"]) or "", "column", col_id, 1)
            overlay = column_overlay(tname, col["name"])
            for phrase in (overlay.get("aliases") or "").split(","):
                add_syn(phrase, "column", col_id, 3)
    commit()
    logger.info("已写入 hephaestus_meta_nl_synonym %d 行", sid)


def main() -> None:
    print("连接达梦，按问答手册金标 + FWBZ 数据字典灌 NL 元数据 ...")
    gold = load_handbook_gold()
    print(
        "手册重点表 %d: %s"
        % (len(gold.tables), ", ".join(sorted({t for t in gold.tables})))
    )
    ensure_tables()
    truncate_meta()
    seed()
    n1 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_table"')
    n2 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_column"')
    n3 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_relation"')
    n4 = execute_query('SELECT COUNT(*) AS n FROM "FWBZ"."hephaestus_meta_nl_synonym"')
    n5 = execute_query(
        "SELECT COUNT(*) AS n FROM \"FWBZ\".\"hephaestus_meta_nl_table\" "
        "WHERE \"nl_enabled\"='1' AND \"priority\"=10"
    )
    print(
        "完成: table=%s column=%s relation=%s synonym=%s handbook_priority10=%s"
        % (
            list(n1[0].values())[0] if n1 else "?",
            list(n2[0].values())[0] if n2 else "?",
            list(n3[0].values())[0] if n3 else "?",
            list(n4[0].values())[0] if n4 else "?",
            list(n5[0].values())[0] if n5 else "?",
        )
    )
    close_dameng()


if __name__ == "__main__":
    main()
