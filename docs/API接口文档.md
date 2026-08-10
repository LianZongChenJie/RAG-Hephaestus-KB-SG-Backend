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

## 三、聊天接口（智能数据问答）

### 3.1 流式对话

**接口地址**: `POST /api/chat-stream`

**功能说明**: 支持智能数据问答的流式对话接口。系统自动判断用户问题是否与达梦数据库相关：
- **数据库相关问题**（含关键词：设备、告警、能耗、碳排放、场馆、客流、停车、照明、统计等）→ 生成 SQL 查询 → 返回 ECharts 图表 + Vue 表格 + 总结
- **非数据库相关问题**（闲聊、知识问答等）→ 直接流式 LLM 回答

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
| num_ctx | int | 否 | 上下文窗口大小，默认 2048 |

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

**响应格式**: Server-Sent Events (SSE) 流式响应，每行以 `data: ` 开头

#### 数据库相关问题 SSE 事件流（7类事件）

| 事件类型 | 触发时机 | 说明 |
|---------|---------|------|
| `mode` | 开始检测 | 告知当前处理阶段 |
| `sql` | SQL 生成后 | 返回生成的 SQL 语句 |
| `table` | 数据查询后 | 返回 Vue 表格结构 |
| `chart` | 图表生成后 | 返回 ECharts 图表配置 |
| `summary` | 总结生成后 | 返回 ≤200 字分析总结 |
| `error` | 出错时 | 返回错误信息 |
| `done` | 结束时 | 标识流式响应结束 |

**SSE 响应示例**（数据库相关问题）:

```
data: {"type": "mode", "value": "detecting"}

data: {"type": "mode", "value": "db", "message": "正在分析数据库..."}

data: {"type": "sql", "sql": "SELECT \"venue_name\", \"location\", \"area\", \"floors\" FROM FWBZ.\"table_venue_info\" ORDER BY \"id\" LIMIT 100;"}

data: {"type": "mode", "value": "db", "message": "正在执行查询..."}

data: {"type": "table", "columns": [{"key": "venue_name", "label": "场馆名称", "width": "auto"}, {"key": "location", "label": "位置", "width": "auto"}, {"key": "area", "label": "面积", "width": "auto"}, {"key": "floors", "label": "Floors", "width": "auto"}], "rows": [{"venue_name": "1号馆", "location": "首钢产业园", "area": "1500", "floors": 4}, {"venue_name": "2号馆", "location": "园区北部", "area": "1000", "floors": 4}, {"venue_name": "3号馆", "location": "一高炉", "area": "2500", "floors": 12}, {"venue_name": "4号馆", "location": "金安桥", "area": "34", "floors": 4}]}

data: {"type": "chart", "chartType": "pie", "chartId": "chart_104132670458", "option": {"title": {"text": "我想知道演唱会会展的具体信息 Floors分布", "left": "center"}, "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"}, "legend": {"bottom": 10, "left": "center"}, "series": [{"type": "pie", "radius": ["35%", "60%"], "avoidLabelOverlap": false, "itemStyle": {"borderRadius": 6, "borderColor": "#fff", "borderWidth": 2}, "label": {"show": true, "formatter": "{b}\n{c} ({d}%)"}, "data": [{"name": "1号馆", "value": 4.0}, {"name": "2号馆", "value": 4.0}, {"name": "3号馆", "value": 12.0}, {"name": "4号馆", "value": 4.0}]}]}}

data: {"type": "mode", "value": "db", "message": "正在生成分析总结..."}

data: {"type": "summary", "content": "本次演唱会将在首钢产业园内举行，共涉及四个场馆：1 号馆位于园区中部，面积 1500 平方米；2 号馆在北部区域，面积为 1000 平方米；3 号馆设在一高炉位置，面积达 2500 平方米且楼层数最多为 12 层；4 号馆位于金安桥附近，面积最小仅 34 平方米。各场馆规模差异显著，其中一高炉场地最为宏大，适合大型演出活动。"}

data: {"done": true}
```

**SSE 响应示例**（非数据库问题）:

```
data: {"type": "message", "content": "您好！"}
data: {"type": "message", "content": "我是"}
data: {"type": "message", "content": "Hephaestus"}
data: {"type": "message", "content": "智能助手"}
...
data: {"done": true}
```

#### 各事件字段说明

**mode 事件**
```json
{"type": "mode", "value": "detecting" | "db" | "llm", "message": "当前状态描述"}
```

**sql 事件**
```json
{"type": "sql", "sql": "SELECT ..."}
```

**table 事件（Vue 表格结构）**
```json
{
  "type": "table",
  "columns": [
    {"key": "date", "label": "日期", "width": "auto"},
    {"key": "today_entry_count", "label": "入场数量(总和)", "width": "auto"}
  ],
  "rows": [
    {"date": "2026-08-07", "today_entry_count": 3377},
    {"date": "2026-08-06", "today_entry_count": 5233}
  ]
}
```
> 说明：key 为英文字段名，label 为中文标签。id/bigint 列自动排除，聚合列自动添加后缀（总和/平均值/计数）。

**chart 事件（ECharts 配置）**
```json
{
  "type": "chart",
  "chartType": "bar" | "pie",
  "chartId": "chart_103045123456",
  "option": {
    "title": {"text": "停车记录 入场数量分布"},
    "series": [{"type": "bar" | "pie", "data": [...]}]
  }
}
```
> 说明：数据量 ≤6 条自动选择饼图（pie），>6 条自动选择柱状图（bar）。

**summary 事件**
```json
{"type": "summary", "content": "分析总结内容（≤200字）..."}
```

**error 事件**
```json
{"type": "error", "message": "错误描述"}
```

**done 事件**
```json
{"done": true}
```

#### 支持的数据库相关问题类型

| 类别 | 关键词示例 | 查询表 |
|------|-----------|--------|
| 设备统计 | 设备、离线、在线、运行状态、设备数量 | device, equipment_category |
| 告警分析 | 告警、报警、故障、停机、异常 | alarm_record |
| 能耗统计 | 能耗、电耗、水耗、用电、用能 | data_day, data_hour, metering_point_data_day |
| 碳排放 | 碳排放、碳强度、碳核算 | data_day + carbon_emission_factor |
| 场馆信息 | 场馆、场馆信息、会展、展厅 | table_venue_info |
| 空间分布 | 空间、区域、楼层、建筑 | space |
| 客流数据 | 客流、人流量、入场、出场、访客 | table_venue_flow |
| 人员统计 | 人员统计、入场人数 | table_personnel_statistics |
| 停车数据 | 停车、车位、车辆、停车场 | table_parking_count |
| 照明管理 | 照明、灯光、回路 | lighting_area, lighting_circuit |
| 计量分析 | 计量点、分时用电、峰谷 | metering_point, metering_point_data_day |
| AI 报告 | 报告、AI报告、历史报表 | ai_report_history |

---

## 四、SQL 生成接口

### 4.1 自然语言生成 SQL（已废弃）

> ⚠️ 此接口已废弃，功能已整合至 `/api/chat-stream`，请使用聊天接口。

**接口地址**: `POST /api/generate-sql`

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

**响应示例**:

```json
{
    "sql": "SELECT COUNT(*) as alarm_count FROM FWBZ.\"alarm_record\" ar JOIN FWBZ.\"device\" d ON ar.\"device_id\" = d.\"id\" JOIN FWBZ.\"table_venue_info\" vi ON d.\"venue_id\" = vi.\"id\" WHERE vi.\"venue_name\" LIKE '%1号馆%' AND ar.\"alarm_time\" >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
    "explanation": "查询 1 号馆最近一周的设备告警数量"
}
```

---

### 4.2 根据设备生成 SQL（已废弃）

> ⚠️ 此接口已废弃，功能已整合至 `/api/chat-stream`。

