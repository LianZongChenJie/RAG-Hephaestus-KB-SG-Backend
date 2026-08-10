"""聊天服务 - SSE 流式对话处理，支持数据库智能问答"""
import asyncio
import json
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Any, AsyncIterator, List, Optional

import httpx

from app.core.config import get_settings
from app.core.database import save_access_log
from app.core.dameng import execute_query
from app.core.ollama import OllamaClient
from app.schemas.chat import ChatMessage, ChatStreamRequest

logger = logging.getLogger(__name__)
settings = get_settings()

# 达梦数据库 Schema 上下文（供 LLM 生成 SQL 使用）
DAMENG_SCHEMA_CONTEXT = """
## 达梦数据库信息
- 类型：Dameng 8.0 (08.00.000)
- Schema：FWBZ
- 标识符引号：表名和字段名必须用双引号包裹，如 "device"."device_name"
- 自增列：使用序列 FWBZ.SEQ_xxx，不支持 AUTO_INCREMENT

## ⚠️ 语法限制（严格遵守，禁止使用 MySQL 语法）

| 错误写法（MySQL）     | 正确写法（达梦 8.0）                           |
|---------------------|----------------------------------------------|
| DATE(col)           | CAST(col AS DATE) 或 TRUNC(col)               |
| DATE_FORMAT(col,f)  | TO_CHAR(col, 'YYYY-MM-DD')                   |
| IFNULL(a,b)         | NVL(a, b)                                     |
| IF(cond,a,b)        | CASE WHEN cond THEN a ELSE b END              |
| NOW()               | SYSDATE                                       |
| TIMESTAMPDIFF(MINUTE,a,b) | (b - a) * 1440                            |
| DATE_SUB / DATE_ADD | col +/- INTERVAL N DAY                        |
| DATEDIFF(a,b)       | (a - b)                                       |
| YEAR(col)/MONTH/DAY | EXTRACT(YEAR FROM col) / TO_CHAR(col,'YYYY') |
| LIMIT n, m           | 两层子查询 + ROWNUM（见下方示例）               |
| LIMIT n              | ROWNUM <= n 或 FETCH FIRST n ROWS ONLY        |
| CONCAT_WS(sep,...)  | col1 || sep || col2 || ...                    |
| FLOOR(col)          | TRUNC(col)                                    |

## LIMIT 分页示例（达梦）
```sql
-- 取第 11~20 条（OFFSET 10, LIMIT 10）
SELECT * FROM (
    SELECT t.*, ROWNUM AS rn FROM (
        SELECT "id", "device_name" FROM FWBZ."device"
        ORDER BY "create_time" DESC
    ) t WHERE ROWNUM <= 20
) WHERE rn > 10

-- 取前 100 条
SELECT * FROM (
    SELECT t.*, ROWNUM AS rn FROM (
        SELECT "id", "device_name" FROM FWBZ."device"
        ORDER BY "create_time" DESC
    ) t WHERE ROWNUM <= 100
)
```

## 时间差计算（告警处理时长，单位：分钟）
```sql
(ar."process_time" - ar."alarm_time") * 1440
```

## 核心业务表结构

### device（设备表）
  id(BIGINT), device_code(VARCHAR), device_name(VARCHAR), category_id(BIGINT),
  space_id(BIGINT), venue_id(BIGINT), run_state(VARCHAR), device_type(VARCHAR),
  last_gather_time(TIMESTAMP), create_time(TIMESTAMP)

### alarm_record（告警记录）
  id(BIGINT), device_id(BIGINT), device_name(VARCHAR), space_id(BIGINT),
  space_name(VARCHAR), alarm_content(TEXT), alarm_time(TIMESTAMP),
  alarm_category_name(VARCHAR), alarm_level_name(VARCHAR), alarm_status(VARCHAR),
  alarm_rule_id(BIGINT), charge_person_name(VARCHAR), process_time(TIMESTAMP)

### data_day（设备日数据）
  id(BIGINT), device_id(BIGINT), value(DECIMAL), time(TIMESTAMP)

### data_hour（设备小时数据）
  id(BIGINT), device_id(BIGINT), value(DECIMAL), time(TIMESTAMP),
  start_value(DECIMAL), end_value(DECIMAL), compute_value(DECIMAL)

### equipment_category（设备类型）
  id(BIGINT), category_name(VARCHAR), full_name(VARCHAR), pid(BIGINT), has_child(VARCHAR)

### table_venue_info（会展场馆）
  id(BIGINT), venue_name(VARCHAR2), location(VARCHAR2), area(VARCHAR2),
  floors(BIGINT), orientation(VARCHAR2), longitude(DECIMAL), latitude(DECIMAL)

### space（空间表）
  id(BIGINT), space_name(VARCHAR), full_name(VARCHAR), full_id(VARCHAR), pid(BIGINT), has_child(VARCHAR)

### metering_point（计量点）
  id(BIGINT), node_name(VARCHAR), node_code(VARCHAR), type(VARCHAR),
  category_id(BIGINT), space_id(BIGINT), metering_unit(BIGINT)

### metering_point_data_day（计量点日数据）
  id(BIGINT), metering_point_id(BIGINT), time(TIMESTAMP), value(DECIMAL)

### table_personnel_statistics（人员统计）
  id(BIGINT), stat_date(DATE), today_entry_count(BIGINT), current_in_count(BIGINT),
  recognition_record_count(BIGINT), abnormal_warning_count(BIGINT)

### table_venue_flow（场馆客流）
  id(BIGINT), data_date(DATE), venue_id(BIGINT), today_in_count(BIGINT),
  today_now_count(BIGINT), max_count(BIGINT), max_time(TIME), average_duration(DOUBLE), status(TINYINT)

### lighting_area（照明区域）
  id(BIGINT), area_name(VARCHAR), area_code(VARCHAR), status(VARCHAR),
  space_name(VARCHAR), type(VARCHAR), all_duration(BIGINT)

### lighting_circuit（照明回路）
  id(BIGINT), circuit_name(VARCHAR), circuit_code(VARCHAR), status(VARCHAR),
  area_id(BIGINT), all_duration(BIGINT), comstat(VARCHAR)

### ai_report_history（AI报告历史）
  id(BIGINT), report_type(VARCHAR), title(VARCHAR), content(CLOB),
  summary(VARCHAR), time_range(VARCHAR), target_name(VARCHAR),
  scope(VARCHAR), created_at(TIMESTAMP)

### carbon_emission_factor（碳排放因子）
  id(VARCHAR), carbon_factor_name(VARCHAR), coefficient(VARCHAR), unit(VARCHAR)

### standard_coal_coefficient（标准煤系数）
  id(VARCHAR), energy_medium(VARCHAR), unit(VARCHAR), eccsc(VARCHAR), ecf(VARCHAR)

### table_parking_count（停车场统计）
  id(BIGINT), date(DATE), today_entry_count(BIGINT), current_in_count(BIGINT),
  remaining_space_count(BIGINT), average_parking_duration(DOUBLE)

## 重要约束
- 设备通过 venue_id 关联会展场馆（table_venue_info.id）
- 设备通过 space_id 关联空间（space.id）
- 告警通过 device_id 关联设备（device.id）
- 计量点数据通过 metering_point_id 关联计量点（metering_point.id）
- 所有时间字段用单引号包裹，如 alarm_time >= '2026-01-01'
"""


