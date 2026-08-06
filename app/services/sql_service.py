"""SQL 生成服务"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.ollama import OllamaClient
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """你是一个专业的达梦数据库 SQL 生成专家，服务于首钢会展小镇智慧园区管理系统。

## 数据库信息
- 类型：Dameng (08.00.000)
- Schema：FWBZ

## 重要规则
1. **标识符引号**：所有表名和字段名必须用双引号包裹，如 "FWBZ"."alarm_record"
2. **日期函数**：达梦数据库使用 SYSDATE 获取当前时间，日期比较可直接用字符串如 '2026-01-01'
3. **分页语法**：使用 LIMIT {limit} OFFSET {offset}
4. **安全限制**：只生成 SELECT 查询，禁止 INSERT/UPDATE/DELETE/ALTER
5. **NULL 处理**：使用 IS NULL / IS NOT NULL，不要用 = NULL

## 常见业务查询模式

### 模式1：按时间范围统计
当用户问"最近7天/本月/本年的XXX"时：
```sql
SELECT COUNT(*) FROM "FWBZ"."alarm_record"
WHERE "alarm_time" >= DATE_SUB(SYSDATE, INTERVAL 7 DAY)
```

### 模式2：按类别分组统计
当用户问"按XXX统计数量/汇总"时，使用 GROUP BY + COUNT/SUM：
```sql
SELECT "alarm_category_name", COUNT(*) as cnt
FROM "FWBZ"."alarm_record"
WHERE "alarm_time" >= DATE_SUB(SYSDATE, INTERVAL 7 DAY)
GROUP BY "alarm_category_name"
ORDER BY cnt DESC
```

### 模式3：设备与告警关联
通过 device_id 或 device_name 关联：
```sql
SELECT d."device_name", COUNT(a."id") as alarm_count
FROM "FWBZ"."device" d
LEFT JOIN "FWBZ"."alarm_record" a ON d."id" = a."device_id"
WHERE d."device_type" = '2'
GROUP BY d."device_name"
```

### 模式4：能耗数据查询
```sql
SELECT dd."time", SUM(dd."value") as total_value
FROM "FWBZ"."data_day" dd
WHERE dd."time" >= DATE_SUB(SYSDATE, INTERVAL 30 DAY)
GROUP BY dd."time"
ORDER BY dd."time"
```

### 模式5：客流数据统计
```sql
SELECT "today_in_count", "today_now_count", "max_count", "average_duration"
FROM "FWBZ"."table_venue_flow"
WHERE "data_date" = CURRENT_DATE
```

## 理解业务术语
- "告警/报警/警报" → alarm_record
- "设备/仪表" → device
- "能耗/用电/电量" → data_day
- "客流/人数/访客" → table_venue_flow
- "空间/区域/位置" → space
- "设备类别/专业" → equipment_category
- "展会/活动/会议" → table_activeMeet_info
- "人员统计" → table_personnel_statistics

请根据用户的问题，参考以下表结构信息生成准确的 SQL 查询语句。
"""

DEVICE_QUESTION_TEMPLATE = """## 表结构信息
{schema_info}

## 当前任务
设备ID: {device_id}

用户问题: {question}

请生成对应的 SQL 查询语句（只生成一条SQL，必须包含设备ID的过滤条件）："""

USER_TEMPLATE = """## 表结构信息
{schema_info}

## 历史对话
{history}

## 当前问题
{question}

