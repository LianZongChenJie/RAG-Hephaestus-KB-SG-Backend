# FWBZ 数据库问答手册

> **适用版本**：达梦 8.0（DM8 V8.1.4.48，Navicat 导出）
> **Schema**：`FWBZ`
> **源文件**：`FWBZ_strut.sql`（2026-08-27 导出，113 张业务表）
> **文档目的**：将表结构翻译为可回答的业务问题，沉淀高频 SQL 范式，便于 RAG 检索 / 报表开发 / 应急排查
> **占位符约定**：所有 SQL 范例中 `{{变量}}` 表示调用方需替换的入参（如日期、ID、名称）

---

## 0. 快速导航

| 编号 | 业务域 | 核心问题方向 | 涉及表数 |
|------|--------|--------------|----------|
| 1 | AI 报告与日志 | 报告查询、运行日志审计 | 2 |
| 2 | 报警与告警 | 告警事件、规则、统计 | 6 |
| 3 | 设备与采集 | 台账、属性、实时/历史数据 | 14 |
| 4 | 空间与项目 | 空间位置、项目台账 | 2 |
| 5 | 能源与计量 | 能耗、单价、碳排、煤耗、计费 | 16 |
| 6 | 照明 | 区域/回路、计划、控制记录 | 5 |
| 7 | 联动与场景 | 联动策略、模式化策略、执行日志 | 9 |
| 8 | 楼宇自控 BA | 控制点、收发历史 | 3 |
| 9 | 视频监控 | 摄像头、点位、区域、巡更计划 | 6 |
| 10 | 门禁/人员识别 | 设备、事件、识别记录 | 5 |
| 11 | 消防 | 烟感/温感、消防报警 | 3 |
| 12 | 停车场 | 进出记录、统计 | 2 |
| 13 | 客流 | 场馆客流、访客、人员统计 | 4 |
| 14 | 投诉建议 | 工单、流转记录 | 4 |
| 15 | 活动会议 | 活动筹备、总结报告 | 5 |
| 16 | 冷源与接口 | 冷源遥测、接口监控、协议 | 8 |
| 17 | 权限与配置 | 角色数据权限、业务配置、单位 | 3 |

---

## 1. AI 报告与运行日志

### 涉及表
- `ai_report_history` —— AI 生成的运行/预测/能碳/故障报告历史
- `sys_log` —— 系统登录日志、操作日志、租户日志

### 可回答的问题
1. 最近一周系统生成了哪些 AI 报告？
2. 某设备最近一次"故障分析报告"是什么内容？
3. 谁在什么时候调用了哪个接口、耗时多少？
4. 最近 24 小时的登录日志有多少条？是否异常？
5. 指定租户（多租户）最近一周的操作日志

### SQL 范式

**Q1.1 按报告类型查询最近 N 天报告列表**
```sql
SELECT id, report_type, title, summary, time_range, target_name, scope, created_at
FROM   FWBZ.ai_report_history
WHERE  created_at >= {{start_time}}
  AND  created_at <  {{end_time}}
  {{-- 报告类型过滤（可选）：run/predict/energy/fault/carbon --}}
  {{-- AND report_type = '{{report_type}}' --}}
ORDER  BY created_at DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q1.2 取某设备某类报告的最新一份**
```sql
SELECT *
FROM   FWBZ.ai_report_history
WHERE  report_type = 'fault'                -- fault/run/predict/energy/carbon
  AND  target_id   = {{device_id}}
ORDER  BY created_at DESC
FETCH  FIRST 1 ROW ONLY;
```

**Q1.3 接口调用耗时 TOP N（定位慢 SQL/慢接口）**
```sql
SELECT request_url,
       method,
       cost_time,
       username,
       create_time
FROM   FWBZ.sys_log
WHERE  log_type  = 2                       -- 2=操作日志
  AND  create_time BETWEEN {{start_time}} AND {{end_time}}
ORDER  BY cost_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q1.4 统计某用户近 N 天操作频次**
```sql
SELECT username,
       COUNT(*) AS op_cnt
FROM   FWBZ.sys_log
WHERE  userid      = '{{user_id}}'
  AND  log_type    = 2
  AND  create_time >= {{start_time}}
GROUP  BY username
ORDER  BY op_cnt DESC;
```

**Q1.5 登录日志审计（多租户）**
```sql
SELECT create_time, username, ip, log_content, client_type
FROM   FWBZ.sys_log
WHERE  log_type     = 1                    -- 1=登录日志
  AND  tenant_id    = {{tenant_id}}
  AND  create_time >= {{start_time}}
ORDER  BY create_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

> **达梦提示**：`log_type` 为 INT，取值 `1 登录 / 2 操作 / 3 租户操作`；`client_type` 为 `pc/app/h5`。

---

## 2. 报警与告警

### 涉及表
- `alarm_category` —— 报警类别字典
- `alarm_level` —— 报警级别字典（含颜色）
- `alarm_rules` —— 报警规则主表
- `alarm_rule_point` —— 规则绑定的设备点位
- `alarm_record` —— 告警事件流水
- `table_fire_alarm_record` —— 消防独立告警流水

### 关键字段速记
- `alarm_record.alarm_status`：`1 未处理 / 2 已消除`
- `alarm_rules.enabled_status`：`0 禁用 / 1 启用`
- `table_fire_alarm_record.handle_status`：`0 未处理 / 1 处理中 / 2 已处理 / 3 误报 / 4 忽略`
- `table_fire_alarm_record.alarm_type`：`烟感/温感/手报/设备故障/低电量/离线`

### 可回答的问题
1. 当前还有多少未处理的告警？分布在哪些级别？
2. 某设备最近 N 天的告警频次是多少？
3. 哪些告警规则从来没有触发过（疑似"死规则"）？
4. 某空间告警的 TOP 10 类型分布
5. 某告警事件的完整处置过程（转工单 → 完成）
6. 哪些消防设备最近 24h 离线？

### SQL 范式

**Q2.1 当前未处理告警分级别统计**
```sql
SELECT alarm_level_id,
       alarm_level_name,
       alarm_level_color,
       COUNT(*) AS cnt
FROM   FWBZ.alarm_record
WHERE  alarm_status = '1'                  -- 1=未处理
  AND  alarm_time  >= {{start_time}}
GROUP  BY alarm_level_id, alarm_level_name, alarm_level_color
ORDER  BY cnt DESC;
```

**Q2.2 某设备近 N 天告警频次**
```sql
SELECT TO_CHAR(alarm_time, 'YYYY-MM-DD') AS d,
       COUNT(*) AS alarm_cnt
FROM   FWBZ.alarm_record
WHERE  device_id  = {{device_id}}
  AND  alarm_time >= {{start_time}}
GROUP  BY TO_CHAR(alarm_time, 'YYYY-MM-DD')
ORDER  BY d;
```

**Q2.3 疑似"死规则" —— 启用了但从未触发**
```sql
SELECT r.id, r.rule_code, r.rule_name
FROM   FWBZ.alarm_rules r
WHERE  r.enabled_status = '1'
  AND  NOT EXISTS (
        SELECT 1 FROM FWBZ.alarm_record rec
        WHERE rec.alarm_rule_id = r.id
          AND rec.alarm_time >= SYSDATE - INTERVAL '{{days}}' DAY
       );
