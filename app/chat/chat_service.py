"""聊天服务 - SSE 流式对话处理，支持数据库智能问答"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional

import httpx

from app.common.config import get_settings
from app.common.database import save_access_log
from app.common.dameng import execute_query
from app.common.logger import get_logger
from app.common.ollama import OllamaClient
from app.chat.meta_nl import (
    ChartPlan,
    DimJoin,
    extract_sql_tables,
    get_catalog,
    listing_type_fk,
    plan_stat_chart,
)
from app.chat.schemas import ChatMessage, ChatStreamRequest
from app.chat.sql_template_loader import extract_sql_from_chunk

settings = get_settings()
logger = get_logger("chat")


def _one_line(text: Optional[str], n: int = 240) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= n else compact[: n - 3] + "..."


def _build_schema_text() -> str:
    """
    从 config/FWBZ_strut.sql 解析真实表结构，生成供 LLM 参考的文本。
    实际解析逻辑收敛在 app.common.sql_schema_parser。
    """
    from app.common.sql_schema_parser import build_schema_text

    text = build_schema_text()
    if text:
        # 行数 ≈ "## 标题" + N × ("### table" + "  列: ..." + "")
        table_count = text.count("\n### ")
        logger.info(f"动态 schema 生成完成，共 {table_count} 个表")
    return text


# 一次性构建动态表结构（服务启动时）
_SCHEMA_TEXT: str = _build_schema_text()

# 上一轮截断查询（进程内短时记忆，供「查看全部」复用 SQL）
_VIEW_ALL_TTL_SEC = 30 * 60
_VIEW_ALL_HARD_CAP = 50000
_LAST_TRUNCATED_QUERY: dict[str, dict[str, Any]] = {}
_VIEW_ALL_PROMPT: Optional[str] = None
# 上一张可下钻统计图（无过期；仅当新问题画出新统计图时替换）
_LAST_CHART_FOLLOWUP: dict[str, dict[str, Any]] = {}
# 上一轮已执行查询（供「按照 xxx 列统计」重绘，含无图的表格结果）
_LAST_RESULT_QUERY: dict[str, dict[str, Any]] = {}

_CHART_REGROUP_RE = re.compile(
    r"(?:请)?(?:换[成成]?|改[成成]?|重新)?"
    r"(?:按照|按|用)\s*"
    r"[「『\"“']?([^」』\"”'\n]{1,24}?)[」』\"”']?\s*"
    r"(?:这一列|这一栏|列|字段|维度)?"
    r"\s*(?:来|进行)?"
    r"(?:分组统计|分组|统计|出图|画图)"
)

# 用户口语 → 结果列（按优先级）
_CHART_DIM_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("在线情况", ("online", "run_state", "status")),
    ("是否在线", ("online", "run_state", "status")),
    ("运行状态", ("run_state", "status", "online")),
    ("在线", ("online", "run_state", "status")),
    ("空间位置", ("region_name", "space_name", "area_name", "venue_name", "install_location")),
    ("安装位置", ("install_location", "region_name", "space_name")),
    ("区域名称", ("area_name", "region_name", "space_name")),
    ("区域", ("area_name", "region_name", "space_name")),
    ("位置", ("region_name", "space_name", "area_name", "venue_name")),
    ("场馆", ("venue_name", "venue_id")),
    ("设备类型", ("device_type", "dev_type_desc", "spec", "category_name")),
    ("分类名", ("category_name", "group_name", "device_kind")),
    ("分类", ("category_name", "group_name", "device_kind", "category_id")),
    ("告警类别", ("alarm_category_name",)),
    ("告警级别", ("alarm_level_name",)),
    ("状态", ("status", "run_state", "online")),
)


# 达梦数据库 Schema 上下文（供 LLM 生成 SQL 使用）
DAMENG_SCHEMA_CONTEXT = """
## 达梦数据库信息
- 类型：Dameng 8.0 (08.00.000)
- Schema：FWBZ
- 标识符引号：达梦大小写敏感，**所有表名和字段名必须用双引号包裹**，如 `"device"."device_name"`、`"alarm_time"`。
- 自增列：使用序列 FWBZ.SEQ_xxx，不支持 AUTO_INCREMENT

## 表结构白名单

每个表名、列名必须出现在上方「数据库真实表结构」中。不确定就回查列表，禁止凭记忆编造。
禁止臆造列；该带的外键不要漏。问设备信息/介绍设备时，`device` 必须选出 `"category_id"`，不要只选 `"device_name"` 和 `"run_state"`。

**按表选用外键（同一列名在不同表含义不同，不要做成全局禁用）：**

| 表 | 设备类型 | 空间 | 场馆 | 不要用 |
|---|---|---|---|---|
| device | category_id | space_id | venue_id | device_category_id、area_id |
| alarm_record | device_category_id | space_id | venue_id | category_id、area_id |
| lighting_area | （无） | space / space_name（文本） | （无） | space_id、create_time、area_id |
| table_parking_count | （无） | （无） | （无） | data_date（日期列是 date） |

- 告警关联规则表是 `alarm_rules`，没有 `alarm_rule_point` 表
- 客流用 `table_venue_flow_hour`，在馆人数列是 `today_now_count`（不要用 `now_count`）
- 明细列不要起中文别名，前端会映射；聚合可用 `AS cnt` / `AS value`

## ⚠️ 语法限制（严格遵守，禁止使用 MySQL, PostgreSQL, Oracle, SqlServer 语法）

| 错误写法（MySQL）     | 正确写法（达梦 8.0）                           |
|---------------------|----------------------------------------------|
| DATE(col)           | CAST(col AS DATE) 或 TRUNC(col)               |
| DATE_FORMAT(col, '%Y-%m-%d') | TO_CHAR(col, 'YYYY-MM-DD')                   |
| DATE_FORMAT(col, '%Y-%m-%d %H:%i:%s') | TO_CHAR(col, 'YYYY-MM-DD HH24:MI:SS') |
| IFNULL(a,b)         | NVL(a, b) 或 COALESCE(a, b)                   |
| IF(cond,a,b)        | CASE WHEN cond THEN a ELSE b END              |
| NOW()               | SYSDATE                                       |
| TIMESTAMPDIFF(MINUTE,a,b) | DATEDIFF(MINUTE, a, b)                      |
| DATE_SUB(col, INTERVAL 1 DAY) | col - 1                                     |
| DATE_ADD(col, INTERVAL 1 DAY) | col + 1                                     |
| DATE_SUB(col, INTERVAL 1 HOUR) | col - 1/24                                 |
| DATE_SUB(col, INTERVAL 30 MINUTE) | col - 30/1440                             |
| DATEDIFF(a,b)       | DATEDIFF(MINUTE, a, b)                       |
| YEAR(col)           | EXTRACT(YEAR FROM col) 或 TO_CHAR(col, 'YYYY') |
| MONTH(col)          | EXTRACT(MONTH FROM col) 或 TO_CHAR(col, 'MM') |
| DAY(col)            | EXTRACT(DAY FROM col) 或 TO_CHAR(col, 'DD') |
| CONCAT_WS(sep, ...) | col1 || sep || col2 || ...                    |
| FLOOR(col)          | TRUNC(col) 或 FLOOR(col)（达梦都支持）        |
| ROUND(col, n)       | ROUND(col, n)（达梦原生支持）                 |
| LENGTH(str)         | LENGTH(str)（达梦原生支持）                   |
| SUBSTRING(str, pos, len) | SUBSTR(str, pos, len)                    |
| GROUP_CONCAT(col)   | LISTAGG(col, ',')                            |

## ⚠️ SQL 语法强制规则（必须遵守）

1. **分页语法**：只使用 `LIMIT n OFFSET m`，禁止使用 ROWNUM、FETCH FIRST、TOP、WHERE ROWNUM 等其他分页写法。

2. **WHERE 子句位置**：WHERE 必须放在 ORDER BY **之前**，禁止把 WHERE 写到 ORDER BY 后面。

3. **禁止占位条件**：禁止生成 `WHERE 0`、`WHERE 1=0`、`WHERE 1=1` 等无意义条件。如果用户没有指定过滤条件，**直接省略 WHERE 子句**，不要自己编造条件。

4. **禁止不完整的 WHERE**：不要在 WHERE 后面留空条件或未完成的表达式。

5. **禁止在函数调用外层包裹双引号**：`DATEDIFF(MINUTE, "alarm_time", "event_completion_time")` 本身是正确的（参数列名有双引号）；但禁止把整个函数调用用双引号包裹，如 `"DATEDIFF(MINUTE, "alarm_time", "event_completion_time")"` 是错误的。ORDER BY 等子句中引用函数时同样禁止在最外层加双引号。

6. **列别名**：明细查询不要给真实列起中文别名。聚合可用 `AS cnt`。禁止 `AS '中文'`（单引号是字符串）。

7. **GROUP BY 规则**：SELECT 中所有非聚合列必须出现在 GROUP BY 中（标准SQL要求），否则会报错。

8. **字符串比较**：字符串比较默认区分大小写。如需不区分大小写，使用 `UPPER(col) = UPPER('value')` 或 `LOWER(col) = LOWER('value')`。

9. **ORDER BY 与 GROUP BY 约束**：当 SQL 包含 GROUP BY 时，ORDER BY 中的列必须满足以下条件之一，否则会报错 "no such group"：
   - 该列出现在 SELECT 列表中（可以是聚合函数的结果，如 `COUNT(*)`、`SUM(...)`，直接用别名排序）
   - 该列出现在 GROUP BY 子句中

   **正确示例**：
   ```sql
   -- ✅ 正确：ORDER BY 使用 GROUP BY 列（照明回路按回路名分组统计）
   SELECT "circuit_name", COUNT(*) AS circuit_count, SUM("all_duration") AS total_duration
   FROM FWBZ."lighting_circuit"
   GROUP BY "circuit_name"
   ORDER BY "circuit_name" DESC;

   -- ✅ 正确：ORDER BY 使用聚合函数（照明区域按告警数排序）
   SELECT "id", "area_name", COUNT(*) AS alarm_count, SUM("all_duration") AS total_duration
   FROM FWBZ."lighting_area"
   GROUP BY "id", "area_name"
   ORDER BY COUNT(*) DESC;
   ```

## LIMIT 分页示例（达梦）
```sql
-- 取前 500 条
SELECT "id", "device_name" FROM FWBZ."device"
ORDER BY "create_time" DESC
LIMIT 500 OFFSET 0

-- 取第 11~20 条（即跳过前10条，取10条）
SELECT "id", "device_name" FROM FWBZ."device"
ORDER BY "create_time" DESC
LIMIT 10 OFFSET 10
```

## 告警处理时长计算（告警处理时长，单位：分钟）
重要：alarm_time 是 TIMESTAMP 类型，禁止直接相减！

正确写法：
```sql
-- 使用 DATEDIFF 函数（达梦原生支持）
DATEDIFF(MINUTE, "alarm_time", "event_completion_time") AS 处理时长分钟数

-- ORDER BY 用别名：
ORDER BY 处理时长分钟数 ASC
```

错误写法（禁止使用）：
```sql
-- ❌ 禁止：直接相减，TIMESTAMP 类型不支持算术运算
("event_completion_time" - "alarm_time") * 1440

-- ❌ 禁止：在 DATEDIFF 外面套 CAST 或 TO_DATE
CAST(DATEDIFF(MINUTE, "alarm_time", "event_completion_time") AS VARCHAR)
```

## 重要关联关系
- device.category_id → equipment_category.id（设备类型）
- device.space_id → space.id；device.venue_id → table_venue_info.id
- alarm_record.device_id → device.id；alarm_record.device_category_id → equipment_category.id
- metering_point.space_id → space.id；日数据.metering_point_id → metering_point.id
- lighting_circuit.area_id → lighting_area.id（lighting_area 没有 space_id，用 space / space_name 文本）