请生成对应的 SQL 查询语句："""


class SQLService:
    """SQL 生成服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def build_prompt(self, question: str, history: List[ChatMessage]) -> Tuple[str, str]:
        """构建 SQL 生成的 prompt"""
        schema_info = self._extract_schema_info()
        history_text = self._format_history(history)

        user_prompt = USER_TEMPLATE.format(
            schema_info=schema_info,
            history=history_text,
            question=question,
        )
        return SYSTEM_PROMPT, user_prompt

    def build_device_prompt(self, device_id: int, question: str) -> Tuple[str, str]:
        """构建基于设备ID的 SQL 生成 prompt"""
        schema_info = self._extract_schema_info()

        user_prompt = DEVICE_QUESTION_TEMPLATE.format(
            schema_info=schema_info,
            device_id=device_id,
            question=question,
        )
        return SYSTEM_PROMPT, user_prompt

    def _extract_schema_info(self) -> str:
        """提取表结构信息用于生成 prompt"""
        query_config = settings.query_config
        if not query_config:
            return "未找到表结构配置"

        lines = []
        db_info = query_config.get("database", {})
        lines.append(f"数据库: {db_info.get('name', 'N/A')}")
        lines.append(f"Schema: {db_info.get('schema', 'FWBZ')}")
        lines.append("")

        tables = query_config.get("tables", {})
        for table_name, table_info in tables.items():
            lines.append(f"【{table_info.get('name', table_name)}】 - {table_info.get('description', '')}")
            fields = table_info.get("fields", {})
            for field_name, field_info in fields.items():
                desc = field_info.get("desc", "")
                ftype = field_info.get("type", "")
                flags = []
                if field_info.get("searchable"):
                    flags.append("可搜索")
                if field_info.get("filterable"):
                    flags.append("可筛选")
                if field_info.get("groupable"):
                    flags.append("可分组")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                lines.append(f"  - {field_name}: {ftype} - {desc}{flag_str}")
            lines.append("")

        return "\n".join(lines)

    def _format_history(self, history: List[ChatMessage]) -> str:
        """格式化历史对话"""
        if not history:
            return "（无历史对话）"

        lines = []
        for msg in history:
            role = "用户" if msg.role == "user" else "助手"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    def extract_sql(self, response: str) -> Tuple[str, Optional[str]]:
        """从模型回复中提取 SQL 和说明"""
        # 尝试提取 ```sql ... ``` 包裹的 SQL
        sql_pattern = r"```sql\s*(.*?)\s*```"
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            sql = match.group(1).strip()
            explanation = response.replace(match.group(0), "").strip()
            if explanation:
                return sql, explanation
            return sql, None

        # 如果没有代码块，检查是否包含 SELECT 语句
        select_pattern = r"(SELECT\s+.*?)(?:;|$)"
        match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            sql = match.group(1).strip()
            parts = response.split(sql, 1)
            if len(parts) > 1 and len(parts[0].strip()) > 10:
                return sql, parts[0].strip()
            return sql, None

        # 没有识别到 SQL，返回原内容作为说明
        return "", response.strip()

    async def generate_sql(self, question: str, history: List[ChatMessage]) -> Tuple[str, Optional[str]]:
        """调用大模型生成 SQL"""
        system_prompt, user_prompt = self.build_prompt(question, history)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("生成 SQL，问题: %s", question[:100])

        payload = self.ollama.build_sql_payload(messages)
        response_text = await self.ollama.chat(payload)

        return self.extract_sql(response_text)

    async def generate_sql_by_device(
        self,
        device_id: int,
        question: str = "查询该设备的基本信息和运行状态"
    ) -> Tuple[str, Optional[str]]:
        """根据设备ID调用大模型生成 SQL"""
        system_prompt, user_prompt = self.build_device_prompt(device_id, question)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("根据设备ID生成 SQL，device_id: %d, 问题: %s", device_id, question)

        payload = self.ollama.build_sql_payload(messages)
        response_text = await self.ollama.chat(payload)

        return self.extract_sql(response_text)

    async def generate_report_sql(
        self,
        report_type: str,
        target_id: int,
        target_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        根据报告类型和目标ID，生成包含所有指标的SQL列表

        Args:
            report_type: 报告类型 (device/venue/exhibition)
            target_id: 目标ID (设备ID/场馆ID/展会ID)
            target_name: 目标名称(可选)

        Returns:
            包含指标名称和SQL的列表
        """
        # 定义每种报告类型对应的指标
        if report_type == "device":
            metrics = self._get_device_report_metrics(target_id, target_name)
        elif report_type == "venue":
            metrics = self._get_venue_report_metrics(target_id, target_name)
        elif report_type == "exhibition":
            metrics = self._get_exhibition_report_metrics(target_id, target_name)
        else:
            raise ValueError(f"不支持的报告类型: {report_type}")

        return metrics

    def _get_device_report_metrics(self, device_id: int, device_name: Optional[str]) -> List[Dict[str, Any]]:
        """获取设备报告的指标定义"""
        return [
            {
                "name": "设备基本信息",
                "description": "设备编号、名称、类型、运行状态",
                "table": "device",
                "filter_field": "id",
                "filter_value": device_id
            },
            {
                "name": "告警统计",
                "description": "该设备的告警总数",
                "table": "alarm_record",
                "filter_field": "device_id",
                "filter_value": device_id
            },
            {
                "name": "故障统计",
                "description": "该设备按告警级别统计",
                "table": "alarm_record",
                "filter_field": "device_id",
                "filter_value": device_id,
                "group_by": "alarm_level_name"
            },
            {
                "name": "能耗统计",
                "description": "该设备的日能耗数据",
                "table": "data_day",
                "filter_field": "device_id",
                "filter_value": device_id
            },
        ]

    def _get_venue_report_metrics(self, venue_id: int, venue_name: Optional[str]) -> List[Dict[str, Any]]:
        """获取场馆报告的指标定义"""
        return [
            {
                "name": "场馆基本信息",
                "description": "场馆名称、位置、楼层",
                "table": "table_venue_info",
                "filter_field": "id",
                "filter_value": venue_id
            },
            {
                "name": "客流统计",
                "description": "当日进场、在场、峰值客流",
                "table": "table_venue_flow",
                "filter_field": "venue_id",
                "filter_value": venue_id
            },
            {
                "name": "设备告警统计",
                "description": "该场馆所有设备的告警",
                "table": "alarm_record",
                "filter_field": "device_id",
                "filter_value": venue_id,
                "join_table": "device",
                "join_condition": "device.venue_id = {target_id}"
            },
            {
                "name": "能耗统计",
                "description": "该场馆所有设备的能耗汇总",
                "table": "data_day",
                "filter_field": "device_id",
                "filter_value": venue_id,
                "join_table": "device",
                "join_condition": "device.venue_id = {target_id}"
            },
        ]

    def _get_exhibition_report_metrics(self, exhibition_id: int, exhibition_name: Optional[str]) -> List[Dict[str, Any]]:
        """获取展会报告的指标定义"""
        return [
            # ===== 展会基本信息 =====
            {
                "name": "展会基本信息",
                "description": "展会名称、开始日期、预计人数",
                "category": "会展数据",
                "table": "table_activeMeet_info",
                "filter_field": "id",
                "filter_value": exhibition_id
            },

            # ===== 人员服务 =====
            {
                "name": "总服务人次",
                "description": "人员识别记录总数",
                "category": "人员服务",
                "table": "table_personnel_statistics",
                "aggregate": "SUM",
                "aggregate_field": "recognition_record_count",
                "where_extra": '"stat_date" >= (SELECT "start_date" FROM FWBZ."table_activeMeet_info" WHERE "id" = {exhibition_id})'
            },
            {
                "name": "投诉数量",
                "description": "展会期间投诉告警数量",
                "category": "人员服务",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "id",
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%投诉%\''
            },
            {
                "name": "建议数量",
                "description": "展会期间建议数量",
                "category": "人员服务",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "id",
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%建议%\''
            },
            {
                "name": "满意度评分",
                "description": "参展商满意度评分",
                "category": "人员服务",
                "table": "alarm_record",
                "aggregate": "AVG",
                "aggregate_field": "value",
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%满意%\''
            },
            {
                "name": "安保出勤",
                "description": "安保人员出勤人次",
                "category": "人员服务",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "id",
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%安保%\''
            },

            # ===== 设备与能耗 =====
            {
                "name": "设备故障数",
                "description": "展会期间设备故障告警数量",
                "category": "设备能耗",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "id",
                "date_field": "alarm_time",
                "where_extra": 'alarm_level_name LIKE \'%故障%\''
            },
            {
                "name": "平均修复时长",
                "description": "故障平均修复时长(分钟)",
                "category": "设备能耗",
                "table": "alarm_record",
                "aggregate": "AVG",
                "aggregate_field": "value",
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%修复%\''
            },
            {
                "name": "总用电量",
                "description": "展会期间所有设备能耗汇总(kWh)",
                "category": "设备能耗",
                "table": "data_day",
                "aggregate": "SUM",
                "aggregate_field": "value",
                "date_field": "time"
            },
            {
                "name": "能耗预算比",
                "description": "实际用电量占预算比例(%)",
                "category": "设备能耗",
                "table": "data_day",
                "aggregate": "SUM",
                "aggregate_field": "value",
                "date_field": "time"
            },
            {
                "name": "单人次能耗",
                "description": "人均用电量(kWh/人)",
                "category": "设备能耗",
                "table": "data_day",
                "aggregate": "AVG",
                "aggregate_field": "value",
                "date_field": "time"
            },

            # ===== 会展数据 =====
            {
                "name": "展会天数",
                "description": "展会已举办天数",
                "category": "会展数据",
                "table": "table_activeMeet_info",
                "aggregate": "DATEDIFF",
                "aggregate_field": "start_date",
                "filter_field": "id",
                "filter_value": exhibition_id
            },
            {
                "name": "总客流",
                "description": "展会期间累计进场人数",
                "category": "会展数据",
                "table": "table_venue_flow",
                "aggregate": "SUM",
                "aggregate_field": "today_in_count",
                "date_field": "data_date"
            },
            {
                "name": "峰值客流",
                "description": "展会期间单日最高进场人数",
                "category": "会展数据",
                "table": "table_venue_flow",
                "aggregate": "MAX",
                "aggregate_field": "max_count",
                "date_field": "data_date"
            },
            {
                "name": "参展商数",
                "description": "参展商数量",
                "category": "会展数据",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "charge_person_name",
                "distinct": True,
                "date_field": "alarm_time",
                "where_extra": 'alarm_category_name LIKE \'%参展%\''
            },
            {
                "name": "应急响应",
                "description": "应急事件响应次数",
                "category": "会展数据",
                "table": "alarm_record",
                "aggregate": "COUNT",
                "aggregate_field": "id",
                "date_field": "alarm_time",
                "where_extra": 'alarm_level_name LIKE \'%紧急%\''
            },
        ]


# ==================== 优化建议生成 ====================

SUGGESTIONS_SYSTEM_PROMPT = """你是一个专业的会展运营优化顾问，服务于首钢会展小镇智慧园区管理系统。

## 你的职责
根据提供的报告数据，分析问题并生成切实可行的优化建议。

## 输出要求
1. 每条建议必须具体、可执行，包含具体措施和预期效果
2. 建议应分门别类：人员服务、设备能耗、会展运营等
3. 优先指出数据中的异常值和潜在风险
4. 量化预期效果（如：降低能耗15%、节省人力成本10%）

## 建议格式
每条建议包含：
- 标题：简洁概括
- 内容：具体措施
- 预期效果：量化收益（可选）

请基于数据生成3-5条优化建议。
"""

SUGGESTIONS_USER_TEMPLATE = """## 报告信息
- 报告类型：{report_type}
- 目标ID：{target_id}
- 目标名称：{target_name}

## 关注领域
{focus_areas}

## 报告数据
{metrics_data}

请基于以上数据，生成优化建议。要求：
1. 每条建议针对具体问题
2. 包含可量化的预期效果
3. 按优先级排序
4. 返回JSON格式：
```json
[
  {{
    "title": "建议标题",
    "content": "具体措施内容",
    "impact": "预期效果",
    "category": "所属类别"
  }}
]
```
"""


class SuggestionService:
    """优化建议生成服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def build_suggestions_prompt(
        self,
        report_type: str,
        target_id: int,
        target_name: Optional[str],
        metrics: List[Dict[str, Any]],
        focus_areas: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """构建生成建议的 prompt"""
        # 格式化关注领域
        focus_text = "、".join(focus_areas) if focus_areas else "全部领域"

        # 格式化数据指标
        metrics_lines = []
        for m in metrics:
            name = m.get("name", "")
            value = m.get("value", "")
            desc = m.get("description", "")
            metrics_lines.append(f"- {name}：{value} （{desc}）" if desc else f"- {name}：{value}")

        metrics_text = "\n".join(metrics_lines) if metrics_lines else "（无数据）"

        user_prompt = SUGGESTIONS_USER_TEMPLATE.format(
            report_type=report_type,
            target_id=target_id,
            target_name=target_name or "未知",
            focus_areas=focus_text,
            metrics_data=metrics_text,
        )

        return SUGGESTIONS_SYSTEM_PROMPT, user_prompt

    def parse_suggestions(self, response: str) -> List[Dict[str, Any]]:
        """解析大模型返回的建议"""
        import json

        # 尝试提取 JSON
        json_pattern = r"```(?:json)?\s*(\[[\s\S]*?\])\s*```"
        match = re.search(json_pattern, response, re.IGNORECASE)

        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析
        try:
            # 找到 [ 开始，] 结束的范围
            start = response.find("[")
            end = response.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # 解析失败，返回原始文本
        return [{
            "title": "数据分析建议",
            "content": response.strip(),
            "impact": None,
            "category": "综合"
        }]

    async def generate_suggestions(
        self,
        report_type: str,
        target_id: int,
        target_name: Optional[str],
        metrics: List[Dict[str, Any]],
        focus_areas: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """调用大模型生成优化建议"""
        system_prompt, user_prompt = self.build_suggestions_prompt(
            report_type, target_id, target_name, metrics, focus_areas
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("生成优化建议，report_type: %s, target_id: %d", report_type, target_id)

        payload = self.ollama.build_sql_payload(messages)
        response_text = await self.ollama.chat(payload)

        return self.parse_suggestions(response_text)