class ChatService:
    """聊天服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def get_last_user_question(self, messages: List[ChatMessage]) -> str:
        """获取最后一个用户问题"""
        for msg in reversed(messages):
            if msg.role == "user" and msg.content.strip():
                return msg.content
        return messages[-1].content if messages else ""

    def build_payload(self, body: ChatStreamRequest) -> dict[str, Any]:
        """构建 Ollama 请求 payload"""
        logger.info(
            "chat-stream model=%s num_gpu=%s num_ctx=%s think=%s",
            self.ollama.model,
            self.ollama.num_gpu,
            body.num_ctx,
            self.ollama.think,
        )
        return self.ollama.build_chat_payload(
            messages=[m.model_dump() for m in body.messages],
            temperature=body.temperature,
            num_ctx=body.num_ctx,
        )

    def _detect_db_related(self, question: str) -> bool:
        """判断用户问题是否与达梦数据库相关（关键词兜底 + LLM 辅助）"""
        q = question.lower()

        # 第一层：确定性关键词匹配（最高优先级）
        db_keywords = [
            # 设备/状态
            "设备", "离线", "在线", "运行状态", "设备数量", "设备统计",
            # 告警
            "告警", "报警", "故障", "停机", "异常",
            # 能耗/碳排放
            "能耗", "电耗", "水耗", "用能", "碳排放", "碳排放量", "碳强度",
            # 场馆/空间
            "场馆", "会展", "空间", "区域", "楼层", "建筑",
            # 客流/人员
            "客流", "人流量", "入场", "出场", "访客", "人员",
            # 停车
            "停车", "车位", "车辆", "停车场",
            # 照明
            "照明", "灯光", "回路",
            # 数据/统计/报表
            "数据", "统计", "报表", "报告", "记录", "查询", "分析",
            # 计量
            "计量", "计量点", "分时",
        ]
        if any(kw in q for kw in db_keywords):
            return True

        # 第二层：LLM 辅助判断（用于模糊场景）
        detect_prompt = f"""用户问题：{question}

