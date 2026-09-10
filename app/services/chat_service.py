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
from app.core.logger import get_logger
from app.core.ollama import OllamaClient
from app.schemas.chat import ChatMessage, ChatStreamRequest

settings = get_settings()
logger = get_logger("chat")


def _build_schema_text() -> str:
    """
    从 config/FWBZ_strut.sql 解析真实表结构，生成供 LLM 参考的文本。
    实际解析逻辑收敛在 app.core.sql_schema_parser。
    """
    from app.core.sql_schema_parser import build_schema_text
    text = build_schema_text()
    if text:
        # 行数 ≈ "## 标题" + N × ("### table" + "  列: ..." + "")
        table_count = text.count("\n### ")
        logger.info(f"动态 schema 生成完成，共 {table_count} 个表")
    return text


# 一次性构建动态表结构（服务启动时）
_SCHEMA_TEXT: str = _build_schema_text()


# 达梦数据库 Schema 上下文（供 LLM 生成 SQL 使用）
DAMENG_SCHEMA_CONTEXT = """
## 达梦数据库信息
- 类型：Dameng 8.0 (08.00.000)
- Schema：FWBZ
- 标识符引号：达梦大小写敏感，**所有表名和字段名必须用双引号包裹**，如 `"device"."device_name"`、`"alarm_time"`。
- 自增列：使用序列 FWBZ.SEQ_xxx，不支持 AUTO_INCREMENT

## 【最高优先级】表结构白名单约束（绝对禁止违反）

**这是铁律，没有例外。**
你使用的每一个表名、每一个字段名，**必须出现在上方「数据库真实表结构」的列表中**。
如果表结构里没有这个表，或某个表里没有这个字段，**绝对不能使用**。

**正确做法：**
- 如果用户问的字段不存在于表结构中，**直接省略这个字段**，不要臆造
- 如果不确定某个表有哪些列，**必须回查上方表结构**，不要凭记忆瞎猜
- 宁可少选列（只选确定存在的），也不要选一个不存在的列名
- JOIN 条件中引用的列也必须存在于对应表中

**常见 LLM 臆造陷阱（真实发生过的错误，禁止再犯）：**
- ❌ `lighting_area` 表：外键是 `space` 和 `space_name`，**没有 `space_id`、`create_time`、`area_id` 字段**（LLM 高频臆造 `space_id`，必须用 `space` 或 `space_name`）
- ❌ `alarm_record` 表：**没有 `category_id`、`area_id` 字段**（有的是 `device_category_id`、`space_id`）
- ❌ `alarm_record` 表：**没有 `alarm_rule_point` 表**（正确关联是 `alarm_rules`）
- ❌ `device` 表：**没有 `area_id` 字段**（外键是 `space_id`、`venue_id`）
- ❌ `table_parking_count` 表：**没有 `data_date` 字段**（正确字段是 `date`）
- ❌ 设备类型关联：字段名是 `device_category_id`，**不是 `category_id`**
- ❌ space 关联：字段名是 `space_id`，**不是 `area_id`**
- ❌ **客流查询一律用 `table_venue_flow_hour`，在馆人数列是 `today_now_count`**（**不是 `now_count`**，那是 `table_visitor_flow` 的列；LLM 高频混淆，禁止使用 `now_count`）

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

6. **列别名规则**：
   - 推荐裸写：`DATEDIFF(...) AS 处理时长分钟数`（无任何引号）
   - 如果别名包含空格、中文或特殊字符，可以加双引号：`AS "处理时长分钟数"`
   - 禁止使用单引号：`AS '处理时长分钟数'` 是错误的（单引号表示字符串常量）
   - 函数调用本身不要加外层双引号

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

## 重要关联关系（必须严格遵守）
- 设备通过 `venue_id` 关联会展场馆（`table_venue_info.id`）
- 设备通过 `space_id` 关联空间（`space.id`）
- 设备通过 **`device_category_id`** 关联设备类型（`equipment_category.id`），**字段名是 device_category_id，不是 category_id**
- 告警通过 `device_id` 关联设备（`device.id`）
- 计量点通过 `space_id` 关联空间（`space.id`）
- 计量点日数据通过 `metering_point_id` 关联计量点（`metering_point.id`）
- 照明回路通过 `area_id` 关联照明区域（`lighting_area.id`）
- **照明区域（`lighting_area`）没有 `space_id` 外键**，其 `space` 字段是 VARCHAR 代码（如"金安桥"），`space_name` 是空间名称；若需关联空间，用 `space_name` 或直接用 `space` 字段过滤
- `table_parking_count` 的日期字段是 **`date`**（不是 `data_date`、`stat_date`）

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
        """判断用户问题是否与达梦数据库相关
        策略：命中业务关键词才走 DB/RAG，否则默认直连 LLM
        """
        q = question.lower()

        # 业务关键词匹配——命中才走 DB/RAG
        db_keywords = [
            # 设备
            "设备", "离线", "在线", "运行状态", "运行状态", "设备数量", "设备统计", "设备类型",
            "阀门", "传感器", "仪表", "机组", "冷机", "热机", "空调", "新风", "风机", "水泵", "光伏",
            # 告警
            "告警", "报警", "故障", "停机", "异常", "重要", "一般", "告警级别", "告警状态",
            "告警内容", "告警时间", "告警记录", "告警处理",
            # 能耗/碳排放
            "能耗", "电耗", "水耗", "气耗", "热耗", "蒸汽", "用能", "综合能耗",
            "碳排放", "碳排放量", "碳强度", "碳因子", "标准煤",
            # 监测数据
            "温度", "湿度", "压力", "流量", "co2", "CO2", "浓度",
            # 场馆/空间
            "场馆", "会展", "空间", "区域", "楼层", "建筑", "位置", "地址",
            "场馆信息", "空间信息", "面积", "经纬度", "朝向",
            # 客流/人员
            "客流", "人流量", "入场", "出场", "访客", "人员", "人员统计",
            "在馆人数", "最大人数", "实时客流",
            # 停车
            "停车", "车位", "车辆", "停车场", "剩余车位", "停车时长", "停车统计",
            # 照明
            "照明", "灯光", "回路", "灯组", "照明区域", "亮灯",
            # 计量
            "计量", "计量点", "分时", "尖", "峰", "平", "谷", "电费",
            # 数据/统计/报表
            "数据", "统计", "报表", "报告", "记录", "查询", "分析", "汇总", "同比", "环比",
            # AI报告
            "ai报告", "AI报告", "分析报告", "日报", "周报", "月报",
            # 运维
            "维护", "保养", "检修", "巡检", "启停", "开关",
            # 阈值/配置
            "阈值", "上下限", "配置", "参数",
            # 通用业务
            "总数", "数量", "有多少", "多少个", "统计", "分布", "占比",
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
            "累计能耗", "总能耗", "综合能耗", "能耗是多少", "能耗多少",
            "能耗统计", "能耗汇总", "用电量", "耗能量",
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
        m = re.search(r'最近\s*(\d+)\s*天|近\s*(\d+)\s*天|过去\s*(\d+)\s*天', question)
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
        return list(dict.fromkeys(re.findall(r'\[([^\]]+)\]', true_formula)))

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

        expr_str = re.sub(r'\[([^\]]+)\]', _substitute, true_formula)

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
            tree = ast.parse(expr_str, mode='eval')
            result = _eval_node(tree)
            if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
                return None
            return round(result, 4)
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as e:
            logger.warning(f"公式求值失败: {true_formula} -> {e}")
            return None

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
            table_hints.append("lighting_area（照明区域）/ lighting_circuit（照明回路）")
        if any(k in q for k in ["计量", "分时"]):
            table_hints.append("metering_point_data_day（计量点日数据）/ metering_point（计量点）")
        if any(k in q for k in ["碳", "碳排放", "碳强度"]):
            table_hints.append("carbon_emission_factor（碳排放因子）/ data_day（能耗数据）")
        if any(k in q for k in ["报告", "ai报告", "报表"]):
            table_hints.append("ai_report_history（AI报告历史）")
        if any(k in q for k in ["设备类型", "category", "分类"]):
            table_hints.append("equipment_category（设备类型）")

        hint_text = ""
        if table_hints:
            hint_text = f"\n\n## 可能的关联表（根据问题推断）\n" + "\n".join(f"- {t}" for t in table_hints)

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

**【P3 范式白名单】本范式里已用到的列名 (改造时只能从这列表选或替换, 不要新增范式外的列):**
{col_whitelist}

```sql
{sql_template}
```
"""

        base_prompt_header = f"""{DAMENG_SCHEMA_CONTEXT}{_SCHEMA_TEXT}{hint_text}

================================================================
【🚨 最高警告 🚨】只使用上方「数据库真实表结构」中存在的表名和字段名！
禁止臆造任何不存在的表名/字段名, 违者 SQL 直接拒绝执行! 你必须**逐个核对**表名和字段名都来自上方列表。
================================================================

## 任务
根据用户问题生成一条达梦数据库 SQL 查询语句。

用户问题：{question}

## 📋 输出前自检清单 (4 条全部满足才输出)
1. ☐ 输出的每个表名, 都能在上方「数据库真实表结构」列表里找到?
2. ☐ 输出的每个列名 (包括 JOIN 条件), 都能在该表的列列表里找到?
3. ☐ 没有用 `time` / `category` / `area_id` 等高频臆造列名?
4. ☐ 达梦方言 (双引号, SYSDATE, NVL, LIMIT n OFFSET 0) 都正确?
**任意一条不满足, 修正后再输出!**

## 【最高优先级】表结构白名单约束

- **只使用上方「数据库真实表结构」中明确列出的表名和字段名**
- 如果用户问的字段不存在于表结构中，**直接省略**，不要脉造
- 如果不确定某个表有哪些列，必须回查上方表结构，**不要凭身世躕猜**
- 宁可少选列，也绝不要选一个不存在的列名
- JOIN 条件中的列也必须存在于对应表中

**已知 LLM 脉造高频陷阱（绝对禁止再犯）：**
- `lighting_area`：**没有 `space_id`、`create_time`、`area_id`**（正确外键是 `space` 和 `space_name`；LLM 反复臆造 `space_id`，严格禁止）
- `alarm_record`：**没有 `category_id`、`area_id`**（正确字段是 `device_category_id`、`space_id`）
- `alarm_record`：**没有 `alarm_rule_point` 表**（正确关联是 `alarm_rules`）
- `device`：**没有 `area_id`**（外键是 `space_id`、`venue_id`）
- `table_parking_count`：**没有 `data_date`**（正确字段是 `date`）
- 设备类型关联字段是 **`device_category_id`**，不是 `category_id`
- **客流查询统一用 `table_venue_flow_hour`，在馆人数列是 `today_now_count`**（**禁止用 `now_count`**，那是 `table_visitor_flow` 的列，LLM 极易混淆）

## ⚠️ 严格遵守达梦 8.0 语法规范（禁止使用 MySQL/PostgreSQL 语法）

### 标识符引号
- 表名和字段名：必须用双引号包裹，如 "device"."device_name"
- 禁止裸列名：如 device_name ❌ → "device_name" ✅

### 日期时间函数（❌ MySQL  ❌ PostgreSQL ✅ 达梦）
| 错误写法 | 正确写法 |
|---------|---------|
| DATE(col) | CAST(col AS DATE) 或 TRUNC(col) |
| DATE_FORMAT(col, 'YYYY-MM-DD') | TO_CHAR(col, 'YYYY-MM-DD') |
| NOW() | SYSDATE |
| CURDATE() | TRUNC(SYSDATE) |
| YEAR(col) | EXTRACT(YEAR FROM col) 或 TO_CHAR(col, 'YYYY') |
| MONTH(col) | EXTRACT(MONTH FROM col) 或 TO_CHAR(col, 'MM') |
| DAY(col) | EXTRACT(DAY FROM col) 或 TO_CHAR(col, 'DD') |
| WEEK(col) | TO_CHAR(col, 'IW') |

### NULL 处理
| 错误写法 | 正确写法 |
|---------|---------|
| IFNULL(a, b) | NVL(a, b) |
| COALESCE(a, b, c) | NVL(a, NVL(b, c)) |
| IF(cond, a, b) | CASE WHEN cond THEN a ELSE b END |

### 日期计算
| 错误写法 | 正确写法 |
|---------|---------|
| DATE_SUB(col, INTERVAL 1 DAY) | col - 1 |
| DATE_ADD(col, INTERVAL 7 DAY) | col + 7 |
| DATEDIFF(a, b) | (a - b) |
| TIMESTAMPDIFF(MINUTE, a, b) | (b - a) * 1440 |

### 分页查询
❌ 错误：LIMIT 10, 20
❌ 错误：LIMIT 20 OFFSET 10
❌ 错误：FETCH FIRST 100 ROWS ONLY（达梦不支持！）
✅ 正确（达梦 8.0）：
```sql
SELECT * FROM (
    SELECT t.*, ROWNUM AS rn FROM (
        SELECT "id", "name" FROM FWBZ."device" ORDER BY "create_time" DESC
    ) t WHERE ROWNUM <= 20
) WHERE rn > 10
```

### 字符串函数
| 错误写法 | 正确写法 |
|---------|---------|
| CONCAT(a, b, sep) | a || sep || b |
| CONCAT_WS(sep, a, b) | a \|\| sep \|\| b |
| GROUP_CONCAT(col) | LISTAGG(col, ',') WITHIN GROUP (ORDER BY col) |
| SUBSTRING(col, 1, 10) | SUBSTR(col, 1, 10) |
| UPPER/Lower | UPPER/LOWER（相同） |

### 数值函数
| 错误写法 | 正确写法 |
|---------|---------|
| FLOOR(col) | TRUNC(col) 或 CAST(col AS INT) |
| ROUND(col, 2) | ROUND(col, 2)（相同） |

### 聚合函数
✅ COUNT / SUM / AVG / MAX / MIN / LISTAGG

## 强制要求
1. **禁止臆造字段**：只使用表结构中明确列出的字段，绝不能使用表结构中没有的字段名
2. 只生成 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP/TRUNCATE 等任何修改操作
3. 表名格式：FWBZ."table_name"（Schema + 双引号表名）
4. 字段名格式：双引号包裹，如 "device_name"
5. **不要加任何别名**，前端会自动把英文列名映射成中文
6. 日期常量用单引号，如 '2026-08-01'（不是 #2026-08-01#）
7. LIMIT 限制：明细查询（无 GROUP BY）最多500条，聚合查询（有 GROUP BY）最多200条，用 ROWNUM 实现分页
8. 必须可以实际执行，不要生成假设性数据

## 输出格式
直接输出 SQL 语句，不要任何解释，不要用 markdown 代码块包裹。

## 示例
```sql
SELECT "device_name" AS "设备名称", "run_state" AS "运行状态", "create_time" AS "创建时间" FROM FWBZ."device"
```
"""
        logger.info(">>> 开始生成SQL >>>")
        logger.info("用户问题: %s", question)
        logger.info("-" * 60)
        
        for attempt in range(3):
            try:
                response = self.ollama.call_llm([
                    {"role": "user", "content": base_prompt_header + template_section + retry_hint}
                ], temperature=0.1)
                sql = response.strip()
                sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE)
                sql = re.sub(r'^```\s*', '', sql)
                sql = re.sub(r'\s*```$', '', sql)
                # 清理末尾分号和空白
                sql = sql.rstrip(';').strip()

                logger.info("LLM原始输出: %s", sql[:1000] if len(sql) > 1000 else sql)

                # 基础验证：必须包含 SELECT 和 FROM
                if sql.upper().startswith('SELECT') and 'FROM' in sql.upper():
                    # ========== LLM 生成的基础语法修复（必须在包装之前执行）==========
                    
                    # 1. 修复 LLM 常见的错误语法：ORDER BY ... WHERE（WHERE 应该在 ORDER BY 之前）
                    # 匹配 "ORDER BY xxx WHERE" 或 "ORDER BY xxx DESC WHERE" 这种错误顺序
                    order_where_match = re.search(r'(\s+ORDER\s+BY\s+.+?)\s+WHERE\s+', sql, re.IGNORECASE | re.DOTALL)
                    if order_where_match:
                        # 提取 ORDER BY 子句和 WHERE 后面的条件
                        order_part = order_where_match.group(1).strip()
                        where_rest = sql[order_where_match.end() - 1:]  # 从 WHERE 开始到末尾
                        
                        # 找到 WHERE 后面第一个非空格字符
                        where_start = re.search(r'\WHERE\s+', sql, re.IGNORECASE)
                        if where_start:
                            # 提取 WHERE 及其后的条件
                            where_clause = where_rest.strip()
                            # 移除 WHERE 后面的 ROWNUM 相关条件（LLM 常见错误）
                            where_clause = re.sub(r'AND\s*\(?\s*ROWNUM\s*[\-<>=\d\s]+\)?', '', where_clause, flags=re.IGNORECASE)
                            where_clause = re.sub(r'WHERE\s+ROWNUM\s*[\-<>=\d\s]+', '', where_clause, flags=re.IGNORECASE)
                            where_clause = where_clause.strip()
                            
                            # 重建 SQL：ORDER BY 放到 WHERE 后面
                            base_part = sql[:order_where_match.start()].strip()
                            if where_clause:
                                sql = f"{base_part} WHERE {where_clause} {order_part}"
                            else:
                                sql = f"{base_part} {order_part}"
                    
                    # 2. 移除 LLM 生成的无效 ROWNUM 条件（如 "AND (ROWNUM - 1) > 0"）
                    sql = re.sub(r'\s+AND\s*\(\s*ROWNUM\s*[\-<>=\d\s()]+\)', '', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'\s+AND\s+ROWNUM\s*[\-<>=\d\s()]+\s*>', ' WHERE ', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'WHERE\s+ROWNUM\s*[\-<>=\d\s()]+\s*>', 'WHERE ', sql, flags=re.IGNORECASE)
                    
                    logger.info("修复WHERE/ORDER后: %s", sql[:500] if len(sql) > 500 else sql)

                    # ========== 达梦 SQL 语法修复 ==========

                    # 注意：不再清理中文别名，保留 LLM 生成的中文别名用于前端展示

                    # 2. 修复分页语法 → 达梦 ROWNUM
                    # 支持：LIMIT N, FETCH FIRST N ROWS ONLY
                    # 分场景限制：明细查询（无 GROUP BY）500条，聚合查询（有 GROUP BY）200条
                    has_group_by = bool(re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE))

                    limit_n = None
                    # 2.1 处理 FETCH FIRST N ROWS ONLY（PostgreSQL/Oracle 语法）
                    fetch_match = re.search(r'\bFETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY\b', sql, re.IGNORECASE)
                    if fetch_match:
                        limit_n = int(fetch_match.group(1))
                        # 移除 FETCH FIRST 子句
                        sql = re.sub(r'\s+FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\b', '', sql, flags=re.IGNORECASE)
                    # 2.2 处理 LIMIT N
                    elif re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE):
                        limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
                        if limit_match:
                            limit_n = int(limit_match.group(1))
                            # 移除原 LIMIT 子句
                            sql = re.sub(r'\s+LIMIT\s+\d+(\s+OFFSET\s+\d+)?', '', sql, flags=re.IGNORECASE)
                            sql = re.sub(r'\s+LIMIT\s+\d+\s*,\s*\d+', '', sql, flags=re.IGNORECASE)
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
                            return m.group(2) + ' ' + m.group(1)
                        sql = re.sub(
                            r'(ORDER\s+BY\s+(?:(?!\bLIMIT\b).)+?)\s+(WHERE\s+(?:(?!\bLIMIT\b).)+?)\s+LIMIT',
                            swap_order_where,
                            sql,
                            flags=re.IGNORECASE
                        )

                        # ── 步骤 2：清理所有分页语法残留
                        # FETCH FIRST N ROWS ONLY（PostgreSQL/DB2）
                        sql = re.sub(r',\s*FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+FETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY', '', sql, flags=re.IGNORECASE)
                        # LIMIT N OFFSET M / LIMIT N, M / LIMIT N（MySQL）
                        sql = re.sub(r'\s+LIMIT\s+\d+\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+LIMIT\s+\d+\s*,\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+LIMIT\s+\d+', '', sql, flags=re.IGNORECASE)
                        # OFFSET ... 独立写法
                        sql = re.sub(r'\s+OFFSET\s+\d+\s*,\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+OFFSET\s+\d+', '', sql, flags=re.IGNORECASE)
                        # TOP N（SQL Server）
                        sql = re.sub(r'\s+TOP\s+\d+', '', sql, flags=re.IGNORECASE)
                        # WHERE ROWNUM / 各类 Oracle/达梦分页残留
                        sql = re.sub(r'\s+WHERE\s+ROWNUM\s*<=\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+ROWNUM\s*<\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+\(\s*ROWNUM\s*-\s*\d+\s*\)\s*\*\s*\d+\s*\+\s*\d+\s*>\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+\d+\s*<\s*ROWNUM\s*<\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+ROWNUM\s+between\s+\d+\s+and\s+\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+rn\s*>\s*\d+\s+AND\s+rn\s*<=\s*\d+', '', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\s+WHERE\s+rn\s*>=\s*\d+\s+AND\s+rn\s*<\s*\d+', '', sql, flags=re.IGNORECASE)

                        # ── 步骤 3：修复 ORDER BY 后 DESC/ASC 和 LIMIT 之间缺少空格
                        #    如 "ORDER BY col DESC LIMIT" → "ORDER BY col DESC LIMIT"
                        sql = re.sub(r'(DESC|ASC)\s*(LIMIT|OFFSET)', r'\1 \2', sql, flags=re.IGNORECASE)

                        # ── 步骤 4：清理 ORDER BY 后残留的 ROWNUM 算术表达式
                        #    如 "ORDER BY col DESC * 5 + 1 > 0" → "ORDER BY col DESC"
                        sql = re.sub(
                            r'ORDER\s+BY\s+[^()]*?\*\s*\d+\s*[+-]\s*\d+\s*[<>=]+\s*\d+',
                            lambda m: re.sub(
                                r'\s*\*\s*\d+\s*[+-]\s*\d+\s*[<>=]+\s*\d+\s*$',
                                '',
                                m.group(0),
                                flags=re.IGNORECASE
                            ),
                            sql,
                            flags=re.IGNORECASE
                        )

                        # ── 步骤 5：清理 ORDER BY 后残留的孤立 LIMIT 数字
                        #    如 "ORDER BY col DESC 500 OFFSET 0" → "ORDER BY col DESC"
                        sql = re.sub(
                            r'ORDER\s+BY\s+[^()]*?\s+\d+\s+OFFSET',
                            lambda m: re.sub(r'\s+\d+(?=\s+OFFSET)', '', m.group(0)),
                            sql,
                            flags=re.IGNORECASE
                        )

                        # ── 步骤 6：修复无意义的 WHERE 条件
                        sql = re.sub(r'\bWHERE\s+0\b', 'WHERE 1=1', sql, flags=re.IGNORECASE)
                        sql = re.sub(r'\bWHERE\s+1\s*=\s*0\b', 'WHERE 1=1', sql, flags=re.IGNORECASE)

                        # ── 步骤 7：统一追加达梦 LIMIT 分页
                        sql = sql.rstrip() + f' LIMIT {final_limit} OFFSET 0'

                    # ── 步骤 8：达梦大小写敏感，所有标识符必须双引号
                    # 达梦 DM8 开启大小写敏感后，未加双引号的表名/列名无法识别。
                    # 策略：直接匹配单词字符序列，在回调里判断是否需要加引号。
                    # 关键字和已引号的标识符跳过，其余全部加双引号。
                    _SQL_KEYWORDS = frozenset({
                        'ASC', 'DESC', 'NULL', 'SYSDATE', 'AND', 'OR', 'NOT',
                        'AS', 'IN', 'ON', 'BY', 'IS', 'LIKE', 'BETWEEN',
                        'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS',
                        'JOIN', 'FROM', 'WHERE', 'ORDER', 'GROUP', 'HAVING',
                        'LIMIT', 'OFFSET', 'SELECT', 'UNION', 'ALL', 'DISTINCT',
                        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'OVER', 'PARTITION',
                        'MINUTE', 'HOUR', 'DAY', 'SECOND', 'YEAR', 'MONTH',
                        'SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'TRUNC', 'TO_CHAR',
                        'CAST', 'COALESCE', 'GREATEST', 'LEAST', 'NVL', 'NVL2',
                        'DATEDIFF', 'TIMESTAMPDIFF', 'DATE', 'TIME',
                        'TO_DATE', 'TO_NUMBER', 'ROW_NUMBER', 'ROWNUM',
                        'SYSTIMESTAMP', 'ROWID', 'ROWIDTOCHAR',
                        'INSERT', 'UPDATE', 'DELETE', 'SET', 'VALUES',
                        'TABLE', 'INDEX', 'VIEW', 'SEQUENCE', 'TRIGGER',
                        'TRUE', 'FALSE', 'UNKNOWN', 'EXISTS',
                    })

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
                            if c.isalpha() or c == '_':
                                j = i
                                while j < n and (sql[j].isalnum() or sql[j] == '_'):
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

                        return ''.join(result)

                    sql = _add_quotes_to_identifiers(sql)
                    logger.info("双引号修复后: %s", sql)

                    # 3. 修复 LLM 常见的列名混淆（按真实表结构判断）
                    # 不同表的日期列名不同：
                    #   table_venue_flow_hour                      → "data_date"（客流表，table_venue_flow 已废弃）
                    #   table_parking_count / table_visitor_flow  → "date"
                    #   table_personnel_statistics               → "stat_date"
                    # 必须按每个 "data_date"/"stat_date" 引用所属的真实表判断，不能全局替换
                    sql = self._fix_date_column_by_schema(sql)
                    logger.info("日期列修复后: %s", sql)

                    # 4. 修复单引号别名 → 去掉引号（达梦里别名不加引号）
                    sql = re.sub(r"\s+AS\s+'([^']+)'", r' AS \1', sql, flags=re.IGNORECASE)

                    # 5. 修复 DATE() 函数 → TRUNC()
                    sql = re.sub(r'\bDATE\(("?[\w.]+"?)\)', r'TRUNC(\1)', sql, flags=re.IGNORECASE)

                    # 6. 修复 IFNULL() → NVL()
                    sql = re.sub(r'\bIFNULL\(', 'NVL(', sql, flags=re.IGNORECASE)

                    # 7. 修复 DATE_SUB/DATE_ADD → +/- INTERVAL
                    sql = re.sub(r'DATE_SUB\(', '(', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'DATE_ADD\(', '(', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'INTERVAL\s+\d+\s+DAY', '', sql, flags=re.IGNORECASE)

                    # 8. 修复 NOW() → SYSDATE
                    sql = re.sub(r'\bNOW\(\)', 'SYSDATE', sql, flags=re.IGNORECASE)

                    # 9. 修复 CONCAT_WS → ||
                    sql = re.sub(r'\bCONCAT_WS\(["\'](.+?)["\']\s*,\s*', lambda m: '(', sql, flags=re.IGNORECASE)

                    # 10. 如果有 GROUP BY + ORDER BY，把 ORDER BY 中的别名替换为列位置序号
                    #    达梦不支持 ORDER BY 使用 SELECT 列表别名（如 ORDER BY alarm_count），
                    #    需要替换为 ORDER BY n（n = 该别名在 SELECT 列表中的位置序号）。
                    if 'GROUP BY' in sql.upper() and re.search(r'\bORDER BY\b', sql, re.IGNORECASE):
                        sql = self._fix_order_by_alias(sql)

                    # 11. 如果有 GROUP BY，移除未分组的非聚合列（如 "id"）
                    if 'GROUP BY' in sql.upper():
                        logger.info(">>> 进入 GROUP BY 修复，原始 SQL: %s", sql)
                        sql = self._fix_group_by(sql)
                        logger.info(">>> GROUP BY 修复完成: %s", sql)

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

                    logger.info(">>> SQL生成成功 >>>")
                    logger.info("最终SQL: %s", sql)
                    logger.info("=" * 60)

                    # 生成后验证：发现臆造列名则触发重试
                    from app.core.dameng import validate_sql_columns
                    col_valid, col_err, invalid_list = validate_sql_columns(sql)
                    if not col_valid:
                        # 构造更具体的错误反馈: 列出每个具体列名 + 所在表
                        invalid_detail = []
                        for inv in invalid_list[:5]:
                            invalid_detail.append(f"  - {inv}")
                        invalid_text = "\n".join(invalid_detail) if invalid_detail else col_err

                        hint_suffix = (
                            f"\n\n【严重错误 - 上一轮 SQL 验证失败】\n"
                            f"以下列名/表名不在 schema 中 (臆造):\n{invalid_text}\n\n"
                            f"请重新生成, 严格只使用上方「数据库真实表结构」!\n"
                            f"**对照上方表结构, 逐个核对表名和字段名**!"
                        )
                        logger.warning(f"SQL 生成后验证失败（attempt {attempt}）: {col_err}，将重试")
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
                            logger.warning("3 次重试后仍含臆造列, 主动清理后继续: %s", invalid_list)
                            for bad_col in invalid_list:
                                # 去掉双引号
                                col_name = bad_col.strip('"')
                                # 从 SELECT 列表中移除（支持带 AS 别名的情况）
                                sql = re.sub(rf',?\s*"{re.escape(col_name)}"(\s+(?:AS\s+(?:"[^"]*"|\w+))?)(?=[,\)]|$)', '', sql, flags=re.IGNORECASE)
                                sql = re.sub(rf',?\s*\b{re.escape(col_name)}\b(\s+(?:AS\s+(?:"[^"]*"|\w+))?)(?=[,\)]|$)', '', sql, flags=re.IGNORECASE)
                            # 清理残留逗号
                            sql = re.sub(r',\s*\b(WHERE|ORDER|GROUP|LIMIT)\b', r' \1', sql, flags=re.IGNORECASE)
                            sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
                            logger.info("清理后SQL: %s", sql)
                            return sql

                    return sql
                else:
                    logger.warning("SQL 生成结果无效（attempt %d）: %s", attempt + 1, sql[:200])

            except Exception as e:
                logger.error("SQL 生成失败（attempt %d）: %s", attempt + 1, str(e))

        logger.warning(">>> SQL生成失败，已达到最大重试次数 <<<")
        return None

    def _execute_sql(self, sql: str) -> tuple[Optional[List[dict]], Optional[str]]:
        """执行 SQL 并返回结果"""
        logger.info("=" * 80)
        logger.info(">>> SQL执行开始 >>>")
        logger.info("SQL语句: %s", sql)
        logger.info("-" * 80)

        # 严格安全门: 仅 SELECT / 拦截多语句 / 强制 LIMIT (明细 500 / 聚合 200)
        from app.core.sql_guard import validate as guard_validate
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
            if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER)\b', sql_upper):
                logger.warning(f"SQL 安全检查拒绝（危险关键词）: {sql[:200]}")
                return None, "禁止执行非查询语句"
            if re.search(r'\bCREATE\b', sql_upper):
                # CREATE 作为独立单词检测（排除 CREATE_TIME 这类列名）
                # 只有出现在句首或前面有分号的才是 DDL
                safe_pattern = r'(?:^|[;])\s*CREATE\b|^\s*CREATE\s+'
                if not re.search(safe_pattern, sql_upper):
                    pass  # CREATE_TIME 等列名是安全的
                else:
                    logger.warning(f"SQL 安全检查拒绝（CREATE DDL）: {sql[:200]}")
                    return None, "禁止执行非查询语句"

            # 预清理：自动剔除已知臆造列名（LLM 常见幻觉）
            # 表 → 臆造列名列表（这些列在该表中不存在，LLM 经常臆造）
            KNOWN_HALLUCINATED_COLS: dict[str, frozenset[str]] = {
                'alarm_record': frozenset({'area_id', 'circuit_name', 'area_name', 'device_code'}),
                'lighting_area': frozenset({'space_id', 'create_time', 'area_id'}),
                'alarm_category': frozenset({'create_time'}),
            }
            for table, bad_cols in KNOWN_HALLUCINATED_COLS.items():
                for col in bad_cols:
                    # 从 SELECT 列表中移除（支持带 AS 别名的情况）
                    # 先处理 `"col"` 形式
                    sql = re.sub(rf',?\s*"{re.escape(col)}"(\s+(?:AS\s+\w+)?(?=[,\)]|$))', '', sql, flags=re.IGNORECASE)
                    # 再处理 `col` 形式（加了双引号的已经是 `"col"`，但保险起见）
                    sql = re.sub(rf',?\s*\b"{re.escape(col)}"\b(\s+(?:AS\s+\w+)?(?=[,\)]|$))', '', sql, flags=re.IGNORECASE)
                    # 也处理无引号的（如果还有）
                    sql = re.sub(rf',?\s*\b{re.escape(col)}\b(\s+(?:AS\s+\w+)?(?=[,\)]|$))', '', sql, flags=re.IGNORECASE)
                # 清理 SELECT 列表首列被单独移除后的残留逗号
                sql = re.sub(r',\s*\bWHERE\b', ' WHERE', sql, flags=re.IGNORECASE)
                sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)

            if sql.strip() == '' or re.match(r'^\s*SELECT\s*\s*$', sql):
                return None, "清理臆造列后 SQL 为空"

            # 列名 schema 验证：检查是否有臆造列名
            from app.core.dameng import validate_sql_columns
            col_valid, col_err, invalid_list = validate_sql_columns(sql)
            if not col_valid:
                logger.warning(f"SQL 列名验证失败: {col_err}")
                return None, f"SQL 包含不存在的列名: {', '.join(invalid_list)}"

            results = execute_query(sql)
            
            if results:
                logger.info(">>> SQL执行成功，返回 %d 条记录 <<<", len(results))
                if results:
                    logger.info("示例数据(第一条): %s", dict(list(results[0].items())[:5]))
            else:
                logger.warning(">>> SQL执行成功，但返回 0 条记录 <<<")
            logger.info("=" * 80)
            
            return results, None
        except Exception as e:
            logger.error(">>> SQL执行异常: %s <<<", str(e))
            logger.error("=" * 80)
            return None, str(e)

    def _build_vue_table(self, data: List[dict]) -> dict:
        """根据查询结果构建 Vue table 结构"""
        if not data:
            return {"columns": [], "rows": []}

        columns = []
        rows = []
        sample = data[0]

        for key in sample.keys():
            # 提取原始列名（去掉 SUM()/AVG()/COUNT()/NVL()/COALESCE 等函数包裹）
            clean_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE|NVL)\s*\(\s*"([^"]+)"\s*,\s*[^)]+\s*\)$', r'\2', key, flags=re.IGNORECASE)
            clean_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$', r'\2', clean_key, flags=re.IGNORECASE)
            clean_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|NVL)\s*\(\s*([^)]+)\s*\)$', r'\2', clean_key, flags=re.IGNORECASE)

            # 排除 id 列
            if clean_key.lower() in ('id', 'bigint', 'rn'):
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

        for row in data[:500]:
            formatted_row = {}
            for k, v in row.items():
                # 提取原始列名（处理 NVL/SUM/AVG/COUNT 等函数包裹）
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE|NVL)\s*\(\s*"([^"]+)"\s*,\s*[^)]+\s*\)$', r'\2', k, flags=re.IGNORECASE)
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(\s*"([^"]+)"\s*\)$', r'\2', clean_k, flags=re.IGNORECASE)
                clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN|NVL)\s*\(\s*([^)]+)\s*\)$', r'\2', clean_k, flags=re.IGNORECASE)
                # 排除 id 列
                if clean_k.lower() in ('id', 'bigint', 'rn'):
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

    def _fix_order_by_alias(self, sql: str) -> str:
        """
        达梦不支持 ORDER BY 使用 SELECT 列表别名（如 ORDER BY alarm_count），
        将 ORDER BY 中的别名替换为列位置序号（如 ORDER BY 3 DESC）。
        同时处理不在别名中的裸列名（可能是 GROUP BY 列，已加双引号的直接保留）。
        """
        try:
            # 提取 SELECT 列表中的别名映射：别名 → 位置序号（从1开始）
            select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE)
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
                while i < len(select_str) and select_str[i] in ' \t\n':
                    i += 1
                if i >= len(select_str):
                    break

                # 判断起始字符
                ch = select_str[i]
                if ch == ',':
                    i += 1
                    continue

                # 找这一项的结束（考虑括号配对）
                depth = 0
                start = i
                while i < len(select_str):
                    c = select_str[i]
                    if c in '([':
                        depth += 1
                    elif c in ')]':
                        depth -= 1
                    elif c == ',' and depth == 0:
                        break
                    i += 1
                item = select_str[start:i].strip()
                i += 1  # 跳过逗号

                if not item:
                    continue
                pos += 1

                # 检测是否有 AS 别名
                as_match = re.search(r'\s+AS\s+(["\']?)(\w+)\1\s*$', item, re.IGNORECASE)
                if as_match:
                    alias_lower = as_match.group(2).lower()
                    alias_map[alias_lower] = pos
                # 也检测没有 AS 的列名（可能是聚合函数 SUM(...)）
                elif re.match(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(', item, re.IGNORECASE):
                    # 聚合函数没有 AS，尝试提取内部列名作为别名（宽松处理）
                    pass

            if not alias_map:
                return sql

            # 提取 ORDER BY 部分
            order_match = re.search(r'ORDER BY\s+(.+?)(?=\s+LIMIT|\s*$|$)', sql, re.IGNORECASE)
            if not order_match:
                return sql

            order_text = order_match.group(0)
            order_expr = order_match.group(1).strip()

            # 逐列处理 ORDER BY（支持多列，逗号分隔）
            fixed_parts = []
            for col_m in re.finditer(
                r'(["\']?)(\w+)\1\s+(ASC|DESC)?(?=\s*,|\s+ORDER\s+BY|\s+LIMIT|\s*$)',
                order_expr,
                re.IGNORECASE
            ):
                raw_alias = col_m.group(2)
                direction = col_m.group(3) or ''
                alias_lower = raw_alias.lower()

                if alias_lower in alias_map:
                    col_pos = alias_map[alias_lower]
                    fixed_parts.append(f'{col_pos} {direction}'.strip())
                    logger.info(
                        f"ORDER BY 别名 '{raw_alias}' → 列位置 {col_pos} "
                        f"(SELECT 第 {col_pos} 项)"
                    )
                else:
                    # 不在别名中，保留原样（可能是 GROUP BY 列名，带双引号）
                    fixed_parts.append(f'"{raw_alias}" {direction}'.strip())

            if not fixed_parts:
                return sql

            new_order = 'ORDER BY ' + ', '.join(fixed_parts)
            sql = sql[:order_match.start()] + new_order + sql[order_match.start() + len(order_text):]
            logger.info(f"ORDER BY 别名替换完成: {sql}")

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

            # 逐项解析 SELECT 列表（支持嵌套括号、*、别名等）
            items = []
            i = 0
            while i < len(select_content):
                # 跳过空白和逗号
                while i < len(select_content) and select_content[i] in ' \t\n,':
                    i += 1
                if i >= len(select_content):
                    break

                # 找这一项的结束位置（顶层逗号为分隔符）
                depth = 0
                start = i
                while i < len(select_content):
                    c = select_content[i]
                    if c in '([,':
                        if c == ',' and depth == 0:
                            break
                        depth += 1 if c in '([' else 0
                    elif c in ')]':
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
                if re.match(r'^(SUM|AVG|COUNT|MAX|MIN|COALESCE)\s*\(', item_upper):
                    new_select_items.append(item)
                # 裸列名（双引号）→ 必须在 GROUP BY 中
                elif re.match(r'^"[^"]+"$', item) or re.match(r"^'[^']+'$", item):
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

            # 修正 ORDER BY：确保 ORDER BY 中的列都在 GROUP BY 中
            # 关键：列位置序号（如 ORDER BY 3）保持不变，不要转成列名
            if grouped_col_originals:
                # 提取 ORDER BY 部分（可能在 LIMIT 之前或之后）
                order_match = re.search(r'ORDER BY\s+(.+?)(?=\s+LIMIT|\s*$|$)', sql, re.IGNORECASE)
                if order_match:
                    order_text = order_match.group(0)  # 完整 "ORDER BY xxx"
                    order_expr = order_match.group(1).strip()  # ORDER BY 后的内容

                    # 逐个提取 ORDER BY 的每个项（支持多列，逗号分隔）
                    fixed_order_parts = []
                    for col_m in re.finditer(
                        r'("?[\w.]+"?)\s+(ASC|DESC)?(?=\s*,|\s+ORDER|\s+LIMIT|\s*$)',
                        order_expr,
                        re.IGNORECASE
                    ):
                        raw_col = col_m.group(1).strip()
                        direction = col_m.group(2) or ''

                        # 情况 1：列位置序号（如 ORDER BY 3）→ 保持不变，达梦原生支持
                        if raw_col.isdigit():
                            fixed_order_parts.append(f'{raw_col} {direction}'.strip())
                            continue

                        # 情况 2：列名 → 检查是否在 GROUP BY 中
                        clean_col = raw_col.strip('"').strip("'").lower()
                        if clean_col in grouped_cols:
                            # 在 GROUP BY 中，加上双引号保留
                            quoted = '"' + grouped_col_originals.get(clean_col, clean_col) + '"'
                            fixed_order_parts.append(f'{quoted} {direction}'.strip())
                        else:
                            # 不在 GROUP BY 中 → 跳过（达梦报错，改用 GROUP BY 第一列兜底）
                            logger.warning(
                                f"ORDER BY 列 '{clean_col}' 不在 GROUP BY 中，将被替换为第一个 GROUP BY 列"
                            )

                    # 如果有有效列，用它们重建 ORDER BY；否则只用第一列
                    if fixed_order_parts:
                        new_order = 'ORDER BY ' + ', '.join(fixed_order_parts)
                    else:
                        first_col = '"' + list(grouped_col_originals.values())[0] + '"'
                        new_order = f'ORDER BY {first_col}'
                    sql = sql[:order_match.start()] + new_order + sql[order_match.start() + len(order_text):]
                    logger.info(f"ORDER BY 修复: {sql}")

            logger.info(f"GROUP BY 修复: {sql}")
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
            # 提取所有 FROM/JOIN 中的表名（忽略 AS 别名，保留原始表名）
            # 匹配 FWBZ."table_name"（捕获 table_name）或 "table_name"（直接捕获）
            from_tables = set()
            for m in re.finditer(
                r'(?:FROM|JOIN)\s+(?:FWBZ\."([^"]+)"|"([^"]+)")',
                sql, re.IGNORECASE
            ):
                # group(1) = FWBZ."table" 情况下的表名，group(2) = 直接 "table" 情况
                captured = m.group(1) or m.group(2)
                from_tables.add(captured.lower())

            # 提取所有在 ON 条件中出现的表引用（"xxx"."yyy" 形式）
            # 但排除已被双引号包裹后已处理的（因为此时双引号已加好）
            on_table_refs = set()
            for m in re.finditer(r'"(\w+)"\."(\w+)"', sql):
                on_table_refs.add(m.group(1).lower())

            # 找出幽灵表（在 ON 中出现但不在 FROM/JOIN 中）
            phantom_tables = on_table_refs - from_tables

            if not phantom_tables:
                return sql

            logger.warning(f">>> 发现幽灵表引用: {phantom_tables}，尝试自动修复")

            for phantom in phantom_tables:
                if phantom == 'device':
                    # "device" 表缺失：需要补全 alarm_record → device 的 JOIN
                    # 策略：在第一个 JOIN 之前插入 LEFT JOIN device，并修正后续 ON 条件
                    # 示例：把 ON "device"."category_id" 改为 ON d."category_id"，
                    #       同时在前面插入 LEFT JOIN FWBZ."device" d ON "alarm_record"."device_id"=d."id"

                    # 找 alarm_record 的位置（主表）
                    alarm_record_pos = re.search(
                        r'FROM\s+(?:FWBZ\.)?"alarm_record"',
                        sql, re.IGNORECASE
                    )
                    if not alarm_record_pos:
                        # 找不到 alarm_record，跳过
                        logger.warning("找不到 alarm_record，无法补全 device JOIN")
                        continue

                    # 找第一个 JOIN 关键字的位置（用于确定插入点）
                    first_join = re.search(r'\s+LEFT\s+JOIN\s+', sql, re.IGNORECASE)
                    first_inner_join = re.search(r'\s+INNER\s+JOIN\s+', sql, re.IGNORECASE)

                    # 取最早出现的 JOIN
                    join_positions = []
                    if first_join:
                        join_positions.append(first_join.start())
                    if first_inner_join:
                        join_positions.append(first_inner_join.start())

                    if not join_positions:
                        # 没有 JOIN，在 FROM 子句之后插入
                        insert_pos = re.search(
                            r'FROM\s+(?:FWBZ\.)?"alarm_record"[^"]*',
                            sql, re.IGNORECASE
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
                        r'"device"\."(\w+)"',
                        sql, re.IGNORECASE
                    )
                    if not first_device_ref:
                        continue

                    device_col = first_device_ref.group(1)
                    logger.info(f"幽灵表 device 被引用列: {device_col}，尝试注入 JOIN")

                    # 插入 LEFT JOIN device，在第一个 JOIN 之前
                    device_join = ' LEFT JOIN FWBZ."device" ON "alarm_record"."device_id"="device"."id"'
                    new_sql = sql[:insert_pos] + device_join + sql[insert_pos:]
                    logger.info(f"注入 device JOIN 后的 SQL: {new_sql[:300]}")
                    sql = new_sql
                else:
                    # 其他幽灵表：无法安全推断 JOIN 路径，直接移除整个 JOIN 块
                    # 原因：去掉表前缀后剩下的裸列名会引入歧义（多表都有 id 等），
                    #       后续修复逻辑无法安全推断应该加哪个表的前缀。
                    logger.warning(f"幽灵表 '{phantom}' 无法安全修复，将移除整个 JOIN 块")

                    # 匹配包含该幽灵表的完整 JOIN 块（从 JOIN 到下一个 JOIN/WHERE/ORDER 之前）
                    # 格式: LEFT JOIN "phantom" ON (...) 或 LEFT JOIN FWBZ."phantom" ON (...)
                    phantom_join_pattern = (
                        rf'\s+(LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|JOIN)\s+'
                        rf'(?:FWBZ\.)?"{re.escape(phantom)}"'
                        rf'(?:\s+AS\s+"[^"]+")?\s+ON\s+.+?'
                        rf'(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)'
                    )
                    sql = re.sub(phantom_join_pattern, '', sql, flags=re.IGNORECASE | re.DOTALL)
                    # 清理可能遗留的连续空格
                    sql = re.sub(r'\s{2,}', ' ', sql)

            logger.info(f"幽灵表修复后 SQL: {sql}")
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
            AR_FK_COLUMNS = frozenset({
                'alarm_rule_id', 'device_id', 'space_id', 'alarm_category_id',
                'alarm_level_id', 'point_id', 'alarm_rule_point_id', 'device_category_id',
                'charge_person', 'device_category_id',
            })

            # alarm_record 的自有列（用于判断右操作数可能属于 alarm_record 而非 JOIN 表）
            AR_COLUMNS = frozenset({
                'id', 'create_time', 'update_time', 'create_by', 'update_by',
                'sys_org_code', 'alarm_rule_id', 'device_id', 'device_name',
                'space_id', 'space_name', 'alarm_content', 'alarm_time',
                'alarm_category_id', 'alarm_category_name', 'alarm_level_id',
                'alarm_level_name', 'charge_person', 'charge_person_name',
                'alarm_status', 'point_id', 'point_name', 'value',
                'condition_value', 'operator', 'time_granularity',
                'alarm_rule_point_id', 'device_category_id', 'alarm_level_color',
                'event_id',
            })

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
                content = re.sub(r'\bON\b', '', on_clause_str, flags=re.IGNORECASE).strip()

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
                    if c == '"' and (i == 0 or content[i-1] != '\\'):
                        in_quote = not in_quote
                        i += 1
                        continue
                    if in_quote:
                        i += 1
                        continue
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                    elif depth == 0 and content[i:i+3].upper() == 'AND' and content[i+3:i+4] in ('', ' ', '\t'):
                        parts.append(content[last:i].strip().strip('()').strip())
                        last = i + 3
                        while last < len(content) and content[last] in ' \t':
                            last += 1
                        i = last
                        continue
                    i += 1
                parts.append(content[last:].strip().strip('()').strip())

                # 步骤4：处理每个原子条件 "col1"="col2"
                fixed_parts = []
                for part in parts:
                    if '=' not in part:
                        fixed_parts.append(part)
                        continue

                    # 分割左右操作数（支持引号包裹的列名）
                    # 找第一个不在引号内的等号
                    eq_pos = -1
                    depth = 0
                    in_q = False
                    for idx, ch in enumerate(part):
                        if ch == '"' and (idx == 0 or part[idx-1] != '\\'):
                            in_q = not in_q
                        if not in_q:
                            if ch == '(':
                                depth += 1
                            elif ch == ')':
                                depth -= 1
                            elif ch == '=' and eq_pos < 0:
                                eq_pos = idx
                    if eq_pos < 0:
                        fixed_parts.append(part)
                        continue

                    left = part[:eq_pos].strip().strip('()"')
                    right = part[eq_pos+1:].strip().strip('()"')
                    new_left = left
                    new_right = right

                    # 左操作数：如果是 alarm_record 的外键列，加前缀
                    if left and left.lower() in AR_FK_COLUMNS and '.' not in left:
                        new_left = f'"alarm_record"."{left}"'
                    # 右操作数：如果是裸 "id"，加目标表前缀
                    if right and '.' not in right:
                        right_lower = right.lower()
                        if right_lower == 'id':
                            new_right = f'"{joined_table}"."id"'
                        elif right_lower in AR_COLUMNS and left.lower() not in AR_FK_COLUMNS:
                            # 右操作数是 alarm_record 列但左操作数不是外键 → 加 alarm_record 前缀
                            new_right = f'"alarm_record"."{right}"'

                    if new_left == left and new_right == right:
                        fixed_parts.append(part)
                    else:
                        fixed_parts.append(f'{new_left}={new_right}')

                # 步骤5：重建 ON 子句
                result = 'ON ' + ' AND '.join(fixed_parts)
                if result != on_clause_str:
                    logger.info(f"  ON 修复: {on_clause_str!r} → {result!r}")
                return result

            # 遍历所有 JOIN 块，修复对应的 ON 条件
            def replace_join_block(m: re.Match) -> str:
                full_match = m.group(0)
                join_type = m.group(1)  # LEFT JOIN, INNER JOIN 等
                table_name_raw = m.group(2)
                table_name = table_name_raw.strip('".').lower()

                # 找这个 JOIN 的完整 ON 条件（使用贪婪匹配以捕获多 AND 条件）
                on_match = re.search(r'\bON\b\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)', full_match, re.IGNORECASE | re.DOTALL)
                if not on_match:
                    return full_match

                fixed_on = fix_single_on(on_match.group(0), table_name)
                # 重建 JOIN 块：只替换 ON 部分
                return re.sub(r'\bON\b\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)', fixed_on, full_match, count=1, flags=re.IGNORECASE | re.DOTALL)

            # 匹配：JOIN 类型 + 表名（支持 FWBZ."table" 或 "table"）+ 可选的 AS 别名 + ON 条件
            # 用贪婪匹配 .+ 配合 lookahead 边界，确保捕获完整的多 AND ON 条件
            pattern = r'(LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|JOIN)\s+(?:FWBZ\.)?"([^"]+)"(?:\s+AS\s+"[^"]+")?\s+ON\s+(.+?)(?=\s+(?:LEFT|INNER|RIGHT)\s+JOIN|\s+WHERE|\s+ORDER\s+BY|\s+GROUP\s+BY|\s+$)'

            if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
                sql = re.sub(
                    pattern,
                    replace_join_block,
                    sql,
                    count=0,  # 全局替换
                    flags=re.IGNORECASE | re.DOTALL
                )

            logger.info(f"ON 条件修复后 SQL: {sql[:300]}")

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
                r'FROM\s+(.+?)(?=\s+WHERE|\s+GROUP|\s+ORDER|\s+HIMIT|\s+OFFSET|\s+UNION|,|\s*$)',
                sql, re.IGNORECASE | re.DOTALL
            )
            from_clause = from_clause_match.group(1) if from_clause_match else ''
            # 提取表名：支持 FWBZ."table" / "FWBZ"."table" / "table" / FWBZ.table
            defined_tables = set()
            for m in re.finditer(
                r'FWBZ\."(\w+)"|FWBZ\.(\w+)|"FWBZ"\.?"(\w+)"|"(\w+)"',
                from_clause, re.IGNORECASE
            ):
                t = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or '').strip().lower()
                if t:
                    defined_tables.add(t)
            if 'alarm_record' not in defined_tables:
                logger.info(f"歧义列名修复跳过：FROM 子句中无 alarm_record 表")
                return sql

            # 歧义列名：多表共有，必须加 alarm_record. 前缀
            AMBIGUOUS = frozenset({'id', 'create_time', 'update_time', 'sys_org_code'})

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
                    col_start = full.index('"', second_quote + 2)  # 跳过 "." 后找到列名开头引号
                    col_end = full.index('"', col_start + 1)        # 再找列名结尾引号
                    table = full[first_quote+1:second_quote]
                    col_val = full[col_start+1:col_end]
                    return '"' + table + '"."alarm_record"."' + col_val + '"'

                # 匹配 "xxx"."yyy" 格式（两个引号组，中间有点）
                pattern = r'"[^"]+"\.[^"]*"' + re.escape(col) + r'"'
                sql, n = re.subn(pattern, expand_qualified, sql, flags=re.IGNORECASE)
                if n > 0:
                    logger.info(f"  步骤1: {col} 在 qualified 格式中被替换 {n} 处")

            # 步骤2：裸歧义列名加前缀（仅当前面没有表前缀时）
            for col in AMBIGUOUS:
                # 匹配裸 "id"：前面不是字母/数字/点/引号
                # 后面不是点/引号（确保不会跨 qualified 边界）
                def replace_bare(m):
                    return '"alarm_record"."' + col + '"'
                pattern = r'(?<![\w."])("' + re.escape(col) + r'")(?![\w."])'
                sql, n = re.subn(pattern, replace_bare, sql, flags=re.IGNORECASE)
                if n > 0:
                    logger.info(f"  步骤2: 裸 {col} 被替换 {n} 处")

            # 步骤3：兜底——修复步骤1产生的三段式 "table"."alarm_record"."col"
            # 例如："device"."alarm_record"."id" → "device"."id"
            sql, n = re.subn(
                r'"([^"]+)"\."alarm_record"\."([^"]+)"',
                r'"".""',
                sql,
                flags=re.IGNORECASE
            )
            if n > 0:
                logger.info(f"  步骤3: 修复三段式 {n} 处")

            logger.info(f"歧义列名修复后 SQL: {sql[:300]}")
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
            from app.core.dameng import _load_schema_from_file

            schema = _load_schema_from_file()
            if not schema:
                return sql

            # 只在 SQL 含 "data_date" 或 "stat_date" 时才处理
            if not re.search(r'"(data_date|stat_date)"', sql, re.IGNORECASE):
                return sql

            # 日期列候选：data_date / date / stat_date
            DATE_COLS = ('data_date', 'date', 'stat_date')

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
                "select", "from", "where", "group", "order", "having", "limit",
                "offset", "union", "with", "on", "as", "join", "inner", "left",
                "right", "outer", "full", "cross", "and", "or", "not", "in",
                "is", "null", "like", "between", "exists", "case", "when",
                "then", "else", "end", "set", "values", "into", "update",
            }
            from_table_pattern = re.compile(
                r'\b(?:FROM|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN|JOIN)\s+'
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
            tables_have_data_date = {t for t in real_tables if 'data_date' in schema.get(t, set())}
            if not tables_have_data_date and real_tables:
                # 所有表都没有 data_date 列，可以安全替换 bare 引用
                # 但需要按表的真实日期列替换，若有多种日期列则无法全局替换
                real_date_cols = {_find_real_date_col(t) for t in real_tables}
                real_date_cols.discard(None)
                # 如果所有表的真实日期列名一致，按该列名替换
                if len(real_date_cols) == 1:
                    target_col = real_date_cols.pop()
                    sql = re.sub(r'"data_date"', f'"{target_col}"', sql, flags=re.IGNORECASE)
                    sql = re.sub(r'"stat_date"', f'"{target_col}"', sql, flags=re.IGNORECASE)

            return sql
        except Exception as e:
            logger.warning(f"日期列修复失败: {e}")
            return sql

    def _format_column_label(self, col_name: str) -> str:
        """将英文列名格式化为中文标签"""
        mapping = {
            # 设备相关
            "device_name": "设备名称", "device_code": "设备编码", "device_type": "设备类型",
            "device_id": "设备ID", "run_state": "运行状态", "last_gather_time": "最后采集时间",
            "create_time": "创建时间",
            # 告警相关
            "alarm_content": "告警内容", "alarm_time": "告警时间", "alarm_category_name": "告警类别",
            "alarm_level_name": "告警级别", "alarm_status": "告警状态", "alarm_count": "告警数量",
            "charge_person_name": "责任人",
            # 场馆相关
            "venue_name": "场馆名称", "venue_id": "场馆ID", "floors": "楼层数", "orientation": "朝向",
            "longitude": "经度", "latitude": "纬度",
            # 空间相关
            "space_name": "空间名称", "space_id": "空间ID", "full_name": "完整名称", "full_id": "完整编号",
            # 分类相关
            "category_name": "类型名称", "category_id": "分类ID", "has_child": "是否有子级",
            # 能耗/计量
            "value": "数值", "total_energy": "总能耗", "carbon_emission": "碳排放",
            "metering_unit": "计量单位", "type": "类型",
            # 客流/人员
            "today_in_count": "今日入场", "current_in_count": "当前在场数", "max_count": "最大人数",
            "average_duration": "平均时长", "today_entry_count": "今日入场数", "average_parking_duration": "平均停车时长",
            "remaining_space_count": "剩余车位数", "recognition_record_count": "识别记录数",
            "abnormal_warning_count": "异常告警数",
            # 照明相关
            "area_name": "区域名称", "area_code": "区域编码", "circuit_name": "回路名称",
            "all_duration": "总时长", "comstat": "通信状态",
            # 停车相关
            "stat_date": "统计日期", "data_date": "日期", "date": "日期",
            # 报告相关
            "report_type": "报告类型", "title": "标题", "summary": "摘要", "content": "内容",
            "target_name": "目标名称", "scope": "范围",
            # 统计相关
            "total_count": "总数", "online_count": "在线数", "offline_count": "离线数",
            "total_value": "总数值", "avg_value": "平均值", "max_value": "最大值", "min_value": "最小值",
            "count": "数量", "percentage": "占比",
            # 通用
            "location": "位置", "area": "面积", "status": "状态",
            "node_name": "节点名称", "node_code": "节点编码",
            "time_range": "时间范围", "created_at": "创建时间",
            "id": "ID", "pid": "父级ID",
            # 照明/其他
            "ceiling_h": "层高", "lighting": "照明", "basic_facility": "基本设施", "buildable": "可建面积",
            # 序号/分页
            "rn": "序号", "rownum": "序号", "rowno": "序号", "no": "序号", "num": "序号",
            # 特殊列名（大小写不敏感）
            "date": "日期", "time": "时间", "name": "名称", "code": "编码",
            "entry": "入场", "exit": "出场", "in": "在场", "out": "离场",
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

        # 辅助函数：解析复杂列名表达式，提取真正的列名
        def _extract_column_name(expr: str) -> str:
            """从复杂表达式中提取列名"""
            # NVL("xxx", 0) -> xxx
            m = re.search(r'NVL\s*\(\s*"?([^",\)]+)"?\s*,\s*[^)]+\)', expr, re.IGNORECASE)
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
            parts = expr.split('.')
            if len(parts) > 1:
                last = parts[-1].strip('" \'')
                return last
            return expr

        # 预处理：建立复杂 key -> 干净列名 的映射
        key_to_column = {}
        for k in keys:
            col_name = _extract_column_name(k)
            key_to_column[k] = col_name

        # 优先选择人类可读的分类列（按优先级排序）
        readable_priority = [
            # 场馆/空间名称（最可读）
            'venue_name', 'space_name', 'area_name', 'location', 'position',
            # 设备/对象名称
            'device_name', 'name', 'node_name', 'title', 'full_name',
            # 告警/状态相关名称
            'alarm_category_name', 'alarm_level_name', 'category_name', 'status',
            # 描述性内容
            'alarm_content', 'content', 'remark', 'description',
            # 最后才用编码类（最不可读）
            'device_code', 'device_type', 'node_code', 'area_code', 'circuit_code',
            'space_id', 'venue_id', 'device_id', 'id', 'bigint'
        ]

        # 找分类列：优先选择人类可读的名称列
        cat_key = None
        cat_key_raw = None

        # 先按优先级找可读列（同时检查原始key和解析后的列名）
        for priority_key in readable_priority:
            # 先检查是否是干净的列名
            if priority_key in keys:
                v = sample.get(priority_key)
                if isinstance(v, (str, datetime, date)):
                    cat_key_raw = priority_key
                    clean_k = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*"([^"]+)"\s*\)$', r'\2', priority_key, flags=re.IGNORECASE)
                    cat_key = clean_k
                    break
            # 再检查复杂表达式解析后的列名
            for raw_key, col_name in key_to_column.items():
                if col_name.lower() == priority_key.lower():
                    v = sample.get(raw_key)
                    if isinstance(v, (str, datetime, date)):
                        cat_key_raw = raw_key
                        cat_key = col_name
                        break
            if cat_key:
                break

        # 如果没找到可读列，用第一个字符串列
        if not cat_key:
            for k in keys:
                v = sample.get(k)
                col_name = key_to_column.get(k, k)
                if col_name.lower() not in ['id', 'bigint'] and isinstance(v, (str, datetime, date)):
                    cat_key_raw = k
                    cat_key = col_name
                    break

        # 找数值列（包含聚合函数列）
        num_candidates = [k for k in keys if isinstance(sample.get(k), (int, float, Decimal))]
        numeric_keys = [
            k for k in num_candidates
            if not re.match(r'^(id|bigint)$', k, re.IGNORECASE)
        ]

        # 如果没有数值列但有分类列，说明是明细数据，每行计数=1
        if not numeric_keys and cat_key:
            # 生成假数值列：每行计数为1
            chart_data = []
            # 按分类列聚合计数
            category_counts = {}
            for row in data:
                key_val = str(row.get(cat_key_raw, "未知"))
                # 格式化标签
                display_val = self._format_category_label(cat_key, key_val, row)
                if display_val not in category_counts:
                    category_counts[display_val] = 0
                category_counts[display_val] += 1

            # 转换为图表数据
            chart_data = [
                {"name": name, "value": count}
                for name, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            ]

            chart_title = self._gen_chart_title(question, "记录数量")
            chart_id = f"chart_{datetime.now().strftime('%H%M%S%f')}"

            if len(chart_data) <= 6:
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
                            "data": chart_data
                        }]
                    }
                }
            else:
                # 柱状图：按分类聚合后的数据
                sorted_data = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:20]
                x_axis_data = [str(name) for name, _ in sorted_data]
                series_data = [float(count) for _, count in sorted_data]

                return {
                    "chartType": "bar",
                    "chartId": chart_id,
                    "option": {
                        "title": {"text": chart_title, "left": "center"},
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "grid": {"left": "3%", "right": "4%", "bottom": "12%", "containLabel": True},
                        "xAxis": {"type": "category", "data": x_axis_data, "axisLabel": {"rotate": 30, "interval": 0}},
                        "yAxis": {"type": "value", "name": "记录数量"},
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

        if not cat_key or not numeric_keys:
            return {}

        first_num_key = numeric_keys[0]
        clean_num_key = re.sub(r'^(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*"([^"]+)"\s*\)$', r'\2', first_num_key, flags=re.IGNORECASE)
        label = self._format_column_label(clean_num_key)

        # 生成人类可读的分类标签
        x_axis_data = []
        for row in data[:20]:
            raw_value = str(row.get(cat_key_raw, ""))
            # 如果是编码类列，尝试进行格式化
            display_value = self._format_category_label(cat_key, raw_value, row)
            x_axis_data.append(display_value)

        series_data = [float(row.get(first_num_key, 0) or 0) for row in data[:20]]

        chart_title = self._gen_chart_title(question, label)
        chart_id = f"chart_{datetime.now().strftime('%H%M%S%f')}"

        if len(data) <= 6:
            pie_data = [
                {"name": x_axis_data[i], "value": float(row.get(first_num_key, 0) or 0)}
                for i, row in enumerate(data[:20])
            ]
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

    def _format_category_label(self, col_key: str, raw_value: str, row: dict) -> str:
        """格式化分类标签，使人类更易读"""
        if not raw_value or raw_value in ['None', 'null', '-']:
            return "未知"

        # 编码类列的格式化规则
        code_format_rules = {
            'device_code': lambda v: self._format_device_code(v, row),
            'device_type': lambda v: self._format_device_type(v),
            'node_code': lambda v: self._format_node_code(v, row),
            'space_name': lambda v: v if v else "未知空间",
            'area_name': lambda v: v if v else "未知区域",
            'venue_name': lambda v: v if v else "未知场馆",
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
        if row.get('device_name') and row.get('device_name') not in [None, 'None', '']:
            return str(row['device_name'])

        # 设备编码解析规则
        if not code:
            return "未知设备"

        # 尝试从编码推断类型
        code_upper = code.upper()
        if 'KT' in code_upper:
            return f"空调-{code}"
        elif 'XF' in code_upper:
            return f"新风-{code}"
        elif 'CH' in code_upper:
            return f"冷机-{code}"
        elif 'PV' in code_upper:
            return f"光伏-{code}"
        elif 'PD' in code_upper or 'DP' in code_upper:
            return f"配电-{code}"
        elif 'ZT' in code_upper:
            return f"照明-{code}"

        # 通用：直接返回编码（截断过长的）
        if len(code) > 12:
            return code[:10] + "..."
        return code

    def _format_device_type(self, device_type: str) -> str:
        """格式化设备类型为中文"""
        type_mapping = {
            '1': '仪表', '2': '设备',
            'meter': '仪表', 'device': '设备',
            'ac': '空调', 'air_condition': '空调机组',
            'fresh_air': '新风机组', 'power': '配电',
            'light': '照明', 'pv': '光伏'
        }
        return type_mapping.get(str(device_type).lower(), str(device_type))

    def _format_node_code(self, code: str, row: dict) -> str:
        """格式化节点编码为人类可读名称"""
        # 如果有 node_name，优先使用
        if row.get('node_name') and row.get('node_name') not in [None, 'None', '']:
            return str(row['node_name'])

        if not code:
            return "未知节点"
        if len(code) > 12:
            return code[:10] + "..."
        return code

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
            logger.info(f"能耗查询: question={question}, time={start_date}~{end_date}")

            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在查询能耗配置...'})}\n\n"

            # ========== 步骤 2: 查 metering_point 配置 ==========
            mp_sql = (
                'SELECT "id", "node_name", "type", "true_formula" '
                'FROM "FWBZ"."metering_point" '
                'WHERE "true_formula" IS NOT NULL AND "true_formula" <> \'\' '
                'LIMIT 500 OFFSET 0'
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

            logger.info(f"查到 {len(metering_points)} 个计量点配置")

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

            logger.info(f"共 {len(all_device_codes)} 个 device_code 需查询")

            # 查 device 表, 建 device_code -> device.id 映射 (分批, 每批 1000)
            code_to_id = {}  # device_code (str) -> device.id (int)
            code_list = list(all_device_codes)
            for i in range(0, len(code_list), 1000):
                chunk = code_list[i:i + 1000]
                codes_sql = ",".join(f"'{c.replace(chr(39), chr(39)*2)}'" for c in chunk)
                device_sql = (
                    f'SELECT "id", "device_code" '
                    f'FROM "FWBZ"."device" '
                    f'WHERE "device_code" IN ({codes_sql}) '
                    f'LIMIT 5000 OFFSET 0'
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

            logger.info(f"device 映射完成, {len(code_to_id)} 个有对应 id")

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
                chunk = device_id_list[i:i + 1000]
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

            logger.info(f"data_day 查询完成, {len(device_values)} 个设备有数据")

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
                energy_rows.append({
                    "energy_medium": readable,
                    "total_value": round(Decimal(str(total)), 4),
                })
            # 按能耗降序
            energy_rows.sort(key=lambda r: float(r["total_value"]), reverse=True)

            # ========== 步骤 6: emit table ==========
            vue_table = {
                "columns": [
                    {"key": "energy_medium", "label": "能介"},
                    {"key": "total_value", "label": "累计能耗"},
                ],
                "rows": [
                    {"energy_medium": r["energy_medium"], "total_value": str(r["total_value"])}
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
            yield f"data: {self._safe_json_dumps({'type': 'table', **vue_table})}\n\n"
            await asyncio.sleep(0)

            # ========== 步骤 7: emit chart (bar) ==========
            chart_id = f"chart_energy_{datetime.now().strftime('%H%M%S%f')}"
            x_axis = [r["energy_medium"] for r in energy_rows]
            series_data = [float(r["total_value"]) for r in energy_rows]
            chart = {
                "chartType": "bar",
                "chartId": chart_id,
                "option": {
                    "title": {"text": self._gen_chart_title(question, "能耗"), "left": "center"},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "12%", "containLabel": True},
                    "xAxis": {"type": "category", "data": x_axis, "axisLabel": {"rotate": 30, "interval": 0}},
                    "yAxis": {"type": "value", "name": "累计能耗"},
                    "series": [{
                        "type": "bar",
                        "data": series_data,
                        "itemStyle": {
                            "color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "#5470C6"},
                                    {"offset": 1, "color": "#91CC75"},
                                ],
                            },
                            "borderRadius": [4, 4, 0, 0],
                        },
                        "label": {"show": True, "position": "top", "formatter": "{c}"},
                    }],
                },
            }
            stream_summary["chart"] = {"chartType": "bar", "chartId": chart_id}
            yield f"data: {self._safe_json_dumps({'type': 'chart', **chart})}\n\n"
            await asyncio.sleep(0)

            # ========== 步骤 8: emit summary ==========
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'db', 'message': '正在生成分析总结...'})}\n\n"
            summary = self._generate_summary(question, energy_rows, vue_table)
            summary = summary.replace('\n', ' ').replace('\r', '').strip()
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
            "error": None,
        }

        try:
            # ========== 阶段1：QA 匹配 (核心: LLM 判用户问题 vs 问题清单) ==========
            yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'detecting'})}\n\n"

            # 能耗公式计算分支(拦截在 QA 匹配之前, 避免 30s 超时)
            if self._is_energy_formula_query(question):
                async for chunk in self._handle_energy_query(
                    question, access_time, client_ip, user_agent, on_summary
                ):
                    yield chunk
                return

            match_result = None
            try:
                from app.services.qa_matcher import get_qa_matcher
                from app.services.sql_template_loader import get_template_loader

                matcher = get_qa_matcher()
                template_loader = get_template_loader()

                if matcher.available():
                    # 同步阻塞调用 → 放线程池, 不卡 event loop
                    match_result = await asyncio.to_thread(matcher.match, question)
                else:
                    logger.warning("QA 匹配器不可用, 走兜底")
            except Exception as e:
                logger.exception(f"QA 匹配异常, 走兜底: {e}")

            # 判定是否匹配
            #   - match_result.matched 用 confidence >= 0.6, 适合 LLM 时代
            #   - 现在用 TF-IDF (score 通常 0.05~0.5), 改用 best_qid 非空判定
            #   - TF-IDF 内部已有阈值过滤 (tfidf_threshold=0.15), 到这里 best_qid 非空 = 已过滤掉低质量候选
            matched = (
                match_result is not None
                and bool(match_result.best_qid)
            )

            if matched:
                qid = match_result.best_qid
                confidence = match_result.best_confidence
                stream_summary["mode"] = "db"
                stream_summary["qid"] = qid
                stream_summary["match_confidence"] = round(confidence, 3)

                # 拿该 Q-ID 的 SQL 范式
                sql_template = template_loader.get(qid) or ""
                if not sql_template:
                    logger.warning(f"Q{qid} 在问答手册中无 SQL 范式, 仍走 DB 模式但无范式参考")

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
                        stream_summary["fallback_reason"] = f"匹配异常: {match_result.error}"
                    elif not match_result.best_qid:
                        stream_summary["fallback_reason"] = "问题清单无匹配"
                    else:
                        stream_summary["fallback_reason"] = (
                            f"匹配 Q{match_result.best_qid} 但置信度 {match_result.best_confidence:.0%} < 60%"
                        )
                else:
                    stream_summary["fallback_reason"] = "匹配器不可用"

                logger.info(
                    f"兜底分支: 走 LLM 流式 | 原因={stream_summary['fallback_reason']}"
                )

                yield f"data: {self._safe_json_dumps({'type': 'mode', 'value': 'llm', 'message': '本问题未匹配到业务清单, 使用通用 LLM 回答...'})}\n\n"

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
