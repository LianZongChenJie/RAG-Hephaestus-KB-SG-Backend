"""读取 hephaestus_meta_nl_*，给统计图表选维度/指标/JOIN。

聊天主链路原先不读这四张表。图表若只看结果列的 Python 类型，会把
device.category_id 这种外键当成 Y 轴数值。这里按 role / 关系纠正。
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("chat.meta_nl")

_ID_ROLES = frozenset({"pk", "fk", "id"})
_DIM_ROLES = frozenset({"dim", "status", "fk"})
_METRIC_NAME_RE = re.compile(
    r"(^|_)(value|cost|amount|energy|power|count|cnt|total|avg|sum|max|min)(_|$)",
    re.IGNORECASE,
)
_FROM_JOIN_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:(?:"?\w+"?\.)?"(\w+)"|(?:\w+\.)?(\w+))',
    re.IGNORECASE,
)
_GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)

# seed 的 resolve_fk_table 只认 col[:-3] 等于表名，device.category_id 对不上
# equipment_category，这里按 strut 注释补齐推荐 JOIN。
_FALLBACK_JOINS: Dict[Tuple[str, str], Tuple[str, str, str, str]] = {
    # from_table, from_col -> to_table, to_pk, name_col, label_cn
    ("device", "category_id"): (
        "equipment_category",
        "id",
        "category_name",
        "设备类别",
    ),
    ("device", "space_id"): ("space", "id", "space_name", "空间位置"),
    ("device", "model_id"): ("device_model", "id", "model_name", "设备模型"),
    ("device", "venue_id"): ("table_venue_info", "id", "venue_name", "场馆"),
    ("device_model", "category_id"): (
        "equipment_category",
        "id",
        "category_name",
        "设备类别",
    ),
    ("alarm_record", "device_category_id"): (
        "equipment_category",
        "id",
        "category_name",
        "设备类别",
    ),
    ("alarm_record", "space_id"): ("space", "id", "space_name", "空间位置"),
    ("alarm_record", "venue_id"): ("table_venue_info", "id", "venue_name", "场馆"),
    ("metering_point", "category_id"): (
        "equipment_category",
        "id",
        "category_name",
        "设备类别",
    ),
    ("cold_source_device", "category_id"): (
        "equipment_category",
        "id",
        "category_name",
        "设备类别",
    ),
}

_QUESTION_DIM_HINTS: Tuple[Tuple[Tuple[str, ...], Tuple[str, ...]], ...] = (
    (("类别", "分类", "类型"), ("category_id", "device_category_id", "device_type", "category_name")),
    (("状态", "在线", "离线", "运行"), ("run_state", "status", "online")),
    (("场馆", "会展"), ("venue_id", "venue_name")),
    (("空间", "位置"), ("space_id", "space_name")),
    (("模型",), ("model_id", "model_name")),
)

_DEFAULT_DIM_ORDER = (
    "category_id",
    "device_category_id",
    "device_type",
    "run_state",
    "status",
    "venue_id",
    "space_id",
    "model_id",
)

_HIGH_CARD_NAMES = frozenset(
    {
        "device_name",
        "name",
        "device_code",
        "node_code",
        "title",
        "full_name",
        "alarm_content",
        "content",
        "remark",
        "description",
        "create_by",
        "id",
    }
)


@dataclass(frozen=True)
class DimJoin:
    to_table: str
    to_column: str
    name_column: str
    label_cn: str
    join_type: str = "LEFT"


@dataclass
class ColMeta:
    table_name: str
    column_name: str
    name_cn: str = ""
    role: str = "other"
    is_pk: bool = False
    is_fk: bool = False
    enum_values: str = ""


@dataclass
class ChartPlan:
    mode: str  # count | metric
    cat_key: str
    cat_label: str
    metric_key: Optional[str] = None
    metric_label: str = "数量"
    join: Optional[DimJoin] = None
    already_aggregated: bool = False
    fact_table: Optional[str] = None


@dataclass
class MetaCatalog:
    tables: Dict[str, str] = field(default_factory=dict)  # table -> name_cn
    columns: Dict[Tuple[str, str], ColMeta] = field(default_factory=dict)
    columns_by_name: Dict[str, List[ColMeta]] = field(default_factory=dict)
    relations: Dict[Tuple[str, str], DimJoin] = field(default_factory=dict)
    synonyms: List[Tuple[str, str, str]] = field(default_factory=list)  # phrase, table, column
    loaded_from_db: bool = False


_LOCK = threading.Lock()
_CATALOG: Optional[MetaCatalog] = None


def reset_catalog_cache() -> None:
    global _CATALOG
    with _LOCK:
        _CATALOG = None


def get_catalog() -> MetaCatalog:
    global _CATALOG
    with _LOCK:
        if _CATALOG is None:
            _CATALOG = _load_catalog()
        return _CATALOG


def _norm(name: Optional[str]) -> str:
    return str(name or "").strip().strip('"').lower()


def infer_role(col: str, *, is_pk: bool = False, is_fk: bool = False) -> str:
    if is_pk:
        return "pk"
    if is_fk:
        return "fk"
    low = col.lower()
    if low in {"time", "data_date", "start_date", "end_date"} or low.endswith(
        ("_time", "_date")
    ):
        return "time"
    if _METRIC_NAME_RE.search(low) or low in {"value", "cost", "count", "amount", "energy", "power"}:
        return "metric"
    if (
        low in {"status", "type", "level", "success_flag", "device_type", "run_state"}
        or "state" in low
        or low.endswith("_status")
    ):
        return "status"
    if low in {"name", "title", "node_name"} or low.endswith("_name"):
        return "name"
    if low.endswith("_id") or low == "id":
        return "id"
    return "other"


def _is_true_metric(col: ColMeta, result_key: str) -> bool:
    if col.role in _ID_ROLES or col.is_pk or col.is_fk:
        return False
    if col.role == "metric":
        return True
    key = result_key.lower()
    if re.match(r"^(sum|avg|count|max|min)\s*\(", key):
        return True
    return bool(_METRIC_NAME_RE.search(key)) and col.role not in {"time", "name", "status"}


def _unique_ratio(data: Sequence[dict], key: str) -> float:
    vals = [str(row.get(key, "")) for row in data]
    return len(set(vals)) / max(len(vals), 1)


def _find_result_key(keys: Sequence[str], col: str) -> Optional[str]:
    want = _norm(col)
    for k in keys:
        if _norm(k) == want:
            return k
    return None


def extract_sql_tables(sql: Optional[str]) -> List[str]:
    if not sql:
        return []
    found: List[str] = []
    seen = set()
    for m in _FROM_JOIN_RE.finditer(sql):
        name = _norm(m.group(1) or m.group(2))
        if not name or name in seen:
            continue
        seen.add(name)
        found.append(name)
    return found


def _guess_tables_from_keys(cat: MetaCatalog, keys: Sequence[str]) -> List[str]:
    keyset = {_norm(k) for k in keys}
    scored: List[Tuple[int, str]] = []
    tables = {t for t, _ in cat.columns}
    for table in tables:
        cols = {c for t, c in cat.columns if t == table}
        overlap = len(keyset & cols)
        if overlap >= 3:
            scored.append((overlap, table))
    scored.sort(reverse=True)
    return [t for _, t in scored]


def _apply_fallback_joins(cat: MetaCatalog) -> None:
    for (ft, fc), (tt, tp, nc, label) in _FALLBACK_JOINS.items():
        key = (_norm(ft), _norm(fc))
        if key not in cat.relations:
            cat.relations[key] = DimJoin(
                to_table=tt,
                to_column=tp,
                name_column=nc,
                label_cn=label,
            )
        col = cat.columns.get(key)
        if col:
            col.is_fk = True
            if col.role in {"id", "other"}:
                col.role = "fk"
            if not col.name_cn or col.name_cn.lower() == fc.replace("_", " "):
                col.name_cn = label


def _seed_minimal_columns(cat: MetaCatalog) -> None:
    """无库时也能识别 device 明细。"""
    device_cols = {
        "id": ("pk", True, False, "主键"),
        "device_code": ("name", False, False, "设备编号"),
        "device_name": ("name", False, False, "设备名称"),
        "category_id": ("fk", False, True, "设备类别"),
        "space_id": ("fk", False, True, "空间位置"),
        "magnification": ("other", False, False, "倍率"),
        "sort": ("other", False, False, "排序"),
        "run_state": ("status", False, False, "运行状态"),
        "model_id": ("fk", False, True, "设备模型"),
        "device_type": ("status", False, False, "设备分类"),
        "last_gather_time": ("time", False, False, "最后采集时间"),
        "venue_id": ("fk", False, True, "场馆"),
        "remark": ("other", False, False, "备注"),
        "automatic_algorithm": ("other", False, False, "自动算法"),
    }
    cat.tables.setdefault("device", "设备基础信息")
    for name, (role, pk, fk, cn) in device_cols.items():
        key = ("device", name)
        if key not in cat.columns:
            meta = ColMeta(
                table_name="device",
                column_name=name,
                name_cn=cn,
                role=role,
                is_pk=pk,
                is_fk=fk,
            )
            cat.columns[key] = meta
            cat.columns_by_name.setdefault(name, []).append(meta)


def _load_from_db() -> Optional[MetaCatalog]:
    try:
        from app.common.dameng import execute_query
    except Exception:
        return None
    try:
        tables = execute_query(
            'SELECT "id", "table_name", "name_cn" '
            'FROM "FWBZ"."hephaestus_meta_nl_table" '
            "WHERE \"nl_enabled\" = '1'"
        )
        cols = execute_query(
            'SELECT "id", "table_id", "column_name", "name_cn", "role", '
            '"is_pk", "is_fk", "enum_values" '
            'FROM "FWBZ"."hephaestus_meta_nl_column" '
            "WHERE \"nl_enabled\" = '1'"
        )
        rels = execute_query(
            'SELECT "from_table_id", "from_column", "to_table_id", '
            '"to_column", "join_type" '
            'FROM "FWBZ"."hephaestus_meta_nl_relation" '
            "WHERE \"nl_enabled\" = '1'"
        )
        syns = execute_query(
            'SELECT "phrase", "target_type", "target_id", "weight" '
            'FROM "FWBZ"."hephaestus_meta_nl_synonym"'
        )
    except Exception as exc:
        logger.info("未读取到 hephaestus_meta_nl_*，图表用本地角色推断: %s", exc)
        return None

    cat = MetaCatalog(loaded_from_db=True)
    id_to_table: Dict[int, str] = {}
    for row in tables or []:
        tid = int(row.get("id") or 0)
        tname = _norm(row.get("table_name"))
        if not tname:
            continue
        id_to_table[tid] = tname
        cat.tables[tname] = str(row.get("name_cn") or tname)

    id_to_col: Dict[int, ColMeta] = {}
    for row in cols or []:
        tname = id_to_table.get(int(row.get("table_id") or 0))
        cname = _norm(row.get("column_name"))
        if not tname or not cname:
            continue
        is_pk = str(row.get("is_pk") or "0") == "1"
        is_fk = str(row.get("is_fk") or "0") == "1"
        role = str(row.get("role") or "").strip() or infer_role(
            cname, is_pk=is_pk, is_fk=is_fk
        )
        meta = ColMeta(
            table_name=tname,
            column_name=cname,
            name_cn=str(row.get("name_cn") or cname),
            role=role,
            is_pk=is_pk,
            is_fk=is_fk,
            enum_values=str(row.get("enum_values") or ""),
        )
        cat.columns[(tname, cname)] = meta
        cat.columns_by_name.setdefault(cname, []).append(meta)
        cid = row.get("id")
        if cid is not None:
            id_to_col[int(cid)] = meta

    name_cols: Dict[str, str] = {}
    name_priority = {
        "category_name": 0,
        "space_name": 0,
        "venue_name": 0,
        "model_name": 0,
        "device_name": 1,
        "name": 2,
        "full_name": 3,
        "title": 4,
    }
    for (tname, cname), meta in cat.columns.items():
        if cname not in name_priority and not (
            meta.role == "name" or cname.endswith("_name")
        ):
            continue
        score = name_priority.get(cname, 10)
        prev = name_cols.get(tname)
        if prev is None or name_priority.get(prev, 10) > score:
            name_cols[tname] = cname

    for row in rels or []:
        ft = id_to_table.get(int(row.get("from_table_id") or 0))
        tt = id_to_table.get(int(row.get("to_table_id") or 0))
        fc = _norm(row.get("from_column"))
        tc = _norm(row.get("to_column")) or "id"
        if not ft or not tt or not fc:
            continue
        name_col = name_cols.get(tt, "name")
        label = cat.tables.get(tt) or tt
        cat.relations[(ft, fc)] = DimJoin(
            to_table=tt,
            to_column=tc,
            name_column=name_col,
            label_cn=label,
            join_type=str(row.get("join_type") or "LEFT").upper() or "LEFT",
        )

    for row in syns or []:
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        target_type = str(row.get("target_type") or "").strip().lower()
        tid = int(row.get("target_id") or 0)
        if target_type == "table":
            tname = id_to_table.get(tid)
            if tname:
                cat.synonyms.append((phrase, tname, ""))
        elif target_type == "column":
            meta = id_to_col.get(tid)
            if meta:
                cat.synonyms.append((phrase, meta.table_name, meta.column_name))

    logger.info(
        "已加载 NL 元数据: table=%s column=%s relation=%s synonym=%s",
        len(cat.tables),
        len(cat.columns),
        len(cat.relations),
        len(cat.synonyms),
    )
    return cat


def _load_catalog() -> MetaCatalog:
    cat = _load_from_db() or MetaCatalog()
    _seed_minimal_columns(cat)
    _apply_fallback_joins(cat)
    return cat


def _resolve_col(
    cat: MetaCatalog, tables: Sequence[str], result_key: str
) -> Optional[ColMeta]:
    name = _norm(result_key)
    for t in tables:
        hit = cat.columns.get((_norm(t), name))
        if hit:
            return hit
    cands = cat.columns_by_name.get(name) or []
    if len(cands) == 1:
        return cands[0]
    for c in cands:
        if c.table_name in {_norm(t) for t in tables}:
            return c
    return None


def _question_dim_hints(question: str) -> List[str]:
    q = question or ""
    ordered: List[str] = []
    for phrases, cols in _QUESTION_DIM_HINTS:
        if any(p in q for p in phrases):
            for c in cols:
                if c not in ordered:
                    ordered.append(c)
    return ordered


def _synonym_hits(cat: MetaCatalog, question: str, tables: Sequence[str]) -> List[str]:
    q = question or ""
    table_set = {_norm(t) for t in tables}
    hits: List[str] = []
    for phrase, tname, cname in cat.synonyms:
        if not phrase or phrase not in q:
            continue
        if tname not in table_set:
            continue
        if cname and cname not in hits:
            hits.append(cname)
    return hits


def _pick_dim_key(
    cat: MetaCatalog,
    *,
    tables: Sequence[str],
    keys: Sequence[str],
    data: Sequence[dict],
    question: str,
    already_aggregated: bool = False,
    prefer_dims: Optional[Sequence[str]] = None,
) -> Optional[str]:
    preferred = list(prefer_dims or ())
    preferred += _question_dim_hints(question) + _synonym_hits(cat, question, tables)
    seen_pref = set()
    ordered_pref = []
    for c in preferred:
        n = _norm(c)
        if n and n not in seen_pref:
            seen_pref.add(n)
            ordered_pref.append(c)
    candidates = ordered_pref + [
        c for c in _DEFAULT_DIM_ORDER if _norm(c) not in seen_pref
    ]
    # 结果里已有可读维表名，优先于外键
    for readable in (
        "category_name",
        "venue_name",
        "space_name",
        "alarm_category_name",
        "alarm_level_name",
    ):
        if _find_result_key(keys, readable) and readable not in candidates:
            candidates.insert(0, readable)

    for col in candidates:
        raw = _find_result_key(keys, col)
        if not raw:
            continue
        if _norm(col) in _HIGH_CARD_NAMES:
            continue
        meta = _resolve_col(cat, tables, col)
        if meta and meta.role in {"pk", "time", "metric"}:
            continue
        if meta and meta.role == "name" and _norm(col) not in {
            "category_name",
            "venue_name",
            "space_name",
            "alarm_category_name",
            "alarm_level_name",
        }:
            continue
        join = _join_for(cat, tables, raw)
        forced = _norm(col) in seen_pref
        max_ratio = 0.85 if join or (meta and (meta.is_fk or meta.role == "fk")) else 0.45
        if (
            not already_aggregated
            and not forced
            and data
            and _unique_ratio(data, raw) > max_ratio
        ):
            continue
        return raw
    # 退而求其次：低基数 status / fk
    for raw in keys:
        name = _norm(raw)
        if name in _HIGH_CARD_NAMES:
            continue
        meta = _resolve_col(cat, tables, raw)
        role = meta.role if meta else infer_role(name)
        if role not in _DIM_ROLES and role != "status":
            continue
        join = _join_for(cat, tables, raw)
        max_ratio = 0.85 if join or (meta and (meta.is_fk or meta.role == "fk")) else 0.45
        if (
            not already_aggregated
            and data
            and _unique_ratio(data, raw) > max_ratio
        ):
            continue
        return raw
    return None


def _join_for(cat: MetaCatalog, tables: Sequence[str], cat_key: str) -> Optional[DimJoin]:
    col = _norm(cat_key)
    if col.endswith("_name"):
        return None
    for t in tables:
        join = cat.relations.get((_norm(t), col))
        if join:
            return join
    join = cat.relations.get(("device", col))
    return join


def plan_stat_chart(
    *,
    source_sql: Optional[str],
    keys: Sequence[str],
    question: str,
    data: Sequence[dict],
    catalog: Optional[MetaCatalog] = None,
    prefer_dims: Optional[Sequence[str]] = None,
) -> Optional[ChartPlan]:
    """根据元数据决定图表：明细走维度 COUNT；外键 JOIN 名称列。"""
    if not keys:
        return None
    cat = catalog or get_catalog()
    sql_tables = extract_sql_tables(source_sql)
    tables = [t for t in sql_tables if t in cat.tables or t == "device"]
    if not tables:
        tables = _guess_tables_from_keys(cat, keys) or ["device"]

    already = bool(source_sql and _GROUP_BY_RE.search(source_sql))
    sample = data[0] if data else {}
    metric_keys: List[str] = []
    for k in keys:
        meta = _resolve_col(cat, tables, k) or ColMeta(
            table_name=tables[0],
            column_name=_norm(k),
            role=infer_role(_norm(k)),
        )
        val = sample.get(k)
        is_num = isinstance(val, (int, float, Decimal)) and not isinstance(val, bool)
        if already:
            if is_num and _is_true_metric(meta, str(k)):
                metric_keys.append(k)
        elif _is_true_metric(meta, str(k)):
            metric_keys.append(k)

    dim_raw = _pick_dim_key(
        cat,
        tables=tables,
        keys=keys,
        data=data,
        question=question,
        already_aggregated=already,
        prefer_dims=prefer_dims,
    )
    if not dim_raw:
        return None

    dim_meta = _resolve_col(cat, tables, dim_raw)
    join = _join_for(cat, tables, dim_raw)
    label = (
        (join.label_cn if join else None)
        or (dim_meta.name_cn if dim_meta else None)
        or dim_raw
    )
    if label.endswith("id") or label.endswith("ID"):
        label = (join.label_cn if join else label.replace("ID", "").replace("id", "")) or label
    if _norm(dim_raw) in {"run_state", "online", "status"}:
        label = "在线情况"

    fact = tables[0] if tables else None
    if metric_keys and already:
        mk = metric_keys[0]
        mmeta = _resolve_col(cat, tables, mk)
        return ChartPlan(
            mode="metric",
            cat_key=dim_raw,
            cat_label=label,
            metric_key=mk,
            metric_label=(mmeta.name_cn if mmeta else mk),
            join=None,
            already_aggregated=True,
            fact_table=fact,
        )
    if metric_keys and not already:
        mk = metric_keys[0]
        mmeta = _resolve_col(cat, tables, mk)
        return ChartPlan(
            mode="metric",
            cat_key=dim_raw,
            cat_label=label,
            metric_key=mk,
            metric_label=(mmeta.name_cn if mmeta else mk),
            join=join,
            already_aggregated=False,
            fact_table=fact,
        )
    return ChartPlan(
        mode="count",
        cat_key=dim_raw,
        cat_label=label,
        join=join,
        already_aggregated=False,
        fact_table=fact,
    )