判断这个问题是否需要查询达梦数据库才能回答。
以下情况需要：询问数量、统计、记录、状态、数据、报表、报告等业务数据。
以下情况不需要：问候、闲聊、纯知识问答、概念解释。

直接回答"是"或"否"，不要解释。"""
        try:
            response = self.ollama.call_llm([
                {"role": "user", "content": detect_prompt}
            ], temperature=0.1)
            answer = response.strip().lower()
            return "是" in answer or "yes" in answer or "true" in answer
        except Exception as e:
            logger.warning(f"数据库关联检测失败: {e}，默认走通用回答")
            return False

    def _generate_sql(self, question: str) -> Optional[str]:
        """根据用户问题生成 SQL 查询语句（支持重试）"""

        # 根据问题关键词，推测可能涉及的表
        q = question.lower()
        table_hints = []
        if any(k in q for k in ["设备", "离线", "在线", "运行"]):
            table_hints.append("device（设备表：device_name, device_type, run_state, last_gather_time）")
        if any(k in q for k in ["告警", "报警", "故障", "停机"]):
            table_hints.append("alarm_record（告警记录：device_name, alarm_time, alarm_category_name, alarm_level_name, alarm_status）")
        if any(k in q for k in ["能耗", "电", "水", "气", "热", "用能"]):
            table_hints.append("data_day（设备日数据：device_id, value, time）")
        if any(k in q for k in ["场馆", "会展", "场馆信息"]):
            table_hints.append("table_venue_info（场馆信息：venue_name, location, area, floors）")
        if any(k in q for k in ["空间", "区域", "楼层"]):
            table_hints.append("space（空间表：space_name, full_name, full_id）")
        if any(k in q for k in ["客流", "入场", "出场", "访客"]):
            table_hints.append("table_venue_flow（场馆客流：data_date, today_in_count, today_now_count, max_count）")
        if any(k in q for k in ["人员", "人员统计"]):
            table_hints.append("table_personnel_statistics（人员统计：stat_date, today_entry_count, current_in_count）")
        if any(k in q for k in ["停车", "车位", "停车场"]):
            table_hints.append("table_parking_count（停车场统计：date, today_entry_count, current_in_count, remaining_space_count）")
        if any(k in q for k in ["照明", "灯光", "回路"]):
            table_hints.append("lighting_area（照明区域）/ lighting_circuit（照明回路）")
        if any(k in q for k in ["计量", "分时"]):
            table_hints.append("metering_point_data_day（计量点日数据）/ metering_point（计量点）")
        if any(k in q for k in ["碳", "碳排放", "碳强度"]):
            table_hints.append("carbon_emission_factor（碳排放因子）/ data_day（能耗数据）")
        if any(k in q for k in ["报告", "ai报告", "报表"]):
            table_hints.append("ai_report_history（AI报告历史：report_type, title, created_at）")
        if any(k in q for k in ["设备类型", "category", "分类"]):
            table_hints.append("equipment_category（设备类型：category_name, full_name）")

        hint_text = ""
        if table_hints:
            hint_text = f"\n\n## 可能的关联表（根据问题推断）\n" + "\n".join(f"- {t}" for t in table_hints)

        base_prompt = f"""{DAMENG_SCHEMA_CONTEXT}{hint_text}