```

**Q2.4 某空间告警类型 TOP 10**
```sql
SELECT alarm_category_name,
       alarm_level_name,
       COUNT(*) AS cnt
FROM   FWBZ.alarm_record
WHERE  space_id  = {{space_id}}
  AND  alarm_time BETWEEN {{start_time}} AND {{end_time}}
GROUP  BY alarm_category_name, alarm_level_name
ORDER  BY cnt DESC
FETCH  FIRST 10 ROWS ONLY;
```

**Q2.5 告警全生命周期（事件维度）**
```sql
SELECT id, alarm_rule_id, alarm_content, value, condition_value, operator,
       alarm_time, transfer_event_time, event_completion_time,
       EXTRACT(EPOCH FROM (event_completion_time - alarm_time)) AS handle_seconds
FROM   FWBZ.alarm_record
WHERE  event_id = '{{event_id}}';
```

**Q2.6 消防告警 24h 离线设备**
```sql
SELECT device_id, alarm_location, alarm_type, alarm_time, handle_status, handler
FROM   FWBZ.table_fire_alarm_record
WHERE  alarm_type   = '离线'
  AND  alarm_time  >= SYSDATE - INTERVAL '1' DAY
ORDER  BY alarm_time DESC;
```

**Q2.7 某告警规则配置详情（含点位）**
```sql
SELECT r.rule_code, r.rule_name, r.alarm_category_name, r.alarm_level_name,
       p.device_name, p.point_name, p.operator, p.condition_value, p.time_granularity
FROM   FWBZ.alarm_rules r
LEFT   JOIN FWBZ.alarm_rule_point p ON p.alarm_rule_id = r.id
WHERE  r.id = {{rule_id}};
```

---

## 3. 设备与采集（核心台账 + 时序数据）

### 涉及表
- `device` / `device_model` / `device_model_attribute` —— 设备主数据
- `device_attribute` / `device_attribute_config` / `device_attribute_data` / `device_attribute_history` —— 设备属性（实时/历史/配置）
- `device_static_data` / `device_static_data_config` —— 设备静态数据
- `data_real` / `data_minute` / `data_hour` / `data_day` / `data_month` / `data_year` —— 时序数据五级粒度
- `gather_rule_config` —— 网关/采集规则
- `equipment_category` —— 设备类别（树形）
- `data_amend_log` —— 数据修正日志

### 关键字段速记
- `device.device_type`：`1 仪表 / 2 设备`
- `equipment_category.type`：`1 仪表 / 2 设备`
- 时序数据粒度：real(实时) → minute → hour → day → month → year
- `device_attribute_history` 唯一键：`(attribute_id, collection_time)`

### 可回答的问题
1. 某空间下挂着哪些设备/仪表？数量分别是多少？
2. 某设备的实时点位数据是多少？
3. 某设备最近 24 小时的能耗曲线（小时粒度）
4. 某设备本月的日能耗趋势
5. 某点位（属性）近 N 天的历史值
6. 哪些设备最后采集时间超过 X 小时没回数据（疑似离线）？
7. 某网关下挂了哪些设备？协议是什么？
8. 某设备最近一次数据修正前后的值

### SQL 范式

**Q3.1 某空间下设备/仪表数量统计**
```sql
SELECT d.device_type,
       DECODE(d.device_type, '1', '仪表', '2', '设备', '其他') AS type_name,
       COUNT(*) AS cnt
FROM   FWBZ.device d
WHERE  d.space_id = {{space_id}}
GROUP  BY d.device_type;
```

**Q3.2 设备实时值（最细粒度）**
```sql
-- 方式A：device 主表的最新采集时间
SELECT d.id, d.device_name, d.device_code, d.run_state, d.last_gather_time
FROM   FWBZ.device d
WHERE  d.id = {{device_id}};

-- 方式B：data_real（每 device 一行最新）
SELECT dr.device_id, dr.value, dr.time
FROM   FWBZ.data_real dr
WHERE  dr.device_id = {{device_id}};
```

**Q3.3 设备最近 24 小时小时能耗曲线**
```sql
SELECT TO_CHAR(dh.time, 'YYYY-MM-DD HH24') || ':00' AS time_bucket,
       SUM(dh.value) AS value
FROM   FWBZ.data_hour dh
WHERE  dh.device_id = {{device_id}}
  AND  dh.time BETWEEN {{start_time}} AND {{end_time}}
GROUP  BY TO_CHAR(dh.time, 'YYYY-MM-DD HH24')
ORDER  BY time_bucket;
```

**Q3.4 设备本月日能耗趋势**
```sql
SELECT TO_CHAR(dd.time, 'YYYY-MM-DD') AS d, dd.value
FROM   FWBZ.data_day dd
WHERE  dd.device_id = {{device_id}}
  AND  dd.time BETWEEN {{start_time}} AND {{end_time}}
ORDER  BY d;
```

**Q3.5 某点位（属性）历史值**
```sql
-- 实时/最新一次
SELECT *
FROM   FWBZ.device_attribute_history dah
WHERE  dah.attribute_id = {{attribute_id}}
ORDER  BY dah.collection_time DESC
FETCH  FIRST 1 ROW ONLY;

-- 某时间区间
SELECT dah.collection_time, dah.value
FROM   FWBZ.device_attribute_history dah
WHERE  dah.attribute_id = {{attribute_id}}
  AND  dah.collection_time BETWEEN {{start_time}} AND {{end_time}}
ORDER  BY dah.collection_time;
```

**Q3.6 离线设备清单（最后采集 > N 小时）**
```sql
SELECT d.id, d.device_name, d.device_code, d.run_state,
       d.last_gather_time,
       EXTRACT(EPOCH FROM (SYSDATE - d.last_gather_time)) / 3600.0 AS offline_hours
FROM   FWBZ.device d
WHERE  d.last_gather_time IS NULL
   OR  d.last_gather_time < SYSDATE - INTERVAL '{{n}}' HOUR
ORDER  BY d.last_gather_time NULLS FIRST;
```

**Q3.7 某网关下挂的设备清单**
```sql
-- 注：device 与 gather_rule_config 无显式外键，按"安装位置/IP"做匹配
SELECT g.gateway_code, g.gateway_name, g.protocol, g.state, g.last_collection_time,
       d.id AS device_id, d.device_name, d.device_code
FROM   FWBZ.gather_rule_config g
LEFT   JOIN FWBZ.device d ON d.space_id = g.install_addr
WHERE  g.gateway_code = '{{gateway_code}}';
```

**Q3.8 数据修正记录（审计）**
```sql
SELECT id, device_id, hour_data_id, time,
       start_value, end_value, compute_value, original_value, value,
       update_by, update_time
FROM   FWBZ.data_amend_log
WHERE  device_id = {{device_id}}
  AND  time BETWEEN {{start_time}} AND {{end_time}}
ORDER  BY update_time DESC;
```

**Q3.9 设备类别树（带"仪表/设备"标识）**
```sql
SELECT id, pid, category_name, full_name, type,
       DECODE(type, '1', '仪表', '2', '设备', '其他') AS type_name,
       has_child
