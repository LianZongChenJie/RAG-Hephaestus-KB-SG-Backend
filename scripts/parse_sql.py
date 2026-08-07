"""
精简 query.json，只保留展会报告相关的表
"""
import json
from pathlib import Path


def simplify_query_json(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 只保留这些核心表（展会报告相关）
    keep_tables = {
        # 告警系统 - 投诉、建议、故障、应急响应
        "alarm_record",
        "alarm_category",
        "alarm_level",
        # 人员统计 - 服务人次、满意度
        "table_personnel_statistics",
        # 场馆客流 - 总客流、峰值客流
        "table_venue_flow",
        "table_venue_info",
        # 展会信息 - 展会天数、参展商
        "table_activeMeet_info",
        "table_activeMeet_preparation_info",
        "table_activeMeet_preparation_type",
        # 能耗数据 - 总用电量
        "data_day",
        "data_hour",
        "data_month",
        "data_year",
        # 能源配置 - 能耗预算比
        "energy_price",
        "energy_pricing_config",
        # 系统日志 - 安保出勤
        "sys_log",
        # 设备关联
        "device",
        "equipment_category",
        "space",
    }

    # 精简表分组
    simplified_groups = {
        "personnel_service": {
            "name": "人员服务",
            "tables": ["table_personnel_statistics"]
        },
        "alarm_system": {
            "name": "告警系统",
            "tables": ["alarm_record", "alarm_category", "alarm_level"]
        },
        "venue_system": {
            "name": "场馆与会展",
            "tables": ["table_venue_info", "table_venue_flow", "table_activeMeet_info",
                       "table_activeMeet_preparation_info", "table_activeMeet_preparation_type"]
        },
        "energy_system": {
            "name": "能耗管理",
            "tables": ["data_day", "data_hour", "data_month", "data_year",
                       "energy_price", "energy_pricing_config"]
        },
        "device_system": {
            "name": "设备与空间",
            "tables": ["device", "equipment_category", "space"]
        },
        "operation_log": {
            "name": "操作日志",
            "tables": ["sys_log"]
        }
    }

    # 过滤表
    old_tables = data.get("tables", {})
    new_tables = {}
    for table_name in keep_tables:
        if table_name in old_tables:
            new_tables[table_name] = old_tables[table_name]

    # 更新数据
    data["table_groups"] = simplified_groups
    data["tables"] = new_tables

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"精简完成！保留 {len(new_tables)} 个表")
    print(f"分组数量: {len(simplified_groups)}")
    
    # 显示文件大小
    import os
    size = os.path.getsize(output_path)
    print(f"文件大小: {size / 1024:.2f} KB")


if __name__ == "__main__":
    input_path = "E:\\纵联宸捷\\首钢项目\\会展小镇项目\\RAG-Hephaestus-KB-SG-Backend\\config\\query.json"
    output_path = input_path  # 直接覆盖
    simplify_query_json(input_path, output_path)