所有时间字段用单引号包裹，如 `alarm_time >= '2026-01-01'`
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
        return self.ollama.build_chat_payload(
            messages=[m.model_dump() for m in body.messages],
            temperature=body.temperature,
            num_ctx=body.num_ctx,
        )

    def _detect_db_related(self, question: str) -> bool:
        """判断用户问题是否与达梦数据库相关
        策略：命中业务关键词才走 DB/RAG，否则默认直连 LLM
        """
        q = question.lower()

        # 业务关键词匹配——命中才走 DB/RAG
        db_keywords = [
            # 设备
            "设备",
            "离线",
            "在线",
            "运行状态",
            "运行状态",
            "设备数量",
            "设备统计",
            "设备类型",
            "阀门",
            "传感器",
            "仪表",
            "机组",
            "冷机",
            "热机",
            "空调",
            "新风",
            "风机",
            "水泵",
            "光伏",
            # 告警
            "告警",
            "报警",
            "故障",
            "停机",
            "异常",
            "重要",
            "一般",
            "告警级别",
            "告警状态",
            "告警内容",
            "告警时间",
            "告警记录",
            "告警处理",
            # 能耗/碳排放
            "能耗",
            "电耗",
            "水耗",
            "气耗",
            "热耗",
            "蒸汽",
            "用能",
            "综合能耗",
            "碳排放",
            "碳排放量",
            "碳强度",
            "碳因子",
            "标准煤",
            # 监测数据
            "温度",
            "湿度",
            "压力",
            "流量",
            "co2",
            "CO2",
            "浓度",
            # 场馆/空间
            "场馆",
            "会展",
            "空间",
            "区域",
            "楼层",
            "建筑",
            "位置",
            "地址",
            "场馆信息",
            "空间信息",
            "面积",
            "经纬度",
            "朝向",
            # 客流/人员
            "客流",
            "人流量",
            "入场",
            "出场",
            "访客",
            "人员",
            "人员统计",
            "在馆人数",
            "最大人数",
            "实时客流",
            # 停车
            "停车",
            "车位",
            "车辆",
            "停车场",
            "剩余车位",
            "停车时长",
            "停车统计",
            # 照明
            "照明",
            "灯光",
            "回路",
            "灯组",
            "照明区域",
            "亮灯",
            # 计量
            "计量",
            "计量点",
            "分时",
            "尖",
            "峰",
            "平",
            "谷",
            "电费",
            # 数据/统计/报表
            "数据",
            "统计",
            "报表",
            "报告",
            "记录",
            "查询",
            "分析",
            "汇总",
            "同比",
            "环比",
            # AI报告
            "ai报告",
            "AI报告",
            "分析报告",
            "日报",
            "周报",
            "月报",
            # 运维
            "维护",
            "保养",
            "检修",
            "巡检",
            "启停",
            "开关",
            # 阈值/配置
            "阈值",
            "上下限",
            "配置",
            "参数",
            # 通用业务
            "总数",
            "数量",
            "有多少",
            "多少个",
            "统计",
            "分布",
            "占比",
        ]
        return any(kw in q for kw in db_keywords)

    def _is_energy_formula_query(self, question: str) -> bool:
        """检测"按能介统计能耗"类问题(需走公式计算分支)

        需同时满足:
          1. 能介聚合意图: 含"能源介质"/"能介", 或 "电" + ("水"/"气"/"热") 枚举
          2. 累计能耗意图: 含"累计"/"总能耗"/"综合能耗"/"能耗是多少"/"能耗多少"
        不匹配: 设备级能耗(Q4.x)、费用查询(Q5.3)、系数查询(Q5.4)
        """
        q = question.lower()
        # 能介聚合关键词
        medium_kws = ["能源介质", "能介"]
        # 或: 电 + (水/气/热) 同时出现
        has_medium = any(k in q for k in medium_kws) or (
            "电" in q and any(k in q for k in ["水", "气", "热"])
        )
        if not has_medium:
            return False
        # 累计能耗意图
        consumption_kws = [
            "累计能耗",
            "总能耗",
            "综合能耗",
            "能耗是多少",
            "能耗多少",
            "能耗统计",
            "能耗汇总",
            "用电量",
            "耗能量",
        ]
        return any(k in q for k in consumption_kws)

    def _parse_energy_time_range(self, question: str) -> tuple:
        """从问题中解析时间范围, 返回 (start_date, end_date)

        支持: 本月(默认)/上月/最近N天/近N天/过去N天/今年/去年
        """
        from datetime import date, timedelta
        from calendar import monthrange

        today = date.today()

        # 上月
        if "上月" in question or "上个月" in question:
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, last_month_end

        # 最近N天 / 近N天 / 过去N天
        m = re.search(r"最近\s*(\d+)\s*天|近\s*(\d+)\s*天|过去\s*(\d+)\s*天", question)
        if m:
            n = int(next(g for g in m.groups() if g))
            return today - timedelta(days=n - 1), today

        # 今年
        if "今年" in question:
            return date(today.year, 1, 1), today

        # 去年
        if "去年" in question:
            return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)

        # 默认本月
        first_of_month = today.replace(day=1)
        return first_of_month, today

    @staticmethod
    def _extract_device_ids(true_formula: str) -> list:
        """从 true_formula 提取 device_code 列表(去重)

        格式: [K026zp401]+[K026zp445]-[K026zp415_5] → ['K026zp401', 'K026zp445', 'K026zp415_5']
        也兼容纯数字 id 格式: [1001]+[1002] → ['1001', '1002']
        """
        if not true_formula:
            return []
        return list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", true_formula)))

    @staticmethod
    def _eval_formula(true_formula, device_values: dict) -> Optional[float]:
        """安全求值 true_formula, 把 [device_code] 替换为实际值后算术求值

        Args:
            true_formula: 如 "[K026zp401]+[K026zp445]-[K026zp415_5]"
            device_values: {device_code: value} 映射, key 可以是 str 或 int

        Returns:
            float 结果(4位小数), 或 None(求值失败/除0)
        """
        import ast
        import operator as op_module
        import math

        if not true_formula:
            return None

        # 1. 替换 [device_code] → 数值
        def _substitute(m):
            code = m.group(1)
            val = device_values.get(code)
            if val is None:
                # 尝试 int 转换(兼容纯数字 key)
                try:
                    val = device_values.get(int(code))
                except (ValueError, TypeError):
                    pass
            if val is None:
                val = 0.0
            return repr(float(val))

        expr_str = re.sub(r"\[([^\]]+)\]", _substitute, true_formula)

        # 2. AST 安全求值
        _ALLOWED_BINOPS = {
            ast.Add: op_module.add,
            ast.Sub: op_module.sub,
            ast.Mult: op_module.mul,
            ast.Div: op_module.truediv,
        }
        _ALLOWED_UNARYOPS = {
            ast.USub: op_module.neg,
            ast.UAdd: op_module.pos,
        }

        def _eval_node(node):
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                return _ALLOWED_BINOPS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
                operand = _eval_node(node.operand)
                return _ALLOWED_UNARYOPS[type(node.op)](operand)
            raise ValueError(f"不允许的 AST 节点: {type(node).__name__}")

        try:
            tree = ast.parse(expr_str, mode="eval")
            result = _eval_node(tree)
            if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
                return None
            return round(result, 4)
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as e:
            logger.warning(f"公式求值失败: {true_formula} -> {e}")
            return None

    @staticmethod
    def _parse_venue_flow_time(question: str) -> tuple:
        """场馆客流问法：距今天数（None=未说日期）、是否要总量。"""
        q = question or ""
        want_total = any(k in q for k in ("总量", "累计", "合计", "总共", "共计"))
        if any(k in q for k in ("前天", "前日")):
            return 2, want_total
        if any(k in q for k in ("昨日", "昨天")):
            return 1, want_total
        if any(k in q for k in ("今日", "今天", "当日")):
            return 0, want_total
        return None, want_total

    @staticmethod
    def _strip_order_limit(sql: str) -> str:
        text = (sql or "").rstrip(";").strip()
        text = re.sub(r"\s+LIMIT\s+\d+\s*$", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+ORDER\s+BY[\s\S]*$", "", text, flags=re.IGNORECASE)
        return text.strip()

    @staticmethod
    def _venue_flow_max_in_sql(date_sql: str) -> str:
        """前一天客流：每馆取进场累计最大的一条，避免凌晨 0 客流行。"""
        d = date_sql
        return (
            'SELECT vi."venue_name", f."today_in_count", f."today_now_count", '
            'f."max_count", f."average_duration" '
            'FROM "FWBZ"."table_venue_flow_hour" f '
            'INNER JOIN "FWBZ"."table_venue_info" vi ON vi."id" = f."venue_id" '
            f'WHERE f."data_date" = {d} '
            'AND f."today_in_count" > 0 '
            'AND f."id" IN ('
            'SELECT MAX(f2."id") '
            'FROM "FWBZ"."table_venue_flow_hour" f2 '
            'INNER JOIN ('
            'SELECT "venue_id", MAX("today_in_count") AS "peak_in" '
            'FROM "FWBZ"."table_venue_flow_hour" '
            f'WHERE "data_date" = {d} AND "today_in_count" > 0 '
            'GROUP BY "venue_id"'
            ') p ON p."venue_id" = f2."venue_id" AND p."peak_in" = f2."today_in_count" '
            f'WHERE f2."data_date" = {d} '
            'GROUP BY f2."venue_id") '
            'ORDER BY vi."id" '
            "LIMIT 200"
        )

    def _apply_venue_flow_question(self, sql: str, question: str) -> str:
        """Q6.1 仍是同一意图。今日用最新 id；昨日/前天用进场最大的一条。"""
        if not sql or "table_venue_flow_hour" not in sql.lower():
            return sql
        offset, want_total = self._parse_venue_flow_time(question)
        if want_total and offset is None:
            return (
                'SELECT SUM(src."today_in_count") AS "total_in_count" FROM ('
                'SELECT f."today_in_count" '
                'FROM "FWBZ"."table_venue_flow_hour" f '
                'WHERE f."id" IN ('
                'SELECT MAX(f2."id") '
                'FROM "FWBZ"."table_venue_flow_hour" f2 '
                'GROUP BY f2."venue_id", f2."data_date"'
                ")) src"
            )
        if offset:
            date_sql = f"(TRUNC(SYSDATE) - {int(offset)})"
            sql = self._venue_flow_max_in_sql(date_sql)
        if want_total:
            inner = self._strip_order_limit(sql)
            return (
                'SELECT SUM(src."today_in_count") AS "total_in_count" '
                f"FROM ({inner}) src"
            )
        return sql

    def _finalize_template_sql(
        self,
        sql: str,
        *,
        qid: Optional[str] = None,
        question: Optional[str] = None,
    ) -> Optional[str]:
        """手册范式已是达梦 SELECT 时直接采用，避免再走 LLM 改写和标识符清洗。"""
        sql = (sql or "").rstrip(";").strip()
        if not sql.upper().startswith("SELECT") or "FROM" not in sql.upper():
            return None
        sql = self._apply_venue_flow_question(sql, question or "")
        from app.common.dameng import validate_sql_columns

        ok, err, _invalid = validate_sql_columns(sql)
        if not ok:
            logger.warning("手册范式 SQL 校验失败 qid=%s err=%s", qid, err)
            return None
        logger.info("使用手册范式 SQL qid=%s sql=%s", qid, _one_line(sql, 300))
        return sql

    def _generate_sql(
        self,
        question: str,
        *,
        sql_template: Optional[str] = None,
        qid: Optional[str] = None,
    ) -> Optional[str]:
        """根据用户问题生成 SQL 查询语句（支持重试）

        Args:
            question: 用户原始问题
            sql_template: 问答手册中该问题对应的 SQL 范式 (可选, 由 qa_matcher 提供)
            qid: 匹配到的问题编号 (如 "5.1"), 用于 prompt 标注
        """
        canned_sql = extract_sql_from_chunk(sql_template)
        if canned_sql:
            ready = self._finalize_template_sql(
                canned_sql, qid=qid, question=question
            )
            if ready:
                logger.info("生成SQL q=%s", _one_line(question, 80))
                return ready
            logger.warning("手册范式不可直接执行 qid=%s，改走模型生成", qid)

        # 根据问题关键词，推测可能涉及的表（列名信息全部来自上方动态 schema，不在此处重复列举）
        q = question.lower()
        table_hints = []
        if any(k in q for k in ["设备", "离线", "在线", "运行"]):
            table_hints.append("device（设备表）")
        if any(k in q for k in ["告警", "报警", "故障", "停机"]):
            table_hints.append("alarm_record（告警记录）")
        if any(k in q for k in ["能耗", "电", "水", "气", "热", "用能"]):
            table_hints.append("data_day（设备日数据）")
        if any(k in q for k in ["场馆", "会展", "场馆信息"]):
            table_hints.append("table_venue_info（会展场馆）")
        if any(k in q for k in ["空间", "区域", "楼层"]):
            table_hints.append("space（空间表）")
        if any(k in q for k in ["客流", "入场", "出场", "访客"]):
            # ⚠️ 客流表统一使用 table_venue_flow_hour（table_venue_flow 表已废弃，数据库中不存在）
            # 查询逻辑：today_in_count / today_now_count / average_duration 取 data_hour 最大的那条
            #         max_count / max_time 取 max_count 最大的那条
            table_hints.append("table_venue_flow_hour（场馆客流分时统计）")
        if any(k in q for k in ["人员", "人员统计"]):
            table_hints.append("table_personnel_statistics（人员统计）")
        if any(k in q for k in ["停车", "车位", "停车场"]):
            table_hints.append("table_parking_count（停车场统计）")
        if any(k in q for k in ["照明", "灯光", "回路"]):
            table_hints.append(
                "lighting_area（照明区域）/ lighting_circuit（照明回路）"
            )
        if any(k in q for k in ["计量", "分时"]):
            table_hints.append(
                "metering_point_data_day（计量点日数据）/ metering_point（计量点）"
            )
        if any(k in q for k in ["碳", "碳排放", "碳强度"]):
            table_hints.append(
                "carbon_emission_factor（碳排放因子）/ data_day（能耗数据）"
            )
        if any(k in q for k in ["报告", "ai报告", "报表"]):
            table_hints.append("ai_report_history（AI报告历史）")
        if any(k in q for k in ["设备类型", "设备信息", "介绍设备", "category", "分类"]):
            table_hints.append("equipment_category（设备类型，device.category_id 关联）")

        hint_text = ""
        if table_hints:
            hint_text = f"\n\n## 可能的关联表（根据问题推断）\n" + "\n".join(
                f"- {t}" for t in table_hints
            )

        # 重试时附带的错误反馈（初始为空，验证失败后填充）
        retry_hint = ""

        # Q-ID 范式参考段 (匹配上问题时由 caller 传入, 让 LLM 有据可依)
        template_section = ""
        if sql_template and qid:
            # P3: 提取范式里出现的列名作为白名单
            template_cols = re.findall(r'"([A-Za-z_]\w*)"', sql_template)
            template_cols = list(dict.fromkeys(template_cols))[:15]  # 去重 + 限数
            col_whitelist = ", ".join(f'"{c}"' for c in template_cols)

            template_section = f"""

## 参考 SQL 范式 (来自问答手册 Q{qid})
这是与用户问题最匹配的标准问题对应的 SQL 范式。**作为参考**, 你需要根据用户问题的具体语境(时间范围/设备名/空间名/数值阈值等)改造它, 不能原样照抄。
- 保留范式的查询意图(选哪些表/怎么连接/怎么聚合)
- 把范式中的 `{{{{变量}}}}` 替换为合适的值或 WHERE 条件; 无明确语境时用 SYSDATE / 通用条件
- 字段名务必从上方「数据库真实表结构」选, 严禁臆造
- 达梦方言规则遵守上方的硬性约束

范式中出现过的列：{col_whitelist}
改造时可保留这些列，也可从上方表结构为同一张表增补真实列（如 device 增补 category_id）。禁止使用表结构里没有的列。

```sql
{sql_template}
```
"""

        base_prompt_header = f"""{DAMENG_SCHEMA_CONTEXT}{_SCHEMA_TEXT}{hint_text}

## 任务
根据用户问题生成一条达梦 SELECT。只使用上方表结构里的表名和列名。

用户问题：{question}

## 生成要求（与上文规则一致，供 qwen3.5:9b 与云端调试共用）
1. 表名、列名必须能在「数据库真实表结构」里找到；外键按表选用，不要全局禁用某个列名。
2. 问设备信息/介绍设备：FROM device 时 SELECT 必须含 `"category_id"`，不要只选 `"device_name"`、`"run_state"`。
3. 分页只用 `LIMIT n OFFSET 0`（明细最多 500，聚合最多 200）。不要 ROWNUM。
4. 明细列不要起中文别名。只输出 SQL，不要解释，不要 markdown。

示例：
SELECT "device_name", "category_id", "run_state", "create_time" FROM "FWBZ"."device" ORDER BY "create_time" DESC LIMIT 500 OFFSET 0
"""
        logger.info("生成SQL q=%s", _one_line(question, 80))

        for attempt in range(3):
            try:
                response = self.ollama.call_llm(
                    [
                        {
                            "role": "user",
                            "content": base_prompt_header
                            + template_section
                            + retry_hint,
                        }
                    ],
                    temperature=0.1,
                )
                sql = response.strip()
                sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
                sql = re.sub(r"^```\s*", "", sql)
                sql = re.sub(r"\s*```$", "", sql)
                # 清理末尾分号和空白
                sql = sql.rstrip(";").strip()

                logger.info("LLM原始输出: %s", _one_line(sql, 500))

                # 基础验证：必须包含 SELECT 和 FROM
                if sql.upper().startswith("SELECT") and "FROM" in sql.upper():
                    # ========== LLM 生成的基础语法修复（必须在包装之前执行）==========

                    # 1. 修复 LLM 常见的错误语法：ORDER BY ... WHERE（WHERE 应该在 ORDER BY 之前）
                    # 匹配 "ORDER BY xxx WHERE" 或 "ORDER BY xxx DESC WHERE" 这种错误顺序
                    order_where_match = re.search(
                        r"(\s+ORDER\s+BY\s+.+?)\s+WHERE\s+",
                        sql,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if order_where_match:
                        # 提取 ORDER BY 子句和 WHERE 后面的条件
                        order_part = order_where_match.group(1).strip()
                        where_rest = sql[
                            order_where_match.end() - 1 :
                        ]  # 从 WHERE 开始到末尾

                        # 找到 WHERE 后面第一个非空格字符
                        where_start = re.search(r"\WHERE\s+", sql, re.IGNORECASE)
                        if where_start:
                            # 提取 WHERE 及其后的条件
                            where_clause = where_rest.strip()
                            # 移除 WHERE 后面的 ROWNUM 相关条件（LLM 常见错误）
                            where_clause = re.sub(
                                r"AND\s*\(?\s*ROWNUM\s*[\-<>=\d\s]+\)?",
                                "",
                                where_clause,
                                flags=re.IGNORECASE,
                            )
                            where_clause = re.sub(
                                r"WHERE\s+ROWNUM\s*[\-<>=\d\s]+",
                                "",
                                where_clause,
                                flags=re.IGNORECASE,
                            )
                            where_clause = where_clause.strip()

                            # 重建 SQL：ORDER BY 放到 WHERE 后面
                            base_part = sql[: order_where_match.start()].strip()
                            if where_clause:
                                sql = f"{base_part} WHERE {where_clause} {order_part}"
                            else:
                                sql = f"{base_part} {order_part}"

                    # 2. 移除 LLM 生成的无效 ROWNUM 条件（如 "AND (ROWNUM - 1) > 0"）
                    sql = re.sub(
                        r"\s+AND\s*\(\s*ROWNUM\s*[\-<>=\d\s()]+\)",
                        "",
                        sql,
                        flags=re.IGNORECASE,
                    )
                    sql = re.sub(
                        r"\s+AND\s+ROWNUM\s*[\-<>=\d\s()]+\s*>",
                        " WHERE ",
                        sql,
                        flags=re.IGNORECASE,
                    )
                    sql = re.sub(
                        r"WHERE\s+ROWNUM\s*[\-<>=\d\s()]+\s*>",
                        "WHERE ",
                        sql,
                        flags=re.IGNORECASE,
                    )

                    logger.info("修复WHERE/ORDER后: %s", _one_line(sql, 500))

                    # ========== 达梦 SQL 语法修复 ==========

                    # 注意：不再清理中文别名，保留 LLM 生成的中文别名用于前端展示

                    # 2. 修复分页语法 → 达梦 ROWNUM
                    # 支持：LIMIT N, FETCH FIRST N ROWS ONLY
                    # 分场景限制：明细查询（无 GROUP BY）500条，聚合查询（有 GROUP BY）200条
                    has_group_by = bool(
                        re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE)
                    )

                    limit_n = None
                    # 2.1 处理 FETCH FIRST N ROWS ONLY（PostgreSQL/Oracle 语法）
                    fetch_match = re.search(
                        r"\bFETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY\b", sql, re.IGNORECASE
                    )
                    if fetch_match:
                        limit_n = int(fetch_match.group(1))
                        # 移除 FETCH FIRST 子句
                        sql = re.sub(
                            r"\s+FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\b",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                    # 2.2 处理 LIMIT N
                    elif re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
                        limit_match = re.search(r"LIMIT\s+(\d+)", sql, re.IGNORECASE)
                        if limit_match:
                            limit_n = int(limit_match.group(1))
                            # 移除原 LIMIT 子句
                            sql = re.sub(
                                r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?",
                                "",
                                sql,
                                flags=re.IGNORECASE,
                            )
                            sql = re.sub(
                                r"\s+LIMIT\s+\d+\s*,\s*\d+",
                                "",
                                sql,
                                flags=re.IGNORECASE,
                            )
                    # 2.3 没有分页语法，自动加上限制防止全表扫描
                    if limit_n is None:
                        limit_n = 200 if has_group_by else 500

                    # 根据场景限制最终数量
                    if has_group_by:
                        final_limit = min(limit_n, 200)
                    else:
                        final_limit = min(limit_n, 500)

                    # 添加达梦分页
                    # 达梦 DM8 原生支持 LIMIT/OFFSET 语法（MySQL/PostgreSQL 风格），
                    # 比嵌套 ROWNUM 更简洁、更不容易出错，直接追加到 SQL 末尾即可。
                    if final_limit:
                        # ── 步骤 1：修复 WHERE 和 ORDER BY 的顺序（必须在清理 LIMIT 之前做，
                        #            因为交换正则依赖 LIMIT 作为右边界才能正确匹配）
                        def swap_order_where(m):
                            return m.group(2) + " " + m.group(1)

                        sql = re.sub(
                            r"(ORDER\s+BY\s+(?:(?!\bLIMIT\b).)+?)\s+(WHERE\s+(?:(?!\bLIMIT\b).)+?)\s+LIMIT",
                            swap_order_where,
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 2：清理所有分页语法残留
                        # FETCH FIRST N ROWS ONLY（PostgreSQL/DB2）
                        sql = re.sub(
                            r",\s*FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        # LIMIT N OFFSET M / LIMIT N, M / LIMIT N（MySQL）
                        sql = re.sub(
                            r"\s+LIMIT\s+\d+\s+OFFSET\s+\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+LIMIT\s+\d+\s*,\s*\d+", "", sql, flags=re.IGNORECASE
                        )
                        sql = re.sub(r"\s+LIMIT\s+\d+", "", sql, flags=re.IGNORECASE)
                        # OFFSET ... 独立写法
                        sql = re.sub(
                            r"\s+OFFSET\s+\d+\s*,\s*\d+", "", sql, flags=re.IGNORECASE
                        )
                        sql = re.sub(r"\s+OFFSET\s+\d+", "", sql, flags=re.IGNORECASE)
                        # TOP N（SQL Server）
                        sql = re.sub(r"\s+TOP\s+\d+", "", sql, flags=re.IGNORECASE)
                        # WHERE ROWNUM / 各类 Oracle/达梦分页残留
                        sql = re.sub(
                            r"\s+WHERE\s+ROWNUM\s*<=\s*\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+ROWNUM\s*<\s*\d+", "", sql, flags=re.IGNORECASE
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+\(\s*ROWNUM\s*-\s*\d+\s*\)\s*\*\s*\d+\s*\+\s*\d+\s*>\s*\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+\d+\s*<\s*ROWNUM\s*<\s*\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+ROWNUM\s+between\s+\d+\s+and\s+\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+rn\s*>\s*\d+\s+AND\s+rn\s*<=\s*\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )
                        sql = re.sub(
                            r"\s+WHERE\s+rn\s*>=\s*\d+\s+AND\s+rn\s*<\s*\d+",
                            "",
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 3：修复 ORDER BY 后 DESC/ASC 和 LIMIT 之间缺少空格
                        #    如 "ORDER BY col DESC LIMIT" → "ORDER BY col DESC LIMIT"
                        sql = re.sub(
                            r"(DESC|ASC)\s*(LIMIT|OFFSET)",
                            r"\1 \2",
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 4：清理 ORDER BY 后残留的 ROWNUM 算术表达式
                        #    如 "ORDER BY col DESC * 5 + 1 > 0" → "ORDER BY col DESC"
                        sql = re.sub(
                            r"ORDER\s+BY\s+[^()]*?\*\s*\d+\s*[+-]\s*\d+\s*[<>=]+\s*\d+",
                            lambda m: re.sub(
                                r"\s*\*\s*\d+\s*[+-]\s*\d+\s*[<>=]+\s*\d+\s*$",
                                "",
                                m.group(0),
                                flags=re.IGNORECASE,
                            ),
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 5：清理 ORDER BY 后残留的孤立 LIMIT 数字
                        #    如 "ORDER BY col DESC 500 OFFSET 0" → "ORDER BY col DESC"
                        sql = re.sub(
                            r"ORDER\s+BY\s+[^()]*?\s+\d+\s+OFFSET",
                            lambda m: re.sub(r"\s+\d+(?=\s+OFFSET)", "", m.group(0)),
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 6：修复无意义的 WHERE 条件
                        sql = re.sub(
                            r"\bWHERE\s+0\b", "WHERE 1=1", sql, flags=re.IGNORECASE
                        )
                        sql = re.sub(
                            r"\bWHERE\s+1\s*=\s*0\b",
                            "WHERE 1=1",
                            sql,
                            flags=re.IGNORECASE,
                        )

                        # ── 步骤 7：统一追加达梦 LIMIT 分页
                        sql = sql.rstrip() + f" LIMIT {final_limit} OFFSET 0"

                    # ── 步骤 8：达梦大小写敏感，所有标识符必须双引号
                    # 达梦 DM8 开启大小写敏感后，未加双引号的表名/列名无法识别。
                    # 策略：直接匹配单词字符序列，在回调里判断是否需要加引号。
                    # 关键字和已引号的标识符跳过，其余全部加双引号。
                    _SQL_KEYWORDS = frozenset(
                        {
                            "ASC",
                            "DESC",
                            "NULL",
                            "SYSDATE",
                            "AND",
                            "OR",
                            "NOT",
                            "AS",
                            "IN",
                            "ON",
                            "BY",
                            "IS",
                            "LIKE",
                            "BETWEEN",
                            "LEFT",
                            "RIGHT",
                            "INNER",
                            "OUTER",
                            "FULL",
                            "CROSS",
                            "JOIN",
                            "FROM",
                            "WHERE",
                            "ORDER",
                            "GROUP",
                            "HAVING",
                            "LIMIT",
                            "OFFSET",
                            "SELECT",
                            "UNION",
                            "ALL",
                            "DISTINCT",
                            "CASE",
                            "WHEN",
                            "THEN",
                            "ELSE",
                            "END",
                            "OVER",
                            "PARTITION",
                            "MINUTE",
                            "HOUR",
                            "DAY",
                            "SECOND",
                            "YEAR",
                            "MONTH",
                            "SUM",
                            "AVG",
                            "COUNT",
                            "MAX",
                            "MIN",
                            "TRUNC",
                            "TO_CHAR",
                            "CAST",
                            "COALESCE",
                            "GREATEST",
                            "LEAST",
                            "NVL",
                            "NVL2",
                            "DATEDIFF",
                            "TIMESTAMPDIFF",
                            "DATE",
                            "TIME",
                            "TO_DATE",
                            "TO_NUMBER",
                            "ROW_NUMBER",
                            "ROWNUM",
                            "SYSTIMESTAMP",
                            "ROWID",
                            "ROWIDTOCHAR",
                            "INSERT",
                            "UPDATE",
                            "DELETE",
                            "SET",
                            "VALUES",
                            "TABLE",
                            "INDEX",
                            "VIEW",
                            "SEQUENCE",
                            "TRIGGER",
                            "TRUE",
                            "FALSE",
                            "UNKNOWN",
                            "EXISTS",
                        }
                    )

                    # 用于判断当前上下文是否在字符串/数字常量中
                    def _add_quotes_to_identifiers(sql: str) -> str:
                        """遍历 SQL 字符串，把所有裸标识符（非关键字、非数字）加上双引号"""
                        # 逐字符扫描：遇到单引号跳到配对结尾；遇到双引号跳过已引号标识符；
                        # 其余地方匹配裸单词标识符，按需加引号。
                        result = []
                        i = 0
                        n = len(sql)
                        while i < n:
                            c = sql[i]

                            # 跳过字符串常量（单引号）
                            if c == "'":
                                result.append(c)
                                i += 1
                                while i < n:
                                    ch = sql[i]
                                    result.append(ch)
                                    if ch == "'":
                                        i += 1
                                        # 达梦字符串内单引号转义：'' 或 '''
                                        if i < n and sql[i] == "'":
                                            result.append(sql[i])
                                            i += 1
                                        break
                                    i += 1
                                continue

                            # 跳过数字常量（如 20, 0）
                            if c.isdigit():
                                result.append(c)
                                i += 1
                                while i < n and sql[i].isdigit():
                                    result.append(sql[i])
                                    i += 1
                                continue

                            # 尝试匹配标识符（字母或下划线开头）
                            if c.isalpha() or c == "_":
                                j = i
                                while j < n and (sql[j].isalnum() or sql[j] == "_"):
                                    j += 1
                                identifier = sql[i:j]
                                upper = identifier.upper()
                                # 关键字不引；其余全部加双引号
                                if upper not in _SQL_KEYWORDS:
                                    result.append(f'"{identifier}"')
                                else:
                                    result.append(identifier)
                                i = j
                                continue

                            # 双引号：跳过已引号的标识符（保留原样）
                            if c == '"':
                                result.append(c)
                                i += 1
                                while i < n and sql[i] != '"':
                                    result.append(sql[i])
                                    i += 1
                                if i < n:
                                    result.append(sql[i])  # closing quote
                                    i += 1
                                continue

                            # 其他字符原样保留
                            result.append(c)
                            i += 1

                        return "".join(result)

                    sql = _add_quotes_to_identifiers(sql)
                    logger.info("双引号修复后: %s", _one_line(sql))

                    # 3. 修复 LLM 常见的列名混淆（按真实表结构判断）
                    # 不同表的日期列名不同：
                    #   table_venue_flow_hour                      → "data_date"（客流表，table_venue_flow 已废弃）
                    #   table_parking_count / table_visitor_flow  → "date"
                    #   table_personnel_statistics               → "stat_date"
                    # 必须按每个 "data_date"/"stat_date" 引用所属的真实表判断，不能全局替换
                    sql = self._fix_date_column_by_schema(sql)
                    logger.info("日期列修复后: %s", _one_line(sql))

                    # 4. 修复单引号别名 → 去掉引号（达梦里别名不加引号）
                    sql = re.sub(
                        r"\s+AS\s+'([^']+)'", r" AS \1", sql, flags=re.IGNORECASE
                    )

                    # 5. 修复 DATE() 函数 → TRUNC()
                    sql = re.sub(
                        r'\bDATE\(("?[\w.]+"?)\)',
                        r"TRUNC(\1)",
                        sql,
                        flags=re.IGNORECASE,
                    )

                    # 6. 修复 IFNULL() → NVL()
                    sql = re.sub(r"\bIFNULL\(", "NVL(", sql, flags=re.IGNORECASE)

                    # 7. 修复 DATE_SUB/DATE_ADD → +/- INTERVAL
                    sql = re.sub(r"DATE_SUB\(", "(", sql, flags=re.IGNORECASE)
                    sql = re.sub(r"DATE_ADD\(", "(", sql, flags=re.IGNORECASE)
                    sql = re.sub(r"INTERVAL\s+\d+\s+DAY", "", sql, flags=re.IGNORECASE)

                    # 8. 修复 NOW() → SYSDATE
                    sql = re.sub(r"\bNOW\(\)", "SYSDATE", sql, flags=re.IGNORECASE)

                    # 9. 修复 CONCAT_WS → ||
                    sql = re.sub(
                        r'\bCONCAT_WS\(["\'](.+?)["\']\s*,\s*',
                        lambda m: "(",
                        sql,
                        flags=re.IGNORECASE,
                    )

                    # 10. 如果有 GROUP BY + ORDER BY，把 ORDER BY 中的别名替换为列位置序号
                    #    达梦不支持 ORDER BY 使用 SELECT 列表别名（如 ORDER BY alarm_count），
                    #    需要替换为 ORDER BY n（n = 该别名在 SELECT 列表中的位置序号）。
                    if "GROUP BY" in sql.upper() and re.search(
                        r"\bORDER BY\b", sql, re.IGNORECASE
                    ):
                        sql = self._fix_order_by_alias(sql)

                    # 11. 如果有 GROUP BY，移除未分组的非聚合列（如 "id"）
                    if "GROUP BY" in sql.upper():
                        logger.info("GROUP BY 修复前: %s", _one_line(sql))
                        sql = self._fix_group_by(sql)
                        logger.info("GROUP BY 修复后: %s", _one_line(sql))

                    # 12. 修复幽灵表引用：ON 条件里引用了某表（如 "device"."xxx"），
                    #     但该表未出现在 FROM/JOIN 子句中（如 LLM 漏写了 device JOIN）。
                    #     自动补全缺失的 JOIN，确保 JOIN 链完整。
                    sql = self._fix_phantom_table_in_join(sql)

                    # 13. 修复 LLM 生成的畸形 ON 条件：
                    #     典型错误：ON ("alarm_rule_id")=("id") — 括号包裹+无表前缀导致歧义
                    #     修复：去除括号，给列名加上正确的表前缀
                    sql = self._fix_malformed_on_conditions(sql)

                    # 14. 修复 SELECT/WHERE/ORDER BY 中无表前缀的歧义裸列名
                    #     典型错误：SELECT "id", "create_time" FROM alarm_record JOIN ...
                    #     当多表都有 id/create_time 时，数据库报错"歧义的列名"
                    #     修复：给这些裸列名加上 alarm_record. 前缀
                    sql = self._fix_ambiguous_bare_columns(sql)

                    logger.info(
                        "生成SQL成功 attempt=%s sql=%s",
                        attempt + 1,
                        _one_line(sql),
                    )

                    # 生成后验证：发现臆造列名则触发重试
                    from app.common.dameng import validate_sql_columns

                    col_valid, col_err, invalid_list = validate_sql_columns(sql)
                    if not col_valid:
                        # 构造更具体的错误反馈: 列出每个具体列名 + 所在表
                        invalid_detail = []
                        for inv in invalid_list[:5]:
                            invalid_detail.append(f"  - {inv}")
                        invalid_text = (
                            "\n".join(invalid_detail) if invalid_detail else col_err
                        )

                        hint_suffix = (
                            f"\n\n【严重错误 - 上一轮 SQL 验证失败】\n"
                            f"以下列名/表名不在 schema 中 (臆造):\n{invalid_text}\n\n"
                            f"请重新生成, 严格只使用上方「数据库真实表结构」!\n"
                            f"**对照上方表结构, 逐个核对表名和字段名**!"
                        )
                        logger.warning(
                            f"SQL 生成后验证失败（attempt {attempt}）: {col_err}，将重试"
                        )
                        if attempt < 2:
                            # 第 1/2 次失败: 带上具体提示重试
                            # 第 2 次重试时, 不传模板 (让 LLM 凭 schema 自由发挥)
                            if attempt == 1:
                                template_section = ""  # 清掉模板
                                logger.info("第 2 次重试, 不传 SQL 范式")
                            retry_hint = hint_suffix
                            continue
                        else:
                            # 第 3 次还失败：主动清理臆造列名后再返回
                            logger.warning(
                                "3 次重试后仍含臆造列, 主动清理后继续: %s", invalid_list
                            )
                            for bad_col in invalid_list:
                                # 去掉双引号
                                col_name = bad_col.strip('"')
                                # 从 SELECT 列表中移除（支持带 AS 别名的情况）
                                sql = re.sub(
                                    rf',?\s*"{re.escape(col_name)}"(\s+(?:AS\s+(?:"[^"]*"|\w+))?)(?=[,\)]|$)',
                                    "",
                                    sql,
                                    flags=re.IGNORECASE,
                                )
                                sql = re.sub(
                                    rf',?\s*\b{re.escape(col_name)}\b(\s+(?:AS\s+(?:"[^"]*"|\w+))?)(?=[,\)]|$)',
                                    "",
                                    sql,
                                    flags=re.IGNORECASE,
                                )
                            # 清理残留逗号
                            sql = re.sub(
                                r",\s*\b(WHERE|ORDER|GROUP|LIMIT)\b",
                                r" \1",
                                sql,
                                flags=re.IGNORECASE,
                            )
                            sql = re.sub(
                                r"SELECT\s+,", "SELECT ", sql, flags=re.IGNORECASE
                            )
                            logger.info("清理后SQL: %s", _one_line(sql))
                            return self._ensure_listing_type_fk(sql)

                    return self._ensure_listing_type_fk(sql)
                else:
                    logger.warning(
                        "SQL 生成结果无效 attempt=%s sql=%s",
                        attempt + 1,
                        _one_line(sql, 200),
                    )

            except Exception as e:
                logger.error("SQL 生成失败（attempt %d）: %s", attempt + 1, str(e))

        logger.warning("生成SQL失败，已达最大重试次数")
        return None

    def _execute_sql(
        self,
        sql: str,
        *,
        result_cap: Optional[int] = None,
    ) -> tuple[Optional[List[dict]], Optional[str]]:
        """执行 SQL 并返回结果。result_cap 用于「查看全部」：先去掉原 LIMIT，再按该上限兜底。"""
        logger.info("执行SQL sql=%s", _one_line(sql))

        # 严格安全门: 仅 SELECT / 拦截多语句 / 强制 LIMIT (明细 500 / 聚合 200)
        from app.common.sql_guard import validate as guard_validate

        if result_cap is not None:
            sql = self._strip_result_limit(sql)
            guard = guard_validate(
                sql, detail_limit=result_cap, aggregate_limit=result_cap
            )
        else:
            guard = guard_validate(sql)
        if not guard.ok:
            logger.warning(f"SQL 安全门拒绝: {guard.reason} | sql={sql[:200]}")
            return None, f"SQL 未通过安全门: {guard.reason}"
        sql = guard.sql  # 用清洗后的 (可能补了 LIMIT)

        try:
            # 安全检查：禁止危险操作（单词边界匹配，避免误伤 create_time 等列名）
            import re

            sql_upper = sql.upper()
            # INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER 用单词边界检测
            if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\b", sql_upper):
                logger.warning(f"SQL 安全检查拒绝（危险关键词）: {sql[:200]}")
                return None, "禁止执行非查询语句"
            if re.search(r"\bCREATE\b", sql_upper):
                # CREATE 作为独立单词检测（排除 CREATE_TIME 这类列名）
                # 只有出现在句首或前面有分号的才是 DDL
                safe_pattern = r"(?:^|[;])\s*CREATE\b|^\s*CREATE\s+"
                if not re.search(safe_pattern, sql_upper):
                    pass  # CREATE_TIME 等列名是安全的
                else:
                    logger.warning(f"SQL 安全检查拒绝（CREATE DDL）: {sql[:200]}")
                    return None, "禁止执行非查询语句"

            # 预清理：自动剔除已知臆造列名（LLM 常见幻觉）
            # 表 → 臆造列名列表（这些列在该表中不存在，LLM 经常臆造）
            KNOWN_HALLUCINATED_COLS: dict[str, frozenset[str]] = {
                "alarm_record": frozenset(
                    {"area_id", "circuit_name", "area_name", "device_code"}
                ),
                "lighting_area": frozenset({"space_id", "create_time", "area_id"}),
                "alarm_category": frozenset({"create_time"}),
            }
            for table, bad_cols in KNOWN_HALLUCINATED_COLS.items():
                for col in bad_cols:
                    # 从 SELECT 列表中移除（支持带 AS 别名的情况）
                    # 先处理 `"col"` 形式
                    sql = re.sub(
                        rf',?\s*"{re.escape(col)}"(\s+(?:AS\s+\w+)?(?=[,\)]|$))',
                        "",
                        sql,
                        flags=re.IGNORECASE,
                    )
                    # 再处理 `col` 形式（加了双引号的已经是 `"col"`，但保险起见）
                    sql = re.sub(
                        rf',?\s*\b"{re.escape(col)}"\b(\s+(?:AS\s+\w+)?(?=[,\)]|$))',
                        "",
                        sql,
                        flags=re.IGNORECASE,
                    )
                    # 也处理无引号的（如果还有）
                    sql = re.sub(
                        rf",?\s*\b{re.escape(col)}\b(\s+(?:AS\s+\w+)?(?=[,\)]|$))",
                        "",
                        sql,
                        flags=re.IGNORECASE,
                    )
                # 清理 SELECT 列表首列被单独移除后的残留逗号
                sql = re.sub(r",\s*\bWHERE\b", " WHERE", sql, flags=re.IGNORECASE)
                sql = re.sub(r"SELECT\s+,", "SELECT ", sql, flags=re.IGNORECASE)

            if sql.strip() == "" or re.match(r"^\s*SELECT\s*\s*$", sql):
                return None, "清理臆造列后 SQL 为空"

            # 列名 schema 验证：检查是否有臆造列名
            from app.common.dameng import validate_sql_columns

            col_valid, col_err, invalid_list = validate_sql_columns(sql)
            if not col_valid:
                logger.warning(f"SQL 列名验证失败: {col_err}")
                return None, f"SQL 包含不存在的列名: {', '.join(invalid_list)}"

            results = execute_query(sql)

            if results:
                logger.info("执行SQL成功 rows=%s", len(results))
            else:
                logger.warning("执行SQL成功但无数据")

            return results, None
        except Exception as e:
            logger.error("执行SQL异常: %s", str(e))
            return None, str(e)

    def _build_vue_table(
        self, data: List[dict], *, max_rows: Optional[int] = 500
    ) -> dict:
        """根据查询结果构建 Vue table 结构。查看全部时 max_rows=None。"""
        if not data:
            return {"columns": [], "rows": []}

        columns = []
        rows = []
        sample = data[0]

        for key in sample.keys():
            # 提取原始列名（去掉 SUM()/AVG()/COUNT()/NVL()/COALESCE 等函数包裹）
            clean_key = re.sub(
                r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE|NVL)\s*\(\s*"([^"]+)"\s*,\s*[^)]+\s*\)$',
                r"\2",
                key,
                flags=re.IGNORECASE,
            )
            clean_key = re.sub(
                r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$',
                r"\2",
                clean_key,
                flags=re.IGNORECASE,
            )
            clean_key = re.sub(
                r"^(SUM|AVG|COUNT|MAX|MIN|NVL)\s*\(\s*([^)]+)\s*\)$",
                r"\2",
                clean_key,
                flags=re.IGNORECASE,
            )

            # 排除 id 列
            if clean_key.lower() in ("id", "bigint", "rn"):
                continue

            # 格式化列为中文标签
            label = self._format_column_label(clean_key)

            # 聚合函数的列添加"总和/平均/计数"后缀
            if re.match(r"^(SUM|AVG|COUNT|MAX|MIN)\s*\(", key, re.IGNORECASE):
                agg_map = {
                    "SUM": "总和",
                    "AVG": "平均值",
                    "COUNT": "计数",
                    "MAX": "最大值",
                    "MIN": "最小值",
                }
                agg = (
                    re.match(r"^(SUM|AVG|COUNT|MAX|MIN)", key, re.IGNORECASE)
                    .group(1)
                    .upper()
                )
                label = (
                    self._format_column_label(clean_key) + f"({agg_map.get(agg, agg)})"
                )

            columns.append({"key": clean_key, "label": label, "width": "auto"})

        row_source = data if max_rows is None else data[:max_rows]
        for row in row_source:
            formatted_row = {}
            for k, v in row.items():
                # 提取原始列名（处理 NVL/SUM/AVG/COUNT 等函数包裹）
                clean_k = re.sub(
                    r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE|NVL)\s*\(\s*"([^"]+)"\s*,\s*[^)]+\s*\)$',
                    r"\2",
                    k,
                    flags=re.IGNORECASE,
                )
                clean_k = re.sub(
                    r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$',
                    r"\2",
                    clean_k,
                    flags=re.IGNORECASE,
                )
                clean_k = re.sub(
                    r"^(SUM|AVG|COUNT|MAX|MIN|NVL)\s*\(\s*([^)]+)\s*\)$",
                    r"\2",
                    clean_k,
                    flags=re.IGNORECASE,
                )
                # 排除 id 列
                if clean_k.lower() in ("id", "bigint", "rn"):
                    continue
                if v is None:
                    formatted_row[clean_k] = "-"
                elif isinstance(v, Decimal):
                    formatted_row[clean_k] = round(float(v), 2)
                elif isinstance(v, datetime):
                    formatted_row[clean_k] = v.strftime("%Y-%m-%d")
                elif hasattr(v, "strftime"):  # date 对象
                    formatted_row[clean_k] = v.strftime("%Y-%m-%d")
                else:
                    formatted_row[clean_k] = v
            rows.append(formatted_row)

        return {"columns": columns, "rows": rows}

    def _fix_order_by_alias(self, sql: str) -> str:
        """
        达梦不支持 ORDER BY 使用 SELECT 列表别名（如 ORDER BY alarm_count），
        将 ORDER BY 中的别名替换为列位置序号（如 ORDER BY 3 DESC）。
        同时处理不在别名中的裸列名（可能是 GROUP BY 列，已加双引号的直接保留）。
        """
        try:
            # 提取 SELECT 列表中的别名映射：别名 → 位置序号（从1开始）
            select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE)
            if not select_match:
                return sql

            select_content = select_match.group(1)
            # 逐项解析 SELECT 列表（支持嵌套括号）
            alias_map = {}  # 别名小写 → 位置序号
            pos = 0
            i = 0
            select_str = select_content.strip()
            while i < len(select_str):
                # 跳过空白
                while i < len(select_str) and select_str[i] in " \t\n":
                    i += 1
                if i >= len(select_str):
                    break

                # 判断起始字符
                ch = select_str[i]
                if ch == ",":
                    i += 1
                    continue

                # 找这一项的结束（考虑括号配对）
                depth = 0
                start = i
                while i < len(select_str):
                    c = select_str[i]
                    if c in "([":
                        depth += 1
                    elif c in ")]":
                        depth -= 1
                    elif c == "," and depth == 0:
                        break
                    i += 1
                item = select_str[start:i].strip()
                i += 1  # 跳过逗号

                if not item:
                    continue
                pos += 1

                # 检测是否有 AS 别名
                as_match = re.search(
                    r'\s+AS\s+(["\']?)(\w+)\1\s*$', item, re.IGNORECASE
                )
                if as_match:
                    alias_lower = as_match.group(2).lower()
                    alias_map[alias_lower] = pos
                # 也检测没有 AS 的列名（可能是聚合函数 SUM(...)）
                elif re.match(
                    r"^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(", item, re.IGNORECASE
                ):
                    # 聚合函数没有 AS，尝试提取内部列名作为别名（宽松处理）
                    pass

            if not alias_map:
                return sql

            # 提取 ORDER BY 部分
            order_match = re.search(
                r"ORDER BY\s+(.+?)(?=\s+LIMIT|\s*$|$)", sql, re.IGNORECASE
            )
            if not order_match:
                return sql

            order_text = order_match.group(0)
            order_expr = order_match.group(1).strip()

            # 逐列处理 ORDER BY（支持多列，逗号分隔）
            fixed_parts = []
            for col_m in re.finditer(
                r'(["\']?)(\w+)\1\s+(ASC|DESC)?(?=\s*,|\s+ORDER\s+BY|\s+LIMIT|\s*$)',
                order_expr,
                re.IGNORECASE,
            ):
                raw_alias = col_m.group(2)
                direction = col_m.group(3) or ""
                alias_lower = raw_alias.lower()

                if alias_lower in alias_map:
                    col_pos = alias_map[alias_lower]
                    fixed_parts.append(f"{col_pos} {direction}".strip())
                    logger.info(
                        "ORDER BY 别名 '%s' → 列位置 %s",
                        raw_alias,
                        col_pos,
                    )
                else:
                    # 不在别名中，保留原样（可能是 GROUP BY 列名，带双引号）
                    fixed_parts.append(f'"{raw_alias}" {direction}'.strip())

            if not fixed_parts:
                return sql

            new_order = "ORDER BY " + ", ".join(fixed_parts)
            sql = (
                sql[: order_match.start()]
                + new_order
                + sql[order_match.start() + len(order_text) :]
            )
            logger.info("ORDER BY 别名替换完成: %s", _one_line(sql))

        except Exception as e:
            logger.warning(f"ORDER BY 别名替换失败: {e}")

        return sql

    def _fix_group_by(self, sql: str) -> str:
        """
        修复 GROUP BY 语句：移除 SELECT 中未分组的非聚合列。
        例如：SELECT "id", "date", SUM("value") FROM ... GROUP BY "date"
        会变成：SELECT "date", SUM("value") FROM ... GROUP BY "date"
        """
        try:
            # 提取 GROUP BY 部分
            group_by_match = re.search(
                r"GROUP BY\s+(.+?)(?=\s+ORDER|\s+LIMIT|\s*$|$)", sql, re.IGNORECASE
            )
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
            select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE)
            if not select_match:
                return sql

            select_content = select_match.group(1)

            # 逐项解析 SELECT 列表（支持嵌套括号、*、别名等）
            items = []
            i = 0
            while i < len(select_content):
                # 跳过空白和逗号
                while i < len(select_content) and select_content[i] in " \t\n,":
                    i += 1
                if i >= len(select_content):
                    break

                # 找这一项的结束位置（顶层逗号为分隔符）
                depth = 0
                start = i
                while i < len(select_content):
                    c = select_content[i]
                    if c in "([,":
                        if c == "," and depth == 0:
                            break
                        depth += 1 if c in "([" else 0
                    elif c in ")]":
                        depth -= 1
                    i += 1
                item = select_content[start:i].strip()
                if item:
                    items.append(item)
                i += 1  # 跳过分隔符

            # 根据 GROUP BY 过滤：聚合函数全部保留，裸列名必须在 GROUP BY 中
            new_select_items = []
            for item in items:
                item_upper = item.upper()
                # 聚合函数（含 COUNT(*)、SUM("x") 等）→ 全部保留
                if re.match(r"^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(", item_upper):
                    new_select_items.append(item)
                # 裸列名（双引号）→ 必须在 GROUP BY 中
                elif re.match(r'^"[^"]+"$', item) or re.match(r"^'[^']+'$", item):
                    col_name = item.strip('"').strip("'").lower()
                    if col_name in grouped_cols:
                        new_select_items.append(item)

            if not new_select_items:
                return sql

            # 重建 SELECT
            new_select = ", ".join(new_select_items)
            sql = re.sub(
                r"SELECT\s+.+?\s+FROM",
                f"SELECT {new_select} FROM",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )

            # 修正 ORDER BY：确保 ORDER BY 中的列都在 GROUP BY 中
            # 关键：列位置序号（如 ORDER BY 3）保持不变，不要转成列名
            if grouped_col_originals:
                # 提取 ORDER BY 部分（可能在 LIMIT 之前或之后）
                order_match = re.search(
                    r"ORDER BY\s+(.+?)(?=\s+LIMIT|\s*$|$)", sql, re.IGNORECASE
                )
                if order_match:
                    order_text = order_match.group(0)  # 完整 "ORDER BY xxx"
                    order_expr = order_match.group(1).strip()  # ORDER BY 后的内容

                    # 逐个提取 ORDER BY 的每个项（支持多列，逗号分隔）
                    fixed_order_parts = []
                    for col_m in re.finditer(
                        r'("?[\w.]+"?)\s+(ASC|DESC)?(?=\s*,|\s+ORDER|\s+LIMIT|\s*$)',
                        order_expr,
                        re.IGNORECASE,
                    ):
                        raw_col = col_m.group(1).strip()
                        direction = col_m.group(2) or ""

                        # 情况 1：列位置序号（如 ORDER BY 3）→ 保持不变，达梦原生支持
                        if raw_col.isdigit():
                            fixed_order_parts.append(f"{raw_col} {direction}".strip())
                            continue

                        # 情况 2：列名 → 检查是否在 GROUP BY 中
                        clean_col = raw_col.strip('"').strip("'").lower()
                        if clean_col in grouped_cols:
                            # 在 GROUP BY 中，加上双引号保留
                            quoted = (
                                '"'
                                + grouped_col_originals.get(clean_col, clean_col)
                                + '"'
                            )
                            fixed_order_parts.append(f"{quoted} {direction}".strip())
                        else:
                            # 不在 GROUP BY 中 → 跳过（达梦报错，改用 GROUP BY 第一列兜底）
                            logger.warning(
                                f"ORDER BY 列 '{clean_col}' 不在 GROUP BY 中，将被替换为第一个 GROUP BY 列"
                            )

                    # 如果有有效列，用它们重建 ORDER BY；否则只用第一列
                    if fixed_order_parts:
                        new_order = "ORDER BY " + ", ".join(fixed_order_parts)
                    else:
                        first_col = '"' + list(grouped_col_originals.values())[0] + '"'
                        new_order = f"ORDER BY {first_col}"
                    sql = (
                        sql[: order_match.start()]
                        + new_order
                        + sql[order_match.start() + len(order_text) :]
                    )
                    logger.info("ORDER BY 修复: %s", _one_line(sql))

            logger.info("GROUP BY 修复: %s", _one_line(sql))
        except Exception as e:
            logger.warning(f"GROUP BY 修复失败: {e}")

        return sql

    def _fix_phantom_table_in_join(self, sql: str) -> str:
        """
        修复幽灵表引用：ON 条件中引用了某表（如 "device"."category_id"），
        但该表未出现在 FROM/JOIN 子句中。
        自动补全缺失的 JOIN，使 JOIN 链完整。

        典型错误（LLM 幻觉）：
          LEFT JOIN FWBZ."equipment_category" ON "device"."category_id"="equipment_category"."id"
          —— "device" 表根本没被 JOIN，导致 SQL 执行报错。

        修复策略：
          1. 提取 SQL 中所有在 ON 条件里出现的表引用（"xxx"."yyy" 形式）。
          2. 提取 FROM/JOIN 子句中实际出现的表名。
          3. 对每个未定义的幽灵表，根据关联关系推断如何补 JOIN：
             - "device" 缺失 → 从 alarm_record 通过 device_id 关联上。
             - 其他情况 → 移除对该幽灵表的引用（不完整的 JOIN 无法自动修复）。
        """
        try:
            # FROM/JOIN 的物理表 + 别名都算已定义。
            # 加引号后常见形态：FROM "FWBZ"."device" "d"
            from_tables = set()
            skip = {
                "on",
                "where",
                "order",
                "group",
                "having",
                "limit",
                "offset",
                "left",
                "right",
                "inner",
                "full",
                "cross",
                "join",
                "union",
                "select",
                "as",
            }
            from_table_pattern = re.compile(
                r"\b(?:FROM|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN)\s+"
                r'(?:(?:"?FWBZ"?\s*\.\s*)?)?"?([A-Za-z_]\w*)"?'
                r'(?:\s+(?:AS\s+)?"?([A-Za-z_]\w*)"?)?',
                re.IGNORECASE,
            )
            for m in from_table_pattern.finditer(sql):
                table = (m.group(1) or "").lower()
                alias = (m.group(2) or "").lower()
                if table and table not in skip and table != "fwbz":
                    from_tables.add(table)
                if alias and alias not in skip:
                    from_tables.add(alias)

            # 提取 qualified 引用（"xxx"."yyy"）；schema 名 FWBZ 不是表。
            on_table_refs = set()
            for m in re.finditer(r'"(\w+)"\."(\w+)"', sql):
                name = m.group(1).lower()
                if name != "fwbz":
                    on_table_refs.add(name)

            # 找出幽灵表（在 ON 中出现但不在 FROM/JOIN 中）
            phantom_tables = on_table_refs - from_tables

            if not phantom_tables:
                return sql

            logger.warning("发现幽灵表引用 %s，尝试自动修复", phantom_tables)

            for phantom in phantom_tables:
                if phantom == "device":
                    # "device" 表缺失：需要补全 alarm_record → device 的 JOIN
                    # 策略：在第一个 JOIN 之前插入 LEFT JOIN device，并修正后续 ON 条件
                    # 示例：把 ON "device"."category_id" 改为 ON d."category_id"，
                    #       同时在前面插入 LEFT JOIN FWBZ."device" d ON "alarm_record"."device_id"=d."id"

                    # 找 alarm_record 的位置（主表）
                    alarm_record_pos = re.search(
                        r'FROM\s+(?:FWBZ\.)?"alarm_record"', sql, re.IGNORECASE
                    )
                    if not alarm_record_pos:
                        # 找不到 alarm_record，跳过
                        logger.warning("找不到 alarm_record，无法补全 device JOIN")
                        continue

                    # 找第一个 JOIN 关键字的位置（用于确定插入点）
                    first_join = re.search(r"\s+LEFT\s+JOIN\s+", sql, re.IGNORECASE)
                    first_inner_join = re.search(
                        r"\s+INNER\s+JOIN\s+", sql, re.IGNORECASE
                    )

                    # 取最早出现的 JOIN
                    join_positions = []
                    if first_join:
                        join_positions.append(first_join.start())
                    if first_inner_join:
                        join_positions.append(first_inner_join.start())

                    if not join_positions:
                        # 没有 JOIN，在 FROM 子句之后插入
                        insert_pos = re.search(
                            r'FROM\s+(?:FWBZ\.)?"alarm_record"[^"]*', sql, re.IGNORECASE
                        )
                        if insert_pos:
                            insert_pos = insert_pos.end()
                        else:
                            continue
                    else:
                        insert_pos = min(join_positions)

                    # 检查是否已有对 device 表的引用（可能作为别名）
                    has_device_ref = re.search(r'"device"\."', sql, re.IGNORECASE)
                    if not has_device_ref:
                        continue

                    # 找第一个引用 "device"."xxx" 的位置，用于确定需要修复的 ON 条件
                    first_device_ref = re.search(
                        r'"device"\."(\w+)"', sql, re.IGNORECASE
                    )
                    if not first_device_ref:
                        continue

                    device_col = first_device_ref.group(1)
                    logger.info("幽灵表 device 被引用列: %s，尝试注入 JOIN", device_col)

                    # 插入 LEFT JOIN device，在第一个 JOIN 之前
                    device_join = ' LEFT JOIN FWBZ."device" ON "alarm_record"."device_id"="device"."id"'
                    new_sql = sql[:insert_pos] + device_join + sql[insert_pos:]
                    logger.info("注入 device JOIN 后: %s", _one_line(new_sql))
                    sql = new_sql
                else:
                    # 其他幽灵表：无法安全推断 JOIN 路径，直接移除整个 JOIN 块
                    # 原因：去掉表前缀后剩下的裸列名会引入歧义（多表都有 id 等），
                    #       后续修复逻辑无法安全推断应该加哪个表的前缀。
                    logger.warning(
                        f"幽灵表 '{phantom}' 无法安全修复，将移除整个 JOIN 块"
                    )

                    # 匹配包含该幽灵表的完整 JOIN 块（从 JOIN 到下一个 JOIN/WHERE/ORDER 之前）
                    # 格式: LEFT JOIN "phantom" ON (...) 或 LEFT JOIN FWBZ."phantom" ON (...)
                    phantom_join_pattern = (
                        rf"\s+(LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|JOIN)\s+"
                        rf'(?:FWBZ\.)?"{re.escape(phantom)}"'
                        rf'(?:\s+AS\s+"[^"]+")?\s+ON\s+.+?'
                        rf"(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)"
                    )
                    sql = re.sub(
                        phantom_join_pattern, "", sql, flags=re.IGNORECASE | re.DOTALL
                    )
                    # 清理可能遗留的连续空格
                    sql = re.sub(r"\s{2,}", " ", sql)

            logger.info("幽灵表修复后: %s", _one_line(sql))
        except Exception as e:
            logger.warning(f"幽灵表引用修复失败: {e}")

        return sql

    def _fix_malformed_on_conditions(self, sql: str) -> str:
        """
        修复 LLM 生成的畸形 ON 条件。

        典型错误（LLM 幻觉）：
          ON ("alarm_rule_id")=("id")
          —— 括号包裹 + 无表前缀 → 数据库报错"歧义的列名[id]"

        修复策略：
          1. 去除 ON 条件中的冗余括号：("xxx") → "xxx"
          2. 识别 ON 条件中的裸列名，自动推断并加上正确的表前缀：
             - alarm_rule_id, device_id, space_id, alarm_category_id,
               alarm_level_id, point_id, alarm_rule_point_id, device_category_id
               → alarm_record.column_name
             - id → 从当前 JOIN 的表推断（如 JOIN alarm_rules → alarm_rules."id"）
        """
        try:
            # 预定义：alarm_record 的外键列（用于判断左操作数应加 alarm_record. 前缀）
            AR_FK_COLUMNS = frozenset(
                {
                    "alarm_rule_id",
                    "device_id",
                    "space_id",
                    "alarm_category_id",
                    "alarm_level_id",
                    "point_id",
                    "alarm_rule_point_id",
                    "device_category_id",
                    "charge_person",
                    "device_category_id",
                }
            )

            # alarm_record 的自有列（用于判断右操作数可能属于 alarm_record 而非 JOIN 表）
            AR_COLUMNS = frozenset(
                {
                    "id",
                    "create_time",
                    "update_time",
                    "create_by",
                    "update_by",
                    "sys_org_code",
                    "alarm_rule_id",
                    "device_id",
                    "device_name",
                    "space_id",
                    "space_name",
                    "alarm_content",
                    "alarm_time",
                    "alarm_category_id",
                    "alarm_category_name",
                    "alarm_level_id",
                    "alarm_level_name",
                    "charge_person",
                    "charge_person_name",
                    "alarm_status",
                    "point_id",
                    "point_name",
                    "value",
                    "condition_value",
                    "operator",
                    "time_granularity",
                    "alarm_rule_point_id",
                    "device_category_id",
                    "alarm_level_color",
                    "event_id",
                }
            )

            def fix_single_on(on_clause_str: str, joined_table: str) -> str:
                """
                修复一个完整 ON 子句（含多 AND 条件）中的裸列名歧义。
                joined_table: 当前 JOIN 的表名（如 alarm_rules, alarm_level 等）

                处理格式：
                - ON ("cond1") AND ("cond2") AND ("cond3")
                - ON (cond1 AND cond2)
                - ON cond1=cond2 AND cond3=cond4
                """
                # 步骤1：去除 ON 关键字
                content = re.sub(
                    r"\bON\b", "", on_clause_str, flags=re.IGNORECASE
                ).strip()

                # 步骤2：提取括号内容（如果整个 ON 被一对外括号包裹）
                # 例如 ON ("device_id"="device_id" AND ...) → content = "device_id"="device_id" AND ..."
                # 我们直接 split by AND at depth=0，处理每个原子条件

                # 步骤3：split by AND at depth=0（处理引号和括号）
                parts = []
                depth = 0
                last = 0
                i = 0
                in_quote = False
                while i < len(content):
                    c = content[i]
                    if c == '"' and (i == 0 or content[i - 1] != "\\"):
                        in_quote = not in_quote
                        i += 1
                        continue
                    if in_quote:
                        i += 1
                        continue
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                    elif (
                        depth == 0
                        and content[i : i + 3].upper() == "AND"
                        and content[i + 3 : i + 4] in ("", " ", "\t")
                    ):
                        parts.append(content[last:i].strip().strip("()").strip())
                        last = i + 3
                        while last < len(content) and content[last] in " \t":
                            last += 1
                        i = last
                        continue
                    i += 1
                parts.append(content[last:].strip().strip("()").strip())

                # 步骤4：处理每个原子条件 "col1"="col2"
                fixed_parts = []
                for part in parts:
                    if "=" not in part:
                        fixed_parts.append(part)
                        continue

                    # 分割左右操作数（支持引号包裹的列名）
                    # 找第一个不在引号内的等号
                    eq_pos = -1
                    depth = 0
                    in_q = False
                    for idx, ch in enumerate(part):
                        if ch == '"' and (idx == 0 or part[idx - 1] != "\\"):
                            in_q = not in_q
                        if not in_q:
                            if ch == "(":
                                depth += 1
                            elif ch == ")":
                                depth -= 1
                            elif ch == "=" and eq_pos < 0:
                                eq_pos = idx
                    if eq_pos < 0:
                        fixed_parts.append(part)
                        continue

                    left = part[:eq_pos].strip().strip('()"')
                    right = part[eq_pos + 1 :].strip().strip('()"')
                    new_left = left
                    new_right = right

                    # 左操作数：如果是 alarm_record 的外键列，加前缀
                    if left and left.lower() in AR_FK_COLUMNS and "." not in left:
                        new_left = f'"alarm_record"."{left}"'
                    # 右操作数：如果是裸 "id"，加目标表前缀
                    if right and "." not in right:
                        right_lower = right.lower()
                        if right_lower == "id":
                            new_right = f'"{joined_table}"."id"'
                        elif (
                            right_lower in AR_COLUMNS
                            and left.lower() not in AR_FK_COLUMNS
                        ):
                            # 右操作数是 alarm_record 列但左操作数不是外键 → 加 alarm_record 前缀
                            new_right = f'"alarm_record"."{right}"'

                    if new_left == left and new_right == right:
                        fixed_parts.append(part)
                    else:
                        fixed_parts.append(f"{new_left}={new_right}")

                # 步骤5：重建 ON 子句
                result = "ON " + " AND ".join(fixed_parts)
                if result != on_clause_str:
                    logger.info("ON 修复: %r → %r", on_clause_str, result)
                return result

            # 遍历所有 JOIN 块，修复对应的 ON 条件
            def replace_join_block(m: re.Match) -> str:
                full_match = m.group(0)
                join_type = m.group(1)  # LEFT JOIN, INNER JOIN 等
                table_name_raw = m.group(2)
                table_name = table_name_raw.strip('".').lower()

                # 找这个 JOIN 的完整 ON 条件（使用贪婪匹配以捕获多 AND 条件）
                on_match = re.search(
                    r"\bON\b\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)",
                    full_match,
                    re.IGNORECASE | re.DOTALL,
                )
                if not on_match:
                    return full_match

                fixed_on = fix_single_on(on_match.group(0), table_name)
                # 重建 JOIN 块：只替换 ON 部分
                return re.sub(
                    r"\bON\b\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)",
                    fixed_on,
                    full_match,
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )

            # 匹配：JOIN 类型 + 表名（支持 FWBZ."table" 或 "table"）+ 可选的 AS 别名 + ON 条件
            # 用贪婪匹配 .+ 配合 lookahead 边界，确保捕获完整的多 AND ON 条件
            pattern = r'(LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|JOIN)\s+(?:FWBZ\.)?"([^"]+)"(?:\s+AS\s+"[^"]+")?\s+ON\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)'

            if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
                sql = re.sub(
                    pattern,
                    replace_join_block,
                    sql,
                    count=0,  # 全局替换
                    flags=re.IGNORECASE | re.DOTALL,
                )

            logger.info("ON 条件修复后: %s", _one_line(sql))

        except Exception as e:
            logger.warning(f"ON 条件修复失败: {e}")

        return sql

    def _fix_ambiguous_bare_columns(self, sql: str) -> str:
        """
        修复 SELECT/WHERE/ORDER BY 等子句中无表前缀的歧义裸列名。

        典型错误：
          SELECT "id", "create_time" FROM alarm_record JOIN ...
          —— 多表都有 id/create_time，数据库报错"歧义的列名"

        修复策略（正则两步法）：
          1. 先把所有 "table"."ambiguous_col" 格式中的内层裸 "id" 等
             替换成 "alarm_record"."xxx"，覆盖步骤2的误匹配
          2. 再把裸 "id" → "alarm_record"."id"
          3. 兜底：修复步骤1产生的 "table"."alarm_record"."col" 三段式畸形

        注意：只有 FROM/JOIN 子句中包含 alarm_record 表时才处理。
              如果 FROM 里根本没有 alarm_record 表，说明歧义列本来就属于其他表，
              不应强制改成 alarm_record. 前缀。
        """
        try:
            # 前置检查：只有 alarm_record 表在 FROM/JOIN 里时才处理歧义列名
            # 从完整 SQL 中提取所有表名（FROM 和 JOIN 子句）
            from_clause_match = re.search(
                r"FROM\s+(.+?)(?=\s+WHERE|\s+GROUP|\s+ORDER|\s+HIMIT|\s+OFFSET|\s+UNION|,|\s*$)",
                sql,
                re.IGNORECASE | re.DOTALL,
            )
            from_clause = from_clause_match.group(1) if from_clause_match else ""
            # 提取表名：支持 FWBZ."table" / "FWBZ"."table" / "table" / FWBZ.table
            defined_tables = set()
            for m in re.finditer(
                r'FWBZ\."(\w+)"|FWBZ\.(\w+)|"FWBZ"\.?"(\w+)"|"(\w+)"',
                from_clause,
                re.IGNORECASE,
            ):
                t = (
                    (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "")
                    .strip()
                    .lower()
                )
                if t:
                    defined_tables.add(t)
            if "alarm_record" not in defined_tables:
                logger.info("歧义列名修复跳过：FROM 中无 alarm_record")
                return sql

            # 歧义列名：多表共有，必须加 alarm_record. 前缀
            AMBIGUOUS = frozenset({"id", "create_time", "update_time", "sys_org_code"})

            # 步骤1：先把所有 "table"."xxx" 里的内层裸歧义列名替换成带前缀版本
            # 例如："device"."id" → "device"."alarm_record"."id"
            # 这样步骤2就不会误伤 qualified 格式
            for col in AMBIGUOUS:
                # 匹配 "table"."col" 中的内层引号区域
                # 捕获：("...") + (.+) + (") + (col) + (")
                # 替换："alarm_record"." —— 在内层列名前插入前缀
                # 简化写法：匹配整个 "table"."col"，捕获表名和列名，重构
                def expand_qualified(m):
                    # m.group(0) = "table"."col"，提取 table 和 col
                    full = m.group(0)
                    # "device"."id" → table="device", col="id"
                    # 逐个找引号：0=表名开头, 7=表名结尾/点, 9=列名开头, 12=列名结尾
                    first_quote = full.index('"')
                    second_quote = full.index('"', first_quote + 1)
                    # 列名开头 = 跳过 second_q 后的点，再跳过列名内容找下一个引号
                    col_start = full.index(
                        '"', second_quote + 2
                    )  # 跳过 "." 后找到列名开头引号
                    col_end = full.index('"', col_start + 1)  # 再找列名结尾引号
                    table = full[first_quote + 1 : second_quote]
                    col_val = full[col_start + 1 : col_end]
                    return '"' + table + '"."alarm_record"."' + col_val + '"'

                # 匹配 "xxx"."yyy" 格式（两个引号组，中间有点）
                pattern = r'"[^"]+"\.[^"]*"' + re.escape(col) + r'"'
                sql, n = re.subn(pattern, expand_qualified, sql, flags=re.IGNORECASE)
                if n > 0:
                    logger.info("歧义列 qualified 替换 %s 处: %s", n, col)

            # 步骤2：裸歧义列名加前缀（仅当前面没有表前缀时）
            for col in AMBIGUOUS:
                # 匹配裸 "id"：前面不是字母/数字/点/引号
                # 后面不是点/引号（确保不会跨 qualified 边界）
                def replace_bare(m):
                    return '"alarm_record"."' + col + '"'

                pattern = r'(?<![\w."])("' + re.escape(col) + r'")(?![\w."])'
                sql, n = re.subn(pattern, replace_bare, sql, flags=re.IGNORECASE)
                if n > 0:
                    logger.info("歧义列裸名替换 %s 处: %s", n, col)

            # 步骤3：兜底——修复步骤1产生的三段式 "table"."alarm_record"."col"
            # 例如："device"."alarm_record"."id" → "device"."id"
            sql, n = re.subn(
                r'"([^"]+)"\."alarm_record"\."([^"]+)"',
                r'"".""',
                sql,
                flags=re.IGNORECASE,
            )
            if n > 0:
                logger.info("歧义列三段式修复 %s 处", n)

            logger.info("歧义列名修复后: %s", _one_line(sql))
        except Exception as e:
            logger.warning(f"歧义列名修复失败: {e}")

        return sql

    def _fix_date_column_by_schema(self, sql: str) -> str:
        """按真实表结构精确修复日期列名混淆

        LLM 常见错误：把 "date"/"stat_date" 写成 "data_date"，
        或反过来把 "data_date" 写成 "date"/"stat_date"。

        真实表结构（来自 config/FWBZ_strut.sql）：
            table_venue_flow_hour                   → "data_date"（table_venue_flow 已废弃）
            table_parking_count / table_visitor_flow → "date"
            table_personnel_statistics             → "stat_date"

        策略：
            1. 解析 SQL 中 FROM/JOIN 的表别名映射 (alias → table)
            2. 对 qualified 引用 (alias."data_date")：按别名查真实表，
               查表的真实日期列名做替换
            3. 对 bare 引用 ("data_date")：若查询涉及的所有表都没有 data_date 列，才替换；
               若有任一表有 data_date 列，保留（交给列校验兜底）
        """
        try:
            from app.common.dameng import _load_schema_from_file

            schema = _load_schema_from_file()
            if not schema:
                return sql

            # 只在 SQL 含 "data_date" 或 "stat_date" 时才处理
            if not re.search(r'"(data_date|stat_date)"', sql, re.IGNORECASE):
                return sql

            # 日期列候选：data_date / date / stat_date
            DATE_COLS = ("data_date", "date", "stat_date")

            def _find_real_date_col(table_lower: str) -> Optional[str]:
                """返回该表的真实日期列名（小写），没有则 None"""
                cols = schema.get(table_lower, set())
                for c in DATE_COLS:
                    if c in cols:
                        return c
                return None

            # ========== 1. 解析 FROM/JOIN 的表+别名映射 ==========
            alias_to_table: dict[str, str] = {}
            sql_keywords_skip = {
                "select",
                "from",
                "where",
                "group",
                "order",
                "having",
                "limit",
                "offset",
                "union",
                "with",
                "on",
                "as",
                "join",
                "inner",
                "left",
                "right",
                "outer",
                "full",
                "cross",
                "and",
                "or",
                "not",
                "in",
                "is",
                "null",
                "like",
                "between",
                "exists",
                "case",
                "when",
                "then",
                "else",
                "end",
                "set",
                "values",
                "into",
                "update",
            }
            from_table_pattern = re.compile(
                r"\b(?:FROM|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN)\s+"
                r'(?:(?:"?FWBZ"?\s*\.\s*)?)?"?([A-Za-z_]\w*)"?'
                r'(?:\s+(?:AS\s+)?"?([A-Za-z_]\w*)"?)?',
                re.IGNORECASE,
            )
            for m in from_table_pattern.finditer(sql):
                table = m.group(1)
                alias = m.group(2)
                if not table or table.lower() in sql_keywords_skip:
                    continue
                tl = table.lower()
                if not alias or alias.lower() in sql_keywords_skip:
                    al = tl
                else:
                    al = alias.lower()
                alias_to_table[al] = tl

            real_tables = set(alias_to_table.values())

            # ========== 2. 处理 qualified 引用: alias."data_date"/alias."stat_date" ==========
            # 按 alias 反查真实表，再查该表的真实日期列名做替换
            def _replace_qualified(m):
                alias_part = m.group(1)  # 如 v. 或 "v".
                col = m.group(2).lower()  # data_date 或 stat_date
                alias_match = re.match(r'"?(\w+)"?\s*\.\s*$', alias_part)
                if alias_match:
                    alias = alias_match.group(1).lower()
                    table = alias_to_table.get(alias)
                    if table:
                        real_col = _find_real_date_col(table)
                        # 真实日期列存在 且 和 LLM 写的不同 → 替换
                        if real_col and real_col != col:
                            return f'{alias_part}"{real_col}"'
                return m.group(0)

            sql = re.sub(
                r'("?(\w+)"?\s*\.\s*)"(data_date|stat_date)"',
                _replace_qualified,
                sql,
                flags=re.IGNORECASE,
            )

            # ========== 3. 处理 bare "data_date"/"stat_date" ==========
            # 只在查询涉及的所有表都没有 data_date 列时，才替换 bare 引用
            # （如果有 table_venue_flow_hour 等有 data_date 的表，bare 引用归属不明，保留交给列校验）
            tables_have_data_date = {
                t for t in real_tables if "data_date" in schema.get(t, set())
            }
            if not tables_have_data_date and real_tables:
                # 所有表都没有 data_date 列，可以安全替换 bare 引用
                # 但需要按表的真实日期列替换，若有多种日期列则无法全局替换
                real_date_cols = {_find_real_date_col(t) for t in real_tables}
                real_date_cols.discard(None)
                # 如果所有表的真实日期列名一致，按该列名替换
                if len(real_date_cols) == 1:
                    target_col = real_date_cols.pop()
                    sql = re.sub(
                        r'"data_date"', f'"{target_col}"', sql, flags=re.IGNORECASE
                    )
                    sql = re.sub(
                        r'"stat_date"', f'"{target_col}"', sql, flags=re.IGNORECASE
                    )

            return sql
        except Exception as e:
            logger.warning(f"日期列修复失败: {e}")
            return sql

    def _format_column_label(self, col_name: str) -> str:
        """将英文列名格式化为中文标签"""
        mapping = {
            # 设备相关
            "device_name": "设备名称",
            "device_code": "设备编码",
            "device_type": "设备类型",
            "device_id": "设备ID",
            "run_state": "运行状态",
            "last_gather_time": "最后采集时间",
            "create_time": "创建时间",
            # 告警相关
            "alarm_content": "告警内容",
            "alarm_time": "告警时间",
            "alarm_category_name": "告警类别",
            "alarm_level_name": "告警级别",
            "alarm_status": "告警状态",
            "alarm_count": "告警数量",
            "charge_person_name": "责任人",
            # 场馆相关
            "venue_name": "场馆名称",
            "venue_id": "场馆ID",
            "floors": "楼层数",
            "orientation": "朝向",
            "longitude": "经度",
            "latitude": "纬度",
            # 空间相关
            "space_name": "空间名称",
            "space_id": "空间ID",
            "full_name": "完整名称",
            "full_id": "完整编号",
            # 分类相关
            "category_name": "分类名",
            "group_name": "分类名",
            "device_kind": "分类名",
            "category_id": "分类ID",
            "has_child": "是否有子级",
            # 能耗/计量
            "value": "数值",
            "total_energy": "总能耗",
            "carbon_emission": "碳排放",
            "metering_unit": "计量单位",
            "online": "在线情况",
            "region_name": "空间位置",
            "device_type": "设备类型",
            "spec": "规格",
            "cnt": "数量",
            # 客流/人员
            "today_in_count": "今日入场",
            "current_in_count": "当前在场数",
            "max_count": "最大人数",
            "average_duration": "平均时长",
            "today_entry_count": "今日入场数",
            "average_parking_duration": "平均停车时长",
            "remaining_space_count": "剩余车位数",
            "recognition_record_count": "识别记录数",
            "abnormal_warning_count": "异常告警数",
            # 照明相关
            "area_name": "区域名称",
            "area_code": "区域编码",
            "circuit_name": "回路名称",
            "all_duration": "总时长",
            "comstat": "通信状态",
            # 停车相关
            "stat_date": "统计日期",
            "data_date": "日期",
            "date": "日期",
            # 报告相关
            "report_type": "报告类型",
            "title": "标题",
            "summary": "摘要",
            "content": "内容",
            "target_name": "目标名称",
            "scope": "范围",
            # 统计相关
            "total_count": "总数",
            "online_count": "在线数",
            "offline_count": "离线数",
            "total_value": "总数值",
            "avg_value": "平均值",
            "max_value": "最大值",
            "min_value": "最小值",
            "count": "数量",
            "percentage": "占比",
            # 通用
            "location": "位置",
            "area": "面积",
            "status": "状态",
            "node_name": "节点名称",
            "node_code": "节点编码",
            "time_range": "时间范围",
            "created_at": "创建时间",
            "id": "ID",
            "pid": "父级ID",
            # 照明/其他
            "ceiling_h": "层高",
            "lighting": "照明",
            "basic_facility": "基本设施",
            "buildable": "可建面积",
            # 序号/分页
            "rn": "序号",
            "rownum": "序号",
            "rowno": "序号",
            "no": "序号",
            "num": "序号",
            # 特殊列名（大小写不敏感）
            "date": "日期",
            "time": "时间",
            "name": "名称",
            "code": "编码",
            "entry": "入场",
            "exit": "出场",
            "in": "在场",
            "out": "离场",
        }
        # 优先精确匹配
        if col_name in mapping:
            return mapping[col_name]
        # 其次模糊匹配（下划线转中文）
        result = col_name.replace("_", " ")
        return result.title()

    _STAT_DIM_PRIORITY = (
        "online",
        "run_state",
        "device_type",
        "region_name",
        "status",
        "category_name",
        "group_name",
        "device_kind",
        "meter_type",
        "alarm_level_name",
        "alarm_category_name",
        "venue_name",
        "space_name",
        "area_name",
        "energy_type",
    )
    _HIGH_CARD_CHART_KEYS = frozenset({
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
    })

    @staticmethod
    def _collapse_chart_items(
        items: List[tuple],
        *,
        max_slices: int = 20,
    ) -> List[tuple]:
        """类别过多时保留头部，其余打进「其他」，保证合计等于全量。"""
        items = [(str(n), float(v)) for n, v in items if n is not None]
        if len(items) <= max_slices:
            return items
        head = items[: max_slices - 1]
        other = sum(v for _, v in items[max_slices - 1 :])
        return head + [("其他", other)]

    @staticmethod
    def _quote_sql_ident(name: Optional[str]) -> str:
        raw = str(name or "").strip().strip('"')
        if not raw:
            return '"col"'
        return '"' + raw.replace('"', '""') + '"'

    @staticmethod
    def _sql_has_ident(sql: str, name: str) -> bool:
        ident = re.escape(name)
        return bool(
            re.search(rf'"{ident}"', sql or "", re.IGNORECASE)
            or re.search(rf"\.{ident}\b", sql or "", re.IGNORECASE)
        )

    def _ensure_listing_type_fk(self, sql: str, catalog=None) -> str:
        """明细漏选类型外键时，按 hephaestus_meta_nl_relation 补列，供按类型出图。"""
        if not sql or re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
            return sql
        tables = extract_sql_tables(sql)
        if not tables:
            return sql
        cat = catalog or get_catalog()
        col = listing_type_fk(cat, tables)
        if not col or self._sql_has_ident(sql, col):
            return sql
        patched = re.sub(
            r"(?i)\bSELECT\s+",
            f"SELECT {self._quote_sql_ident(col)}, ",
            sql,
            count=1,
        )
        if patched != sql:
            logger.info("明细已补选类型外键 %s.%s", tables[0], col)
        return patched

    def _compose_chart_sql(
        self,
        source_sql: Optional[str],
        *,
        cat_key: Optional[str],
        num_key: Optional[str] = None,
        count_mode: bool = False,
        full_stats: bool = False,
        dim_join: Optional[DimJoin] = None,
        already_aggregated: bool = False,
        fact_table: Optional[str] = None,
    ) -> str:
        """图表取数 SQL：明细按维 COUNT/SUM，外键 JOIN 名称列。"""
        inner = self._strip_result_limit(source_sql or "").strip().rstrip(";")
        if not inner:
            return ""
        if not cat_key:
            return inner
        if not self._sql_has_ident(inner, cat_key):
            table = fact_table or next(iter(extract_sql_tables(inner)), None)
            if table:
                inner = (
                    f"SELECT {self._quote_sql_ident(cat_key)}\n"
                    f'FROM "FWBZ".{self._quote_sql_ident(table)}'
                )
        cat = self._quote_sql_ident(cat_key)
        name_expr = f"chart_src.{cat}"
        join_sql = ""
        if dim_join and dim_join.to_table and dim_join.name_column:
            dim_table = self._quote_sql_ident(dim_join.to_table)
            dim_pk = self._quote_sql_ident(dim_join.to_column or "id")
            dim_name = self._quote_sql_ident(dim_join.name_column)
            jt = (dim_join.join_type or "LEFT").upper()
            if jt not in {"LEFT", "INNER"}:
                jt = "LEFT"
            name_expr = f"NVL(chart_dim.{dim_name}, '未知')"
            join_sql = (
                f"\n{jt} JOIN \"FWBZ\".{dim_table} chart_dim"
                f"\n  ON chart_src.{cat} = chart_dim.{dim_pk}"
            )
        if count_mode:
            sql = (
                f"SELECT {name_expr} AS name, COUNT(*) AS value\n"
                f"FROM (\n{inner}\n) chart_src{join_sql}\n"
                f"GROUP BY {name_expr}\n"
                f"ORDER BY value DESC"
            )
        elif already_aggregated:
            num = (
                f"chart_src.{self._quote_sql_ident(num_key)}" if num_key else "1"
            )
            sql = (
                f"SELECT {name_expr} AS name, {num} AS value\n"
                f"FROM (\n{inner}\n) chart_src{join_sql}"
            )
        else:
            num = (
                f"chart_src.{self._quote_sql_ident(num_key)}" if num_key else "1"
            )
            sql = (
                f"SELECT {name_expr} AS name, SUM({num}) AS value\n"
                f"FROM (\n{inner}\n) chart_src{join_sql}\n"
                f"GROUP BY {name_expr}\n"
                f"ORDER BY value DESC"
            )
        if not full_stats:
            sql += "\nLIMIT 20"
        return sql

    def _fetch_chart_items(self, chart_sql: Optional[str]) -> Optional[List[tuple]]:
        """执行图表 SQL，得到 (name, value)。失败返回 None，由调用方回退内存聚合。"""
        sql = (chart_sql or "").strip()
        if not sql:
            return None
        try:
            from app.common.sql_guard import validate as guard_validate

            guard = guard_validate(sql)
            if not guard.ok:
                logger.warning("图表 SQL 被安全门拒绝: %s", guard.reason)
                return None
            rows = execute_query(guard.sql)
            items: List[tuple] = []
            for row in rows or []:
                if "name" in row or "NAME" in row:
                    name = row.get("name", row.get("NAME"))
                    value = row.get("value", row.get("VALUE"))
                else:
                    vals = list(row.values())
                    if len(vals) < 2:
                        continue
                    name, value = vals[0], vals[1]
                if name is None or value is None:
                    continue
                items.append((str(name), float(value)))
            return items
        except Exception as exc:
            logger.warning("图表 SQL 执行失败，回退结果集聚合: %s", exc)
            return None

    def _sse_chart_packets(self, echarts: dict) -> List[str]:
        """chart 前先发 type=sql，供前端核对图表取数。"""
        if not echarts:
            return []
        chart_sql = echarts.pop("sql", "") or ""
        echarts.pop("_followup", None)
        return [
            f"data: {self._safe_json_dumps({'type': 'sql', 'sql': chart_sql})}\n\n",
            f"data: {self._safe_json_dumps({'type': 'chart', **echarts})}\n\n",
        ]

    def _repick_stat_category(
        self,
        data: List[dict],
        keys: List[str],
        key_to_column: dict,
        cat_key: Optional[str],
        cat_key_raw: Optional[str],
    ) -> tuple:
        """查看全部时优先用状态/类型等低基数列，避免按设备名画 20 根无意义的柱。"""
        if not data:
            return cat_key, cat_key_raw

        def unique_ratio(raw_key: str) -> float:
            vals = [str(row.get(raw_key, "")) for row in data]
            return len(set(vals)) / max(len(vals), 1)

        def find_raw(col: str) -> Optional[str]:
            if col in keys:
                return col
            for k in keys:
                if str(k).lower() == col.lower():
                    return k
            for raw, name in key_to_column.items():
                if str(name).lower() == col.lower():
                    return raw
            return None

        if cat_key and cat_key.lower() not in self._HIGH_CARD_CHART_KEYS:
            raw = cat_key_raw or find_raw(cat_key)
            if raw and unique_ratio(raw) <= 0.4:
                return cat_key, raw

        for dim in self._STAT_DIM_PRIORITY:
            raw = find_raw(dim)
            if not raw:
                continue
            sample = data[0].get(raw)
            if not isinstance(sample, (str, datetime, date, int, float, Decimal)):
                continue
            if unique_ratio(raw) > 0.4:
                continue
            return dim, raw
        return cat_key, cat_key_raw

    def _build_echarts(
        self,
        data: List[dict],
        question: str,
        *,
        full_stats: bool = False,
        source_sql: Optional[str] = None,
        prefer_dims: Optional[List[str]] = None,
        force_prefer: bool = False,
    ) -> dict:
        """根据查询结果构建 ECharts 配置。full_stats=True 时按全量聚合。"""
        if not data:
            return {}

        sample = data[0]
        keys = list(sample.keys())

        # 辅助函数：解析复杂列名表达式，提取真正的列名
        def _extract_column_name(expr: str) -> str:
            """从复杂表达式中提取列名"""
            # NVL("xxx", 0) -> xxx
            m = re.search(
                r'NVL\s*\(\s*"?([^",\)]+)"?\s*,\s*[^)]+\)', expr, re.IGNORECASE
            )
            if m:
                return m.group(1).strip()
            # 兼容旧格式 NVL("xxx", '默认值')
            m = re.search(r'NVL\s*\(\s*"?([^",\)]+)"?', expr, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            # TO_CHAR("table"."col", 'format') -> col
            m = re.search(r'"?\w+"?\."?(\w+)"?', expr, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            # 尝试直接取最后一部分
            parts = expr.split(".")
            if len(parts) > 1:
                last = parts[-1].strip("\" '")
                return last
            return expr

        # 预处理：建立复杂 key -> 干净列名 的映射
        key_to_column = {}
        for k in keys:
            col_name = _extract_column_name(k)
            key_to_column[k] = col_name

        plan: Optional[ChartPlan] = plan_stat_chart(
            source_sql=source_sql,
            keys=keys,
            question=question,
            data=data,
            prefer_dims=prefer_dims,
            force_prefer=force_prefer,
        )
        dim_join: Optional[DimJoin] = plan.join if plan else None
        already_aggregated = bool(plan.already_aggregated) if plan else False
        fact_table = plan.fact_table if plan else None
        chart_axis_label = "记录数量"

        cat_key = None
        cat_key_raw = None
        numeric_keys: List[str] = []

        if plan:
            cat_key_raw = plan.cat_key
            cat_key = key_to_column.get(plan.cat_key, plan.cat_key)
            chart_axis_label = plan.cat_label or plan.metric_label or chart_axis_label
            if plan.mode == "metric" and plan.metric_key:
                numeric_keys = [plan.metric_key]
            logger.info(
                "图表元数据: mode=%s dim=%s metric=%s join=%s label=%s",
                plan.mode,
                plan.cat_key,
                plan.metric_key,
                f"{dim_join.to_table}.{dim_join.name_column}" if dim_join else None,
                chart_axis_label,
            )
        else:
            readable_priority = [
                "category_name",
                "group_name",
                "device_kind",
                "online",
                "run_state",
                "device_type",
                "region_name",
                "venue_name",
                "space_name",
                "area_name",
                "location",
                "position",
                "alarm_category_name",
                "alarm_level_name",
                "status",
                "device_code",
                "node_code",
                "area_code",
                "circuit_code",
                "space_id",
                "venue_id",
                "device_id",
            ]
            for priority_key in readable_priority:
                if priority_key in keys:
                    v = sample.get(priority_key)
                    if isinstance(v, (str, datetime, date, int, float, Decimal)):
                        cat_key_raw = priority_key
                        cat_key = priority_key
                        break
                for raw_key, col_name in key_to_column.items():
                    if col_name.lower() == priority_key.lower():
                        v = sample.get(raw_key)
                        if isinstance(v, (str, datetime, date, int, float, Decimal)):
                            cat_key_raw = raw_key
                            cat_key = col_name
                            break
                if cat_key:
                    break
            if not cat_key:
                for k in keys:
                    v = sample.get(k)
                    col_name = key_to_column.get(k, k)
                    if col_name.lower() not in ["id", "bigint"] and isinstance(
                        v, (str, datetime, date)
                    ):
                        cat_key_raw = k
                        cat_key = col_name
                        break
            if full_stats:
                cat_key, cat_key_raw = self._repick_stat_category(
                    data, keys, key_to_column, cat_key, cat_key_raw
                )
            num_candidates = [
                k for k in keys if isinstance(sample.get(k), (int, float, Decimal))
            ]
            numeric_keys = [
                k
                for k in num_candidates
                if not re.match(r"^(id|bigint|.+_id)$", str(k), re.IGNORECASE)
            ]

        def _with_chart_sql(
            payload: dict, *, count_mode: bool, num_key: Optional[str] = None
        ) -> dict:
            payload["sql"] = self._compose_chart_sql(
                source_sql,
                cat_key=cat_key_raw or cat_key,
                num_key=num_key,
                count_mode=count_mode,
                full_stats=full_stats,
                dim_join=dim_join,
                already_aggregated=already_aggregated,
                fact_table=fact_table,
            )
            payload["_followup"] = {
                "cat_key": cat_key_raw or cat_key,
                "join": (
                    {
                        "to_table": dim_join.to_table,
                        "to_column": dim_join.to_column,
                        "name_column": dim_join.name_column,
                        "join_type": dim_join.join_type,
                        "label_cn": dim_join.label_cn,
                    }
                    if dim_join
                    else None
                ),
            }
            return payload

        # 明细无真实指标：按维 COUNT（外键 JOIN 名称），不要把 category_id 当 Y 轴
        if not numeric_keys and cat_key:
            chart_sql = self._compose_chart_sql(
                source_sql,
                cat_key=cat_key_raw or cat_key,
                count_mode=True,
                full_stats=full_stats,
                dim_join=dim_join,
                already_aggregated=False,
                fact_table=fact_table,
            )
            items = self._fetch_chart_items(chart_sql)
            if items and not dim_join:
                items = [
                    (self._format_category_label(cat_key, str(name), {}), val)
                    for name, val in items
                ]
            if not items:
                category_counts = {}
                for row in data:
                    key_val = str(row.get(cat_key_raw, "未知"))
                    display_val = self._format_category_label(cat_key, key_val, row)
                    category_counts[display_val] = (
                        category_counts.get(display_val, 0) + 1
                    )
                items = sorted(
                    category_counts.items(), key=lambda x: x[1], reverse=True
                )
            if full_stats:
                items = self._collapse_chart_items(items)
            else:
                items = items[:20]
            chart_data = [{"name": name, "value": count} for name, count in items]

            chart_title = self._gen_chart_title(question, chart_axis_label)
            if full_stats:
                chart_title = f"{chart_title}（全量）"
            chart_id = f"chart_{datetime.now().strftime('%H%M%S%f')}"

            if len(chart_data) <= 6:
                return _with_chart_sql(
                    {
                    "chartType": "pie",
                    "chartId": chart_id,
                    "option": {
                        "title": {"text": chart_title, "left": "center"},
                        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                        "legend": {"bottom": 10, "left": "center"},
                        "series": [
                            {
                                "type": "pie",
                                "radius": ["35%", "60%"],
                                "avoidLabelOverlap": False,
                                "itemStyle": {
                                    "borderRadius": 6,
                                    "borderColor": "#fff",
                                    "borderWidth": 2,
                                },
                                "label": {"show": True, "formatter": "{b}\n{c} ({d}%)"},
                                "data": chart_data,
                            }
                        ],
                    },
                    },
                    count_mode=True,
                )
            else:
                # 柱状图：按分类聚合后的数据
                x_axis_data = [str(name) for name, _ in items]
                series_data = [float(count) for _, count in items]

                return _with_chart_sql(
                    {
                    "chartType": "bar",
                    "chartId": chart_id,
                    "option": {
                        "title": {"text": chart_title, "left": "center"},
                        "tooltip": {
                            "trigger": "axis",
                            "axisPointer": {"type": "shadow"},
                        },
                        "grid": {
                            "left": "3%",
                            "right": "4%",
                            "bottom": "12%",
                            "containLabel": True,
                        },
                        "xAxis": {
                            "type": "category",
                            "data": x_axis_data,
                            "axisLabel": {"rotate": 30, "interval": 0},
                        },
                        "yAxis": {"type": "value", "name": "数量"},
                        "series": [
                            {
                                "type": "bar",
                                "data": series_data,
                                "itemStyle": {
                                    "color": {
                                        "type": "linear",
                                        "x": 0,
                                        "y": 0,
                                        "x2": 0,
                                        "y2": 1,
                                        "colorStops": [
                                            {"offset": 0, "color": "#5470C6"},
                                            {"offset": 1, "color": "#91CC75"},
                                        ],
                                    },
                                    "borderRadius": [4, 4, 0, 0],
                                },
                                "label": {
                                    "show": True,
                                    "position": "top",
                                    "formatter": "{c}",
                                },
                            }
                        ],
                    },
                    },
                    count_mode=True,
                )

        if not cat_key or not numeric_keys:
            return {}

        first_num_key = numeric_keys[0]
        clean_num_key = re.sub(
            r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*"([^"]+)"\s*\)$',
            r"\2",
            first_num_key,
            flags=re.IGNORECASE,
        )
        label = (
            (plan.cat_label if plan and plan.cat_label else None)
            or self._format_column_label(clean_num_key)
        )

        chart_sql = self._compose_chart_sql(
            source_sql,
            cat_key=cat_key_raw or cat_key,
            num_key=first_num_key,
            count_mode=False,
            full_stats=full_stats,
            dim_join=dim_join,
            already_aggregated=already_aggregated,
            fact_table=fact_table,
        )
        fetched = self._fetch_chart_items(chart_sql)
        if fetched:
            items = self._collapse_chart_items(fetched) if full_stats else fetched[:20]
        elif full_stats:
            agg: dict[str, float] = {}
            for row in data:
                raw_value = str(row.get(cat_key_raw, ""))
                display_value = self._format_category_label(cat_key, raw_value, row)
                agg[display_value] = agg.get(display_value, 0.0) + float(
                    row.get(first_num_key, 0) or 0
                )
            items = self._collapse_chart_items(
                sorted(agg.items(), key=lambda x: x[1], reverse=True)
            )
        else:
            agg = {}
            for row in data:
                raw_value = str(row.get(cat_key_raw, ""))
                display_value = self._format_category_label(cat_key, raw_value, row)
                agg[display_value] = agg.get(display_value, 0.0) + float(
                    row.get(first_num_key, 0) or 0
                )
            items = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:20]
        x_axis_data = [name for name, _ in items]
        series_data = [value for _, value in items]

        chart_title = self._gen_chart_title(question, label)
        if full_stats:
            chart_title = f"{chart_title}（全量）"
        chart_id = f"chart_{datetime.now().strftime('%H%M%S%f')}"

        if len(x_axis_data) <= 6:
            pie_data = [
                {"name": x_axis_data[i], "value": series_data[i]}
                for i in range(len(x_axis_data))
            ]
            return _with_chart_sql(
                {
                "chartType": "pie",
                "chartId": chart_id,
                "option": {
                    "title": {"text": chart_title, "left": "center"},
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                    "legend": {"bottom": 10, "left": "center"},
                    "series": [
                        {
                            "type": "pie",
                            "radius": ["35%", "60%"],
                            "avoidLabelOverlap": False,
                            "itemStyle": {
                                "borderRadius": 6,
                                "borderColor": "#fff",
                                "borderWidth": 2,
                            },
                            "label": {"show": True, "formatter": "{b}\n{c} ({d}%)"},
                            "data": pie_data,
                        }
                    ],
                },
                },
                count_mode=False,
                num_key=first_num_key,
            )
        else:
            return _with_chart_sql(
                {
                "chartType": "bar",
                "chartId": chart_id,
                "option": {
                    "title": {"text": chart_title, "left": "center"},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {
                        "left": "3%",
                        "right": "4%",
                        "bottom": "12%",
                        "containLabel": True,
                    },
                    "xAxis": {
                        "type": "category",
                        "data": x_axis_data,
                        "axisLabel": {"rotate": 30, "interval": 0},
                    },
                    "yAxis": {"type": "value", "name": label},
                    "series": [
                        {
                            "type": "bar",
                            "data": series_data,
                            "itemStyle": {
                                "color": {
                                    "type": "linear",
                                    "x": 0,
                                    "y": 0,
                                    "x2": 0,
                                    "y2": 1,
                                    "colorStops": [
                                        {"offset": 0, "color": "#5470C6"},
                                        {"offset": 1, "color": "#91CC75"},
                                    ],
                                },
                                "borderRadius": [4, 4, 0, 0],
                            },
                            "label": {
                                "show": True,
                                "position": "top",
                                "formatter": "{c}",
                            },
                        }
                    ],
                },
                },
                count_mode=False,
                num_key=first_num_key,
            )

    def _format_category_label(self, col_key: str, raw_value: str, row: dict) -> str:
        """格式化分类标签，使人类更易读"""
        if not raw_value or raw_value in ["None", "null", "-"]:
            return "未知"

        if col_key.lower() in {"run_state", "status", "online"}:
            raw = raw_value.strip().lower()
            if raw.endswith(".0"):
                raw = raw[:-2]
            mapped = {
                "0": "离线",
                "1": "在线",
                "2": "故障",
                "offline": "离线",
                "online": "在线",
                "false": "离线",
                "true": "在线",
            }
            return mapped.get(raw, raw_value)

        # 编码类列的格式化规则
        code_format_rules = {
            "device_code": lambda v: self._format_device_code(v, row),
            "device_type": lambda v: self._format_device_type(v),
            "node_code": lambda v: self._format_node_code(v, row),
            "space_name": lambda v: v if v else "未知空间",
            "area_name": lambda v: v if v else "未知区域",
            "venue_name": lambda v: v if v else "未知场馆",
        }

        # 如果是编码类列，进行格式化
        if col_key in code_format_rules:
            return code_format_rules[col_key](raw_value)

        # 对于普通字符串，截断过长的值
        if len(raw_value) > 15:
            return raw_value[:12] + "..."
        return raw_value

    def _format_device_code(self, code: str, row: dict) -> str:
        """格式化设备编码为人类可读名称"""
        # 如果有 device_name，优先使用
        if row.get("device_name") and row.get("device_name") not in [None, "None", ""]:
            return str(row["device_name"])

        # 设备编码解析规则
        if not code:
            return "未知设备"

        # 尝试从编码推断类型
        code_upper = code.upper()
        if "KT" in code_upper:
            return f"空调-{code}"
        elif "XF" in code_upper:
            return f"新风-{code}"
        elif "CH" in code_upper:
            return f"冷机-{code}"
        elif "PV" in code_upper:
            return f"光伏-{code}"
        elif "PD" in code_upper or "DP" in code_upper:
            return f"配电-{code}"
        elif "ZT" in code_upper:
            return f"照明-{code}"

        # 通用：直接返回编码（截断过长的）
        if len(code) > 12:
            return code[:10] + "..."
        return code

    def _format_device_type(self, device_type: str) -> str:
        """格式化设备类型为中文"""
        type_mapping = {
            "1": "仪表",
            "2": "设备",
            "meter": "仪表",
            "device": "设备",
            "ac": "空调",
            "air_condition": "空调机组",
            "fresh_air": "新风机组",
            "power": "配电",
            "light": "照明",
            "pv": "光伏",
        }
        return type_mapping.get(str(device_type).lower(), str(device_type))

    def _format_node_code(self, code: str, row: dict) -> str:
        """格式化节点编码为人类可读名称"""
        # 如果有 node_name，优先使用
        if row.get("node_name") and row.get("node_name") not in [None, "None", ""]:
            return str(row["node_name"])

        if not code:
            return "未知节点"
        if len(code) > 12:
            return code[:10] + "..."
        return code

    def _gen_chart_title(self, question: str, label: str) -> str:
        """根据问题生成图表标题"""
        q_short = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", question)[:20]
        return f"{q_short} {label}分布" if q_short else f"{label}分布"

    _DETAIL_CAP = 500
    _AGGREGATE_CAP = 200
    _COUNT_QUESTION_KWS = (
        "有多少",
        "多少个",
        "多少台",
        "共几",
        "总共多少",
        "总数",
        "共多少",
    )
    _VIEW_ALL_HINT = "回复「查看全部」则进行全部信息查看。"

    def _sql_has_group_by(self, sql: str) -> bool:
        return bool(re.search(r"\bGROUP\s+BY\b", sql or "", re.IGNORECASE))

    def _sql_safety_cap(self, sql: str) -> int:
        """明细 500 / 聚合 200，与 sql_guard、SQL 生成侧一致。"""
        return self._AGGREGATE_CAP if self._sql_has_group_by(sql) else self._DETAIL_CAP

    def _extract_sql_limit(self, sql: str) -> Optional[int]:
        if not sql:
            return None
        m = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"\bFETCH\s+FIRST\s+(\d+)\s+ROWS", sql, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _strip_result_limit(self, sql: str) -> str:
        s = (sql or "").strip().rstrip(";").strip()
        s = re.sub(r"\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$", "", s, flags=re.IGNORECASE)
        s = re.sub(
            r"\s+FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\s*$", "", s, flags=re.IGNORECASE
        )
        return s.strip()

    def _is_truncated_preview(self, sql: str, row_count: int) -> bool:
        """只有撞上安全上限（500/200）才算截断；LIMIT 10 这类业务分页不算。"""
        if row_count <= 0:
            return False
        ceiling = self._sql_safety_cap(sql)
        applied = self._extract_sql_limit(sql)
        if applied is not None and applied < ceiling:
            return False
        return row_count >= ceiling

    def _count_unbounded_rows(self, sql: str) -> Optional[int]:
        """去掉 LIMIT 后包一层 COUNT(*)，失败返回 None。"""
        inner = self._strip_result_limit(sql)
        if not inner:
            return None
        count_sql = f'SELECT COUNT(*) AS "total_count" FROM ({inner}) "_cnt"'
        try:
            from app.common.sql_guard import validate as guard_validate

            guard = guard_validate(count_sql)
            if not guard.ok:
                logger.warning("全量 COUNT 被安全门拒绝: %s", guard.reason)
                return None
            rows = execute_query(guard.sql)
            if not rows:
                return None
            raw = next(iter(rows[0].values()), None)
            if raw is None:
                return None
            return int(raw)
        except Exception as exc:
            logger.warning("全量 COUNT 失败: %s", exc)
            return None

    def _resolve_result_cardinality(
        self, sql: str, data: List[dict]
    ) -> tuple[int, Optional[int], bool]:
        """返回 (preview_count, total_count, truncated)。"""
        preview = len(data or [])
        truncated = self._is_truncated_preview(sql, preview)
        total: Optional[int] = None
        if truncated:
            total = self._count_unbounded_rows(sql)
        else:
            total = preview
        return preview, total, truncated

    def _is_count_question(self, question: str) -> bool:
        q = question or ""
        return any(kw in q for kw in self._COUNT_QUESTION_KWS)

    def _append_view_all_hint(self, summary: str, truncated: bool) -> str:
        """截断结果在总结末尾追加操作提示（代码追加，不占模型 200 字配额）。"""
        text = (summary or "").replace("\n", " ").replace("\r", "").strip()
        if not truncated or not text:
            return text
        if "查看全部" in text:
            return text
        return f"{text} {self._VIEW_ALL_HINT}"

    def _query_store_key(self, client_ip: Optional[str]) -> str:
        return (client_ip or "unknown").strip() or "unknown"

    def _remember_truncated_query(
        self,
        client_ip: Optional[str],
        *,
        sql: str,
        question: str,
        qid: Optional[str],
        preview_count: int,
        total_count: Optional[int],
    ) -> None:
        _LAST_TRUNCATED_QUERY[self._query_store_key(client_ip)] = {
            "sql": sql,
            "question": question,
            "qid": qid,
            "preview_count": preview_count,
            "total_count": total_count,
            "ts": time.time(),
        }

    def _load_truncated_query(
        self, client_ip: Optional[str]
    ) -> Optional[dict[str, Any]]:
        key = self._query_store_key(client_ip)
        ctx = _LAST_TRUNCATED_QUERY.get(key)
        if not ctx:
            return None
        if time.time() - float(ctx.get("ts") or 0) > _VIEW_ALL_TTL_SEC:
            _LAST_TRUNCATED_QUERY.pop(key, None)
            return None
        return ctx

    def _clear_truncated_query(self, client_ip: Optional[str]) -> None:
        _LAST_TRUNCATED_QUERY.pop(self._query_store_key(client_ip), None)

    def _chart_slice_names(self, echarts: Optional[dict]) -> List[str]:
        if not echarts:
            return []
        option = echarts.get("option") or {}
        names: List[str] = []
        xaxis = option.get("xAxis")
        if isinstance(xaxis, dict):
            for n in xaxis.get("data") or []:
                if n is not None and str(n).strip():
                    names.append(str(n).strip())
        if not names:
            for series in option.get("series") or []:
                for item in series.get("data") or []:
                    if isinstance(item, dict) and item.get("name") not in (None, ""):
                        names.append(str(item["name"]).strip())
        seen = set()
        out = []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def _is_chart_slice_sql(self, sql: str) -> bool:
        """下钻 SQL 不能当成下一轮匹配用的父图。"""
        text = sql or ""
        if "slice_dim" in text:
            return True
        # UNION 等无维表 JOIN 的切片：FROM (父SQL) src WHERE CAST(src."分类" ...
        return bool(
            re.search(r"\)\s+src\s+WHERE\s+CAST\s*\(\s*src\.", text, re.IGNORECASE)
        )

    def _remember_chart_followup(
        self,
        client_ip: Optional[str],
        *,
        sql: str,
        question: str,
        qid: Optional[str],
        echarts: Optional[dict],
        replace: bool = False,
    ) -> None:
        slices = self._chart_slice_names(echarts)
        follow = (echarts or {}).get("_followup") or {}
        if not slices or not sql:
            return
        key = self._query_store_key(client_ip)
        # 某一类设备的明细/在线情况图：不覆盖父图切片，便于接着看其它类
        if not replace and self._is_chart_slice_sql(sql):
            return
        _LAST_CHART_FOLLOWUP[key] = {
            "sql": self._strip_result_limit(sql),
            "question": question,
            "qid": qid,
            "cat_key": follow.get("cat_key"),
            "join": follow.get("join"),
            "slices": slices,
        }
        logger.info(
            "记住图表切片: n=%s dim=%s join=%s sample=%s",
            len(slices),
            follow.get("cat_key"),
            (follow.get("join") or {}).get("to_table"),
            slices[:5],
        )

    def _load_chart_followup(
        self, client_ip: Optional[str]
    ) -> Optional[dict[str, Any]]:
        return _LAST_CHART_FOLLOWUP.get(self._query_store_key(client_ip))

    def _remember_last_result(
        self,
        client_ip: Optional[str],
        *,
        sql: str,
        keys: List[str],
        question: str,
        qid: Optional[str],
    ) -> None:
        if not sql or not keys:
            return
        _LAST_RESULT_QUERY[self._query_store_key(client_ip)] = {
            "sql": self._strip_result_limit(sql),
            "keys": list(keys),
            "question": question,
            "qid": qid,
        }

    def _load_last_result(self, client_ip: Optional[str]) -> Optional[dict[str, Any]]:
        return _LAST_RESULT_QUERY.get(self._query_store_key(client_ip))

    def _parse_chart_regroup_phrase(self, question: str) -> Optional[str]:
        """用户是否明确要求按某一列重绘统计图。"""
        raw = (question or "").strip()
        if len(raw) < 4:
            return None
        m = _CHART_REGROUP_RE.search(raw)
        if not m:
            return None
        phrase = re.sub(r"[\s的]+$", "", (m.group(1) or "").strip("\"'“”‘’「」『』 "))
        phrase = re.sub(r"^(这个|该|此)", "", phrase)
        if len(phrase) < 1 or len(phrase) > 24:
            return None
        return phrase

    def _available_chart_dim_keys(self, keys: List[str]) -> List[str]:
        skip = self._HIGH_CARD_CHART_KEYS | {
            "cnt",
            "count",
            "value",
            "total_value",
            "rn",
            "rownum",
            "rowno",
        }
        out = []
        for k in keys or []:
            name = str(k).strip()
            if not name or name.lower() in skip:
                continue
            if re.match(r"^(id|.+_id)$", name, re.IGNORECASE):
                continue
            out.append(name)
        return out

    def _resolve_chart_dim_phrase(
        self, phrase: str, keys: List[str]
    ) -> Optional[str]:
        """把「空间位置 / area_name」解析成上一轮结果里真实存在的列。"""
        want = (phrase or "").strip().strip("\"'")
        if not want or not keys:
            return None
        key_map = {str(k).lower(): k for k in keys}
        if want.lower() in key_map:
            raw = key_map[want.lower()]
            if str(raw).lower() not in self._HIGH_CARD_CHART_KEYS:
                return raw
            return None
        label_map = {}
        for k in keys:
            label_map[self._format_column_label(str(k))] = k
        if want in label_map:
            raw = label_map[want]
            if str(raw).lower() not in self._HIGH_CARD_CHART_KEYS:
                return raw
        ranked_aliases = sorted(_CHART_DIM_ALIASES, key=lambda x: len(x[0]), reverse=True)
        for alias, cols in ranked_aliases:
            if want != alias and alias not in want and want not in alias:
                continue
            for col in cols:
                if col.lower() in key_map:
                    return key_map[col.lower()]
        # 标签模糊：区域名称 vs 区域
        for label, raw in label_map.items():
            if want in label or label in want:
                if str(raw).lower() not in self._HIGH_CARD_CHART_KEYS:
                    return raw
        return None

    def _normalize_slice_question(self, question: str) -> str:
        s = (question or "").strip()
        s = s.strip("\"'“”‘’「」『』")
        return s.strip()

    def _match_last_chart_slice(
        self, question: str, slices: List[str]
    ) -> Optional[str]:
        """用户原话是否点到上一张图的某个切片名（不依赖特定问法）。"""
        if self._is_exact_view_all(question):
            return None
        raw = self._normalize_slice_question(question)
        if len(raw) < 2:
            return None
        candidates = [
            str(s).strip()
            for s in slices or []
            if s is not None and str(s).strip() and str(s).strip() != "其他"
        ]
        if not candidates:
            return None
        ranked = sorted(candidates, key=len, reverse=True)
        for name in ranked:
            if raw == name:
                return name
        for name in ranked:
            if name in raw:
                return name
        return None

    def _compose_slice_filter_sql(
        self, ctx: dict[str, Any], slice_name: str
    ) -> str:
        inner = self._strip_result_limit(ctx.get("sql") or "").strip().rstrip(";")
        cat_key = ctx.get("cat_key")
        join = ctx.get("join") or {}
        if not inner or not cat_key:
            return ""
        literal = str(slice_name).replace("'", "''")
        cat = self._quote_sql_ident(cat_key)
        if join.get("to_table") and join.get("name_column"):
            dim_table = self._quote_sql_ident(join["to_table"])
            dim_pk = self._quote_sql_ident(join.get("to_column") or "id")
            dim_name = self._quote_sql_ident(join["name_column"])
            if literal == "未知":
                return (
                    f"SELECT src.*\n"
                    f"FROM (\n{inner}\n) src\n"
                    f'LEFT JOIN "FWBZ".{dim_table} slice_dim\n'
                    f"  ON src.{cat} = slice_dim.{dim_pk}\n"
                    f"WHERE slice_dim.{dim_name} IS NULL"
                )
            return (
                f"SELECT src.*\n"
                f"FROM (\n{inner}\n) src\n"
                f'LEFT JOIN "FWBZ".{dim_table} slice_dim\n'
                f"  ON src.{cat} = slice_dim.{dim_pk}\n"
                f"WHERE NVL(slice_dim.{dim_name}, '未知') = '{literal}'"
            )
        return (
            f"SELECT src.*\n"
            f"FROM (\n{inner}\n) src\n"
            f"WHERE CAST(src.{cat} AS VARCHAR) = '{literal}'"
        )

    def _sql_is_category_count_overview(self, sql: str) -> bool:
        """上一轮是分类计数（GROUP BY / UNION COUNT），切片不能只筛这一行。"""
        text = sql or ""
        if not re.search(r"\bCOUNT\s*\(", text, re.IGNORECASE):
            return False
        return bool(
            re.search(r"\bUNION\b", text, re.IGNORECASE)
            or re.search(r"\bGROUP\s+BY\b", text, re.IGNORECASE)
        )

    def _listing_qid_for_chart_slice(
        self, ctx: dict[str, Any], slice_name: str
    ) -> Optional[str]:
        """概览图点某一类时，改走清单里的「查看xxx」明细题。"""
        if not self._sql_is_category_count_overview(ctx.get("sql") or ""):
            return None
        name = (slice_name or "").strip()
        if not name:
            return None
        parent_qid = str(ctx.get("qid") or "").strip()
        parent_domain = parent_qid.split(".")[0] if "." in parent_qid else ""
        variants = [name]
        if name.endswith("设备"):
            variants.append(name[:-2])
        else:
            variants.append(name + "设备")
        titles = {v: True for v in variants}
        titles.update({f"查看{v}": True for v in variants})
        titles.update({f"{v}列表": True for v in variants})
        titles.update({f"查看{v}列表": True for v in variants})

        from app.chat.sql_template_loader import get_template_loader

        loader = get_template_loader()
        hits: List[tuple] = []
        for qid in loader.all_qids():
            if qid == parent_qid:
                continue
            title = re.sub(r"\s+", "", (loader.get_title(qid) or "").strip())
            title = title.split("，")[0].split(",")[0]
            if title not in titles:
                continue
            if not loader.get_executable_sql(qid):
                continue
            same = 0 if parent_domain and qid.startswith(parent_domain + ".") else 1
            hits.append((same, qid))
        if hits:
            hits.sort()
            return hits[0][1]
        fallback = {
            "楼控设备": "7.2",
            "楼控": "7.2",
            "冷源设备": "7.3",
            "冷源": "7.3",
            "电表设备": "7.4",
            "电表": "7.4",
            "安防设备": "7.5",
            "安防": "7.5",
        }
        mapped = fallback.get(name) or fallback.get(name.replace("设备", ""))
        if mapped and mapped != parent_qid:
            return mapped
        return None

    def _normalize_view_all_text(self, question: str) -> str:
        return re.sub(r"[\s。！？!?,.，、]+", "", question or "")

    def _is_exact_view_all(self, question: str) -> bool:
        compact = self._normalize_view_all_text(question)
        if compact in {
            "查看全部",
            "看全部",
            "显示全部",
            "全部数据",
            "全部信息",
            "导出全部",
            "查看全部数据",
            "查看全部信息",
            "请查看全部",
        }:
            return True
        return compact.endswith("查看全部") and len(compact) <= 8

    def _load_view_all_prompt(self) -> str:
        global _VIEW_ALL_PROMPT
        if _VIEW_ALL_PROMPT is not None:
            return _VIEW_ALL_PROMPT
        path = Path(__file__).resolve().parents[2] / "prompts" / "view_all.md"
        try:
            _VIEW_ALL_PROMPT = path.read_text(encoding="utf-8")
        except OSError:
            _VIEW_ALL_PROMPT = '判断用户是否要查看上一轮截断查询的全部数据。只输出 JSON {"action":"export_all"} 或 {"action":"unrelated"}。'
        return _VIEW_ALL_PROMPT

    def _classify_view_all_intent(
        self,
        question: str,
        last_query: Optional[dict[str, Any]],
    ) -> bool:
        """是否要把上一轮截断结果一次拉全。"""
        if self._is_exact_view_all(question):
            return True
        if not last_query:
            return False
        compact = self._normalize_view_all_text(question)
        if "全部" not in compact or len(compact) > 24:
            return False
        prompt = self._load_view_all_prompt()
        user = (
            f"{prompt}\n\n## 用户原话\n{question}\n\n"
            f"## 上一轮\n已截断：是；预览 {last_query.get('preview_count')} 条；"
            f"全量 {last_query.get('total_count')}\n"
        )
        try:
            raw = self.ollama.call_llm(
                [{"role": "user", "content": user}],
                temperature=0.1,
                json_mode=True,
            )
            text = (raw or "").strip()
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                payload = json.loads(text[start : end + 1])
                return str(payload.get("action") or "").strip() == "export_all"
        except Exception as exc:
            logger.warning("查看全部意图判别失败: %s", exc)
        return False

    async def _handle_view_all_followup(
        self,
        *,
        question: str,
        client_ip: Optional[str],
        on_summary: Optional[callable],
        stream_summary: dict[str, Any],
    ) -> AsyncIterator[str]:
        last = self._load_truncated_query(client_ip)
        if not last or not last.get("sql"):
            msg = "请先完成一次查询。结果超出预览条数后，再回复「查看全部」。"
            stream_summary["mode"] = "db"
            stream_summary["error"] = "无上一轮截断查询"
            stream_summary["summary"] = msg
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '未找到可展开的上一轮查询'})}\n\n"
            yield f"data: {self._safe_json_dumps({'type': 'message', 'content': msg})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return

        orig_question = last.get("question") or question
        sql = last["sql"]
        stream_summary["mode"] = "db"
        stream_summary["qid"] = last.get("qid")
        stream_summary["sql"] = sql
        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在查询全部数据...'})}\n\n"
        yield f"data: {self._safe_json_dumps({'type': 'sql', 'sql': self._strip_result_limit(sql)})}\n\n"

        data, err = self._execute_sql(sql, result_cap=_VIEW_ALL_HARD_CAP)
        if err:
            stream_summary["error"] = f"查询执行失败: {err}"
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

        row_count = len(data)
        still_capped = row_count >= _VIEW_ALL_HARD_CAP
        total_count = last.get("total_count") if still_capped else row_count
        stream_summary["row_count"] = row_count
        stream_summary["preview_count"] = row_count
        stream_summary["total_count"] = total_count
        stream_summary["truncated"] = still_capped

        vue_table = self._build_vue_table(data, max_rows=None)
        stream_summary["table"] = vue_table
        self._remember_last_result(
            client_ip,
            sql=self._strip_result_limit(sql),
            keys=list(data[0].keys()),
            question=orig_question,
            qid=last.get("qid"),
        )
        yield f"data: {self._safe_json_dumps({'type': 'table', 'sql': self._strip_result_limit(sql), **vue_table})}\n\n"
        await asyncio.sleep(0)

        echarts = self._build_echarts(
            data,
            orig_question,
            full_stats=True,
            source_sql=self._strip_result_limit(sql),
        )
        if echarts:
            stream_summary["chart"] = {
                "chartType": echarts.get("chartType"),
                "chartId": echarts.get("chartId"),
            }
            stream_summary["chart_sql"] = echarts.get("sql") or ""
            self._remember_chart_followup(
                client_ip,
                sql=self._strip_result_limit(sql),
                question=orig_question,
                qid=last.get("qid"),
                echarts=echarts,
            )
            for packet in self._sse_chart_packets(echarts):
                yield packet
            await asyncio.sleep(0)

        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
        summary = self._generate_summary(
            orig_question,
            data,
            vue_table,
            preview_count=row_count,
            total_count=total_count,
            truncated=still_capped,
        )
        if still_capped:
            summary = self._append_view_all_hint(summary, True)
        stream_summary["summary"] = summary
        yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
        if not still_capped:
            self._clear_truncated_query(client_ip)
        if on_summary:
            await on_summary(stream_summary)

    async def _reject_chart_regroup(
        self,
        *,
        phrase: str,
        last_result: Optional[dict[str, Any]],
        on_summary: Optional[callable],
        stream_summary: dict[str, Any],
    ) -> AsyncIterator[str]:
        if not last_result:
            msg = (
                f"请先完成一次查询，再说明要按哪一列统计，例如：按照{phrase}统计。"
            )
        else:
            labels = [
                self._format_column_label(k)
                for k in self._available_chart_dim_keys(last_result.get("keys") or [])
            ]
            shown = "、".join(labels[:8]) if labels else "无可用分类列"
            msg = f"上一轮结果没有「{phrase}」列，无法按它重绘统计图。当前可按：{shown}。"
        stream_summary["mode"] = "db"
        stream_summary["error"] = "无法按指定列统计"
        stream_summary["summary"] = msg
        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '无法按指定列统计'})}\n\n"
        yield f"data: {self._safe_json_dumps({'type': 'message', 'content': msg})}\n\n"
        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
        if on_summary:
            await on_summary(stream_summary)

    async def _handle_chart_regroup_followup(
        self,
        *,
        question: str,
        dim_key: str,
        dim_phrase: str,
        client_ip: Optional[str],
        on_summary: Optional[callable],
        stream_summary: dict[str, Any],
    ) -> AsyncIterator[str]:
        last = self._load_last_result(client_ip) or {}
        sql = (last.get("sql") or "").strip()
        if not sql:
            async for chunk in self._reject_chart_regroup(
                phrase=dim_phrase,
                last_result=None,
                on_summary=on_summary,
                stream_summary=stream_summary,
            ):
                yield chunk
            return

        stream_summary["mode"] = "db"
        stream_summary["qid"] = last.get("qid")
        stream_summary["sql"] = sql
        label = self._format_column_label(dim_key)
        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': f'正在按「{label}」重新统计...'})}\n\n"
        yield f"data: {self._safe_json_dumps({'type': 'sql', 'sql': sql})}\n\n"

        data, err = self._execute_sql(sql)
        if err:
            stream_summary["error"] = f"查询执行失败: {err}"
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': f'查询执行失败: {err}'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return
        if not data:
            msg = "上一轮查询没有数据，无法重绘统计图。"
            stream_summary["error"] = "查询结果为空"
            stream_summary["summary"] = msg
            yield f"data: {self._safe_json_dumps({'type': 'message', 'content': msg})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return

        preview_count, total_count, truncated = self._resolve_result_cardinality(
            sql, data
        )
        stream_summary["row_count"] = preview_count
        stream_summary["preview_count"] = preview_count
        stream_summary["total_count"] = total_count
        stream_summary["truncated"] = truncated

        vue_table = self._build_vue_table(data)
        stream_summary["table"] = vue_table
        self._remember_last_result(
            client_ip,
            sql=sql,
            keys=list(data[0].keys()),
            question=last.get("question") or question,
            qid=last.get("qid"),
        )
        yield f"data: {self._safe_json_dumps({'type': 'table', 'sql': sql, **vue_table})}\n\n"
        await asyncio.sleep(0)

        echarts = self._build_echarts(
            data,
            question,
            source_sql=sql,
            prefer_dims=[dim_key],
            force_prefer=True,
        )
        if echarts:
            stream_summary["chart"] = {
                "chartType": echarts.get("chartType"),
                "chartId": echarts.get("chartId"),
            }
            stream_summary["chart_sql"] = echarts.get("sql") or ""
            self._remember_chart_followup(
                client_ip,
                sql=sql,
                question=last.get("question") or question,
                qid=last.get("qid"),
                echarts=echarts,
                replace=True,
            )
            for packet in self._sse_chart_packets(echarts):
                yield packet
            await asyncio.sleep(0)
        else:
            msg = f"无法按「{label}」生成统计图，请换一列再试。"
            stream_summary["error"] = "无法按指定列统计"
            stream_summary["summary"] = msg
            yield f"data: {self._safe_json_dumps({'type': 'message', 'content': msg})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return

        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
        summary = self._generate_summary(
            question,
            data,
            vue_table,
            preview_count=preview_count,
            total_count=total_count,
            truncated=truncated,
        )
        summary = self._append_view_all_hint(summary, truncated)
        stream_summary["summary"] = summary
        yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
        if on_summary:
            await on_summary(stream_summary)

    async def _handle_chart_slice_followup(
        self,
        *,
        question: str,
        slice_name: str,
        client_ip: Optional[str],
        on_summary: Optional[callable],
        stream_summary: dict[str, Any],
    ) -> AsyncIterator[str]:
        ctx = self._load_chart_followup(client_ip) or {}
        listing_qid = self._listing_qid_for_chart_slice(ctx, slice_name)
        sql = ""
        follow_qid = ctx.get("qid")
        if listing_qid:
            from app.chat.sql_template_loader import get_template_loader

            canned = get_template_loader().get_executable_sql(listing_qid)
            sql = self._finalize_template_sql(canned or "", qid=listing_qid) or ""
            follow_qid = listing_qid
            logger.info(
                "图表切片改走清单明细 qid=%s slice=%s", listing_qid, slice_name
            )
        if not sql:
            sql = self._compose_slice_filter_sql(ctx, slice_name)
        if not sql:
            stream_summary["error"] = "无法按图表切片生成查询"
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': '无法按上一张图的切片筛选数据。'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return

        stream_summary["mode"] = "db"
        stream_summary["qid"] = follow_qid
        stream_summary["sql"] = sql
        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': f'正在查看「{slice_name}」...'})}\n\n"
        yield f"data: {self._safe_json_dumps({'type': 'sql', 'sql': sql})}\n\n"

        data, err = self._execute_sql(sql)
        if err:
            stream_summary["error"] = f"查询执行失败: {err}"
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': f'查询执行失败: {err}'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return
        if not data:
            msg = f"上一张图中的「{slice_name}」没有对应明细。"
            stream_summary["error"] = "查询结果为空"
            stream_summary["summary"] = msg
            yield f"data: {self._safe_json_dumps({'type': 'message', 'content': msg})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)
            return

        preview_count, total_count, truncated = self._resolve_result_cardinality(
            sql, data
        )
        stream_summary["row_count"] = preview_count
        stream_summary["preview_count"] = preview_count
        stream_summary["total_count"] = total_count
        stream_summary["truncated"] = truncated
        if truncated:
            self._remember_truncated_query(
                client_ip,
                sql=sql,
                question=question,
                qid=follow_qid,
                preview_count=preview_count,
                total_count=total_count,
            )

        vue_table = self._build_vue_table(data)
        stream_summary["table"] = vue_table
        self._remember_last_result(
            client_ip,
            sql=sql,
            keys=list(data[0].keys()),
            question=question,
            qid=follow_qid,
        )
        yield f"data: {self._safe_json_dumps({'type': 'table', 'sql': sql, **vue_table})}\n\n"
        await asyncio.sleep(0)

        if listing_qid:
            echarts = self._build_echarts(data, question, source_sql=sql)
        else:
            parent_dim = str(ctx.get("cat_key") or "").strip().lower()
            drill_dims = [
                dim
                for dim in (
                    "online",
                    "run_state",
                    "region_name",
                    "space_name",
                    "venue_name",
                    "device_type",
                    "status",
                )
                if dim != parent_dim
            ]
            echarts = self._build_echarts(
                data,
                question,
                source_sql=sql,
                prefer_dims=drill_dims,
            )
        if echarts:
            stream_summary["chart"] = {
                "chartType": echarts.get("chartType"),
                "chartId": echarts.get("chartId"),
            }
            stream_summary["chart_sql"] = echarts.get("sql") or ""
            if listing_qid:
                self._remember_chart_followup(
                    client_ip,
                    sql=sql,
                    question=question,
                    qid=follow_qid,
                    echarts=echarts,
                    replace=True,
                )
            for packet in self._sse_chart_packets(echarts):
                yield packet
            await asyncio.sleep(0)

        yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
        summary = self._generate_summary(
            question,
            data,
            vue_table,
            preview_count=preview_count,
            total_count=total_count,
            truncated=truncated,
        )
        summary = self._append_view_all_hint(summary, truncated)
        stream_summary["summary"] = summary
        yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
        if on_summary:
            await on_summary(stream_summary)

    def _fallback_summary(
        self,
        preview_count: int,
        total_count: Optional[int],
        truncated: bool,
    ) -> str:
        if truncated and total_count is not None:
            return self._append_view_all_hint(
                f"共 {total_count} 条，下表为前 {preview_count} 条预览。", True
            )
        if truncated:
            return self._append_view_all_hint(
                f"下表为前 {preview_count} 条预览，已截断，实际总数可能更多。", True
            )
        return f"查询返回 {preview_count} 条数据，详见下方图表和表格。"

    def _generate_summary(
        self,
        question: str,
        data: List[dict],
        vue_table: dict,
        *,
        preview_count: Optional[int] = None,
        total_count: Optional[int] = None,
        truncated: bool = False,
    ) -> str:
        """让 LLM 根据查询结果生成简短总结（<= 200字）"""
        preview = preview_count if preview_count is not None else len(data or [])
        data_summary = self._summarize_data(
            data,
            preview_count=preview,
            total_count=total_count,
            truncated=truncated,
        )
        if truncated:
            total_text = (
                f"{total_count} 条"
                if total_count is not None
                else "未知（已截断，不少于预览条数）"
            )
            count_rule = (
                f"必须写「共 {total_count} 条，下表为前 {preview} 条预览」。"
                if total_count is not None
                else f"必须写「仅前 {preview} 条预览，已截断，实际可能更多」。"
            )
        else:
            total_text = f"{total_count if total_count is not None else preview} 条（未截断，即全量）"
            count_rule = f"可以说「共 {preview} 条」，这就是全量。"

        count_lead = ""
        if self._is_count_question(question):
            count_lead = "用户在问数量：先给全量数字，再说明表格是否为预览。\n"

        prompt = f"""## 用户问题
{question}

## 条数说明（以这里为准，不要自己数预览行）
- 预览条数：{preview}
- 全量总数：{total_text}
- 是否截断：{"是" if truncated else "否"}

## 查询结果摘要（仅预览样本，不是全集）
{data_summary}

## Vue表格预览
列：{[c["label"] for c in vue_table.get("columns", [])]}
预览行数：{len(vue_table.get("rows", []))} 条

## 任务
生成一段简短总结（不超过200字）。
{count_lead}## 强制规则
1. {count_rule}
2. 禁止把预览条数写成总数。禁止「共获取{preview}条」「共检索到{preview}条」「系统共有{preview}条」「共监测到{preview}条」。
3. 禁止根据预览推断「全部在线 / 未发现异常 / 整体稳定」。
4. 禁止评价「数据结构完整、可用于资产管理」等空话。
5. 只概括预览里能看见的分布，并点明这是预览（若已截断）。
直接输出总结内容，不要解释，不要用引号包裹。"""
        try:
            response = self.ollama.call_llm(
                [{"role": "user", "content": prompt}], temperature=0.3
            )
            return self._append_view_all_hint(response.strip()[:200], truncated)
        except Exception as e:
            logger.warning(f"总结生成失败: {e}")
            return self._fallback_summary(preview, total_count, truncated)

    def _summarize_data(
        self,
        data: List[dict],
        *,
        preview_count: int,
        total_count: Optional[int],
        truncated: bool,
    ) -> str:
        """将查询结果压缩为文本摘要（供总结生成用）"""
        if not data:
            return "无数据"
        sample = data[0]
        keys = list(sample.keys())
        lines = []
        for i, row in enumerate(data[:5]):
            vals = []
            for k in keys[:4]:
                v = row.get(k)
                if v is None:
                    vals.append("空")
                elif isinstance(v, Decimal):
                    vals.append(f"{float(v):.2f}")
                else:
                    vals.append(str(v)[:20])
            lines.append(f"第{i+1}行: " + ", ".join(vals))
        if truncated and total_count is not None:
            more = f"\n...以上为前 {preview_count} 条预览，全量共 {total_count} 条（已截断，不是全集）"
        elif truncated:
            more = f"\n...以上为前 {preview_count} 条预览，已截断，不是全量，实际总数未知且不少于 {preview_count}"
        elif preview_count > 5:
            more = f"\n...共 {preview_count} 条（未截断，即全量）"
        else:
            more = f"\n共 {preview_count} 条（未截断，即全量）"
        return "\n".join(lines) + more

    def _safe_json_dumps(self, obj: Any) -> str:
        """安全的 JSON 序列化（处理 Decimal、datetime、date 等类型）"""

        def default(o):
            if isinstance(o, Decimal):
                return float(o)
            if isinstance(o, datetime):
                return o.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(o, "strftime") and callable(o.strftime):  # date 对象
                return o.strftime("%Y-%m-%d")
            if hasattr(o, "__dict__"):
                return o.__dict__
            return str(o)

        return json.dumps(obj, ensure_ascii=False, default=default)

    async def _handle_energy_query(
        self,
        question: str,
        access_time: datetime,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        on_summary: Optional[callable] = None,
    ) -> AsyncIterator[str]:
        """处理按能介统计能耗的查询(公式计算分支)

        流程:
          1. 解析时间范围
          2. 查 metering_point 配置(true_formula)
          3. 查 energy_medium_manage 能介名称映射
          4. 批量查 data_day 按 device_id 汇总
          5. 按公式求值, 按能介分组
          6. emit table/chart/summary SSE 事件
        """
        from datetime import date, timedelta
        from decimal import Decimal

        stream_summary = {
            "mode": "energy",
            "qid": None,
            "match_confidence": 0.0,
            "fallback_reason": None,
            "sql": None,
            "table": None,
            "chart": None,
            "summary": None,
            "row_count": 0,
            "error": None,
        }

        try:
            # ========== 步骤 1: 解析时间范围 ==========
            start_date, end_date = self._parse_energy_time_range(question)
            logger.info(
                "能耗查询 q=%s range=%s~%s",
                _one_line(question, 80),
                start_date,
                end_date,
            )

            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在查询能耗配置...'})}\n\n"

            # ========== 步骤 2: 查 metering_point 配置 ==========
            mp_sql = (
                'SELECT "id", "node_name", "type", "true_formula" '
                'FROM "FWBZ"."metering_point" '
                'WHERE "true_formula" IS NOT NULL AND "true_formula" <> \'\' '
                "LIMIT 500 OFFSET 0"
            )
            metering_points = execute_query(mp_sql)

            if not metering_points:
                stream_summary["error"] = "无 true_formula 配置"
                stream_summary["summary"] = "未找到能耗计量点配置，无法计算。"
                yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '未找到能耗计量点配置，无法计算。'})}\n\n"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)
                return

            logger.info("能耗计量点 %s 个", len(metering_points))

            # ========== 步骤 3: 查 energy_medium_manage 能介名称 ==========
            medium_name_map = {}
            try:
                medium_sql = 'SELECT "code", "name" FROM "FWBZ"."energy_medium_manage" LIMIT 100 OFFSET 0'
                medium_rows = execute_query(medium_sql)
                for row in medium_rows or []:
                    code = str(row.get("code", "")).strip()
                    name = str(row.get("name", "")).strip()
                    if code:
                        medium_name_map[code] = name
            except Exception as e:
                logger.warning(f"能介名称查询失败, 用 type 原值: {e}")

            # ========== 步骤 4: 提取 device_code 并映射到 device.id ==========
            all_device_codes = set()
            for mp in metering_points:
                formula = mp.get("true_formula") or ""
                codes = self._extract_device_ids(formula)
                all_device_codes.update(codes)

            if not all_device_codes:
                stream_summary["error"] = "公式无有效设备引用"
                stream_summary["summary"] = "能耗公式无有效设备引用。"
                yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '能耗公式无有效设备引用。'})}\n\n"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)
                return

            logger.info("能耗 device_code %s 个", len(all_device_codes))

            # 查 device 表, 建 device_code -> device.id 映射 (分批, 每批 1000)
            code_to_id = {}  # device_code (str) -> device.id (int)
            code_list = list(all_device_codes)
            for i in range(0, len(code_list), 1000):
                chunk = code_list[i : i + 1000]
                codes_sql = ",".join(
                    f"'{c.replace(chr(39), chr(39)*2)}'" for c in chunk
                )
                device_sql = (
                    f'SELECT "id", "device_code" '
                    f'FROM "FWBZ"."device" '
                    f'WHERE "device_code" IN ({codes_sql}) '
                    f"LIMIT 5000 OFFSET 0"
                )
                try:
                    rows = execute_query(device_sql)
                    for row in rows or []:
                        did = row.get("id")
                        dcode = str(row.get("device_code") or "").strip()
                        if did is not None and dcode:
                            code_to_id[dcode] = did
                except Exception as e:
                    logger.error(f"device 查询失败 (chunk {i}): {e}")

            logger.info("能耗 device 映射 %s 个", len(code_to_id))

            if not code_to_id:
                stream_summary["error"] = "device_code 无对应设备"
                stream_summary["summary"] = "能耗公式引用的设备在设备表中未找到。"
                yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '能耗公式引用的设备在设备表中未找到。'})}\n\n"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)
                return

            # 批量查 data_day (分批, 每批 1000)
            # key: device_code (str) -> total_value (float)
            device_values = {}
            id_to_code = {v: k for k, v in code_to_id.items()}
            device_id_list = list(id_to_code.keys())
            # 时间范围: 半开区间 [start, end+1day)
            start_str = start_date.strftime("%Y-%m-%d")
            end_plus_1 = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")

            for i in range(0, len(device_id_list), 1000):
                chunk = device_id_list[i : i + 1000]
                id_list_str = ",".join(str(d) for d in chunk)
                data_sql = (
                    f'SELECT "device_id", SUM("value") AS "total_value" '
                    f'FROM "FWBZ"."data_day" '
                    f'WHERE "device_id" IN ({id_list_str}) '
                    f"AND \"time\" >= TO_DATE('{start_str}', 'YYYY-MM-DD') "
                    f"AND \"time\" < TO_DATE('{end_plus_1}', 'YYYY-MM-DD') "
                    f'GROUP BY "device_id" LIMIT 5000 OFFSET 0'
                )
                try:
                    rows = execute_query(data_sql)
                    for row in rows or []:
                        dev_id = row.get("device_id")
                        val = row.get("total_value")
                        if dev_id is not None and val is not None:
                            dcode = id_to_code.get(dev_id)
                            if dcode:
                                device_values[dcode] = float(val)
                except Exception as e:
                    logger.error(f"data_day 批量查询失败 (chunk {i}): {e}")

            logger.info("能耗查询完成 devices_with_data=%s", len(device_values))

            if not device_values:
                stream_summary["error"] = "无能耗数据"
                stream_summary["summary"] = "所选时间范围内无能耗数据。"
                yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '所选时间范围内无能耗数据。'})}\n\n"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)
                return

            # ========== 步骤 5: 按公式求值并按能介分组 ==========
            medium_totals = {}  # type_code -> sum
            for mp in metering_points:
                formula = mp.get("true_formula") or ""
                type_code = str(mp.get("type") or "").strip()
                val = self._eval_formula(formula, device_values)
                if val is not None:
                    medium_totals[type_code] = medium_totals.get(type_code, 0) + val

            if not medium_totals:
                stream_summary["error"] = "公式求值全失败"
                stream_summary["summary"] = "能耗公式计算失败，请检查设备数据完整性。"
                yield f"data: {self._safe_json_dumps({'type': 'message', 'content': '能耗公式计算失败，请检查设备数据完整性。'})}\n\n"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)
                return

            # 组装结果行
            energy_rows = []
            for type_code, total in medium_totals.items():
                readable = medium_name_map.get(type_code) or type_code or "未知"
                energy_rows.append(
                    {
                        "energy_medium": readable,
                        "total_value": round(Decimal(str(total)), 4),
                    }
                )
            # 按能耗降序
            energy_rows.sort(key=lambda r: float(r["total_value"]), reverse=True)

            # ========== 步骤 6: emit table ==========
            vue_table = {
                "columns": [
                    {"key": "energy_medium", "label": "能介"},
                    {"key": "total_value", "label": "累计能耗"},
                ],
                "rows": [
                    {
                        "energy_medium": r["energy_medium"],
                        "total_value": str(r["total_value"]),
                    }
                    for r in energy_rows
                ],
                "total": len(energy_rows),
            }
            stream_summary["table"] = vue_table
            stream_summary["row_count"] = len(energy_rows)
            # 伪 SQL 描述(前端展示用, 不执行)
            pseudo_sql = f"-- 能耗公式计算: 读 metering_point.true_formula, 按 type 分组汇总 (时间: {start_str} ~ {end_date.strftime('%Y-%m-%d')})"
            stream_summary["sql"] = pseudo_sql
            yield f"data: {self._safe_json_dumps({'type': 'sql', 'sql': pseudo_sql})}\n\n"
            yield f"data: {self._safe_json_dumps({'type': 'table', 'sql': pseudo_sql, **vue_table})}\n\n"
            await asyncio.sleep(0)

            # ========== 步骤 7: emit chart (bar) ==========
            chart_id = f"chart_energy_{datetime.now().strftime('%H%M%S%f')}"
            x_axis = [r["energy_medium"] for r in energy_rows]
            series_data = [float(r["total_value"]) for r in energy_rows]
            chart = {
                "chartType": "bar",
                "chartId": chart_id,
                "option": {
                    "title": {
                        "text": self._gen_chart_title(question, "能耗"),
                        "left": "center",
                    },
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {
                        "left": "3%",
                        "right": "4%",
                        "bottom": "12%",
                        "containLabel": True,
                    },
                    "xAxis": {
                        "type": "category",
                        "data": x_axis,
                        "axisLabel": {"rotate": 30, "interval": 0},
                    },
                    "yAxis": {"type": "value", "name": "累计能耗"},
                    "series": [
                        {
                            "type": "bar",
                            "data": series_data,
                            "itemStyle": {
                                "color": {
                                    "type": "linear",
                                    "x": 0,
                                    "y": 0,
                                    "x2": 0,
                                    "y2": 1,
                                    "colorStops": [
                                        {"offset": 0, "color": "#5470C6"},
                                        {"offset": 1, "color": "#91CC75"},
                                    ],
                                },
                                "borderRadius": [4, 4, 0, 0],
                            },
                            "label": {
                                "show": True,
                                "position": "top",
                                "formatter": "{c}",
                            },
                        }
                    ],
                },
            }
            union_parts = []
            for r in energy_rows:
                medium = str(r["energy_medium"]).replace("'", "''")
                union_parts.append(
                    f'SELECT \'{medium}\' AS "energy_medium", '
                    f'{float(r["total_value"])} AS "total_value" FROM DUAL'
                )
            energy_chart_src = (
                "\nUNION ALL\n".join(union_parts)
                if union_parts
                else 'SELECT NULL AS "energy_medium", 0 AS "total_value" FROM DUAL'
            )
            chart["sql"] = self._compose_chart_sql(
                energy_chart_src,
                cat_key="energy_medium",
                num_key="total_value",
                count_mode=False,
                full_stats=True,
            )
            stream_summary["chart"] = {"chartType": "bar", "chartId": chart_id}
            stream_summary["chart_sql"] = chart.get("sql") or ""
            for packet in self._sse_chart_packets(chart):
                yield packet
            await asyncio.sleep(0)

            # ========== 步骤 8: emit summary ==========
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
            summary = self._generate_summary(question, energy_rows, vue_table)
            summary = summary.replace("\n", " ").replace("\r", "").strip()
            stream_summary["summary"] = summary
            yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
            await asyncio.sleep(0)

            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)

        except Exception as exc:
            logger.exception(f"能耗查询异常: {exc}")
            stream_summary["error"] = f"能耗查询异常: {exc}"
            yield f"data: {self._safe_json_dumps({'type': 'error', 'message': f'能耗查询异常: {exc}'})}\n\n"
            yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
            if on_summary:
                await on_summary(stream_summary)

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

        新版流程 (2026-08-31 改造):
            1. QA 匹配: 调 LLM 比对"问题清单", 拿到 Q-ID
            2. 匹配上 → 拿"问答手册"中该 Q-ID 的 SQL 范式
                       → 调 LLM 生成 SQL (带范式参考)
                       → SQL 安全门 → 达梦执行 → 表格/图表/总结
            3. 未匹配 → 直接调 LLM 流式 (兜底回答, 跳过 SQL 路径)

        SSE 事件协议保持 (前端零改动):
            - mode: {value, message}
            - sql: {sql}
            - table: {columns, rows, total}
            - chart: {chartType, chartId, option}
            - summary: {content}
            - message: {content}  (兜底分支的流式 token)
            - error: {message}
            - done: true
        """
        full_reply = ""
        mode = "unknown"
        self.ollama.reset_usage()
        # 收集流式结果摘要，供日志记录
        stream_summary = {
            "mode": None,
            "qid": None,
            "match_confidence": 0.0,
            "fallback_reason": None,
            "sql": None,
            "table": None,
            "chart": None,
            "summary": None,
            "row_count": 0,
            "preview_count": 0,
            "total_count": None,
            "truncated": False,
            "error": None,
        }

        try:
            # ========== 阶段1：QA 匹配 (核心: LLM 判用户问题 vs 问题清单) ==========
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'detecting'})}\n\n"

            last_truncated = self._load_truncated_query(client_ip)
            if self._classify_view_all_intent(question, last_truncated):
                async for chunk in self._handle_view_all_followup(
                    question=question,
                    client_ip=client_ip,
                    on_summary=on_summary,
                    stream_summary=stream_summary,
                ):
                    yield chunk
                return

            last_chart = self._load_chart_followup(client_ip)
            slice_name = self._match_last_chart_slice(
                question, (last_chart or {}).get("slices") or []
            )
            regroup_phrase = self._parse_chart_regroup_phrase(question)
            last_result = self._load_last_result(client_ip)
            regroup_dim = (
                self._resolve_chart_dim_phrase(
                    regroup_phrase, (last_result or {}).get("keys") or []
                )
                if regroup_phrase and last_result
                else None
            )
            if regroup_phrase and regroup_dim:
                async for chunk in self._handle_chart_regroup_followup(
                    question=question,
                    dim_key=regroup_dim,
                    dim_phrase=regroup_phrase,
                    client_ip=client_ip,
                    on_summary=on_summary,
                    stream_summary=stream_summary,
                ):
                    yield chunk
                return
            compact_q = self._normalize_view_all_text(question)
            if (
                regroup_phrase
                and last_result
                and not regroup_dim
                and not slice_name
                and not self._is_energy_formula_query(question)
                and len(compact_q) <= 18
            ):
                async for chunk in self._reject_chart_regroup(
                    phrase=regroup_phrase,
                    last_result=last_result,
                    on_summary=on_summary,
                    stream_summary=stream_summary,
                ):
                    yield chunk
                return

            if last_chart and slice_name:
                async for chunk in self._handle_chart_slice_followup(
                    question=question,
                    slice_name=slice_name,
                    client_ip=client_ip,
                    on_summary=on_summary,
                    stream_summary=stream_summary,
                ):
                    yield chunk
                return

            # 能耗公式计算分支(拦截在 QA 匹配之前, 避免 30s 超时)
            if self._is_energy_formula_query(question):
                async for chunk in self._handle_energy_query(
                    question, access_time, client_ip, user_agent, on_summary
                ):
                    yield chunk
                return

            match_result = None
            try:
                from app.chat.qa_matcher import get_qa_matcher
                from app.chat.sql_template_loader import get_template_loader

                matcher = get_qa_matcher()
                template_loader = get_template_loader()

                if matcher.available():
                    match_result = await asyncio.to_thread(matcher.match, question)
                else:
                    logger.warning("QA 匹配器不可用, 走兜底")
            except Exception as e:
                logger.exception(f"QA 匹配异常, 走兜底: {e}")

            matched = match_result is not None and bool(match_result.best_qid)

            if matched:
                qid = match_result.best_qid
                confidence = match_result.best_confidence
                sql_template = template_loader.get(qid) or ""
                stream_summary["mode"] = "db"
                stream_summary["qid"] = qid
                stream_summary["match_confidence"] = round(confidence, 3)
                if not sql_template:
                    logger.warning(
                        f"Q{qid} 在问答手册中无 SQL 范式, 仍走 DB 模式但无范式参考"
                    )

                mode = "db"
                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': f'匹配到标准问题 Q{qid} (置信度 {confidence:.0%}), 正在生成查询...'})}\n\n"

                # ========== 阶段2：生成 SQL (带 Q-ID 范式) ==========
                sql = self._generate_sql(
                    question,
                    sql_template=sql_template or None,
                    qid=qid if sql_template else None,
                )
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

                # ========== 阶段3：执行 SQL (内置 sql_guard 严格门) ==========
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

                preview_count, total_count, truncated = (
                    self._resolve_result_cardinality(
                        stream_summary.get("sql") or sql, data
                    )
                )
                stream_summary["row_count"] = preview_count
                stream_summary["preview_count"] = preview_count
                stream_summary["total_count"] = total_count
                stream_summary["truncated"] = truncated
                if truncated:
                    logger.info(
                        "查询结果已截断: preview=%s total=%s sql_cap=%s",
                        preview_count,
                        total_count,
                        self._sql_safety_cap(stream_summary.get("sql") or sql),
                    )
                    self._remember_truncated_query(
                        client_ip,
                        sql=stream_summary.get("sql") or sql,
                        question=question,
                        qid=qid,
                        preview_count=preview_count,
                        total_count=total_count,
                    )

                # ========== 阶段4：构建 Vue 表格 ==========
                vue_table = self._build_vue_table(data)
                stream_summary["table"] = vue_table
                self._remember_last_result(
                    client_ip,
                    sql=stream_summary.get("sql") or sql,
                    keys=list(data[0].keys()),
                    question=question,
                    qid=qid,
                )
                yield f"data: {self._safe_json_dumps({'type': 'table', 'sql': stream_summary.get('sql') or sql, **vue_table})}\n\n"
                await asyncio.sleep(0)

                # ========== 阶段5：构建 ECharts ==========
                echarts = self._build_echarts(
                    data,
                    question,
                    source_sql=stream_summary.get("sql") or sql,
                )
                if echarts:
                    stream_summary["chart"] = {
                        "chartType": echarts.get("chartType"),
                        "chartId": echarts.get("chartId"),
                    }
                    stream_summary["chart_sql"] = echarts.get("sql") or ""
                    self._remember_chart_followup(
                        client_ip,
                        sql=stream_summary.get("sql") or sql,
                        question=question,
                        qid=qid,
                        echarts=echarts,
                    )
                    for packet in self._sse_chart_packets(echarts):
                        yield packet
                    await asyncio.sleep(0)

                # ========== 阶段6：生成总结 ==========
                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
                summary = self._generate_summary(
                    question,
                    data,
                    vue_table,
                    preview_count=preview_count,
                    total_count=total_count,
                    truncated=truncated,
                )
                summary = self._append_view_all_hint(summary, truncated)
                stream_summary["summary"] = summary
                yield f"data: {self._safe_json_dumps({'type': 'summary', 'content': summary})}\n\n"
                await asyncio.sleep(0)

                full_reply = f"[Q{qid} 匹配] {summary}"
                yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                if on_summary:
                    await on_summary(stream_summary)

            else:
                # ========== 兜底分支: 未匹配到标准问题, 直接调 LLM 流式回答 ==========
                mode = "llm"
                stream_summary["mode"] = "llm"
                if match_result is not None:
                    if match_result.error:
                        stream_summary["fallback_reason"] = (
                            f"匹配异常: {match_result.error}"
                        )
                    elif not match_result.best_qid:
                        stream_summary["fallback_reason"] = "问题清单无匹配"
                    else:
                        stream_summary["fallback_reason"] = (
                            f"匹配 Q{match_result.best_qid} 但置信度 {match_result.best_confidence:.0%} < 60%"
                        )
                else:
                    stream_summary["fallback_reason"] = "匹配器不可用"

                logger.info(
                    "兜底 LLM 流式 reason=%s", stream_summary["fallback_reason"]
                )

                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'llm', 'message': '本问题未匹配到业务清单, 使用通用 LLM 回答...'})}\n\n"

                response_parts = []

                async for chunk in self.ollama.stream_chat(payload):
                    if chunk.get("error"):
                        yield f"data: {self._safe_json_dumps({'type': 'error', 'message': chunk.get('error')})}\n\n"
                        yield f"data: {self._safe_json_dumps({'done': True})}\n\n"
                        stream_summary["error"] = chunk.get("error")
                        if on_summary:
                            await on_summary(stream_summary)
                        break
                    if chunk.get("done"):
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
            prompt_tokens, completion_tokens, token_count = self.ollama.usage_snapshot()
            await save_access_log(
                question=question,
                access_time=access_time,
                token_count=token_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                response=full_reply[:2000] if full_reply else None,
                model=self.ollama.model,
                client_ip=client_ip,
                user_agent=user_agent,
            )