FROM   FWBZ.equipment_category
START  WITH pid = 0
CONNECT BY PRIOR id = pid
ORDER  SIBLINGS BY sort;
```

---

## 4. 空间位置

### 涉及表
- `space` —— 空间位置（树形，含 `pid / has_child / full_name / full_id`）

### 可回答的问题
1. 空间树长什么样？
2. 某空间下子空间列表
3. 某空间下挂着多少设备/计量点？

### SQL 范式

**Q4.1 空间树（递归）**
```sql
SELECT id, pid, space_name, full_name, has_child, sort
FROM   FWBZ.space
START  WITH pid = 0
CONNECT BY PRIOR id = pid
ORDER  SIBLINGS BY sort;
```

**Q4.2 某空间直接子空间**
```sql
SELECT *
FROM   FWBZ.space
WHERE  pid = {{space_id}}
ORDER  BY sort;
```

**Q4.3 某空间所有后代空间 ID（用 `full_id` 模糊）**
```sql
SELECT id, space_name, full_name
FROM   FWBZ.space
WHERE  full_id LIKE '%{{space_id}}%';     -- 依赖项目里 full_id 编码规则
```

---

## 5. 能源与计量

### 涉及表
- `energy_medium_manage` —— 能源介质（电/水/气/热…）
- `energy_attribute_management` —— 能源属性字典
- `energy_price` —— 单价（基础）
- `energy_pricing_config` —— 计费配置（峰谷分时 / 阶梯 / 固定）
- `standard_coal_coefficient` —— 折标煤系数（当量/等价）
- `carbon_emission_factor` —— 碳排放因子
- `metering_point` —— 计量点（含 `formula` 公式）
- `metering_point_rel` —— 计量点 ↔ 设备/子计量点关联
- `metering_point_data_hour/day/month/year` —— 计量点值（按时/日/月/年）
- `metering_point_cost_data_hour/day/month/year` —— 计量点金额（按所选计费配置计算后的成本）
- `energy_analysis_config` / `energy_analysis_chart` / `energy_analysis_benchmark` —— 能效分析配置
- `energy_flow_diagram_config` —— 能流图节点
- `unit_management` —— 计量单位

### 关键字段速记
- `energy_pricing_config.billing_way`：`1 峰谷分时 / 2 固定 / 3 阶梯`
- `metering_point_rel.rel_type`：`1 设备 / 2 计量点`
- `metering_point.type` 字典：`energy_flow_type`

### 可回答的问题
1. 各能源介质（电/水/气/热）本月累计能耗是多少？
2. 某计量点本月日能耗与日费用
3. 某能源本月成本（按所选计费配置）
4. 各能介的折标煤系数 / 碳排放因子是多少？
5. 某能介当前生效的计费配置是什么？
6. 某能效分析方案包含哪些图表/基准？
7. 某计量点下挂的设备清单

### SQL 范式

**Q5.1 各能介本月累计能耗（基于计量点）**
```sql
SELECT mp.id, mp.node_name, mp.type,
       SUM(mpd.value) AS month_value
FROM   FWBZ.metering_point mp
LEFT   JOIN FWBZ.metering_point_data_month mpd
       ON mpd.metering_point_id = mp.id
      AND mpd.time BETWEEN {{start_time}} AND {{end_time}}
GROUP  BY mp.id, mp.node_name, mp.type
ORDER  BY month_value DESC;
```

**Q5.2 计量点日能耗 + 日费用（成本表）**
```sql
SELECT TO_CHAR(mpd.time, 'YYYY-MM-DD')  AS d,
       mpd.value                        AS energy,
       mpc.cost                          AS cost
FROM   FWBZ.metering_point_data_day mpd
LEFT   JOIN FWBZ.metering_point_cost_data_day mpc
       ON mpc.metering_point_id = mpd.metering_point_id
      AND mpc.time              = mpd.time
WHERE  mpd.metering_point_id = {{metering_point_id}}
  AND  mpd.time BETWEEN {{start_time}} AND {{end_time}}
ORDER  BY d;
```

**Q5.3 某能介当前生效的计费配置**
```sql
SELECT *
FROM   FWBZ.energy_pricing_config
WHERE  category = '{{energy_medium}}'        -- electricity / water / heating …
  AND  status   = '1';
```

**Q5.4 折标煤 + 碳排放系数**
```sql
-- 折标煤
SELECT energy_medium, unit, eccsc, ecf
FROM   FWBZ.standard_coal_coefficient
WHERE  energy_medium = '{{energy_medium}}';

-- 碳排放因子
SELECT carbon_factor_name, coefficient, unit
FROM   FWBZ.carbon_emission_factor
ORDER  BY sort;
```

**Q5.5 计量点公式 + 关联设备**
```sql
SELECT mp.id, mp.node_name, mp.formula, mp.true_formula,
       mpr.rel_id, mpr.rel_type,
       DECODE(mpr.rel_type, '1', '设备', '2', '子计量点', '其他') AS rel_type_name,
       d.device_name
FROM   FWBZ.metering_point mp
LEFT   JOIN FWBZ.metering_point_rel mpr ON mpr.metering_point_id = mp.id
LEFT   JOIN FWBZ.device d               ON d.id = mpr.rel_id AND mpr.rel_type = '1'
WHERE  mp.id = {{metering_point_id}};
```

**Q5.6 能效分析方案的图表与基准**
```sql
-- 图表配置
SELECT c.chart_name, c.chart_type, c.point_id, c.unit
FROM   FWBZ.energy_analysis_chart c
WHERE  c.config_id = {{config_id}};

-- 基准
SELECT b.label, b.value, b.operator, b.content
FROM   FWBZ.energy_analysis_benchmark b
WHERE  b.config_id = {{config_id}};
```

**Q5.7 能流图节点（含父子树）**
```sql
SELECT id, parent_id, node_name, type, metering_point_id, sort
FROM   FWBZ.energy_flow_diagram_config
START  WITH parent_id = 0
CONNECT BY PRIOR id = parent_id
ORDER  SIBLINGS BY sort;
```

**Q5.8 单位字典**
```sql
SELECT code, name, english_ame
FROM   FWBZ.unit_management
ORDER  BY sort;
```

---

## 6. 照明

### 涉及表
- `lighting_area` —— 照明区域（含"建筑/区域"类型）
- `lighting_circuit` —— 照明回路
- `lighting_plan` / `lighting_plan_execution_time` —— 照明计划 + 执行时间
- `lighting_operation_log` —— 照明控制操作记录

### 关键字段速记
- `lighting_area.space`：`1 金安桥 / 2 一高炉`
- `lighting_area.type`：`1 建筑 / 2 区域`
- `lighting_plan.rel_type`：`区域/回路`
- `lighting_plan_execution_time.enabled_week`：形如 `'1,2,3'` 表示 周一/二/三

### 可回答的问题
1. 当前哪些回路处于开启状态？开启时长？
2. 某区域的计划执行表
3. 某回路最近 N 条操作记录
4. 各计划今日执行了几次？

### SQL 范式

**Q6.1 当前开着的回路**
```sql
SELECT c.id, c.circuit_name, c.area_id, a.area_name, c.start_time,
       EXTRACT(EPOCH FROM (SYSDATE - c.start_time)) / 60 AS open_minutes