## 任务
根据用户问题生成一条达梦数据库 SQL 查询语句。

用户问题：{question}

## 要求
1. 只生成 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP 等任何修改操作
2. 表名格式：FWBZ."table_name"
3. 字段名格式：用双引号包裹（如 "device_name"），禁止裸列名
4. 日期常量用单引号（如 '2026-08-01'）
5. 合理使用聚合函数（COUNT/SUM/AVG/MAX/MIN）和 GROUP BY
6. LIMIT 最多100条（达梦用 ROWNUM 或 FETCH FIRST n ROWS ONLY）
7. 必须可以实际执行，不要生成假设性数据
8. 禁止使用 DATE() 函数，用 CAST(col AS DATE) 或 TRUNC(col)
9. 时间差计算用 (end_time - start_time) * 1440，不用 TIMESTAMPDIFF()
10. NULL 处理用 NVL(a, b)，不用 IFNULL()

## 输出格式
直接输出 SQL 语句，不要任何解释，不要用 markdown 代码块包裹。
"""
        for attempt in range(2):
            try:
                response = self.ollama.call_llm([
                    {"role": "user", "content": base_prompt}
                ], temperature=0.1)
                sql = response.strip()
                sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE)
                sql = re.sub(r'^```\s*', '', sql)
                sql = re.sub(r'\s*```$', '', sql)
                sql = sql.strip()

                # 基础验证：必须包含 SELECT 和 FROM
                if sql.upper().startswith('SELECT') and 'FROM' in sql.upper():
                    # 清理 AS 别名（避免达梦中文别名编码问题）
                    sql = re.sub(r'\s+AS\s+"[^"]+"\s*', ' ', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'\s+AS\s+\'[^\']*\'\s*', ' ', sql, flags=re.IGNORECASE)

                    # 如果有 GROUP BY，移除未分组的非聚合列（如 "id"）
                    if 'GROUP BY' in sql.upper():
                        sql = self._fix_group_by(sql)

                    return sql
                else:
                    logger.warning(f"SQL 生成结果无效（attempt {attempt+1}）: {sql}")

            except Exception as e:
                logger.error(f"SQL 生成失败（attempt {attempt+1}）: {e}")

        return None

    def _execute_sql(self, sql: str) -> tuple[Optional[List[dict]], Optional[str]]:
        """执行 SQL 并返回结果"""
        try:
            # 安全检查：禁止危险操作（单词边界匹配，避免误伤 create_time 等列名）
            import re
            sql_upper = sql.upper()
            # INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER 用单词边界检测
            if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\b', sql_upper):
                logger.warning(f"SQL 安全检查拒绝（危险关键词）: {sql[:100]}")
                return None, "禁止执行非查询语句"
            if re.search(r'\bCREATE\b', sql_upper):
                # CREATE 作为独立单词检测（排除 CREATE_TIME 这类列名）
                # 只有出现在句首或前面有分号的才是 DDL
                safe_pattern = r'(?:^|[;])\s*CREATE\b|^\s*CREATE\s+'
                if not re.search(safe_pattern, sql_upper):
                    pass  # CREATE_TIME 等列名是安全的
                else:
                    logger.warning(f"SQL 安全检查拒绝（CREATE DDL）: {sql[:100]}")
                    return None, "禁止执行非查询语句"

            results = execute_query(sql)
            return results, None
        except Exception as e:
            return None, str(e)

    def _build_vue_table(self, data: List[dict]) -> dict:
        """根据查询结果构建 Vue table 结构"""
        if not data:
            return {"columns": [], "rows": []}

        columns = []
        rows = []
        sample = data[0]

        for key in sample.keys():
            # 提取原始列名（去掉 SUM()/AVG()/COUNT() 等函数包裹）
            clean_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$', r'\2', key, flags=re.IGNORECASE)
            clean_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*([^)]+)\s*\)$', r'\2', clean_key, flags=re.IGNORECASE)

            # 排除 id 列
            if clean_key.lower() in ('id', 'bigint'):
                continue

            # 格式化列为中文标签
            label = self._format_column_label(clean_key)

            # 聚合函数的列添加"总和/平均/计数"后缀
            if re.match(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(', key, re.IGNORECASE):
                agg_map = {"SUM": "总和", "AVG": "平均值", "COUNT": "计数", "MAX": "最大值", "MIN": "最小值"}
                agg = re.match(r'^(SUM|AVG|COUNT|MAX|MIN)', key, re.IGNORECASE).group(1).upper()
                label = self._format_column_label(clean_key) + f"({agg_map.get(agg, agg)})"

            columns.append({
                "key": clean_key,
                "label": label,
                "width": "auto"
            })

        for row in data[:100]:
            formatted_row = {}
            for k, v in row.items():
                # 提取原始列名
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$', r'\2', k, flags=re.IGNORECASE)
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*([^)]+)\s*\)$', r'\2', clean_k, flags=re.IGNORECASE)
                # 排除 id 列
                if clean_k.lower() in ('id', 'bigint'):
                    continue
                if v is None:
                    formatted_row[clean_k] = "-"
                elif isinstance(v, Decimal):
                    formatted_row[clean_k] = round(float(v), 2)
                elif isinstance(v, datetime):
                    formatted_row[clean_k] = v.strftime("%Y-%m-%d")
                elif hasattr(v, 'strftime'):  # date 对象
                    formatted_row[clean_k] = v.strftime("%Y-%m-%d")
                else:
                    formatted_row[clean_k] = v
            rows.append(formatted_row)

        return {"columns": columns, "rows": rows}

    def _fix_group_by(self, sql: str) -> str:
        """
        修复 GROUP BY 语句：移除 SELECT 中未分组的非聚合列。
        例如：SELECT "id", "date", SUM("value") FROM ... GROUP BY "date"
        会变成：SELECT "date", SUM("value") FROM ... GROUP BY "date"
        """
        try:
            # 提取 GROUP BY 部分
            group_by_match = re.search(r'GROUP BY\s+(.+?)(?=\s+ORDER|\s+LIMIT|\s*$|$)', sql, re.IGNORECASE)
            if not group_by_match:
                return sql

            group_by_part = group_by_match.group(1)
            # 提取 GROUP BY 中的列名（保留原始大小写用于替换 ORDER BY）
            grouped_cols = set()
            grouped_col_originals = {}
            for col_match in re.finditer(r'"([^"]+)"', group_by_part):
                col = col_match.group(1)
                grouped_cols.add(col.lower())
                grouped_col_originals[col.lower()] = col

            # 提取 SELECT 和 FROM 之间的部分
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE)
            if not select_match:
                return sql

            select_content = select_match.group(1)
            # 解析每个 SELECT 项
            new_select_items = []
            for item_match in re.finditer(r'(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\([^)]+\)|"[^"]+"|\'[^\']+\'', select_content, re.IGNORECASE):
                item = item_match.group(0).strip()
                item_upper = item.upper()

                # 聚合函数保留
                if any(item_upper.startswith(f'{agg}') for agg in ['SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'COALESCE']):
                    new_select_items.append(item)
                    continue

                # 去掉引号判断是否在 GROUP BY 中
                col_name = item.strip('"').strip("'").lower()
                if col_name in grouped_cols:
                    new_select_items.append(item)

            if not new_select_items:
                return sql

            # 重建 SELECT
            new_select = ', '.join(new_select_items)
            sql = re.sub(
                r'SELECT\s+.+?\s+FROM',
                f'SELECT {new_select} FROM',
                sql,
                count=1,
                flags=re.IGNORECASE
            )

            # 修正 ORDER BY：把不在 GROUP BY 中的列替换为第一个 GROUP BY 列
            if grouped_col_originals:
                first_col = '"' + list(grouped_col_originals.values())[0] + '"'
                # 匹配 ORDER BY 后面跟的列名（可能带ASC/DESC）
                def replace_order_col(m):
                    order_part = m.group(1)
                    # 提取列名
                    col_m = re.search(r'"([^"]+)"', order_part)
                    if col_m:
                        col_lower = col_m.group(1).lower()
                        if col_lower not in grouped_cols:
                            # 替换为 GROUP BY 第一列
                            direction = re.search(r'\b(ASC|DESC)\b', order_part, re.IGNORECASE)
                            dir_str = ' ' + direction.group(0).upper() if direction else ''
                            return f'ORDER BY {first_col}{dir_str}'
                    return m.group(0)

                sql = re.sub(r'ORDER BY\s+("?[^"\s,]+"?\s*(?:ASC|DESC)?)', replace_order_col, sql, flags=re.IGNORECASE)

            logger.info(f"GROUP BY 修复: {sql}")
        except Exception as e:
            logger.warning(f"GROUP BY 修复失败: {e}")

        return sql

    def _format_column_label(self, col_name: str) -> str:
        """将英文列名格式化为中文标签"""
        mapping = {
            "device_name": "设备名称", "device_code": "设备编码", "device_type": "设备类型",
            "category_name": "类型名称", "full_name": "完整名称", "space_name": "空间名称",
            "venue_name": "场馆名称", "area": "面积", "location": "位置",
            "run_state": "运行状态", "alarm_content": "告警内容", "alarm_time": "告警时间",
            "alarm_category_name": "告警类别", "alarm_level_name": "告警级别",
            "alarm_status": "告警状态", "alarm_count": "告警数量",
            "total_count": "总数", "online_count": "在线数", "offline_count": "离线数",
            "total_value": "总数值", "avg_value": "平均值", "max_value": "最大值",
            "min_value": "最小值", "stat_date": "统计日期", "data_date": "日期",
            "today_in_count": "今日入场", "current_in_count": "当前人数",
            "max_count": "最大人数", "average_duration": "平均时长",
            "today_entry_count": "入场人数", "remaining_space_count": "剩余车位数",
            "area_name": "区域名称", "circuit_name": "回路名称", "status": "状态",
            "node_name": "节点名称", "node_code": "节点编码",
            "value": "数值", "total_energy": "总能耗", "carbon_emission": "碳排放",
            "report_type": "报告类型", "title": "标题", "summary": "摘要",
            "created_at": "创建时间", "time_range": "时间范围",
            "id": "ID", "count": "数量", "percentage": "占比"
        }
        # 优先精确匹配
        if col_name in mapping:
            return mapping[col_name]
        # 其次模糊匹配（下划线转中文）
        result = col_name.replace("_", " ")
        return result.title()

    def _build_echarts(self, data: List[dict], question: str) -> dict:
        """根据查询结果构建 ECharts 配置"""
        if not data:
            return {}

        sample = data[0]
        keys = list(sample.keys())

        # 找分类列（日期/字符串类型，排除 id 等）
        cat_key = None
        cat_key_raw = None
        for k in keys:
            v = sample.get(k)
            if k.lower() not in ['id', 'bigint'] and isinstance(v, (str, datetime, date)):
                cat_key_raw = k
                # 清理函数包裹
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*"([^"]+)"\s*\)$', r'\2', k, flags=re.IGNORECASE)
                cat_key = clean_k
                break

        # 找数值列（包含聚合函数列）
        num_candidates = [k for k in keys if isinstance(sample.get(k), (int, float, Decimal))]
        numeric_keys = [
            k for k in num_candidates
            if not re.match(r'^(id|bigint)$', k, re.IGNORECASE)
        ]

        if not cat_key or not numeric_keys:
            return {}

        first_num_key = numeric_keys[0]
        clean_num_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*"([^"]+)"\s*\)$', r'\2', first_num_key, flags=re.IGNORECASE)
        label = self._format_column_label(clean_num_key)

        x_axis_data = [str(row.get(cat_key_raw, "")) for row in data[:20]]
        series_data = [float(row.get(first_num_key, 0) or 0) for row in data[:20]]

        chart_title = self._gen_chart_title(question, label)
        chart_id = f"chart_{datetime.now().strftime('%H%M%S%f')}"

        if len(data) <= 6:
            pie_data = [{"name": str(row.get(cat_key, "")), "value": float(row.get(first_num_key, 0) or 0)} for row in data[:20]]
            return {
                "chartType": "pie",
                "chartId": chart_id,
                "option": {
                    "title": {"text": chart_title, "left": "center"},
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                    "legend": {"bottom": 10, "left": "center"},
                    "series": [{
                        "type": "pie",
                        "radius": ["35%", "60%"],
                        "avoidLabelOverlap": False,
                        "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2},
                        "label": {"show": True, "formatter": "{b}\n{c} ({d}%)"},
                        "data": pie_data
                    }]
                }
            }
        else:
            return {
                "chartType": "bar",
                "chartId": chart_id,
                "option": {
                    "title": {"text": chart_title, "left": "center"},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "12%", "containLabel": True},
                    "xAxis": {"type": "category", "data": x_axis_data, "axisLabel": {"rotate": 30, "interval": 0}},
                    "yAxis": {"type": "value", "name": label},
                    "series": [{
                        "type": "bar",
                        "data": series_data,
                        "itemStyle": {
                            "color": {
                                "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "#5470C6"},
                                    {"offset": 1, "color": "#91CC75"}
                                ]
                            },
                            "borderRadius": [4, 4, 0, 0]
                        },
                        "label": {"show": True, "position": "top", "formatter": "{c}"}
                    }]
                }
            }

    def _gen_chart_title(self, question: str, label: str) -> str:
        """根据问题生成图表标题"""
        q_short = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', question)[:20]
        return f"{q_short} {label}分布" if q_short else f"{label}分布"

    def _generate_summary(self, question: str, data: List[dict], vue_table: dict) -> str:
        """让 LLM 根据查询结果生成简短总结（<= 200字）"""
        data_summary = self._summarize_data(data)
        prompt = f"""## 用户问题
{question}

