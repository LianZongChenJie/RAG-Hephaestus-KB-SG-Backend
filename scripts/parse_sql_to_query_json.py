"""
解析 FWBZ_strut.sql，提取所有表结构，生成 query.json 格式的 JSON
"""
import json
import re
import os

SQL_FILE = r"E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\config\FWBZ_strut.sql"
OUTPUT_FILE = r"E:\纵联宸捷\首钢项目\会展小镇项目\RAG-Hephaestus-KB-SG-Backend\config\query.json"

# 跳过的后台字段（审计字段对 AI 理解业务无帮助）
SKIP_COLUMNS = {
    "create_by", "create_time", "update_by", "update_time",
    "sys_org_code", "remark", "sort"
}

# 类型映射（简化为大模型能理解的基本类型）
def simplify_type(dtype: str) -> str:
    dtype = dtype.upper().strip()
    if "INT" in dtype or "BIGINT" in dtype or "TINYINT" in dtype or "SMALLINT" in dtype:
        return "BIGINT"
    if "DECIMAL" in dtype or "DOUBLE" in dtype or "NUMERIC" in dtype:
        return "DECIMAL"
    if "CHAR" in dtype or "VARCHAR" in dtype or "TEXT" in dtype:
        return "VARCHAR"
    if "DATE" in dtype or "TIME" in dtype or "TIMESTAMP" in dtype:
        return "TIMESTAMP"
    if "CLOB" in dtype:
        return "TEXT"
    return "VARCHAR"


def parse_sql_file(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 按 CREATE TABLE 分块
    pattern = re.compile(
        r'CREATE\s+TABLE\s+"FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
        re.DOTALL | re.IGNORECASE
    )

    # 提取所有表注释
    table_comment_pattern = re.compile(
        r'COMMENT\s+ON\s+TABLE\s+"FWBZ"\."(\w+)"\s+IS\s+\'([^\']*)\'',
        re.IGNORECASE
    )
    table_comments = {}
    for m in table_comment_pattern.finditer(content):
        table_comments[m.group(1)] = m.group(2).strip()

    # 提取所有列注释
    col_comment_pattern = re.compile(
        r'COMMENT\s+ON\s+COLUMN\s+"FWBZ"\."(\w+)"\."(\w+)"\s+IS\s+\'([^\']*)\'',
        re.IGNORECASE
    )
    col_comments = {}
    for m in col_comment_pattern.finditer(content):
        key = (m.group(1), m.group(2))
        col_comments[key] = m.group(3).strip()

    tables = {}
    for m in pattern.finditer(content):
        table_name = m.group(1)
        table_body = m.group(2)

        # 解析每行字段
        fields = {}
        for line in table_body.split("\n"):
            line = line.strip().strip(",").strip()
            if not line or line.startswith("--"):
                continue
            # 跳过注释行
            if re.match(r'^\s*".*"\s+VARCHAR', line, re.IGNORECASE) is None and \
               re.match(r'^\s*"\w+"\s+\w+', line) is None:
                continue

            # 匹配字段定义
            col_match = re.match(r'"(\w+)"\s+([\w\(\)\,\.]+)', line, re.IGNORECASE)
            if not col_match:
                continue

            col_name = col_match.group(1)
            col_type_raw = col_match.group(2).strip()

            # 跳过审计字段
            if col_name in SKIP_COLUMNS:
                continue

            # 获取注释
            comment = col_comments.get((table_name, col_name), "")
            if not comment:
                comment = col_name  # 用字段名作为 fallback

            col_type = simplify_type(col_type_raw)

            fields[col_name] = {
                "type": col_type,
                "desc": comment
            }

        if fields:
            tables[table_name] = {
                "name": table_name,
                "description": table_comments.get(table_name, table_name),
                "fields": fields
            }

    return tables


def merge_to_query_json(existing_tables: dict, new_tables: dict) -> dict:
    """合并新表到现有 query.json，保留已有的，不过覆盖同名表"""
    merged = dict(existing_tables)
    for name, table_def in new_tables.items():
        merged[name] = table_def
    return merged


def main():
    # 读取现有 query.json
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        existing = json.load(f)

    print(f"现有 query.json 包含 {len(existing.get('tables', {}))} 个表")

    # 解析 SQL
    new_tables = parse_sql_file(SQL_FILE)
    print(f"SQL 文件解析出 {len(new_tables)} 个表")

    # 合并
    merged_tables = merge_to_query_json(existing.get("tables", {}), new_tables)

    existing["tables"] = merged_tables

    # 写回
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"完成！共 {len(merged_tables)} 个表已写入 {OUTPUT_FILE}")

    # 列出新增的表
    existing_names = set(existing.get("tables", {}).keys()) - set(new_tables.keys())
    new_names = set(new_tables.keys()) - (existing.get("tables", {}).keys())
    print(f"\n新增表: {sorted(new_names)}")


if __name__ == "__main__":
    main()