FROM   FWBZ.lighting_circuit c
LEFT   JOIN FWBZ.lighting_area a ON a.id = c.area_id
WHERE  c.status = '开启'
ORDER  BY c.start_time;
```

**Q6.2 某区域计划明细**
```sql
SELECT p.id, p.plan_name, p.rel_type, p.rel_ids, p.execution_time, p.operation_type, p.status
FROM   FWBZ.lighting_plan p
WHERE  EXISTS (
        SELECT 1 FROM FWBZ.lighting_area a
        WHERE a.area_code = '{{area_code}}'
          AND (',' || p.rel_ids || ',') LIKE ('%,' || a.id || ',%')
       );
```

**Q6.3 回路操作记录**
```sql
SELECT *
FROM   FWBZ.lighting_operation_log
WHERE  rel_type = '回路'
  AND  rel_id   = {{circuit_id}}
ORDER  BY operation_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q6.4 计划今日已执行次数（依赖执行记录；本表无，可结合 `log_strategy_execute_record`）**
```sql
SELECT COUNT(*) AS exec_cnt
FROM   FWBZ.log_strategy_execute_record
WHERE  business_type = '0'                  -- 0=模式化管理
  AND  business_key  = {{plan_id}}
  AND  executed_time >= TRUNC(SYSDATE);
```

---

## 7. 联动控制 & 场景化策略

### 涉及表
- `linkage_strategy` / `linkage_front_point` / `linkage_rear_point` —— 联动策略 + 前置/后置点位
- `patterning_strategy` / `patterning_execution_time` / `patterning_point` / `patterning_related` —— 场景化策略
- `log_strategy_execute_record` / `log_point_execute_record` —— 策略与点位执行日志

### 关键字段速记
- `log_strategy_execute_record.business_type`：`0 模式化 / 1 联动`
- `log_strategy_execute_record.success_flag`：`成功/失败/执行中`
- `patterning_strategy.enabled_status`：`0 禁 / 1 启`
- `patterning_strategy.model_type`：`手动 / 自动`
- `patterning_execution_time.enabled_week`：形如 `'1,2,3,4,5'` 表示工作日

### 可回答的问题
1. 当前启用了哪些联动策略？前置条件是什么？
2. 某联动策略今天触发了几次？成功率？
3. 哪些策略在最近 24h 失败了？
4. 某空间下的所有场景化策略
5. 某个点位最近一次执行的结果

### SQL 范式

**Q7.1 启用中的联动策略**
```sql
SELECT id, strategy_code, strategy_name, strategy_target, enabled_status
FROM   FWBZ.linkage_strategy
WHERE  enabled_status = '1'
ORDER  BY strategy_code;
```

**Q7.2 联动策略完整定义**
```sql
SELECT s.strategy_code, s.strategy_name, s.strategy_target,
       fp.point_name AS front_point, fp.operator, fp.condition_value AS front_val,
       rp.point_name AS rear_point, rp.condition_value AS rear_val
FROM   FWBZ.linkage_strategy s
LEFT   JOIN FWBZ.linkage_front_point fp ON fp.linkage_strategy_id = s.id
LEFT   JOIN FWBZ.linkage_rear_point  rp ON rp.linkage_strategy_id = s.id
WHERE  s.id = {{strategy_id}};
```

**Q7.3 联动今日触发次数与成功率**
```sql
SELECT
   COUNT(*)                                                     AS exec_cnt,
   SUM(CASE WHEN success_flag = '成功'    THEN 1 ELSE 0 END)    AS ok_cnt,
   SUM(CASE WHEN success_flag = '失败'    THEN 1 ELSE 0 END)    AS fail_cnt,
   SUM(CASE WHEN success_flag = '执行中'  THEN 1 ELSE 0 END)    AS running_cnt
FROM   FWBZ.log_strategy_execute_record
WHERE  business_type = '1'                   -- 1=联动
  AND  business_key  = {{strategy_id}}
  AND  executed_time >= TRUNC(SYSDATE);
```

**Q7.4 24h 内失败的策略**
```sql
SELECT business_type, business_key, description, executed_time, executed_by
FROM   FWBZ.log_strategy_execute_record
WHERE  success_flag = '失败'
  AND  executed_time >= SYSDATE - INTERVAL '1' DAY
ORDER  BY executed_time DESC;
```

**Q7.5 某空间下的所有场景化策略**
```sql
SELECT id, strategy_code, strategy_name, strategy_scene, model_type, enabled_status
FROM   FWBZ.patterning_strategy
WHERE  space_id   = {{space_id}}
  {{-- AND model_type = '自动' --}}
ORDER  BY strategy_code;
```

**Q7.6 某策略执行时间表**
```sql
SELECT patterning_id, begin_date, begin_time, enabled_week, end_date, version
FROM   FWBZ.patterning_execution_time
WHERE  patterning_id = {{patterning_id}};
```

**Q7.7 点位执行明细（某次执行记录）**
```sql
SELECT per.point_name, per.device_name, per.condition_value,
       per.condition_remark, per.success_flag, per.executed_time
FROM   FWBZ.log_point_execute_record per
WHERE  per.strategy_execute_id = {{strategy_execute_id}};
```

---

## 8. 楼宇自控（BA）控制点

### 涉及表
- `building_control_point` —— 实时点位（`UNIQUE(gateway_adr, bacnet_adr)`）
- `building_control_point_history` —— 接收历史
- `building_control_point_send_history` —— 下发控制历史

### 可回答的问题
1. 某点位当前值是多少？
2. 某点位最近 24h 的采集趋势
3. 某点位最近 N 条下发指令

### SQL 范式

**Q8.1 当前值（按网关 + bacnet 唯一）**
```sql
SELECT id, gateway_adr, bacnet_adr, value, collection_time, content
FROM   FWBZ.building_control_point
WHERE  gateway_adr = '{{gateway_adr}}'
  AND  bacnet_adr  = '{{bacnet_adr}}';
```

**Q8.2 24h 采集趋势**
```sql
SELECT value, collection_time
FROM   FWBZ.building_control_point_history
WHERE  point_id = {{point_id}}
  AND  collection_time >= SYSDATE - INTERVAL '1' DAY
ORDER  BY collection_time;
```

**Q8.3 最近 N 条下发控制**
```sql
SELECT id, point_id, value, collection_time
FROM   FWBZ.building_control_point_send_history
WHERE  point_id = {{point_id}}
ORDER  BY collection_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

---

## 9. 视频监控

### 涉及表
- `camera_info` / `table_camera_info` —— 摄像头主数据（两份表，字段基本一致）
- `table_camera_resource` —— 海康/萤石等平台同步过来的监控点资源
- `table_camera_group` —— 摄像头分组
- `table_region_resource` —— 区域资源（树形）
- `table_plan_camera` —— 巡更计划与摄像头的关联

### 关键字段速记
- `camera_info.online`：`1 在线 / 0 离线`
- `table_camera_resource.camera_type`：`0 枪机 / 1 半球 / 2 快球 / 3 带云台枪机`
- `table_region_resource.catalog_type`：`0 国标 / 1 雪亮 / 2 司法 / 9 自定义 / 10 普通 / 11 级联 / 12 楼栋单元`
- `table_region_resource.cascade_type`：`0 本级 / 1 级联 / 2 混合`

### 可回答的问题
1. 离线摄像头清单
2. 某分组下所有摄像头
3. 某区域（含子区域）下所有摄像头
4. 某经纬度附近 N 米的摄像头
5. 某巡更计划调用的摄像头

### SQL 范式

**Q9.1 离线摄像头清单**
```sql
SELECT id, name, ip, port, group_name, space_path, last_gather_time
FROM   FWBZ.camera_info
WHERE  online = 0
ORDER  BY group_name, sort_num;
```

**Q9.2 某分组摄像头**
```sql
SELECT *
FROM   FWBZ.camera_info
WHERE  group_id = {{group_id}}
ORDER  BY sort_num;
```

**Q9.3 某区域（含子区域）摄像头**
```sql
SELECT *
FROM   FWBZ.camera_info
WHERE  space_path LIKE '%{{space_name}}%'
ORDER  BY sort_num;
```

**Q9.4 海康同步监控点（按在线状态）**
```sql
SELECT index_code, name, camera_type, region_path_name, online, gmt_modified
FROM   FWBZ.table_camera_resource
WHERE  online = 1                         -- 1=在线
  {{-- AND region_index_code = '{{region_index_code}}' --}}
