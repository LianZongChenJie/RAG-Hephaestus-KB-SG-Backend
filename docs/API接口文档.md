# 首钢会展小镇智慧园区管理系统 - API 接口文档

> 基于 FastAPI + Ollama + 达梦数据库的智慧园区管理系统

---

## 一、项目概述

### 1.1 系统架构

- **后端框架**: FastAPI (Python 3.10+)
- **AI 模型**: Ollama (qwen9b-gpu-fast)
- **数据库**: 达梦数据库 (Dameng 08.00.000)
- **Schema**: FWBZ

### 1.2 接口分类

| 模块 | 前缀 | 说明 |
|------|------|------|
| 健康检查 | `/api/health` | 系统状态探测 |
| 聊天 | `/api/chat-stream` | AI 对话接口 |
| SQL 生成 | `/api` | SQL 语句生成与执行 |
| AI 报告 | `/api/ai-report` | 智能报告生成与查询 |

---

## 二、健康检查接口

### 2.1 系统健康检查

**接口地址**: `GET /api/health`

**功能说明**: 检查系统状态和 Ollama 服务连接情况。

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| ok | bool | 系统是否正常 |
| ollama | bool | Ollama 是否可用 |
| model | string | 使用的模型名称 |
| model_ready | bool | 模型是否就绪 |
| mode | string | 运行模式 |
| detail | string | 详细信息 |

**响应示例**:

```json
{
    "ok": true,
    "ollama": true,
    "model": "qwen9b-gpu-fast",
    "model_ready": true,
    "mode": "qwen9b-gpu-fast",
    "detail": "Ollama service is running"
}
```

---

## 三、聊天接口

### 3.1 流式对话

**接口地址**: `POST /api/chat-stream`

**功能说明**: 通过 SSE 流式返回 AI 对话响应。

**请求头**:

| 头名 | 说明 |
|------|------|
| Content-Type | application/json |

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| messages | array | 是 | 对话历史消息列表 |
| temperature | float | 否 | 温度参数（0.1-2.0），默认 0.7 |
| stream | bool | 否 | 是否流式返回，默认 true |

**messages 格式**:

```json
{
    "messages": [
        {
            "role": "user",
            "content": "你好"
        }
    ],
    "temperature": 0.6,
    "num_ctx": 2048
}
```

**响应格式**: Server-Sent Events (SSE) 流式响应

```
data: {"content": "你好"}
data: {"content": "！"}
data: {"content": "有什么"}
data: {"content": "我"}
data: {"content": "可以帮助"}
data: {"content": "你的"}
data: {"content": "吗"}
data: {"content": "？"}
data: {"content": "😊"}
data: {"done": true}
```

---

## 四、SQL 生成接口

### 4.1 自然语言生成 SQL

**接口地址**: `POST /api/generate-sql`

**功能说明**: 根据用户问题调用大模型生成 SQL 语句。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| question | string | 是 | 用户的问题 |
| history | array | 否 | 对话历史（用于理解上下文） |

**请求示例**:

```json
{
    "question": "查询1号馆最近一周的设备告警数量",
    "history": [
        {
            "role": "user",
            "content": "1号馆有哪些设备"
        }
    ]
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| sql | string | 生成的 SQL 语句 |
| explanation | string | SQL 语句的说明 |

**响应示例**:

```json
{
    "sql": "SELECT \n    COUNT(*) as alarm_count,\n    r.id as region_id,\n    r.name as region_name,\n    MIN(e.happen_time) as first_alarm_time,\n    MAX(e.happen_time) as last_alarm_time\nFROM \n    table_event_log e\nJOIN \n    table_region_resource r ON 1=1 -- 假设告警事件表中有区域ID字段，或者通过设备编码关联。\n                                -- 如果告警表中没有直接的区域ID，通常需要通过 src_parent_index (父设备) -> device_table -> region_path 进行多层级联。\nWHERE \n    e.happen_time >= DATE_SUB(NOW(), INTERVAL 7 DAY) -- 最近一周\n    AND r.name LIKE '%1号馆%'                         -- 匹配区域名称\nGROUP BY \n    r.id, r.name",
    "explanation": "为了查询\"1 号馆”最近一周的设备告警数量，我们需要关联以下几个表并执行聚合操作：\n\n1.  **区域定位**：在 `table_region_resource` 表中查找名称包含“1 号馆”的区域记录。由于该表有树形结构（通过 `region_path`），通常直接匹配 `name` 或遍历路径即可找到对应节点 ID (`id`)，然后利用其作为过滤条件关联下级资源或直接统计挂载在该区域下的告警事件。\n2.  **时间筛选**：在 `table_event_log` (假设表名为此，根据字段推断) 中筛选 `happen_time` 在最近一周内的记录。\n3.  **数据聚合**：按区域分组（或针对该特定区域）统计告警数量 (`COUNT(*)`)。\n\n*注：由于提供的 schema 中没有明确列出存储“设备告警原始日志”的主表名（通常此类系统会有 `table_event_log`、`device_alarm_record` 等），以下 SQL **假设**存在一张名为 `table_event_log` (或类似命名，如 `alarm_logs`) 的表来存储具体的事件记录。如果实际库中该表名称不同，请替换 `FROM table_event_log AS e` 部分。*\n\n```sql"
}
```

---

### 4.2 根据设备生成 SQL

**接口地址**: `POST /api/device/sql`

**功能说明**: 根据设备ID生成获取设备相关数据的SQL。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| device_id | int | 是 | 设备ID |
| question | string | 否 | 补充的问题描述 |

**请求示例**:

```json
{
    "device_id": 123,
    "question": "查询该设备的基本信息、告警记录和能耗数据"
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| device_id | int | 设备ID |
| question | string | 原始问题 |
| sql | string | 生成的 SQL |
| explanation | string | SQL 说明 |


**响应示例**:

```json
{
    "device_id": 123,
    "question": "查询该设备的基本信息、告警记录和能耗数据",
    "sql": "SELECT \n    e.id AS event_id,\n    e.event_type,\n    e.event_code,\n    e.happen_time,\n    e.src_parent_index AS device_code, -- 假设设备ID对应事件的父索引或需额外关联映射\n    e.timeout,\n    e.gmt_create,\n    r.name AS region_name,           -- 尝试通过区域资源表补充信息（若无直接设备表则无法获取完整基本信息）\n    r.catalog_type AS area_type\nFROM \n    table_event_history e\nLEFT JOIN \n    table_region_resource r ON e.src_parent_index = r.index_code OR (r.parent_external_index_code IS NOT NULL AND ... ) -- 此处关联逻辑因缺少明确的主从关系字段而存在不确定性，通常需设备表作为中间层\nWHERE \n    e.src_parent_index = '123'       -- 过滤条件：假设事件源父索引包含或等于设备ID（实际生产中通常需要 device_id -> src_parent_index 的映射表）\nUNION ALL\n-- 由于缺少能耗表和基础信息表的定义，此处无法生成有效查询。\nSELECT NULL AS dummy FROM DUAL;      -- 占位符表示缺失部分",
    "explanation": "由于提供的表结构定义中**未直接列出**存储“设备基本信息”、“告警记录”和“能耗数据”的具体表名及字段映射关系（例如通常这些功能可能分布在 `device_info`, `alarm_record`, `energy_data` 等表中，但当前上下文缺失），且仅提供了部分关联表（如事件、接口、区域资源）。\n\n基于现有信息中最接近的**告警/事件记录**是 `table_event_history`（通过 `src_parent_index` 或假设设备ID与父索引关联）和 `region_resource`（用于获取层级信息，但缺乏直接的设备基本信息表），无法生成包含所有三个维度的完整准确 SQL。\n\n若仅基于现有 Schema **尝试构建最合理的查询逻辑**（假设存在隐含的关联或通过区域资源反查，但这在标准SQL中通常不可行除非有中间设备表）：\n\n> **重要提示**：根据您提供的 `table_schema` 定义，缺少直接存储“设备基本信息”和“能耗数据”的表结构。以下 SQL 仅能查询到与事件相关的记录（假设 `device_id` 映射为 `src_parent_index`），并尝试关联区域信息。**若要完整回答您的问题，需要补充对应的设备基础表和能耗表的字段定义**。\n\n如果必须生成一条基于现有上下文的SQL（主要聚焦于**告警/事件**部分，因为这是唯一有明确定义的记录表）：\n\n\n\n**修正后的、更符合逻辑的回答（指出数据缺失并给出基于现有表的最佳尝试）**：\n\n鉴于提供的表结构中**没有直接名为“设备基本信息”或“能耗数据”的表**，且 `table_event_history` 中的 `src_parent_index` 描述为“事件发生的事件源父设备编码”，我们可以构建一个查询该设备的**告警/事件记录**。对于基本信息和能耗，由于缺乏对应表的定义（如 `device_info`, `energy_record`），SQL 无法完整执行。\n\n如果必须生成一条仅针对现有表结构的 SQL（假设用户主要关注事件记录）：\n\n```sql\nSELECT \n    e.id,\n    e.event_type AS event_name,\n    e.event_code,\n    e.happen_time AS alarm_time,\n    e.src_parent_index AS device_id, -- 映射设备ID\n    e.timeout,\n    e.gmt_create,\n    JSON_EXTRACT(e.event_data, '$.info') as extra_info \nFROM \n    table_event_history e\nWHERE \n    src_parent_index = '123'\nORDER BY \n    happen_time DESC;\n```\n\n**结论**：由于缺少“设备基本信息表”和“能耗数据表”的定义，无法生成包含这三部分数据的完整 SQL。上述查询仅能获取该设备的**告警/事件记录**。"
}
```

---

### 4.3 生成报告 SQL 列表

**接口地址**: `POST /api/generate-report-sql`

**功能说明**: 根据报告类型和目标名称，生成包含所有指标的SQL列表。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| report_type | enum | 是 | 报告类型：`device`/`venue`/`exhibition` |
| target_id | int | 否 | 目标ID（二选一，不传则根据 target_name 自动查找） |
| target_name | string | 否 | 目标名称（二选一，根据报告类型查对应表获取ID） |

> **传参规则**：
> - 只传 `target_name`：系统自动根据名称查找对应 ID
> - 两者都传：优先使用 `target_id`
> - `target_name` 为空时只支持精确 ID 查询

**请求示例**:

```json
{
    "report_type": "exhibition",
    "target_name": "智能制造博览会"
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_type | string | 报告类型 |
| target_id | int | 目标ID（自动解析后的结果） |
| target_name | string | 目标名称 |
| metrics | array | 指标SQL列表 |

**metrics 每项格式**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| name | string | 指标名称 |
| sql | string | 对应的 SQL 语句 |
| description | string | 指标说明 |

**响应示例**:

```json
{
    "report_type": "exhibition",
    "target_id": null,
    "target_name": "智能制造博览会",
    "metrics": [
        {
            "name": "展会基本信息",
            "sql": "SELECT * FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会' LIMIT 1",
            "description": "展会名称、开始日期、预计人数"
        },
        {
            "name": "总服务人次",
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会关联场馆在展会期间的进场总人次"
        },
        {
            "name": "投诉数量",
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"type_name\" = '投诉' LIMIT 1",
            "description": "展会期间投诉建议数量"
        },
        {
            "name": "建议数量",
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"type_name\" = '建议' LIMIT 1",
            "description": "展会期间建议数量"
        },
        {
            "name": "满意度评分",
            "sql": "SELECT AVG(\"value\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%满意%' LIMIT 1",
            "description": "参展商满意度评分"
        },
        {
            "name": "安保出勤",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%安保%' LIMIT 1",
            "description": "安保人员出勤人次"
        },
        {
            "name": "设备故障数",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_level_name\" LIKE '%故障%' LIMIT 1",
            "description": "展会期间设备故障告警数量"
        },
        {
            "name": "平均修复时长",
            "sql": "SELECT CASE WHEN COUNT(*) = 0 THEN 0 ELSE SUM((t1.\"process_time\" - t1.\"alarm_time\") * 24 * 60) / COUNT(*) END as result FROM FWBZ.\"alarm_record\" t1 WHERE t1.\"alarm_level_name\" LIKE '%故障%' AND t1.\"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')",
            "description": "故障平均修复时长(分钟)"
        },
        {
            "name": "总用电量",
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间计量点位能耗汇总(kWh)"
        },
        {
            "name": "能耗预算比",
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"data_day\" WHERE \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "实际用电量占预算比例(%)"
        },
        {
            "name": "单人次能耗",
            "sql": "SELECT CASE WHEN (SELECT SUM(t2.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t2 WHERE t2.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) = 0 THEN 0 ELSE (SELECT SUM(\"value\") FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) / (SELECT SUM(t3.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t3 WHERE t3.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t3.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t3.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) END as result FROM DUAL",
            "description": "人均用电量(kWh/人)"
        },
        {
            "name": "展会天数",
            "sql": "SELECT COUNT(*) as result FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会'",
            "description": "展会已举办天数（按名称过滤，取记录条数）"
        },
        {
            "name": "总客流",
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间累计进场人数"
        },
        {
            "name": "峰值客流",
            "sql": "SELECT MAX(\"max_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间单日最高进场人数"
        },
        {
            "name": "参展商数",
            "sql": "SELECT COUNT(DISTINCT \"charge_person_name\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%参展%' LIMIT 1",
            "description": "参展商数量"
        },
        {
            "name": "应急响应",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_level_name\" LIKE '%紧急%' LIMIT 1",
            "description": "应急事件响应次数"
        }
    ]
}
```

---

### 4.4 生成优化建议

**接口地址**: `POST /api/generate-suggestions`

**功能说明**: 根据报告数据调用大模型生成优化建议。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| report_type | enum | 是 | 报告类型：`device`/`venue`/`exhibition` |
| target_id | int | 否 | 目标ID |
| target_name | string | 否 | 目标名称 |
| metrics | array | 是 | 指标数据列表 |
| focus_areas | array | 否 | 重点关注领域 |

**metrics 每项格式**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| name | string | 指标名称 |
| value | any | 指标值（与 sql 二选一，优先使用 value） |
| sql | string | SQL 语句（与 value 二选一，后端自动执行查询获取值） |
| description | string | 指标说明 |

> **说明**：每个指标可以传入 `value`（已执行的结果）或 `sql`（后端自动执行）。两者都不传时，该指标值为空。

**请求示例（推荐：传 SQL，后端自动执行）**:

```json
{
    "report_type": "exhibition",
    "target_name": "智能制造博览会",
    "metrics": [
        {
            "name": "展会基本信息",
            "sql": "SELECT * FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会' LIMIT 1",
            "description": "展会名称、开始日期、预计人数"
        },
        {
            "name": "总服务人次",
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会关联场馆在展会期间的进场总人次"
        },
        {
            "name": "投诉数量",
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"type_name\" = '投诉' LIMIT 1",
            "description": "展会期间投诉建议数量"
        },
        {
            "name": "建议数量",
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"type_name\" = '建议' LIMIT 1",
            "description": "展会期间建议数量"
        },
        {
            "name": "满意度评分",
            "sql": "SELECT AVG(\"value\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%满意%' LIMIT 1",
            "description": "参展商满意度评分"
        },
        {
            "name": "安保出勤",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%安保%' LIMIT 1",
            "description": "安保人员出勤人次"
        },
        {
            "name": "设备故障数",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_level_name\" LIKE '%故障%' LIMIT 1",
            "description": "展会期间设备故障告警数量"
        },
        {
            "name": "平均修复时长",
            "sql": "SELECT CASE WHEN COUNT(*) = 0 THEN 0 ELSE SUM((t1.\"process_time\" - t1.\"alarm_time\") * 24 * 60) / COUNT(*) END as result FROM FWBZ.\"alarm_record\" t1 WHERE t1.\"alarm_level_name\" LIKE '%故障%' AND t1.\"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t1.\"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')",
            "description": "故障平均修复时长(分钟)"
        },
        {
            "name": "总用电量",
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间计量点位能耗汇总(kWh)"
        },
        {
            "name": "能耗预算比",
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"data_day\" WHERE \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "实际用电量占预算比例(%)"
        },
        {
            "name": "单人次能耗",
            "sql": "SELECT CASE WHEN (SELECT SUM(t2.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t2 WHERE t2.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t2.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) = 0 THEN 0 ELSE (SELECT SUM(\"value\") FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) / (SELECT SUM(t3.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t3 WHERE t3.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t3.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND t3.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会')) END as result FROM DUAL",
            "description": "人均用电量(kWh/人)"
        },
        {
            "name": "展会天数",
            "sql": "SELECT COUNT(*) as result FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会'",
            "description": "展会已举办天数（按名称过滤，取记录条数）"
        },
        {
            "name": "总客流",
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间累计进场人数"
        },
        {
            "name": "峰值客流",
            "sql": "SELECT MAX(\"max_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') LIMIT 1",
            "description": "展会期间单日最高进场人数"
        },
        {
            "name": "参展商数",
            "sql": "SELECT COUNT(DISTINCT \"charge_person_name\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_category_name\" LIKE '%参展%' LIMIT 1",
            "description": "参展商数量"
        },
        {
            "name": "应急响应",
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '智能制造博览会') AND \"alarm_level_name\" LIKE '%紧急%' LIMIT 1",
            "description": "应急事件响应次数"
        }
    ]
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_type | string | 报告类型 |
| target_id | int | 目标ID |
| suggestions | array | 建议列表 |

**suggestions 每项格式**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| title | string | 建议标题 |
| content | string | 建议内容 |
| impact | string | 预期效果 |
| category | string | 建议类别 |

**响应示例**:

```json
{
    "report_type": "exhibition",
    "target_id": null,
    "suggestions": [
        {
            "title": "数据分析建议",
            "content": "由于您提供的报告数据中，关键指标（如总服务人次、投诉数量、满意度评分、能耗预算比等）均为占位符或零值，无法直接计算具体的量化偏差。作为会展运营优化顾问，我将基于**智能制造博览会**的行业特性及智慧园区管理系统的通用逻辑，模拟出最可能出现的典型风险场景（如：高客流下的安保压力、设备故障响应延迟、能源浪费），并生成以下 3-5 条针对性的优化建议。\n\n```json\n[\n  {\n    \"title\": \"动态安保资源配置与峰值预警\",\n    \"content\": \"基于历史数据模拟，当单日峰值客流超过总服务人次的40%时（即进入高负荷状态），立即启动二级应急响应机制：1. 将静态巡逻岗调整为定点值守 + 流动巡查模式；2. 联动园区门禁系统，对非参展车辆实施自动拦截与分流引导；3. 在入口增设智能闸机预检通道。\",\n    \"impact\": \"预计降低安保响应时间至5分钟以内，减少因拥堵导致的投诉率10%，提升观众入场体验满意度8%。\",\n    \"category\": \"人员服务\"\n  },\n  {\n    \"title\": \"设备故障‘零等待’快速修复机制\",\n    \"content\": \"针对展会期间可能出现的照明或网络中断风险，建立分级维修预案：1. 核心区域（主展馆）配备2小时内可更换的备用模块；2. 非核心区故障启用移动应急发电车与临时布线方案；3. 将平均修复时长目标设定为<15分钟。\",\n    \"impact\": \"确保设备可用性达到99.8%，消除因设备停机导致的参展商中断运营风险，避免单次事故造成的潜在经济损失超2万元。\",\n    \"category\": \"会展运营\"\n  },\n  {\n    \"title\": “按需照明”智能能耗管控策略\",\n    \"content\": \"利用智慧园区管理系统实时监测各展位人流密度：1. 当某区域连续30分钟无人员活动时，自动调暗公共通道灯光至节能模式；2. 对未签约或撤展区域的空调与照明实施强制关闭逻辑；3. 设定能耗预算红线，一旦实际用电量超预算85%即触发预警。\",\n    \"impact\": \"预计降低整体展会期间总用电量15%-20%，单人次能耗下降0.05 kWh/人，直接节约能源成本约12%。\",\n    \"category\": \"设备能耗\"\n  },\n  {\n    \"title\": “服务前置”主动式客诉拦截计划\",\n    \"content\": \"改变被动等待投诉的模式：1. 在人流密集区（如餐饮、休息区）增设流动服务站，每30分钟进行一次满意度快速询问；2. 针对展会期间常见的Wi-Fi拥堵问题，提前部署5G专网分流方案并公示热点分布图；3. 建立“建议即奖励”机制，鼓励观众通过小程序提交改进意见。\",\n    \"impact\": \"将被动投诉数量降低60%，主动收集的建议转化率提升25%，整体参展商满意度评分目标提升至95分以上。\",\n    \"category\": \"人员服务\"\n  }\n]\n```",
            "impact": null,
            "category": "综合"
        }
    ]
}
```

---

### 4.5 执行 SQL 查询

**接口地址**: `POST /api/execute-sql`

**功能说明**: 执行 SQL 查询（仅支持 SELECT）。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| sql | string | 是 | SQL 语句（必须以 SELECT 开头） |
| params | array | 否 | SQL 参数 |

**请求示例**:

```json
{
    "sql": "SELECT * FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = ? LIMIT 1",
    "params": ["演唱会"]
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| columns | array | 列名列表 |
| rows | array | 数据行列表 |
| row_count | int | 行数 |
| execution_time | float | 执行时间（秒） |

**响应示例**:

```json
{
    "columns": [
        "id",
        "active_name",
        "venue_id",
        "venue_floors",
        "start_date",
        "start_time",
        "end_time",
        "people_quantity",
        "create_by",
        "create_time",
        "update_by",
        "sys_org_code",
        "update_time",
        "active_progress"
    ],
    "rows": [
        {
            "id": 13,
            "active_name": "演唱会",
            "venue_id": 1,
            "venue_floors": "4",
            "start_date": "2026-08-06",
            "start_time": "07:00:00",
            "end_time": "10:00:00",
            "people_quantity": 6000,
            "create_by": "fwbz_hz",
            "create_time": "2026-08-05T18:59:35.754000",
            "update_by": "fwbz_hz",
            "sys_org_code": null,
            "update_time": "2026-08-06T11:14:29.144000",
            "active_progress": 20.83
        }
    ],
    "row_count": 1,
    "execution_time": 0.14
}
```

---

### 4.6 会后报告接口

**接口地址**: `POST /api/report/full`

**功能说明**: 一站式生成完整会后报告接口（SQL生成 → 执行 → 建议生成）。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| report_type | enum | 是 | 报告类型：`device`/`venue`/`exhibition` |
| target_id | int | 否 | 目标ID（可选） |
| target_name | string | 否 | 目标名称（可用作筛选条件） |
| focus_areas | array | 否 | 重点关注领域 |

**请求示例**:

```json
{
    "report_type": "exhibition",
    "target_name": "演唱会",
    "focus_areas": ["人员服务", "设备能耗", "会展数据"]
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_type | string | 报告类型 |
| target_id | int | 目标ID |
| target_name | string | 目标名称 |
| data | array | 报告数据列表 |
| suggestions | array | 优化建议列表 |

**data 每项格式**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| name | string | 指标名称 |
| sql | string | 执行的 SQL |
| description | string | 指标说明 |
| columns | array | 列名列表 |
| rows | array | 数据行 |
| row_count | int | 行数 |

**响应示例**:

```json
{
    "report_type": "exhibition",
    "target_id": null,
    "target_name": "演唱会",
    "data": [
        {
            "name": "展会基本信息",
            "description": "展会名称、开始日期、预计人数",
            "category": "会展数据",
            "columns": [
                "id",
                "active_name",
                "venue_id",
                "venue_floors",
                "start_date",
                "start_time",
                "end_time",
                "people_quantity",
                "create_by",
                "create_time",
                "update_by",
                "sys_org_code",
                "update_time",
                "active_progress"
            ],
            "rows": [
                {
                    "id": 13,
                    "active_name": "演唱会",
                    "venue_id": 1,
                    "venue_floors": "4",
                    "start_date": "2026-08-06",
                    "start_time": "07:00:00",
                    "end_time": "10:00:00",
                    "people_quantity": 6000,
                    "create_by": "fwbz_hz",
                    "create_time": "2026-08-05T18:59:35.754000",
                    "update_by": "fwbz_hz",
                    "sys_org_code": null,
                    "update_time": "2026-08-06T11:14:29.144000",
                    "active_progress": 20.83
                }
            ],
            "row_count": 1,
            "sql": "SELECT * FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会' LIMIT 1"
        },
        {
            "name": "总服务人次",
            "description": "展会关联场馆在展会期间的进场总人次",
            "category": "人员服务",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') LIMIT 1"
        },
        {
            "name": "投诉数量",
            "description": "展会期间投诉建议数量",
            "category": "人员服务",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t2.\"type_name\" = '投诉' LIMIT 1"
        },
        {
            "name": "建议数量",
            "description": "展会期间建议数量",
            "category": "人员服务",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "sql": "SELECT COUNT(\"t1.id\") as result FROM FWBZ.\"table_complaint_info\" t1 JOIN FWBZ.\"table_complaint_type\" t2 ON t1.\"type_id\" = t2.\"id\" WHERE t1.\"complaint_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t1.\"complaint_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t2.\"type_name\" = '建议' LIMIT 1"
        },
        {
            "name": "满意度评分",
            "description": "参展商满意度评分",
            "category": "人员服务",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT AVG(\"value\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_category_name\" LIKE '%满意%' LIMIT 1"
        },
        {
            "name": "安保出勤",
            "description": "安保人员出勤人次",
            "category": "人员服务",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 0
                }
            ],
            "row_count": 1,
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_category_name\" LIKE '%安保%' LIMIT 1"
        },
        {
            "name": "设备故障数",
            "description": "展会期间设备故障告警数量",
            "category": "设备能耗",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 0
                }
            ],
            "row_count": 1,
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_level_name\" LIKE '%故障%' LIMIT 1"
        },
        {
            "name": "平均修复时长",
            "description": "故障平均修复时长(分钟)",
            "category": "设备能耗",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 0.0
                }
            ],
            "row_count": 1,
            "sql": "SELECT CASE WHEN COUNT(*) = 0 THEN 0 ELSE SUM((t1.\"process_time\" - t1.\"alarm_time\") * 24 * 60) / COUNT(*) END as result FROM FWBZ.\"alarm_record\" t1 WHERE t1.\"alarm_level_name\" LIKE '%故障%' AND t1.\"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t1.\"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会')"
        },
        {
            "name": "总用电量",
            "description": "展会期间计量点位能耗汇总(kWh)",
            "category": "设备能耗",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') LIMIT 1"
        },
        {
            "name": "能耗预算比",
            "description": "实际用电量占预算比例(%)",
            "category": "设备能耗",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT SUM(\"value\") as result FROM FWBZ.\"data_day\" WHERE \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') LIMIT 1"
        },
        {
            "name": "单人次能耗",
            "description": "人均用电量(kWh/人)",
            "category": "设备能耗",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT CASE WHEN (SELECT SUM(t2.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t2 WHERE t2.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t2.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t2.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会')) = 0 THEN 0 ELSE (SELECT SUM(\"value\") FROM FWBZ.\"metering_point_data_day\" WHERE \"metering_point_id\" = (SELECT \"config_value\" FROM FWBZ.\"business_config\" WHERE \"config_key\" = 'energyMetering:electric:pointId') AND \"time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会')) / (SELECT SUM(t3.\"today_in_count\") FROM FWBZ.\"table_venue_flow\" t3 WHERE t3.\"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t3.\"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND t3.\"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会')) END as result FROM DUAL"
        },
        {
            "name": "展会天数",
            "description": "展会已举办天数（按名称过滤，取记录条数）",
            "category": "会展数据",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 2
                }
            ],
            "row_count": 1,
            "sql": "SELECT COUNT(*) as result FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会'"
        },
        {
            "name": "总客流",
            "description": "展会期间累计进场人数",
            "category": "会展数据",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT SUM(\"today_in_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') LIMIT 1"
        },
        {
            "name": "峰值客流",
            "description": "展会期间单日最高进场人数",
            "category": "会展数据",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": null
                }
            ],
            "row_count": 1,
            "sql": "SELECT MAX(\"max_count\") as result FROM FWBZ.\"table_venue_flow\" WHERE \"venue_id\" = (SELECT \"venue_id\" FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"data_date\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') LIMIT 1"
        },
        {
            "name": "参展商数",
            "description": "参展商数量",
            "category": "会展数据",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 0
                }
            ],
            "row_count": 1,
            "sql": "SELECT COUNT(DISTINCT \"charge_person_name\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_category_name\" LIKE '%参展%' LIMIT 1"
        },
        {
            "name": "应急响应",
            "description": "应急事件响应次数",
            "category": "会展数据",
            "columns": [
                "result"
            ],
            "rows": [
                {
                    "result": 0
                }
            ],
            "row_count": 1,
            "sql": "SELECT COUNT(\"id\") as result FROM FWBZ.\"alarm_record\" WHERE \"alarm_time\" >= (SELECT MIN(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_time\" <= (SELECT MAX(\"start_date\") FROM FWBZ.\"table_activeMeet_info\" WHERE \"active_name\" = '演唱会') AND \"alarm_level_name\" LIKE '%紧急%' LIMIT 1"
        }
    ],
    "suggestions": [
        {
            "title": "紧急修复数据采集链路",
            "content": "立即排查智慧园区管理系统中演唱会项目的 API 接口状态，检查门禁闸机、能耗计量表及客流计数器的数据采集配置是否已正确绑定至当前活动 ID。同步核查后台日志，确认是否存在因网络波动导致的数据上传失败。若硬件正常但数据为0，需手动触发一次全量数据校准或临时启用离线采集模式并尽快补传历史数据。",
            "impact": "消除 100% 的数据盲区风险，确保后续所有运营决策基于真实客流与能耗数据进行；避免因数据缺失导致的预算超支误判（预计挽回潜在管理成本约 2-5 万元/场）。",
            "category": "会展数据"
        },
        {
            "title": "建立动态安保弹性调度机制",
            "content": "鉴于当前安保出勤为0且无投诉，需在演唱会高潮期（通常为首尾两天）实施‘潮汐式’排班。利用已修复的实时客流数据设定阈值：当单小时进场人数超过峰值预警线 20%时，系统自动触发增援指令；同时建立快速响应小组，针对设备故障或突发拥堵进行分钟级干预。",
            "impact": "将应急响应时间从平均 X 分钟缩短至<5 分钟内（量化目标）；预计降低无效人力成本15%，提升观众安全感评分至4.8分以上。",
            "category": "人员服务"
        },
        {
            "title": "实施分时段精准能耗管控策略",
            "content": "针对演唱会灯光音响高负荷特性，制定‘按需供能’方案：在客流低谷期（如散场后1小时）自动切断非核心区域照明与空调；利用修复后的单人次能耗数据建立基准线，对异常波动进行实时告警。引入智能逆变器技术，确保舞台设备供电稳定性同时减少待机损耗。",
            "impact": "预计降低整体场馆能耗12%-18%（对比传统全开模式）；在保障演出效果前提下，将单场活动电费支出控制在预算的95%以内。",
            "category": "设备能耗"
        },
        {
            "title": "构建零投诉服务闭环管理体系",
            "content": "虽然当前无数据，但需预设‘主动式’服务体系：在入场前通过小程序推送注意事项减少咨询；设置流动服务站快速处理观众临时需求（如充电宝、寻物）；建立设备故障<10分钟修复的 SLA 标准，确保演唱会期间零因设备问题引发的投诉。",
            "impact": "将潜在投诉率控制在0.5%以下；提升参展商与观众满意度评分至4.9分及以上，避免品牌声誉受损风险。",
            "category": "人员服务"
        }
    ]
}
```

---

## 五、AI 报告接口

### 5.1 AI运行报告

**接口地址**: `POST /api/ai-report/run`

**功能说明**: 基于 AI 对设备运行数据、告警数据、能耗数据进行深度分析。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| scope | string | 是 | 范围：`all`/`zone`/`device` |
| time_range | string | 是 | 时间：`day`/`week`/`month`/`quarter`/`year` |
| venue_name | string | 否 | 会展名称（筛选数据） |
| zone_name | string | 否 | 分区名称 |
| device_id | int | 否 | 设备ID |
| device_name | string | 否 | 设备名称 |

**请求示例**:

```json
{
    "scope": "all",
    "time_range": "week",
    "venue_name": "1号馆"
}
```

**响应参数**:

| 参数名          | 类型 | 说明        |
|--------------|------|-----------|
| report_id    | int | 报告ID      |
| report_title | string | 报告标题      |
| metrics      | array | 核心指标      |
| summary      | string | AI分析总结    |
| details      | array | 预留字段暂时没用到 |
| suggestions  | array | 优化建议      |

**响应示例**:

```json
{
    "report_id": 2,
    "report_title": "金安桥园区设备运行周报 - 2026年5月24日",
    "report_desc": "本报告基于金安桥园区（包含1-6号楼及相关附属区域）在当周的监测数据，重点分析了各楼栋的告警分布情况、空间层级结构及设备状态。分析范围覆盖从B1层至F4层的多个关键功能区域。",
    "scope": "all",
    "time_range": "week",
    "metrics": [
        {
            "value": "379",
            "label": "园区总告警数"
        },
        {
            "value": "金安桥4号楼B1 (128)",
            "label": "最高频告警楼栋及楼层"
        },
        {
            "value": "6",
            "label": "金安桥6号楼F1告警数"
        },
        {
            "value": "5",
            "label": "金安桥4号楼整体告警数"
        },
        {
            "value": "27",
            "label": "涉及空间层级总数 (B1/F1-F4/夹层等)"
        }
    ],
    "summary": "本周监测数据显示，园区设备运行总体平稳，但存在明显的局部异常集中现象。'金安桥4号楼B1'是告警最集中的区域，单点告警数高达128次，远超其他楼栋（如6号楼F1的6次、2号楼B1的1次），表明该区域可能存在系统性故障或环境干扰问题。此外，数据中记录了包括提升泵在内的多种设备类型，但当前告警分布主要集中在建筑本体空间而非特定单一设备点（除4号楼外）。需重点关注金安桥4号楼B1区域的排查工作，防止小范围故障演变为大面积停机风险。",
    "suggestions": [
        "立即组织技术团队对'金安桥4号楼B1'进行专项巡检，重点检查消防、安防及环境传感器是否存在批量误报或硬件损坏。",
        "针对告警频次较高的区域（如4号楼），建议增加该区域的设备冗余度或优化报警阈值设置，以区分真实故障与干扰信号。",
        "建立跨楼栋联动预警机制：鉴于2号楼和6号楼也有零星告警，需分析是否与4号楼存在关联影响（如电网波动、网络延迟等）。"
    ],
    "details": {}
}
```

---

### 5.2 AI预测报告

**接口地址**: `POST /api/ai-report/predict`

**功能说明**: 基于 AI 预测设备能耗趋势和关键参数变化。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| predict_type | string | 是 | 类型：`energy`/`device`/`all` |
| time_range | string | 是 | 预测时间范围 |
| venue_name | string | 否 | 会展名称 |
| device_id | int | 否 | 设备ID |
| device_name | string | 否 | 设备名称 |

**请求示例**:

```json
{
    "predict_type": "all",
    "time_range": "week",
    "venue_name": "演唱会"
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_id | int | 报告ID |
| predict_items | array | 预测项列表 |
| warning_items | array | 预警项列表 |
| summary | string | 预测分析总结 |


**响应示例**:

```json
{
    "report_id": 4,
    "report_title": "厂区用电空间能耗趋势预测与安全预警分析",
    "predict_items": [
        {
            "item_name": "除尘改造A3区用电 (1_2_143)",
            "predict_value": "+5.2%",
            "confidence": 0.85,
            "trend": "up",
            "description": "随着环保设备负荷增加及季节性粉尘处理需求上升，预计未来7天该区域用电量将呈上升趋势。"
        },
        {
            "item_name": "原料仓用电 (1_2_149)",
            "predict_value": "-0.5%",
            "confidence": 0.78,
            "trend": "down",
            "description": "受近期仓储作业节奏放缓及夜间照明控制策略优化影响，预计用电量将微幅下降并趋于稳定。"
        },
        {
            "item_name": "主电室用电 (1_2_85)",
            "predict_value": "+0.1%",
            "confidence": 0.92,
            "trend": "stable",
            "description": "作为核心供电枢纽，负荷波动极小，预计保持平稳运行状态。"
        },
        {
            "item_name": "提升泵站用电 (1_2_83)",
            "predict_value": "+3.5%",
            "confidence": 0.65,
            "trend": "up",
            "description": "受上游水源调度计划影响，预计未来一周泵组运行频率将增加，导致用电量上升。"
        }
    ],
    "warning_items": [
        {
            "device_name": "N4-2用电 (1_2_82)",
            "warning_type": "负荷过载风险",
            "warning_content": "检测到该区域连续3小时电流负载率超过额定值的95%，存在跳闸隐患。",
            "confidence": 0.88,
            "suggest_time": "建议在今日14:00前完成线路巡检或负载均衡调整"
        },
        {
            "device_name": "备件库用电 (1_2_90)",
            "warning_type": "异常波动",
            "warning_content": "夜间非作业时段出现不明原因的小幅电流脉冲，疑似设备漏电或控制回路干扰。",
            "confidence": 0.72,
            "suggest_time": "建议于明日早班前进行绝缘电阻测试"
        }
    ],
    "summary": "整体来看，厂区用电空间呈现“核心稳定、边缘波动”的特征。除尘与泵站区域受生产计划影响负荷上升明显，需重点关注其供电线路的温升情况；原料仓及主电室运行平稳。目前发现N4-2存在过载风险，建议优先处理以避免非计划停机。",
    "suggestions": [
        "立即对N4-2用电回路进行负载重新分配或扩容检查。",
        "针对除尘改造A3区提前储备备用电源模块以应对峰值负荷。",
        "优化提升泵站的启停控制逻辑，避免频繁启动造成的能耗激增。"
    ]
}
```

---

### 5.3 AI节能报告

**接口地址**: `POST /api/ai-report/energy`

**功能说明**: 基于 AI 分析用能数据，量化节能效果。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| time_range | string | 是 | 时间范围 |
| venue_name | string | 否 | 会展名称 |
| zone_name | string | 否 | 分区名称 |

**请求示例**:

```json
{
    "time_range": "month",
    "venue_name": "演唱会"
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_id | int | 报告ID |
| metrics | array | 核心指标 |
| strategy_items | array | 策略效果列表 |
| summary | string | 节能分析总结 |


**响应示例**:

```json
{
    "report_id": 2,
    "report_title": "金安桥园区设备运行周报 - 2026年5月24日",
    "report_desc": "本报告基于金安桥园区（包含1-6号楼及相关附属区域）在当周的监测数据，重点分析了各楼栋的告警分布情况、空间层级结构及设备状态。分析范围覆盖从B1层至F4层的多个关键功能区域。",
    "scope": "all",
    "time_range": "week",
    "metrics": [
        {
            "value": "379",
            "label": "园区总告警数"
        },
        {
            "value": "金安桥4号楼B1 (128)",
            "label": "最高频告警楼栋及楼层"
        },
        {
            "value": "6",
            "label": "金安桥6号楼F1告警数"
        },
        {
            "value": "5",
            "label": "金安桥4号楼整体告警数"
        },
        {
            "value": "27",
            "label": "涉及空间层级总数 (B1/F1-F4/夹层等)"
        }
    ],
    "summary": "本周监测数据显示，园区设备运行总体平稳，但存在明显的局部异常集中现象。'金安桥4号楼B1'是告警最集中的区域，单点告警数高达128次，远超其他楼栋（如6号楼F1的6次、2号楼B1的1次），表明该区域可能存在系统性故障或环境干扰问题。此外，数据中记录了包括提升泵在内的多种设备类型，但当前告警分布主要集中在建筑本体空间而非特定单一设备点（除4号楼外）。需重点关注金安桥4号楼B1区域的排查工作，防止小范围故障演变为大面积停机风险。",
    "suggestions": [
        "立即组织技术团队对'金安桥4号楼B1'进行专项巡检，重点检查消防、安防及环境传感器是否存在批量误报或硬件损坏。",
        "针对告警频次较高的区域（如4号楼），建议增加该区域的设备冗余度或优化报警阈值设置，以区分真实故障与干扰信号。",
        "建立跨楼栋联动预警机制：鉴于2号楼和6号楼也有零星告警，需分析是否与4号楼存在关联影响（如电网波动、网络延迟等）。"
    ],
    "details": {}
}
```

---

### 5.4 AI故障分析报告

**接口地址**: `POST /api/ai-report/fault`

**功能说明**: 基于 AI 分析设备故障数据，识别故障规律。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| time_range | string | 是 | 时间范围 |
| venue_name | string | 否 | 会展名称 |
| device_id | int | 否 | 设备ID |
| device_name | string | 否 | 设备名称 |
| zone_name | string | 否 | 分区名称 |

**请求示例**:

```json
{
    "time_range": "month",
    "venue_name": "1号馆"
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_id | int | 报告ID |
| metrics | array | 核心指标 |
| fault_distribution | array | 故障分布 |
| summary | string | 故障分析总结 |

**响应示例**:

```json
{
    "report_id": 2,
    "report_title": "金安桥园区设备运行周报 - 2026年5月24日",
    "report_desc": "本报告基于金安桥园区（包含1-6号楼及相关附属区域）在当周的监测数据，重点分析了各楼栋的告警分布情况、空间层级结构及设备状态。分析范围覆盖从B1层至F4层的多个关键功能区域。",
    "scope": "all",
    "time_range": "week",
    "metrics": [
        {
            "value": "379",
            "label": "园区总告警数"
        },
        {
            "value": "金安桥4号楼B1 (128)",
            "label": "最高频告警楼栋及楼层"
        },
        {
            "value": "6",
            "label": "金安桥6号楼F1告警数"
        },
        {
            "value": "5",
            "label": "金安桥4号楼整体告警数"
        },
        {
            "value": "27",
            "label": "涉及空间层级总数 (B1/F1-F4/夹层等)"
        }
    ],
    "summary": "本周监测数据显示，园区设备运行总体平稳，但存在明显的局部异常集中现象。'金安桥4号楼B1'是告警最集中的区域，单点告警数高达128次，远超其他楼栋（如6号楼F1的6次、2号楼B1的1次），表明该区域可能存在系统性故障或环境干扰问题。此外，数据中记录了包括提升泵在内的多种设备类型，但当前告警分布主要集中在建筑本体空间而非特定单一设备点（除4号楼外）。需重点关注金安桥4号楼B1区域的排查工作，防止小范围故障演变为大面积停机风险。",
    "suggestions": [
        "立即组织技术团队对'金安桥4号楼B1'进行专项巡检，重点检查消防、安防及环境传感器是否存在批量误报或硬件损坏。",
        "针对告警频次较高的区域（如4号楼），建议增加该区域的设备冗余度或优化报警阈值设置，以区分真实故障与干扰信号。",
        "建立跨楼栋联动预警机制：鉴于2号楼和6号楼也有零星告警，需分析是否与4号楼存在关联影响（如电网波动、网络延迟等）。"
    ],
    "details": {}
}
```

---

### 5.5 查询报告列表

**接口地址**: `GET /api/ai-report/history`

**查询参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 10 |
| report_type | string | 否 | 报告类型 |
| time_range | string | 否 | 时间范围 |
| target_name | string | 否 | 目标名称搜索 |
| start_date | string | 否 | 开始日期 YYYY-MM-DD |
| end_date | string | 否 | 结束日期 YYYY-MM-DD |

**请求示例**:

```
GET /api/ai-report/history?page=1&page_size=10&report_type=run
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| items | array | 报告列表 |
| total | int | 总数 |
| page | int | 当前页 |
| page_size | int | 每页数量 |
| total_pages | int | 总页数 |

**响应示例**:

```json
{
    "items": [
        {
            "id": 2,
            "report_type": "run",
            "title": "金安桥园区设备运行周报 - 2026年5月24日",
            "time_range": "week",
            "target_id": null,
            "target_name": null,
            "scope": "all",
            "summary": "本周监测数据显示，园区设备运行总体平稳，但存在明显的局部异常集中现象。'金安桥4号楼B1'是告警最集中的区域，单点告警数高达128次，远超其他楼栋（如6号楼F1的6次、2号楼B1的1次），表明该区域可能存在系统性故障或环境干扰问题。此外，数据中记录了包括提升泵在内的多种设备类型，但当前告警分布主要集中在建筑本体空间而非特定单一设备点（除4号楼外）。需重点关注金安桥4号楼B1区域的排查工作，防止小范围故障演变为大面积停机风险。",
            "created_at": "2026-08-07T15:14:43.648000"
        },
        {
            "id": 1,
            "report_type": "run",
            "title": "园区设备运行综合分析报告",
            "time_range": "week",
            "target_id": null,
            "target_name": null,
            "scope": "all",
            "summary": "报告生成中，请稍后查看详细数据",
            "created_at": "2026-08-07T15:11:47.486000"
        }
    ],
    "total": 2,
    "page": 1,
    "page_size": 10,
    "total_pages": 1
}
```

---

### 5.6 获取报告详情

**接口地址**: `GET /api/ai-report/history/{report_id}`

**路径参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| report_id | int | 是 | 报告ID |

**请求示例**:

```
GET /api/ai-report/history/1
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| id | int | 报告ID |
| report_type | string | 报告类型：run/predict/energy/fault |
| title | string | 报告标题 |
| time_range | string | 时间范围：day/week/month/quarter/year |
| target_id | int/null | 目标ID |
| target_name | string/null | 目标名称 |
| scope | string | 报告范围 |
| summary | string | 报告摘要 |
| content | string | 报告完整内容（JSON字符串） |
| query_params | object | 查询参数 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |

**响应示例**:

```json
{
    "id": 1,
    "report_type": "run",
    "title": "园区设备运行综合分析报告",
    "time_range": "week",
    "target_id": null,
    "target_name": null,
    "scope": "all",
    "summary": "报告生成中，请稍后查看详细数据",
    "content": "{\"report_title\": \"园区设备运行综合分析报告\", \"report_desc\": \"基于真实数据的设备运行分析\", \"metrics\": [], \"summary\": \"报告生成中，请稍后查看详细数据\", \"suggestions\": []}",
    "query_params": {
        "scope": "all",
        "time_range": "week",
        "venue_name": "演唱会",
        "start_date": "2026-07-31",
        "end_date": "2026-08-07",
        "zone_name": null,
        "device_id": null,
        "device_name": null
    },
    "created_at": "2026-08-07T15:11:47.486000",
    "updated_at": "2026-08-07T15:11:47.486000"
}
```

---

### 5.7 获取报告统计

**接口地址**: `GET /api/ai-report/stats`

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| total_count | int | 报告总数 |
| by_type | object | 按类型统计 |
| by_time_range | object | 按时长统计 |
| recent_count | int | 最近7天数量 |

**响应示例**:

```json
{
    "total_count": 15,
    "by_type": {
        "energy": 11,
        "predict": 2,
        "run": 2
    },
    "by_time_range": {
        "month": 11,
        "week": 4
    },
    "recent_count": 15
}
```


---

### 5.8 删除报告

**接口地址**: `DELETE /api/ai-report/history/{report_id}`

**路径参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| report_id | int | 是 | 报告ID |

**请求示例**:

```
DELETE /api/ai-report/history/1
```

**响应示例**:

```json
{
    "message": "报告删除成功",
    "id": 15
}
```

---

### 5.9 获取会展列表

**接口地址**: `GET /api/ai-report/venues`

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| items | array | 会展列表 |
| total | int | 总数 |

**响应示例**:

```json
{
    "items": [
        {
            "id": 1,
            "venue_name": "1号馆",
            "location": "首钢产业园",
            "orientation": "东西",
            "area": "1500",
            "floors": 4
        },
        {
            "id": 2,
            "venue_name": "2号馆",
            "location": "园区北部",
            "orientation": "南北",
            "area": "1000",
            "floors": 4
        },
        {
            "id": 3,
            "venue_name": "3号馆",
            "location": "一高炉",
            "orientation": "坐北朝南",
            "area": "2500",
            "floors": 12
        },
        {
            "id": 4,
            "venue_name": "4号馆",
            "location": "金安桥",
            "orientation": "南",
            "area": "34",
            "floors": 4
        }
    ],
    "total": 4
}
```

---

## 六、错误码说明

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 无法连接 Ollama |
| 504 | Ollama 响应超时 |

**常见错误响应**:

```json
{
    "detail": "无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用"
}
```

```json
{
    "detail": "只支持 SELECT 查询，禁止 INSERT/UPDATE/DELETE 等操作"
}
```

---

## 七、数据库说明

### 7.1 主要数据表

| 表名 | 说明 |
|------|------|
| `device` | 设备基础信息 |
| `alarm_record` | 告警记录 |
| `data_day` | 日能耗数据 |
| `table_venue_info` | 会展场馆信息 |
| `table_venue_flow` | 场馆客流统计 |
| `table_personnel_statistics` | 人员统计 |
| `table_complaint_info` | 投诉建议 |
| `metering_point` | 计量点配置 |
| `metering_point_data_day` | 计量点数据 |
| `energy_price` | 能源价格 |
| `energy_pricing_config` | 分时电价配置 |
| `carbon_emission_factor` | 碳排放因子 |
| `ai_report_history` | AI报告历史 |

### 7.2 关联关系

```
table_venue_info.id
    ↓
device.venue_id
    ↓
alarm_record.device_id
data_day.device_id
device_attribute_history.device_id
```

---

## 八、调用示例

### 8.1 使用 curl

```bash
# 健康检查
curl -X GET "http://localhost:8000/api/health"

# 生成运行报告
curl -X POST "http://localhost:8000/api/ai-report/run" \
  -H "Content-Type: application/json" \
  -d '{"scope": "all", "time_range": "week", "venue_name": "1号馆"}'

# 获取会展列表
curl -X GET "http://localhost:8000/api/ai-report/venues"

# 生成完整报告
curl -X POST "http://localhost:8000/api/report/full" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "exhibition", "target_name": "智能制造博览会"}'

# 执行SQL
curl -X POST "http://localhost:8000/api/execute-sql" \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT COUNT(*) FROM \"FWBZ\".\"device\""}'
```

### 8.2 使用 Python

```python
import requests

# 生成运行报告
response = requests.post(
    "http://localhost:8000/api/ai-report/run",
    json={
        "scope": "all",
        "time_range": "week",
        "venue_name": "1号馆"
    }
)
print(response.json())
```

---

## 九、更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0 | 2026-08-07 | 初始版本，支持 SQL 生成、报告生成、聊天接口 |
| v1.1 | 2026-08-07 | AI报告支持会展名称筛选 |
| v1.2 | 2026-08-07 | AI报告自动保存到数据库 |

---

> 文档生成时间: 2026-08-07
> 更多信息请访问项目仓库
