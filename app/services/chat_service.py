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
    """
    import re
    from pathlib import Path

    schema_file = Path(__file__).parent.parent / "config" / "FWBZ_strut.sql"
    if not schema_file.exists():
        logger.warning(f"Schema 文件不存在，跳过动态表结构: {schema_file}")
        return ""

    try:
        content = schema_file.read_text(encoding='utf-8')
        tables: List[Tuple[str, List[str]]] = []
        # 匹配 CREATE TABLE "FWBZ"."table_name" ( ... );
        for match in re.finditer(
                r'CREATE\s+TABLE\s+"FWBZ"\."(\w+)"\s*\((.*?)\)\s*;',
                content, re.IGNORECASE | re.DOTALL):
            tname = match.group(1)
            block = match.group(2)
            cols: List[str] = []
            for line in block.splitlines():
                line = line.strip()
                if re.match(r'^(PRIMARY|UNIQUE|CHECK|CONSTRAINT|INDEX|FOREIGN)', line, re.IGNORECASE):
                    continue
                for cm in re.finditer(r'"(\w+)"', line):
                    cols.append(cm.group(1))
            if cols:
                tables.append((tname, cols))

        # 格式化成简洁文本
        lines = ["## 数据库真实表结构（来源：config/FWBZ_strut.sql）", ""]
        for tname, cols in tables:
            col_str = ", ".join(f'"{c}"' for c in cols)
            lines.append(f"### {tname}")
            lines.append(f"  列: {col_str}")
            lines.append("")

        logger.info(f"动态 schema 生成完成，共 {len(tables)} 个表")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Schema 文件解析失败: {e}")
        return ""


# 一次性构建动态表结构（服务启动时）
_SCHEMA_TEXT: str = _build_schema_text()


# 达梦数据库 Schema 上下文（供 LLM 生成 SQL 使用）
DAMENG_SCHEMA_CONTEXT = """
## 达梦数据库信息
- 类型：Dameng 8.0 (08.00.000)
- Schema：FWBZ
- 标识符引号：达梦大小写敏感，**所有表名和字段名必须用双引号包裹**，如 `"device"."device_name"`、`"alarm_time"`。
- 自增列：使用序列 FWBZ.SEQ_xxx，不支持 AUTO_INCREMENT

## ⚠️ 语法限制（严格遵守，禁止使用 MySQL 语法）

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
| DATEDIFF(a,b)       | 使用 DATEDIFF(MINUTE, a, b)，禁止改为 (a - b) |
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

5. **禁止在函数调用外层包裹双引号**：`DATEDIFF(MINUTE, "alarm_time", "process_time")` 本身是正确的（参数列名有双引号）；但禁止把整个函数调用用双引号包裹，如 `"DATEDIFF(MINUTE, "alarm_time", "process_time")"` 是错误的。ORDER BY 等子句中引用函数时同样禁止在最外层加双引号。

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

10. **禁止臆造字段**：只使用表结构中明确列出的字段，**绝不能使用表结构中没有的字段名**。常见臆造陷阱：
    - `lighting_area` 表的主键是 `"id"`，**没有 `area_id`**（`area_id` 在 `lighting_circuit` 表中）
    - `lighting_circuit` 表通过 `area_id` 外键关联 `lighting_area.id`
    - 如果不确定某个表有哪些列，回头查看本提示词开头的「核心业务表结构」部分

## LIMIT 分页示例（达梦）