ORDER  BY dis_order, name;
```

**Q9.5 区域树（海康/萤石）**
```sql
SELECT id, index_code, parent_index_code, name, catalog_type, leaf, total_quantity
FROM   FWBZ.table_region_resource
START  WITH parent_index_code IS NULL
CONNECT BY PRIOR index_code = parent_index_code
ORDER  SIBLINGS BY sort;
```

**Q9.6 巡更计划调用摄像头**
```sql
SELECT pp.plan_name, pc.index_code, cr.name AS camera_name
FROM   FWBZ.table_patrol_plan pp
LEFT   JOIN FWBZ.table_plan_camera pc ON pc.plan_id = pp.id
LEFT   JOIN FWBZ.table_camera_resource cr ON cr.index_code = pc.index_code
WHERE  pp.id = {{plan_id}};
```

---

## 10. 门禁 / 人员识别

### 涉及表
- `table_acs_device` —— 门禁设备
- `table_door_resource` —— 门禁点（通道）
- `table_door_event` —— 门禁事件流水
- `table_person_recognition` —— 人脸/人员识别记录
- `table_personnel_statistics` —— 人员统计（按日）

### 关键字段速记
- `table_acs_device.online`：`0 离线 / 1 在线`
- `table_door_resource.door_state`：`0 初始 / 1 开门 / 2 关门 / 3 离线`
- `table_door_event.in_and_out_type`：`1 进 / 0 出 / -1 未知`
- `table_person_recognition.person_type`：`员工 / 访客 / VIP / 临时人员 / 黑名单`

### 可回答的问题
1. 在线/离线门禁设备清单
2. 某门禁点最近 N 条刷卡记录
3. 某门今天的进出次数
4. 某人员最近 N 天的识别记录
5. 每日人员统计（进场、在场、异常）

### SQL 范式

**Q10.1 门禁设备在线状态**
```sql
SELECT name, ip, port, region_path_name, online, gmt_modified
FROM   FWBZ.table_acs_device
WHERE  online = 1
ORDER  BY name;
```

**Q10.2 某门禁点最近刷卡记录**
```sql
SELECT event_id, event_time, person_name, card_no, in_and_out_type, door_name
FROM   FWBZ.table_door_event
WHERE  door_index_code = '{{door_index_code}}'
ORDER  BY event_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q10.3 某门今日进出次数**
```sql
SELECT in_and_out_type,
       COUNT(*) AS cnt
FROM   FWBZ.table_door_event
WHERE  door_index_code = '{{door_index_code}}'
  AND  event_time >= TRUNC(SYSDATE)
GROUP  BY in_and_out_type;
```

**Q10.4 某人员最近识别记录**
```sql
SELECT recognize_time, person_type, recognize_location, confidence, direction, venue
FROM   FWBZ.table_person_recognition
WHERE  employee_no = '{{employee_no}}'
   OR  person_name = '{{person_name}}'
ORDER  BY recognize_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q10.5 每日人员统计（最近 30 天）**
```sql
SELECT stat_date, today_entry_count, current_in_count,
       recognition_record_count, abnormal_warning_count
FROM   FWBZ.table_personnel_statistics
WHERE  stat_date >= SYSDATE - INTERVAL '30' DAY
ORDER  BY stat_date DESC;
```

---

## 11. 消防

### 涉及表
- `table_smoke_detector` —— 烟感/温感/光感/消防栓设备
- `table_smoke_detector_type` —— 消防设备类型字典
- `table_fire_alarm_record` —— 消防报警流水

### 关键字段速记
- `table_smoke_detector.device_type`：`1 烟感 / 2 温感 / 3 光感 / 4 消防栓`
- `table_fire_alarm_record.alarm_level`：`1 低 / 2 中 / 3 高 / 4 紧急`

### 可回答的问题
1. 哪些消防设备电量低？
2. 哪些设备最近 N 天没回心跳（最后巡检时间过老）？
3. 紧急（level=4）未处理消防报警
4. 各类型消防设备数量

### SQL 范式

**Q11.1 低电量设备**
```sql
SELECT device_name, device_type, location, power_level, last_check_time
FROM   FWBZ.table_smoke_detector
WHERE  power_level IN ('低','LOW','10%')          -- 视项目实际值而定
ORDER  BY last_check_time;
```

**Q11.2 长时间未巡检**
```sql
SELECT device_name, device_type, location, last_check_time,
       SYSDATE - last_check_time AS days_since_check
FROM   FWBZ.table_smoke_detector
WHERE  last_check_time IS NULL
   OR  last_check_time < SYSDATE - INTERVAL '{{n}}' DAY
ORDER  BY last_check_time NULLS FIRST;
```

**Q11.3 紧急未处理消防报警**
```sql
SELECT id, device_id, alarm_location, alarm_type, alarm_level,
       alarm_date, alarm_time, alarm_content
FROM   FWBZ.table_fire_alarm_record
WHERE  alarm_level    = 4                       -- 4=紧急
  AND  handle_status  = 0                       -- 0=未处理
ORDER  BY alarm_date DESC, alarm_time DESC;
```

**Q11.4 各类型消防设备数量**
```sql
SELECT t.type_name, COUNT(*) AS cnt
FROM   FWBZ.table_smoke_detector d
LEFT   JOIN FWBZ.table_smoke_detector_type t ON t.id = d.device_type
GROUP  BY t.type_name
ORDER  BY cnt DESC;
```

---

## 12. 停车场

### 涉及表
- `table_parking_count` —— 每日统计（进场/在场/剩余/平均时长）
- `table_parking_record` —— 每条进出记录

### 可回答的问题
1. 今日/昨日停车统计
2. 某车牌最近 N 条停车记录
3. 哪些车辆在停车场停放超过 N 小时？
4. 各停车场今日流量

### SQL 范式

**Q12.1 今日停车统计**
```sql
SELECT *
FROM   FWBZ.table_parking_count
WHERE  date = TRUNC(SYSDATE);
```

**Q12.2 某车牌最近 N 条记录**
```sql
SELECT *
FROM   FWBZ.table_parking_record
WHERE  plate_no = '{{plate_no}}'
ORDER  BY park_date DESC, park_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q12.3 当前在场且停放 > N 小时**
```sql
SELECT plate_no, parking_lot, space_no,
       park_date, park_time, park_duration
FROM   FWBZ.table_parking_record
WHERE  direction = '入口'
  AND  NOT EXISTS (
        SELECT 1 FROM FWBZ.table_parking_record exit_r
        WHERE exit_r.plate_no   = table_parking_record.plate_no
          AND exit_r.direction  = '出口'
          AND exit_r.park_date  = table_parking_record.park_date
          AND exit_r.park_time  > table_parking_record.park_time
       )
  AND  (SYSDATE - TO_DATE(TO_CHAR(park_date,'YYYY-MM-DD') || park_time, 'YYYY-MM-DD HH24:MI:SS')) > INTERVAL '{{n}}' HOUR;
```

