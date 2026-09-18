"""问答手册 SQL 作为 seed_meta_nl 金标：不连库。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from seed_meta_nl import (  # noqa: E402
    classify_table,
    load_handbook_gold,
    parse_handbook_sql_joins,
    parse_handbook_tables,
    resolve_business_fk,
    resolve_fk_table,
)


def test_parse_handbook_core_tables():
    gold = load_handbook_gold(ROOT / "config" / "FWBZ保障平台问答手册.md")
    names = set(gold.tables)
    for table in (
        "device",
        "data_day",
        "metering_point",
        "metering_point_rel",
        "equipment_category",
        "space",
        "cold_source_device",
        "cold_source_equipment_category",
        "energy_analysis_config",
        "energy_analysis_chart",
        "table_door_resource",
        "table_acs_device",
        "lighting_circuit",
        "lighting_area",
        "table_venue_flow_hour",
        "table_venue_info",
        "table_activemeet_info",
        "table_camera_resource",
        "device_model",
        "alarm_record",
    ):
        assert table in names, table
    assert "metering_point_data_day" not in names
    assert gold.tables["data_day"] == {"智慧能源"}
    assert "设备管理" in gold.tables["device"]
    assert "韧性安全" in gold.tables["table_acs_device"]


def test_parse_handbook_joins():
    gold = load_handbook_gold(ROOT / "config" / "FWBZ保障平台问答手册.md")
    keys = {
        (a.lower(), b.lower(), c.lower(), d.lower())
        for a, b, c, d, _t in gold.joins
    }
    assert ("device", "category_id", "equipment_category", "id") in keys
    assert ("metering_point", "space_id", "space", "id") in keys
    assert (
        "cold_source_device",
        "category_id",
        "cold_source_equipment_category",
        "id",
    ) in keys
    assert ("data_day", "device_id", "device", "id") in keys
    assert ("lighting_circuit", "area_id", "lighting_area", "id") in keys
    assert ("table_venue_flow_hour", "venue_id", "table_venue_info", "id") in keys
    door_acs = {
        ("table_door_resource", "parent_index_code", "table_acs_device", "index_code"),
        ("table_acs_device", "index_code", "table_door_resource", "parent_index_code"),
    }
    assert keys & door_acs


def test_classify_priority_layers():
    gold = load_handbook_gold(ROOT / "config" / "FWBZ保障平台问答手册.md")
    topic, aliases, prio, enabled = classify_table("device", gold)
    assert enabled == "1" and prio == 10
    assert topic == "设备管理"
    assert aliases and "楼控设备" in aliases

    topic, aliases, prio, enabled = classify_table("table_acs_device", gold)
    assert topic == "韧性安全" and prio == 10 and enabled == "1"
    assert aliases and "门禁控制器" in aliases

    topic, _a, prio, enabled = classify_table("cold_source_device", gold)
    assert topic == "智慧能源" and prio == 10

    topic, _a, prio, enabled = classify_table("data_day", gold)
    assert topic == "智慧能源" and prio == 10 and enabled == "1"

    _t, _a, prio, enabled = classify_table("lighting_plan", gold)
    assert prio == 40 and enabled == "1"

    _t, _a, prio, enabled = classify_table("metering_point_data_day", gold)
    assert enabled == "0" and prio >= 800

    _t, _a, prio, enabled = classify_table("sys_log", gold)
    assert enabled == "0"

    _t, _a, prio, enabled = classify_table("table_parking_record", gold)
    assert enabled == "0"


def test_parse_sql_helpers():
    sql = """
    SELECT d."device_name"
    FROM "FWBZ"."device" d
    INNER JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
    LEFT JOIN "FWBZ"."space" s ON s."id" = d."space_id"
    """
    assert parse_handbook_tables(sql) == ["device", "equipment_category", "space"]
    joins = parse_handbook_sql_joins(sql)
    keys = {(a, b, c, d) for a, b, c, d, _t in joins}
    assert ("device", "category_id", "equipment_category", "id") in keys
    assert ("device", "space_id", "space", "id") in keys


def test_resolve_business_fk_real_links():
    names = {
        "device",
        "space",
        "equipment_category",
        "cold_source_device",
        "cold_source_equipment_category",
        "device_model",
        "table_venue_info",
        "table_acs_device",
        "table_door_resource",
        "lighting_circuit",
        "lighting_area",
        "alarm_record",
        "data_day",
    }
    assert resolve_fk_table("category_id", names) is None
    assert resolve_business_fk("device", "category_id", names) == (
        "equipment_category",
        "id",
    )
    assert resolve_business_fk("device", "space_id", names) == ("space", "id")
    assert resolve_business_fk("device", "model_id", names) == ("device_model", "id")
    assert resolve_business_fk("device", "venue_id", names) == (
        "table_venue_info",
        "id",
    )
    assert resolve_business_fk("cold_source_device", "category_id", names) == (
        "cold_source_equipment_category",
        "id",
    )
    assert resolve_business_fk("table_door_resource", "parent_index_code", names) == (
        "table_acs_device",
        "index_code",
    )
    assert resolve_business_fk("lighting_circuit", "area_id", names) == (
        "lighting_area",
        "id",
    )
    assert resolve_business_fk("alarm_record", "device_category_id", names) == (
        "equipment_category",
        "id",
    )
    assert resolve_business_fk("data_day", "device_id", names) == ("device", "id")
    assert resolve_business_fk("device", "id", names) is None
