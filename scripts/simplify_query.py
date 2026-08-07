"""
精简 query.json - 去掉用不到的内容
"""
import json


def simplify_query_json(input_path: str) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 通用审计字段 - 查询基本不需要
    skip_fields = {
        "create_by", "update_by", "create_time", "update_time",
        "sys_org_code", "id", "remark"
    }

    # 精简每个表的字段
    tables = data.get("tables", {})
    for table_name, table_info in tables.items():
        fields = table_info.get("fields", {})
        new_fields = {}

        for field_name, field_info in fields.items():
            # 跳过审计字段
            if field_name in skip_fields:
                continue

            # 只保留有用的标记
            new_info = {
                "type": field_info.get("type", ""),
                "desc": field_info.get("desc", "")
            }

            # 如果是可用的标记才保留
            if field_info.get("filterable"):
                new_info["filterable"] = True
            if field_info.get("searchable"):
                new_info["searchable"] = True
            if field_info.get("groupable"):
                new_info["groupable"] = True

            new_fields[field_name] = new_info

        table_info["fields"] = new_fields

    # 写入文件
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 显示结果
    import os
    size = os.path.getsize(input_path)
    print(f"精简完成！文件大小: {size / 1024:.2f} KB")

    # 统计字段数量
    total_fields = sum(len(t.get("fields", {})) for t in tables.values())
    print(f"总表数: {len(tables)}, 总字段数: {total_fields}")


if __name__ == "__main__":
    path = "E:\\纵联宸捷\\首钢项目\\会展小镇项目\\RAG-Hephaestus-KB-SG-Backend\\config\\query.json"
    simplify_query_json(path)