**Q12.4 各停车场今日流量**
```sql
SELECT parking_lot,
       SUM(CASE WHEN direction = '入口' THEN 1 ELSE 0 END) AS in_cnt,
       SUM(CASE WHEN direction = '出口' THEN 1 ELSE 0 END) AS out_cnt
FROM   FWBZ.table_parking_record
WHERE  park_date = TRUNC(SYSDATE)
GROUP  BY parking_lot
ORDER  BY in_cnt DESC;
```

---

## 13. 客流（场馆 / 访客）

### 涉及表
- `table_venue_info` —— 场馆基本信息
- `table_venue_flow_hour` —— 场馆客流分时统计（⚠️ `table_venue_flow` 已废弃，统一用 hour 表）
- `table_visitor_flow` —— 访客（汇总）

### 查询逻辑要点（**客流统一按此规则取数**）

> 一律从 `table_venue_flow_hour` 取数（按 `data_date` + `venue_id` 过滤后），区分两类字段：

| 字段类别 | 字段 | 取数规则 |
|---|---|---|
| **当日累计类** | `today_in_count`（客流量/累计入场）<br>`today_now_count`（在馆人数）<br>`average_duration`（平均时长） | 取 **`data_hour` 最大的那条** 的对应字段（即"当前/最新"小时的累计值） |
| **当日峰值类** | `max_count`（人流峰值）<br>`max_time`（峰值时间） | 取 **`max_count` 最大的那条** 的对应字段（即当日哪一小时峰值最高） |

- 单条 SQL 范式见 Q13.1（汇总）/ Q13.4（单场馆）/ Q13.2（分时曲线）
- 子查询必须加 `ROWNUM = 1`，避免同 key 出现重复 `max_count` 时返回多行报错
- 没有当日数据的场馆（可能未营业）不返回

### 可回答的问题
1. 哪些场馆今天客流峰值最高？
2. 某场馆 24 小时分时客流曲线
3. 各场馆今日进/在场/峰值
4. 某场馆今日客流汇总

### SQL 范式

**Q13.1 今日各场馆客流**
> 范式逻辑：**客流量 / 在馆人数 / 平均时长** 取 `data_hour` 最大的那条；**峰值 / 峰值时间** 取 `max_count` 最大的那条。

```sql
SELECT vi.id AS venue_id,
       vi.venue_name,
       vi.location,
       -- 客流量(今日累计入场): data_date + venue_id 下, data_hour 最大的那条
       (SELECT vfh.today_in_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = vi.id
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = vi.id
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS today_in_count,
       -- 在馆人数: data_date + venue_id 下, data_hour 最大的那条
       (SELECT vfh.today_now_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = vi.id
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = vi.id
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS today_now_count,
       -- 平均时长: data_date + venue_id 下, data_hour 最大的那条
       (SELECT vfh.average_duration
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = vi.id
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = vi.id
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS average_duration,
       -- 人流峰值: data_date + venue_id 下, max_count 最大的那条
       (SELECT vfh.max_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = vi.id
          AND  vfh.data_date = TRUNC(SYSDATE)
        ORDER  BY vfh.max_count DESC
        AND  ROWNUM = 1) AS max_count,
       -- 峰值时间: data_date + venue_id 下, max_count 最大的那条
       (SELECT vfh.max_time
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = vi.id
          AND  vfh.data_date = TRUNC(SYSDATE)
        ORDER  BY vfh.max_count DESC
        AND  ROWNUM = 1) AS max_time
FROM   FWBZ.table_venue_info vi
WHERE  EXISTS (SELECT 1
               FROM   FWBZ.table_venue_flow_hour vfh3
               WHERE  vfh3.venue_id = vi.id
                 AND  vfh3.data_date = TRUNC(SYSDATE))
ORDER  BY (SELECT vfh.max_count
           FROM   FWBZ.table_venue_flow_hour vfh
           WHERE  vfh.venue_id = vi.id
             AND  vfh.data_date = TRUNC(SYSDATE)
           ORDER  BY vfh.max_count DESC
           AND  ROWNUM = 1) DESC;
```

**Q13.2 某场馆 24h 客流曲线**
> 明细查询（按小时逐条展示），不应用"取最大"逻辑。

```sql
SELECT vfh.data_hour, vfh.today_in_count, vfh.today_now_count, vfh.max_count
FROM   FWBZ.table_venue_flow_hour vfh
WHERE  vfh.venue_id  = {{venue_id}}
  AND  vfh.data_date = TRUNC(SYSDATE)
ORDER  BY vfh.data_hour;
```

**Q13.3 访客统计近 30 天**
```sql
SELECT date, today_count, now_count, max_count, average_stop_duration
FROM   FWBZ.table_visitor_flow
WHERE  date >= SYSDATE - INTERVAL '30' DAY
ORDER  BY date DESC;
```

**Q13.4 某场馆今日客流汇总**
> 单场馆版本，逻辑与 Q13.1 一致：客流量取 `data_hour` 最大的那条；峰值取 `max_count` 最大的那条。
> 适用问题："某场馆今日客流是多少？" / "今天 X 馆进/在场/峰值多少？"

```sql
SELECT vi.id AS venue_id,
       vi.venue_name,
       vi.location,
       -- 客流量(今日累计入场): 取 data_hour 最大的那条
       (SELECT vfh.today_in_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = {{venue_id}}
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = {{venue_id}}
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS today_in_count,
       -- 在馆人数: 取 data_hour 最大的那条
       (SELECT vfh.today_now_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = {{venue_id}}
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = {{venue_id}}
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS today_now_count,
       -- 平均时长: 取 data_hour 最大的那条
       (SELECT vfh.average_duration
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = {{venue_id}}
          AND  vfh.data_date = TRUNC(SYSDATE)
          AND  vfh.data_hour = (SELECT MAX(vfh2.data_hour)
                                FROM   FWBZ.table_venue_flow_hour vfh2
                                WHERE  vfh2.venue_id = {{venue_id}}
                                  AND  vfh2.data_date = TRUNC(SYSDATE))
          AND  ROWNUM = 1) AS average_duration,
       -- 人流峰值: 取 max_count 最大的那条
       (SELECT vfh.max_count
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = {{venue_id}}
          AND  vfh.data_date = TRUNC(SYSDATE)
        ORDER  BY vfh.max_count DESC
        AND  ROWNUM = 1) AS max_count,
       -- 峰值时间: 取 max_count 最大的那条
       (SELECT vfh.max_time
        FROM   FWBZ.table_venue_flow_hour vfh
        WHERE  vfh.venue_id = {{venue_id}}
          AND  vfh.data_date = TRUNC(SYSDATE)
        ORDER  BY vfh.max_count DESC
        AND  ROWNUM = 1) AS max_time
FROM   FWBZ.table_venue_info vi
WHERE  vi.id = {{venue_id}}
  AND  EXISTS (SELECT 1
               FROM   FWBZ.table_venue_flow_hour vfh3
               WHERE  vfh3.venue_id = {{venue_id}}
                 AND  vfh3.data_date = TRUNC(SYSDATE));
```