## LIMIT 分页示例（达梦）
```sql
-- 取前 500 条
SELECT "id", "device_name" FROM FWBZ."device"
ORDER BY "create_time" DESC
LIMIT 500 OFFSET 0

-- 取第 11~20 条（即跳过前10条，取10条）
-- 注意：语法是 LIMIT n OFFSET m，不是 LIMIT m,n
SELECT "id", "device_name" FROM FWBZ."device"
ORDER BY "create_time" DESC
LIMIT 10 OFFSET 10
时间差计算（告警处理时长，单位：分钟）
重要：alarm_time 和 process_time 是 TIMESTAMP 类型，禁止直接相减！

正确写法：

sql
-- 使用 DATEDIFF 函数（达梦原生支持）
-- 注意：列名必须加双引号，别名写在函数外部
DATEDIFF(MINUTE, "alarm_time", "process_time") AS 处理时长分钟数

-- ORDER BY 必须用同样的函数或用别名：
ORDER BY DATEDIFF(MINUTE, "alarm_time", "process_time") ASC
-- 或
ORDER BY 处理时长分钟数 ASC
错误写法（禁止使用）：

sql
-- ❌ 禁止：直接相减或乘 1440，TIMESTAMP 类型不支持算术运算
("process_time" - "alarm_time") * 1440

-- ❌ 禁止：在 DATEDIFF 外面套 CAST 或 TO_DATE
CAST(DATEDIFF(MINUTE, "alarm_time", "process_time") AS VARCHAR)
核心业务表结构
device（设备表）
id(BIGINT), device_code(VARCHAR), device_name(VARCHAR), category_id(BIGINT),
space_id(BIGINT), venue_id(BIGINT), run_state(VARCHAR), device_type(VARCHAR),
last_gather_time(TIMESTAMP), create_time(TIMESTAMP)

alarm_record（告警记录）
id(BIGINT), device_id(BIGINT), device_name(VARCHAR), space_id(BIGINT),
space_name(VARCHAR), alarm_content(TEXT), alarm_time(TIMESTAMP),
alarm_category_name(VARCHAR), alarm_level_name(VARCHAR), alarm_status(VARCHAR),
alarm_rule_id(BIGINT), charge_person_name(VARCHAR), process_time(TIMESTAMP)

⚠️ 注意：alarm_record 表中不存在 area_id、circuit_name、area_name、device_code 等字段！
绝对不要在 SQL 中臆造这些列！

data_day（设备日数据）
id(BIGINT), device_id(BIGINT), value(DECIMAL), time(TIMESTAMP)

data_hour（设备小时数据）
id(BIGINT), device_id(BIGINT), value(DECIMAL), time(TIMESTAMP),
start_value(DECIMAL), end_value(DECIMAL), compute_value(DECIMAL)

equipment_category（设备类型）
id(BIGINT), category_name(VARCHAR), full_name(VARCHAR), pid(BIGINT), has_child(VARCHAR)

table_venue_info（会展场馆）
id(BIGINT, 主键), venue_name(VARCHAR2), location(VARCHAR2), area(VARCHAR2),
floors(BIGINT), orientation(VARCHAR2), longitude(DECIMAL), latitude(DECIMAL)
⚠️ 注意：该表主键是 id，不是 venue_id，没有 venue_id 字段

space（空间表）
id(BIGINT), space_name(VARCHAR), full_name(VARCHAR), full_id(VARCHAR), pid(BIGINT), has_child(VARCHAR)

metering_point（计量点）
id(BIGINT), node_name(VARCHAR), node_code(VARCHAR), type(VARCHAR),
category_id(BIGINT), space_id(BIGINT), metering_unit(BIGINT)

metering_point_data_day（计量点日数据）
id(BIGINT), metering_point_id(BIGINT), time(TIMESTAMP), value(DECIMAL)

table_personnel_statistics（人员统计）
id(BIGINT), stat_date(DATE), today_entry_count(BIGINT), current_in_count(BIGINT),
recognition_record_count(BIGINT), abnormal_warning_count(BIGINT)

table_venue_flow（场馆客流）
id(BIGINT), data_date(DATE), venue_id(BIGINT), today_in_count(BIGINT),
today_now_count(BIGINT), max_count(BIGINT), max_time(TIME), average_duration(DOUBLE), status(TINYINT)

lighting_area（照明区域）
id(BIGINT), area_name(VARCHAR), area_code(VARCHAR), status(VARCHAR),
space_name(VARCHAR), type(VARCHAR), all_duration(BIGINT)

lighting_circuit（照明回路）
id(BIGINT), circuit_name(VARCHAR), circuit_code(VARCHAR), status(VARCHAR),
area_id(BIGINT), all_duration(BIGINT), comstat(VARCHAR)

ai_report_history（AI报告历史）
id(BIGINT), report_type(VARCHAR), title(VARCHAR), content(CLOB),
summary(VARCHAR), time_range(VARCHAR), target_name(VARCHAR),
scope(VARCHAR), created_at(TIMESTAMP)

carbon_emission_factor（碳排放因子）
id(VARCHAR), carbon_factor_name(VARCHAR), coefficient(VARCHAR), unit(VARCHAR)

standard_coal_coefficient（标准煤系数）
id(VARCHAR), energy_medium(VARCHAR), unit(VARCHAR), eccsc(VARCHAR), ecf(VARCHAR)

table_parking_count（停车场统计）
id(BIGINT), date(DATE), today_entry_count(BIGINT), current_in_count(BIGINT),
remaining_space_count(BIGINT), average_parking_duration(DOUBLE)

重要约束
设备通过 venue_id 关联会展场馆（table_venue_info.id）

设备通过 space_id 关联空间（space.id）

设备通过 category_id 关联设备类型（equipment_category.id）

告警通过 device_id 关联设备（device.id）

计量点通过 space_id 关联空间（space.id）

计量点日数据通过 metering_point_id 关联计量点（metering_point.id）

照明回路通过 area_id 关联照明区域（lighting_area.id）

所有时间字段用单引号包裹，如 alarm_time >= '2026-01-01'
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

        # 重试时附带的错误反馈（初始为空，验证失败后填充）
        retry_hint = ""

        base_prompt_header = f"""{DAMENG_SCHEMA_CONTEXT}{_SCHEMA_TEXT}{hint_text}

============================================================
【警告】生成 SQL 前必须先查阅上方表结构，只使用列出的真实列名！
禁止臆造任何不在表结构中的字段名！
============================================================

## 任务
根据用户问题生成一条达梦数据库 SQL 查询语句。

用户问题：{question}

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
        
        for attempt in range(2):
            try:
                response = self.ollama.call_llm([
                    {"role": "user", "content": base_prompt_header + retry_hint}
                ], temperature=0.1)
                sql = response.strip()
                sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE)
                sql = re.sub(r'^```\s*', '', sql)
                sql = re.sub(r'\s*```$', '', sql)
                # 清理末尾分号和空白
                sql = sql.rstrip(';').strip()

                logger.info("LLM原始输出: %s", sql[:500] if len(sql) > 500 else sql)

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

                    # 3. 修复 LLM 常见的列名混淆（按表映射）
                    # table_parking_count 的日期列是 "date"，不是 "data_date"
                    sql = re.sub(
                        r'"table_parking_count"' + r'.*?"data_date"',
                        lambda m: m.group(0).replace('"data_date"', '"date"'),
                        sql,
                        flags=re.IGNORECASE
                    )
                    # 直接全局替换 "data_date" → "date"（无表上下文限制，防止漏网）
                    sql = re.sub(r'"data_date"', '"date"', sql, flags=re.IGNORECASE)

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

                    logger.info(">>> SQL生成成功 >>>")
                    logger.info("最终SQL: %s", sql)
                    logger.info("=" * 60)

                    # 生成后验证：发现臆造列名则触发重试
                    from app.core.dameng import validate_sql_columns
                    col_valid, col_err, invalid_list = validate_sql_columns(sql)
                    if not col_valid:
                        hint_suffix = (
                            f"\n\n【严重错误】你刚才生成的 SQL 包含了不存在的列名（臆造）："
                            f"{', '.join(invalid_list)}。"
                            f"请重新生成 SQL，严格只使用上方「数据库真实表结构」中列出的列名！"
                            f"如果不确定某个列是否存在，查阅表结构，不要臆造！"
                        )
                        logger.warning(f"SQL 生成后验证失败（attempt {attempt}）: {col_err}，将重试")
                        if attempt < 1:
                            # 第一次失败：带上提示重试
                            retry_hint = hint_suffix
                            continue
                        else:
                            # 第二次还失败：主动清理臆造列名后再返回
                            logger.warning("重试后仍含臆造列，主动清理后继续: %s", invalid_list)
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
                'lighting_area': frozenset({'area_id', 'area_code'}),
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
            "charge_person_name": "责任人", "process_time": "处理时间",
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