**接口地址**: `POST /api/device/sql`

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
    "venue_name": "演唱会"
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
    "report_id": 18,
    "report_title": "金安桥园区设备运行周报 - 2026年5月24日",
    "report_desc": "本周金安桥园区共监测到13个空间节点，其中B1层及F1层报警频次较高。整体系统运行平稳，需重点关注老旧楼栋的消防与安防预警机制优化。",
    "scope": "all",
    "time_range": "week",
    "metrics": [
        {
            "value": "4.08%",
            "label": "平均告警率"
        },
        {
            "value": "534",
            "label": "总告警次数"
        }
    ],
    "summary": "本周园区整体运行平稳，但金安桥4号楼B1层（510次）及6号楼F1层（24次）告警异常突出。建议优先排查这两处区域的传感器灵敏度与误报源，同时优化夜间巡检策略以快速响应潜在风险。",
    "suggestions": [
        "立即对金安桥4号楼B1层的报警系统进行专项诊断，排除设备老化或环境干扰导致的频繁误报。",
        "加强6号楼F1层及2号楼相关区域的实时监控频次，确保突发状况能在5分钟内响应处置。"
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
    "report_id": 19,
    "report_title": "能源系统运行趋势预测报告",
    "predict_items": [
        {
            "item_name": "主电室用电负荷",
            "predict_value": "预计明日峰值将上升约5%",
            "confidence": 0.82,
            "trend": "up",
            "description": "基于近7日生产计划增加，预测未来24小时总用电量呈上升趋势。"
        },
        {
            "item_name": "除尘改造A3区能耗",
            "predict_value": "维持当前水平波动±1%",
            "confidence": 0.95,
            "trend": "stable",
            "description": "设备已完成改造，运行效率稳定，预测未来一周无明显变化。"
        },
        {
            "item_name": "原料仓用电总量",
            "predict_value": "预计环比下降3%",
            "confidence": 0.78,
            "trend": "down",
            "description": "受季节性因素影响，仓储作业频率降低，预测用电量将小幅回落。"
        }
    ],
    "warning_items": [
        {
            "device_name": "N4-2用电系统",
            "warning_type": "电压波动预警",
            "warning_content": "检测到连续3次瞬时电压跌落，存在设备跳闸风险。",
            "confidence": 0.89,
            "suggest_time": "1小时内"
        },
        {
            "device_name": "提升泵站用电",
            "warning_type": "能耗异常预警",
            "warning_content": "单位水量耗电量超出阈值20%，可能预示泵体效率下降。",
            "confidence": 0.85,
            "suggest_time": "4小时内"
        },
        {
            "device_name": "N4-3水 F1系统",
            "warning_type": "水位监测预警",
            "warning_content": "F1区域水位持续高位，需警惕溢流风险。",
            "confidence": 0.92,
            "suggest_time": "立即处理"
        }
    ],
    "summary": "整体能源消耗平稳，主电室负荷将小幅上升。N4-2电压波动及提升泵站能效异常需重点关注，建议优先排查隐患。",
    "suggestions": [
        "加强对N4-2系统的稳压设备巡检频率至每2小时一次。",
        "安排技术人员对提升泵进行效率检测与清洗维护。",
        "启动F1区域排水应急预案，确保水位安全。"
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
    "report_id": null,
    "report_title": "AI 节能效果分析报告 - 2026年5月",
    "report_desc": "基于真实能耗数据，分析峰平谷用电策略及阶梯水费优化成效。报告涵盖关键指标、实施策略总结及后续改进建议，旨在提升能源利用效率并降低运营成本。",
    "metrics": [
        {
            "value": "1250.5 kWh",
            "label": "总用电量"
        },
        {
            "value": "896.2 m³",
            "label": "总用水量"
        },
        {
            "value": "3450.0 CNY",
            "label": "能源总费用"
        }
    ],
    "strategy_items": [
        {
            "strategy_name": "峰谷电价套利优化策略",
            "implement_date": "2026-01-15",
            "before_daily": "48.5 kWh",
            "after_daily": "32.1 kWh",
            "daily_saving": "16.4 kWh",
            "saving_rate": "33.8%",
            "total_saving": "5079.0 CNY",
            "status": "执行中"
        },
        {
            "strategy_name": "非高峰时段设备调度策略",
            "implement_date": "2026-02-10",
            "before_daily": "38.2 kWh",
            "after_daily": "25.8 kWh",
            "daily_saving": "12.4 kWh",
            "saving_rate": "32.5%",
            "total_saving": "3960.0 CNY",
            "status": "执行中"
        },
        {
            "strategy_name": "阶梯水费临界点控制策略",
            "implement_date": "2026-03-05",
            "before_daily": "18.5 m³",
            "after_daily": "14.2 m³",
            "daily_saving": "4.3 m³",
            "saving_rate": "23.2%",
            "total_saving": "260.0 CNY",
            "status": "已完成"
        }
    ],
    "summary": "通过实施峰谷套利、设备错峰调度及水费阶梯控制三大策略，本月累计节约能源费用约 9839 元。整体节能率达 31%，有效降低了运营成本并提升了电网响应能力。",
    "suggestions": [
        "持续监控高耗能时段负荷变化，动态调整生产计划以进一步挖掘峰谷价差红利。",
        "引入更精准的用水预测模型，确保用水量稳定控制在阶梯临界点以下。"
    ]
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
    "venue_name": "演唱会"
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
    "report_id": 23,
    "report_title": "设备故障智能分析报告 - 2026年7月",
    "report_desc": "基于真实数据生成，聚焦高频故障点位与处理效率，为运维决策提供精准支撑。",
    "metrics": [
        {
            "value": "1871",
            "label": "总故障数"
        },
        {
            "value": "20%",
            "label": "待处理占比"
        }
    ],
    "fault_distribution": [
        {
            "category": "供水系统",
            "count": 45,
            "percentage": 63.9
        },
        {
            "category": "回水系统",
            "count": 18,
            "percentage": 25.7
        },
        {
            "category": "末端压力监测",
            "count": 0,
            "percentage": 0.0
        }
    ],
    "fault_items": [
        {
            "device_name": "N4-2回水",
            "fault_type": "水压异常",
            "fault_time": "2026-07-15T08:30:00Z",
            "duration": "2h 15m",
            "cause": "阀门卡滞导致回流受阻",
            "solution": "更换密封圈并润滑阀芯"
        },
        {
            "device_name": "提升泵站回水",
            "fault_type": "电机过载",
            "fault_time": "2026-07-18T14:20:00Z",
            "duration": "3h 5m",
            "cause": "叶轮缠绕异物引发负载激增",
            "solution": "清理杂物并校准电机参数"
        },
        {
            "device_name": "N3-4/N4-3/N4-4供水",
            "fault_type": "流量不足",
            "fault_time": "2026-07-19T09:15:00Z",
            "duration": "1h 45m",
            "cause": "管道局部堵塞",
            "solution": "疏通管网并加装过滤网"
        },
        {
            "device_name": "N3-4/N4-3/N4-4回水",
            "fault_type": "温度超标",
            "fault_time": "2026-07-21T11:05:00Z",
            "duration": "4h 20m",
            "cause": "冷却系统效率下降",
            "solution": "清洗换热器并补充防冻液"
        },
        {
            "device_name": "6号楼末端给水压力",
            "fault_type": "低压报警",
            "fault_time": "2026-07-23T16:45:00Z",
            "duration": "0h 58m",
            "cause": "主泵启停频繁导致波动",
            "solution": "优化控制策略并加装稳压罐"
        }
    ],
    "summary": "本月共发生1871起故障，供水系统占比最高。主要原因为设备老化与异物堵塞，已制定针对性维保计划以降低复发率。",
    "suggestions": [
        "对高频故障设备进行预防性更换关键部件",
        "加强回水系统的定期清洗与维护"
    ]
}
```

---

### 5.5 多模态能碳计算报告

**接口地址**: `POST /api/ai-report/carbon`

**功能说明**: 基于 AI 对电、水、气、热四类能源的实时计量数据进行分析，融合物理机理模型与机器学习算法，对园区能碳排放进行多维度精准核算。

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| time_range | string | 是 | 时间范围 |
| venue_name | string | 否 | 会展名称 |
| zone_name | string | 否 | 分区名称 |

**time_range 可选值**:

| 值 | 说明 |
|----|------|
| day | 日报 |
| week | 周报 |
| month | 月报 |
| quarter | 季度报告 |
| year | 年度报告 |

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
| report_title | string | 报告标题 |
| report_desc | string | 报告描述 |
| energy_type_count | int | 监测能源类型数量 |
| today_carbon | float | 今日碳排放(吨CO₂) |
| today_carbon_change | float | 今日碳排放环比变化(%) |
| month_carbon | float | 本月累计碳排放(吨CO₂) |
| month_carbon_change | float | 本月碳排放环比变化(%) |
| carbon_intensity | float | 碳强度(kgCO₂/㎡) |
| carbon_intensity_change | float | 碳强度环比变化(%) |
| metrics | array | 核心指标 |
| carbon_sources | array | 碳排放来源占比 |
| carbon_trends | array | 碳排放月度趋势 |
| summary | string | AI分析总结 |
| suggestions | array | 碳减排建议 |

**响应示例**:

```json
{
    "report_id": 25,
    "report_title": "多模态能碳计算报告 - 2026年6月",
    "report_desc": "本报告基于会展小镇内电、水、气、热四类能源的实时计量数据，融合物理机理模型与机器学习算法，对园区能碳排放进行多维度精准核算。",
    "energy_type_count": 4,
    "today_carbon": 28.5,
    "today_carbon_change": -3.2,
    "month_carbon": 856.3,
    "month_carbon_change": -5.8,
    "carbon_intensity": 0.45,
    "carbon_intensity_change": -8.2,
    "metrics": [
        {
            "value": "856.3",
            "label": "本月碳排(吨CO₂)"
        },
        {
            "value": "-5.8%",
            "label": "环比变化"
        },
        {
            "value": "0.45",
            "label": "碳强度(kg/㎡)"
        },
        {
            "value": "12.3%",
            "label": "减排潜力"
        }
    ],
    "carbon_sources": [
        {
            "source": "电力",
            "value": 582.28,
            "percentage": 68.0
        },
        {
            "source": "天然气",
            "value": 188.39,
            "percentage": 22.0
        },
        {
            "source": "热力",
            "value": 59.94,
            "percentage": 7.0
        },
        {
            "source": "其他",
            "value": 25.69,
            "percentage": 3.0
        }
    ],
    "carbon_trends": [
        {
            "month": "2026-01",
            "actual": 920.5,
            "target": 950.0
        },
        {
            "month": "2026-02",
            "actual": 875.3,
            "target": 920.0
        },
        {
            "month": "2026-03",
            "actual": 892.1,
            "target": 900.0
        }
    ],
    "summary": "本月碳排放总量为856.3吨CO₂，较上月下降5.8%。电力是主要碳排放来源，占比68%，建议重点优化用电结构。",
    "suggestions": [
        "优化空调系统运行策略，降低电力消耗",
        "推广绿色能源使用，减少碳排放",
        "建立碳排放预警机制，实时监控碳排放异常"
    ]
}
```

---

### 5.6 查询报告列表

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

### 5.7 获取报告详情

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

### 5.8 获取报告统计

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

### 5.9 删除报告

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

### 5.10 获取会展列表

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

### 5.11 AI能源分析报告

**接口地址**: `POST /api/ai-report/energy-analysis`

**功能说明**: 基于实时数据对能源系统（空调机组、新风机组、配电系统、冷源系统、光伏系统）进行综合分析，生成包含分析总结、优化建议和异常警告的报告。

**子系统类型**：

| 类型代码 | 说明 | 匹配规则 |
|---------|------|---------|
| overview | 全系统概览 | 所有子系统汇总 |
| air_condition | 空调机组 | device_code含KT 或 category_name含"空调" |
| fresh_air | 新风机组 | device_code含XF 或 category_name含"新风" |
| power_distribution | 配电系统 | device_code含PD/DP 或 category_name含"配电/低压" |
| cold_source | 冷源系统 | device_code含CH 或 category_name含"冷/制冷" |
| photovoltaic | 光伏系统 | device_code含PV 或 category_name含"光伏" |
| all | 全部系统 | 所有子系统详细数据 |

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| system_type | string | 是 | 子系统类型 |
| venue_name | string | 否 | 会展名称（筛选数据） |
| time_range | string | 否 | 时间范围（day/week/month/quarter/year），默认day |
| device_name | string | 否 | 设备名称（可选） |

**请求示例**:

```json
{
    "system_type": "overview",
    "venue_name": "会展小镇",
    "time_range": "day",
    "device_name": null
}
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| report_id | int | 报告ID |
| report_title | string | 报告标题 |
| report_time | string | 报告生成时间 |
| system_type | string | 分析的系统类型 |
| overview | object | 概览数据 |
| air_condition | object | 空调机组数据 |
| fresh_air | object | 新风机组数据 |
| power_distribution | object | 配电系统数据 |
| cold_source | object | 冷源系统数据 |
| photovoltaic | object | 光伏系统数据 |
| summary | string | AI分析总结 |
| suggestions | array | 优化建议 |
| warnings | array | 异常警告 |
| analysis_dimensions | array | 分析维度 |

**响应示例**:

```json
{
    "report_id": 25,
    "report_title": "会展小镇全系统概览分析报告 - 2026-08-10",
    "report_time": "2026-08-10 15:32:00",
    "system_type": "overview",
    "overview": {
        "subsystem_count": 6,
        "total_devices": 343,
        "online_devices": 340,
        "offline_devices": 3,
        "total_alarms": 12,
        "pending_alarms": 2
    },
    "air_condition": {
        "total_count": 6,
        "running_count": 5,
        "fault_count": 1,
        "today_energy": 0,
        "avg_cop": 4.2,
        "devices": [
            {"id": 1, "device_code": "A1-KT-F1-01", "device_name": "1号空调机组", "run_state": "停止", "space_name": "会展小镇-2号楼"},
            {"id": 2, "device_code": "A1-KT-F3-01", "device_name": "3号空调机组", "run_state": "停止", "space_name": "会展小镇-2号楼"},
            {"id": 3, "device_code": "A2-KT-F3-01", "device_name": "5号空调机组", "run_state": "停止", "space_name": "会展小镇-3号楼"},
            {"id": 4, "device_code": "A2-KT-F3-02", "device_name": "6号空调机组", "run_state": "运行", "space_name": "会展小镇-3号楼"},
            {"id": 5, "device_code": "A2-KT-F3-03", "device_name": "7号空调机组", "run_state": "停止", "space_name": "会展小镇-3号楼"},
            {"id": 6, "device_code": "D6-KT-F2-01", "device_name": "除尘空调机组", "run_state": "停止", "space_name": "会展小镇-9号楼-除尘"}
        ]
    },
    "fresh_air": {
        "total_count": 27,
        "running_count": 27,
        "avg_pm25": 15.36,
        "today_energy": 0,
        "devices": [
            {"id": 101, "device_code": "C1-XF-MF-01", "device_name": "1号新风机组", "run_state": "在线", "space_name": "会展小镇-1号楼"},
            {"id": 102, "device_code": "C1-XF-MF-02", "device_name": "2号新风机组", "run_state": "在线", "space_name": "会展小镇-1号楼"},
            {"id": 103, "device_code": "A1-XF-B1-01", "device_name": "地下1层新风", "run_state": "在线", "space_name": "会展小镇-2号楼"}
        ]
    },
    "power_distribution": {
        "total_count": 300,
        "running_count": 300,
        "today_energy": 0,
        "power_factor": 0.84,
        "devices": [
            {"id": 201, "device_code": "Kccgz211", "device_name": "1号配电柜", "run_state": "在线", "space_name": "会展小镇-9号楼-除尘改造"},
            {"id": 202, "device_code": "Kccgz212", "device_name": "2号配电柜", "run_state": "在线", "space_name": "会展小镇-9号楼-除尘改造"}
        ]
    },
    "cold_source": {
        "total_count": 8,
        "running_count": 7,
        "today_cooling": 12456,
        "avg_cop": 5.8,
        "devices": [
            {"id": 301, "device_code": "CH-A-01", "device_name": "磁悬浮冷水机组A", "run_state": "运行", "space_name": "冷站"},
            {"id": 302, "device_code": "CH-A-02", "device_name": "磁悬浮冷水机组B", "run_state": "运行", "space_name": "冷站"},
            {"id": 303, "device_code": "CH-B-01", "device_name": "离心式冷水机组1", "run_state": "运行", "space_name": "冷站"},
            {"id": 304, "device_code": "CH-B-02", "device_name": "离心式冷水机组2", "run_state": "停机", "space_name": "冷站"},
            {"id": 305, "device_code": "CH-C-01", "device_name": "螺杆式冷水机组", "run_state": "运行", "space_name": "冷站"}
        ]
    },
    "photovoltaic": {
        "total_count": 12,
        "installed_capacity": 856,
        "today_generation": 3456,
        "efficiency": 18.5,
        "devices": [
            {"id": 401, "device_code": "PV-A-01", "device_name": "A馆屋顶-东组串", "run_state": "发电", "space_name": "A馆屋顶"},
            {"id": 402, "device_code": "PV-A-02", "device_name": "A馆屋顶-西组串", "run_state": "发电", "space_name": "A馆屋顶"},
            {"id": 403, "device_code": "PV-B-01", "device_name": "B馆屋顶组串", "run_state": "发电", "space_name": "B馆屋顶"},
            {"id": 404, "device_code": "PV-C-01", "device_name": "C馆屋顶组串", "run_state": "发电", "space_name": "C馆屋顶"},
            {"id": 405, "device_code": "PV-P-01", "device_name": "停车场车棚组串", "run_state": "发电", "space_name": "停车场"}
        ]
    },
    "summary": "全园区共接入6大能源子系统，对接设备343台，当前在线340台，在线率99.1%。告警总数12条，待处理2条。冷源系统运行效率良好，平均COP达5.8；光伏系统今日发电量3456kWh，效率18.5%；配电系统功率因数0.84，符合标准要求。",
    "suggestions": [
        "建议提高COP低于5.0的机组负荷分配，预计可提升整体能效约3%",
        "建议对D6-KT-F2-01号故障空调机组进行维修，保障系统稳定运行",
        "建议优化空调机组启停策略，在非高峰时段采用节能模式运行",
        "光伏系统效率良好，建议继续保持定期清洁维护"
    ],
    "warnings": [
        "D6-KT-F2-01号空调机组处于故障状态，请及时安排维修",
        "CH-B-02离心式冷水机组处于停机状态，请检查原因并及时恢复"
    ],
    "analysis_dimensions": [
        "运行效率分析",
        "能耗水平分析",
        "设备健康分析",
        "优化潜力分析"
    ]
}
```

---

### 5.12 获取能源系统列表

**接口地址**: `GET /api/ai-report/energy-analysis/systems`

**响应参数**:

| 参数名 | 类型 | 说明 |
|-------|------|------|
| items | array | 系统列表 |
| total | int | 总数 |

**响应示例**:

```json
{
    "items": [
        {"code": "overview", "name": "全系统概览", "icon": "dashboard"},
        {"code": "air_condition", "name": "空调机组", "icon": "ac"},
        {"code": "fresh_air", "name": "新风机组", "icon": "wind"},
        {"code": "power_distribution", "name": "配电系统", "icon": "electricity"},
        {"code": "cold_source", "name": "冷源系统", "icon": "snowflake"},
        {"code": "photovoltaic", "name": "光伏系统", "icon": "sun"},
        {"code": "all", "name": "全部系统", "icon": "all"}
    ],
    "total": 7
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
| v1.3 | 2026-08-10 | chat-stream 支持智能数据问答，自动生成 SQL 查询达梦数据库，返回 ECharts 图表 + Vue 表格 + 总结；SQL 生成/执行增加 GROUP BY 修复；旧版 SQL 接口标记为废弃 |
| v1.4 | 2026-08-10 | 新增AI能源分析报告接口（/api/ai-report/energy-analysis），支持对空调机组、新风机组、配电系统、冷源系统、光伏系统进行实时数据分析和AI建议生成；严格遵守达梦8.0语法规范 |

---

> 文档生成时间: 2026-08-10
> 更多信息请访问项目仓库