---

## 14. 投诉建议

### 涉及表
- `table_complaint_type` / `table_complaint_status` —— 字典
- `table_complaint_info` —— 投诉主表
- `table_complaint_record` —— 投诉流转记录

### 关键字段速记
- `table_complaint_info.status`：`待处理 / 处理中 / 已处理 / 已关闭 / 已驳回`
- `table_complaint_record.status_from` / `status_to` —— 状态变化

### 可回答的问题
1. 各类型投诉待处理数量
2. 某投诉完整处理过程
3. 近 30 天投诉量趋势
4. 各处理人处理的投诉量

### SQL 范式

**Q14.1 待处理投诉分类型**
```sql
SELECT t.type_name, COUNT(*) AS cnt
FROM   FWBZ.table_complaint_info ci
LEFT   JOIN FWBZ.table_complaint_type t ON t.id = ci.type_id
WHERE  ci.status = '待处理'
GROUP  BY t.type_name
ORDER  BY cnt DESC;
```

**Q14.2 投诉完整处理过程**
```sql
SELECT ci.id, ci.title, ci.complaint_date, ci.complaint_time, ci.status,
       cr.handle_date, cr.handle_time, cr.handler,
       cr.status_from, cr.status_to, cr.handle_content
FROM   FWBZ.table_complaint_info ci
LEFT   JOIN FWBZ.table_complaint_record cr ON cr.complaint_id = ci.id
WHERE  ci.id = {{complaint_id}}
ORDER  BY cr.handle_date, cr.handle_time;
```

**Q14.3 近 30 天投诉量趋势**
```sql
SELECT complaint_date, COUNT(*) AS cnt
FROM   FWBZ.table_complaint_info
WHERE  complaint_date >= SYSDATE - INTERVAL '30' DAY
GROUP  BY complaint_date
ORDER  BY complaint_date;
```

**Q14.4 各处理人处理量**
```sql
SELECT handler, COUNT(*) AS cnt
FROM   FWBZ.table_complaint_info
WHERE  status = '已处理'
  AND  handler IS NOT NULL
GROUP  BY handler
ORDER  BY cnt DESC;
```

---

## 15. 活动会议

### 涉及表
- `table_activeMeet_info` —— 活动主表
- `table_activeMeet_preparation_type` —— 筹备类型字典
- `table_activeMeets_device_type` —— 筹备类型 ↔ 设备类型 关联
- `table_activeMeet_preparation_info` —— 各活动的筹备进度
- `table_activeMeet_report` —— 活动总结报告

### 关键字段速记
- `table_activeMeet_info.active_progress`：`0~100` 进度百分比
- `table_activeMeet_preparation_info.status`：`0 未完成 / 1 已完成`
- `table_activeMeet_report.status`：`0 待总结 / 1 已总结`

### 可回答的问题
1. 当前进行中 / 待开始的活动
2. 某活动的筹备完成情况
3. 已结束活动的总结报告
4. 某活动总用电量、单人次能耗

### SQL 范式

**Q15.1 进行中的活动**
```sql
SELECT *
FROM   FWBZ.table_activeMeet_info
WHERE  start_date <= TRUNC(SYSDATE)
  AND  (start_date + 1) > TRUNC(SYSDATE)        -- 当天开始的活动
   OR  active_progress > 0 AND active_progress < 100
ORDER  BY start_date DESC;
```

**Q15.2 某活动筹备完成度**
```sql
SELECT pt.type_name,
       SUM(api.preparation_value) AS plan_value,
       SUM(api.real_value)        AS real_value,
       SUM(CASE WHEN api.status = 1 THEN 1 ELSE 0 END) AS done_cnt
FROM   FWBZ.table_activeMeet_preparation_info api
LEFT   JOIN FWBZ.table_activeMeet_preparation_type pt
       ON pt.id = api.active_meets_device_type_id
WHERE  api.active_meet_id = {{active_id}}
GROUP  BY pt.type_name;
```

**Q15.3 已总结报告**
```sql
SELECT *
FROM   FWBZ.table_activeMeet_report
WHERE  status = '1'
ORDER  BY start_date DESC;
```

**Q15.4 活动能耗 + 单人次能耗（用能耗表关联，需根据设备/计量点配置调整）**
```sql
SELECT r.active_name, r.start_date, r.end_date, r.day_number,
       r.consumption_electricity, r.passenger_flow, r.person_energy_consumption
FROM   FWBZ.table_activeMeet_report r
WHERE  r.active_name LIKE '%{{keyword}}%'
ORDER  BY r.start_date DESC;
```

---

## 16. 冷源系统 & 接口监控

### 涉及表
- `table_cold_source_history` —— 冷源遥测历史
- `table_tagid_info` / `table_page_info` —— 冷源 tag ↔ 前端字段映射
- `table_mqtt_history` —— MQTT 低压配电遥测
- `table_interface_info` —— 接口信息
- `table_interface_history` —— 接口请求历史
- `table_http_system` —— 系统接口
- `table_protocol_type_info` —— 接口协议字典

### 可回答的问题
1. 某 tag 最近 N 个遥测值
2. 哪些接口最近 5 分钟没心跳？
3. 接口平均响应时间 TOP10
4. 哪些接口调用量最大

### SQL 范式

**Q16.1 冷源某 tag 最近 N 个值**
```sql
SELECT *
FROM   FWBZ.table_cold_source_history
WHERE  tag_id = {{tag_id}}
ORDER  BY data_time DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

**Q16.2 接口心跳异常（5 分钟内无心跳）**
```sql
SELECT sys_name, interface_path, protocol_type_id, request_time,
       SYSDATE - request_time AS heartbeat_lag
FROM   FWBZ.table_interface_info
WHERE  request_time IS NULL
   OR  request_time < SYSDATE - INTERVAL '5' MINUTE;
```

**Q16.3 接口平均响应时间 TOP10**
```sql
SELECT i.sys_name, i.interface_path,
       AVG(h.response_time) AS avg_ms,
       COUNT(*)             AS call_cnt
FROM   FWBZ.table_interface_info i
LEFT   JOIN FWBZ.table_interface_history h
       ON h.system_id      = i.id
      AND h.clinet_date   >= SYSDATE - INTERVAL '1' DAY
GROUP  BY i.sys_name, i.interface_path
HAVING COUNT(*) > 0
ORDER  BY avg_ms DESC
FETCH  FIRST 10 ROWS ONLY;
```

**Q16.4 MQTT 低压配电某设备 key 最近值**
```sql
SELECT *
FROM   FWBZ.table_mqtt_history
WHERE  dev_keys    = '{{dev_keys}}'
  AND  unique_key  = '{{unique_key}}'