## 查询结果摘要
{data_summary}

## Vue表格预览
列：{[c["label"] for c in vue_table.get("columns", [])]}
行数：{len(vue_table.get("rows", []))} 条

## 任务
根据以上信息，生成一段简短的总结性语句（不超过200字），说明数据的主要发现和结论。
直接输出总结内容，不要解释，不要用引号包裹。"""
        try:
            response = self.ollama.call_llm([
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            return response.strip()[:200]
        except Exception as e:
            logger.warning(f"总结生成失败: {e}")
            return f"查询返回 {len(data)} 条数据，详见下方图表和表格。"

    def _summarize_data(self, data: List[dict]) -> str:
        """将查询结果压缩为文本摘要（供总结生成用）"""
        if not data:
            return "无数据"
        sample = data[0]
        keys = list(sample.keys())
        # 取前5条数据的关键字段
        lines = []
        for i, row in enumerate(data[:5]):
            vals = []
            for k in keys[:4]:  # 最多4个字段
                v = row.get(k)
                if v is None:
                    vals.append("空")
                elif isinstance(v, Decimal):
                    vals.append(f"{float(v):.2f}")
                else:
                    vals.append(str(v)[:20])
            lines.append(f"第{i+1}行: " + ", ".join(vals))
        more = f"\n...共 {len(data)} 条数据" if len(data) > 5 else ""
        return "\n".join(lines) + more

    def _safe_json_dumps(self, obj: Any) -> str:
        """安全的 JSON 序列化（处理 Decimal、datetime、date 等类型）"""
        def default(o):
            if isinstance(o, Decimal):
                return float(o)
            if isinstance(o, datetime):
                return o.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(o, 'strftime') and callable(o.strftime):  # date 对象
                return o.strftime("%Y-%m-%d")
            if hasattr(o, '__dict__'):
                return o.__dict__
            return str(o)
        return json.dumps(obj, ensure_ascii=False, default=default)

    async def stream_chat(
        self,
        payload: dict[str, Any],
        *,
        question: str,
        access_time: datetime,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        on_summary: Optional[callable] = None,
    ) -> AsyncIterator[str]:
        """
        执行流式对话，产出 SSE 格式数据。
        支持两种模式：
        1. 数据库相关 → 生成SQL查询 → 返回 ECharts + Vue表格 + 总结
        2. 非数据库相关 → 直接流式 LLM 回答
        """
        full_reply = ""
        mode = "unknown"
        # 收集流式结果摘要，供日志记录
        stream_summary = {
            "mode": None,
            "sql": None,
            "table": None,
            "chart": None,
            "summary": None,
            "row_count": 0,
            "error": None,
        }

        try:
            # ========== 阶段1：判断是否数据库相关 ==========
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'detecting'})}\n\n"
            is_db_related = self._detect_db_related(question)

            if is_db_related:
                mode = "db"
                stream_summary["mode"] = "db"
                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在分析数据库...'})}\n\n"

                # ========== 阶段2：生成 SQL ==========
                sql = self._generate_sql(question)
                if not sql:
                    stream_summary["error"] = "无法生成查询语句"
                    stream_summary["summary"] = None
                    yield f"data: {self._safe_json_dumps({'type': 'error', 'message': '无法生成查询语句'})}\n\n"
                    yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                    if on_summary:
                        await on_summary(stream_summary)
                    return

                stream_summary["sql"] = sql
                yield f"data: {self._safe_json_dumps({'type': 'sql', 'sql': sql})}\n\n"
                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在执行查询...'})}\n\n"

                # ========== 阶段3：执行 SQL ==========
                data, err = self._execute_sql(sql)
                if err:
                    stream_summary["error"] = f"查询执行失败: {err}"
                    stream_summary["summary"] = None
                    yield f"data: {self._safe_json_dumps({'type': 'error', 'message': f'查询执行失败: {err}'})}\n\n"
                    yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                    if on_summary:
                        await on_summary(stream_summary)
                    return

                if not data:
                    stream_summary["error"] = "查询结果为空"
                    stream_summary["summary"] = "查询结果为空"
                    yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '查询结果为空，请尝试调整查询条件。'})}\n\n"
                    yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                    if on_summary:
                        await on_summary(stream_summary)
                    return

                stream_summary["row_count"] = len(data)

                # ========== 阶段4：构建 Vue 表格 ==========
                vue_table = self._build_vue_table(data)
                stream_summary["table"] = vue_table
                yield f"data: {self._safe_json_dumps({'type': 'table', **vue_table})}\n\n"
                await asyncio.sleep(0)

                # ========== 阶段5：构建 ECharts ==========
                echarts = self._build_echarts(data, question)
                if echarts:
                    stream_summary["chart"] = {"chartType": echarts.get("chartType"), "chartId": echarts.get("chartId")}
                    yield f"data: {self._safe_json_dumps({'type': 'chart', **echarts})}\n\n"
                    await asyncio.sleep(0)

                # ========== 阶段6：生成总结 ==========
                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
                summary = self._generate_summary(question, data, vue_table)
                summary = summary.replace('\n', ' ').replace('\r', '').strip()
                stream_summary["summary"] = summary
                yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
                await asyncio.sleep(0)

                full_reply = f"[数据库查询结果] {summary}"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)

            else:
                # ========== 非数据库相关：直接流式 LLM 回答 ==========
                mode = "llm"
                stream_summary["mode"] = "llm"
                response_parts = []
                prompt_tokens = None
                completion_tokens = None

                async for chunk in self.ollama.stream_chat(payload):
                    if chunk.get("done"):
                        prompt_tokens = chunk.get("prompt_eval_count")
                        completion_tokens = chunk.get("eval_count")
                        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                        stream_summary["summary"] = full_reply
                        if on_summary:
                            await on_summary(stream_summary)
                        break

                    message = chunk.get("message") or {}
                    delta = message.get("content") or ""
                    if delta:
                        response_parts.append(delta)
                        full_reply = "".join(response_parts)
                        yield f"data: {self._safe_json_dumps({'type': 'message', 'content': delta})}\n\n"
                        await asyncio.sleep(0)

        except httpx.ConnectError:
            stream_summary["error"] = "无法连接 Ollama"
            stream_summary["summary"] = full_reply or None
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': '无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
        except httpx.ReadTimeout:
            stream_summary["error"] = "Ollama 响应超时"
            stream_summary["summary"] = full_reply or None
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': 'Ollama 响应超时，请稍后重试'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
        except Exception as exc:
            logger.exception("stream error")
            stream_summary["error"] = f"服务异常: {exc}"
            stream_summary["summary"] = full_reply or None
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': f'服务异常: {exc}'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
        finally:
            # 写入访问日志
            total = None
            if mode == "llm":
                try:
                    # 尝试获取 token 统计（如果流式已经结束）
                    total = len(full_reply) // 4  # 粗估
                except Exception:
                    pass

            await save_access_log(
                question=question,
                access_time=access_time,
                token_count=total,
                prompt_tokens=None,
                completion_tokens=None,
                response=full_reply[:2000] if full_reply else None,
                model=self.ollama.model,
                client_ip=client_ip,
                user_agent=user_agent,
            )