ORDER  BY time_stamp DESC
FETCH  FIRST {{top_n}} ROWS ONLY;
```

---

## 17. 权限与配置

### 涉及表
- `role_data_permission` —— 角色数据权限
- `business_config` —— 业务配置（KV）
- `unit_management` —— 计量单位（已在能源域列出）

### 可回答的问题
1. 某角色被授权了哪些资源？
2. 某业务配置项的当前值

### SQL 范式

**Q17.1 某角色授权资源**
```sql
SELECT permission_type, resource_id
FROM   FWBZ.role_data_permission
WHERE  role_code = '{{role_code}}';
```

**Q17.2 取业务配置值（KV）**
```sql
SELECT name, config_key, config_value, remark
FROM   FWBZ.business_config
WHERE  config_key = '{{config_key}}';
```

---

## 18. 跨域综合分析（精选）

> 这部分展示多个业务域表联合查询的范式。

### Q18.1 某场馆的"一次活动"综合报告
```sql
SELECT
  vi.venue_name,
  ai.active_name, ai.start_date, ai.end_time,
  ar.service_personnel, ar.complaints_total, ar.recommended_total,
  ar.device_failures_total, ar.consumption_electricity, ar.person_energy_consumption,
  ar.passenger_flow, ar.peak_flow, ar.exhibitors
FROM   FWBZ.table_venue_info        vi
LEFT   JOIN FWBZ.table_activeMeet_info  ai  ON ai.venue_id = vi.id
LEFT   JOIN FWBZ.table_activeMeet_report ar  ON ar.active_name = ai.active_name
WHERE  vi.id = {{venue_id}}
  AND  ai.start_date BETWEEN {{start}} AND {{end}};
```

### Q18.2 某空间"设备健康度"画像
```sql
SELECT
  COUNT(*)                                                            AS device_total,
  SUM(CASE WHEN d.run_state     = '运行'  THEN 1 ELSE 0 END)          AS running,
  SUM(CASE WHEN d.last_gather_time < SYSDATE - INTERVAL '1' HOUR
           OR d.last_gather_time IS NULL THEN 1 ELSE 0 END)            AS offline,
  COUNT(DISTINCT rec.id)                                               AS alarm_cnt,
  COUNT(DISTINCT far.id)                                              AS fire_alarm_cnt
FROM   FWBZ.device d
LEFT   JOIN FWBZ.alarm_record rec
       ON rec.device_id = d.id
      AND rec.alarm_time >= SYSDATE - INTERVAL '{{n}}' DAY
LEFT   JOIN FWBZ.table_fire_alarm_record far
       ON far.device_id   = d.id
      AND far.alarm_time >= SYSDATE - INTERVAL '{{n}}' DAY
WHERE  d.space_id = {{space_id}};
```

### Q18.3 "能碳看板" —— 某能介本月能耗、折标煤、碳排、成本
```sql
WITH energy_sum AS (
   SELECT mp.id AS metering_point_id, mp.node_name, mp.type,
          SUM(mpd.value) AS value
   FROM   FWBZ.metering_point mp
   JOIN   FWBZ.metering_point_data_month mpd ON mpd.metering_point_id = mp.id
   WHERE  mpd.time BETWEEN {{start}} AND {{end}}
   GROUP  BY mp.id, mp.node_name, mp.type
)
SELECT es.node_name,
       es.value                                  AS energy,
       es.value * scc.eccsc                      AS coal_equivalent,   -- 折标煤
       es.value * cef.coefficient                AS carbon,            -- 碳排
       es.value * ep.unit_price                  AS cost
FROM   energy_sum es
LEFT   JOIN FWBZ.standard_coal_coefficient   scc ON scc.energy_medium = es.type
LEFT   JOIN FWBZ.carbon_emission_factor       cef ON 1 = 1                -- 按业务规则匹配
LEFT   JOIN FWBZ.energy_price                 ep  ON ep.energy_medium   = es.type;
```

### Q18.4 设备"告警 → 工单 → 完成"全链路（待与工单系统集成）
```sql
SELECT rec.id AS alarm_id, rec.alarm_content, rec.alarm_time,
       rec.transfer_event_time, rec.event_completion_time, rec.event_id,
       per.point_name, per.success_flag, per.executed_time
FROM   FWBZ.alarm_record rec
LEFT   JOIN FWBZ.log_point_execute_record per
       ON per.strategy_execute_id = rec.event_id
WHERE  rec.event_id = '{{event_id}}';
```

---

## 19. 达梦 8.0 SQL 注意事项

1. **分页**：推荐 `FETCH FIRST n ROWS ONLY`（标准 SQL 兼容）；亦支持 `LIMIT n OFFSET m`。
2. **递归查询**：达梦支持 `START WITH ... CONNECT BY PRIOR ... ORDER SIBLINGS BY ...`。
3. **空值排序**：`ORDER BY col NULLS FIRST / NULLS LAST`。
4. **时间差**：`EXTRACT(EPOCH FROM (SYSDATE - col)) / 3600.0`；或 `SYSDATE - col` 直接相减（达梦返回 `INTERVAL DAY TO SECOND`）。
5. **字符串拼接**：`||` 或 `CONCAT(str1, str2)`，二者在达梦中等价。
6. **DECODE vs CASE**：达梦对 `DECODE` 兼容良好，可优先用 `DECODE` 做枚举翻译。
7. **CHAR 与 VARCHAR**：`"FWBZ".alarm_record.alarm_status` 是 `VARCHAR(1 CHAR)`，比较时注意 `'1'` 而非数字 1。
8. **大对象**：`ai_report_history.content` 为 `CLOB`、`project.project_files` 为 `CLOB`；如需检索请考虑 FULLTEXT 或 ETL。
9. **触发器**：`table_event_notify`、`table_fire_alarm_record` 自带 BEFORE UPDATE 触发器维护 `gmt_modified`。
10. **多租户**：`sys_log.tenant_id` INT，需在跨租户查询时显式加 `WHERE tenant_id = ?`。

---

## 20. 常见问题速查

| 业务问题 | 涉及表 | 速查公式 |
|----------|--------|----------|
| 现在有 N 条告警？ | `alarm_record` | `WHERE alarm_status = '1' AND alarm_time >= ...` |
| X 设备当前值？ | `data_real` / `device_attribute` | `WHERE device_id = ?` |
| X 能介本月能耗？ | `metering_point_data_month` + `metering_point` | `SUM(value)` 分组 |
| X 设备最近是否离线？ | `device` | `last_gather_time < SYSDATE - N HOUR` |
| 当前活动？ | `table_activeMeet_info` | `active_progress BETWEEN 0 AND 100` |
| 紧急消防报警？ | `table_fire_alarm_record` | `alarm_level = 4 AND handle_status = 0` |
| 摄像头离线清单？ | `camera_info` / `table_camera_resource` | `online = 0` |
| 今日进馆人数？ | `table_venue_flow_hour` | `data_date = TRUNC(SYSDATE)`（取 data_hour 最大的那条 today_in_count） |
| 待处理投诉？ | `table_complaint_info` | `status = '待处理'` |
| 死规则？ | `alarm_rules NOT EXISTS alarm_record` | 见 Q2.3 |
| 单次执行成功率？ | `log_strategy_execute_record` | `SUM(CASE WHEN success_flag = '成功' ...)` |
| 接口慢调用？ | `sys_log` / `table_interface_history` | `ORDER BY cost_time DESC` |

---

> **维护建议**
> 1. 任何表结构变更需同步更新本文件对应章节；
> 2. SQL 范式遇到不兼容时优先用 `EXPLAIN PLAN` 验证执行路径；
> 3. 高频报表建议落到物化视图或单独宽表，避免每次实时聚合大表（`alarm_record`、`device_attribute_history`、`metering_point_data_*`）。
