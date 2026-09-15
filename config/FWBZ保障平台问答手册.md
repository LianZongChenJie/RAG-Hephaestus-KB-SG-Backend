# 服贸会小镇服务保障平台 · SQL 范式

> 与 `FWBZ保障平台问题清单.md` **同号**。JOIN 按 `hephaestus_meta_nl_relation` + 代码里补的 `device.category_id → equipment_category`。
> 达梦 8：表列双引号、`LIMIT n`、时间用 `SYSDATE` / `TRUNC`。不选 CLOB/TEXT（`true_formula`、`alarm_content`、`sys_log.log_content`）。
> `metering_point_data_*` 现网为空，能耗事实表用 `data_day`（`data_day.device_id = device.id`）。

---

## 2. 智慧能源

**Q2.1 能源计量规则**
```sql
SELECT mp."id", mp."node_code", mp."node_name", mp."type",
       mp."category_id", ec."category_name", mp."space_id", s."space_name", mp."sort"
FROM "FWBZ"."metering_point" mp
LEFT JOIN "FWBZ"."equipment_category" ec ON ec."id" = mp."category_id"
LEFT JOIN "FWBZ"."space" s ON s."id" = mp."space_id"
ORDER BY mp."sort", mp."id"
LIMIT 500
```

**Q2.2 能源计量数据包括：空调，新风，电表等设备的能耗计量数据**
```sql
SELECT d."device_name", d."device_code", ec."category_name",
       dd."time", dd."value"
FROM "FWBZ"."data_day" dd
INNER JOIN "FWBZ"."device" d ON d."id" = dd."device_id"
INNER JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
WHERE dd."time" >= TRUNC(SYSDATE) - 7
  AND (
    ec."category_name" IN (
      '空调机组', '新风机组', '风机盘管', '热回收机组',
      '电表', '低压配电', '配电设备'
    )
    OR ec."pid" IN (8, 17, 25, 37)
  )
ORDER BY dd."time" DESC, dd."value" DESC
LIMIT 500
```

**Q2.3 服贸会区域总耗电**
```sql
SELECT mp."node_name", SUM(dd."value") AS "value"
FROM "FWBZ"."metering_point" mp
INNER JOIN "FWBZ"."metering_point_rel" rel
  ON rel."metering_point_id" = mp."id" AND rel."rel_type" = '1'
INNER JOIN "FWBZ"."data_day" dd ON dd."device_id" = rel."rel_id"
WHERE mp."node_name" = '服贸会区域总耗电'
  AND dd."time" >= TRUNC(SYSDATE, 'MM')
GROUP BY mp."node_name"
LIMIT 200
```

**Q2.4 暖通设备概览**
```sql
SELECT ec."category_name", COUNT(d."id") AS "cnt"
FROM "FWBZ"."device" d
INNER JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
WHERE ec."category_name" IN (
  '空调机组', '新风机组', '风机盘管', '热回收机组', '排风机',
  '送排风', '卫生间排风', '新风和排风机', '空调和排风', '空调和新风和排风'
)
GROUP BY ec."category_name"
ORDER BY "cnt" DESC
LIMIT 200
```

**Q2.5 暖通设备管控**
```sql
SELECT d."id", d."device_code", d."device_name", d."category_id",
       ec."category_name", d."run_state", d."last_gather_time", d."space_id"
FROM "FWBZ"."device" d
INNER JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
WHERE ec."category_name" IN (
  '空调机组', '新风机组', '风机盘管', '热回收机组', '排风机',
  '送排风', '卫生间排风', '新风和排风机', '空调和排风', '空调和新风和排风'
)
ORDER BY d."run_state", ec."category_name", d."device_name"
LIMIT 500
```

**Q2.6 冷源设备概览**
```sql
SELECT cc."category_name", COUNT(d."id") AS "cnt"
FROM "FWBZ"."cold_source_device" d
LEFT JOIN "FWBZ"."cold_source_equipment_category" cc ON cc."id" = d."category_id"
GROUP BY cc."category_name"
ORDER BY "cnt" DESC
LIMIT 200
```

**Q2.7 冷源设备管控**
```sql
SELECT d."id", d."device_code", d."device_name", d."category_id",
       cc."category_name", d."status", d."last_time", d."system_code"
FROM "FWBZ"."cold_source_device" d
LEFT JOIN "FWBZ"."cold_source_equipment_category" cc ON cc."id" = d."category_id"
ORDER BY cc."category_name", d."device_name"
LIMIT 500
```

**Q2.8 能源优化**
```sql
SELECT c."id", c."name", c."status", c."remark", c."sort",
       ch."chart_name", ch."chart_type", ch."point_id", ch."unit"
FROM "FWBZ"."energy_analysis_config" c
LEFT JOIN "FWBZ"."energy_analysis_chart" ch ON ch."config_id" = c."id"
ORDER BY c."sort", ch."sort"
LIMIT 200
```

---

## 3. 韧性安全

**Q3.1 门禁设备管理**
```sql
SELECT
  '门禁' AS "category_name",
  d."id",
  d."name" AS "device_name",
  d."index_code",
  CAST(d."door_state" AS VARCHAR(16)) AS "status",
  d."region_name",
  acs."name" AS "spec"
FROM "FWBZ"."table_door_resource" d
LEFT JOIN "FWBZ"."table_acs_device" acs
  ON acs."index_code" = d."parent_index_code"
ORDER BY d."name"
LIMIT 200
```

**Q3.2 门禁控制管理**
```sql
SELECT "id", "name", "index_code", "dev_type_desc", "online",
       "ip", "region_name", "manufacturer"
FROM "FWBZ"."table_acs_device"
ORDER BY "online" DESC, "name"
LIMIT 500
```

---

## 4. 照明控制

**Q4.1 照明设备概览**
```sql
SELECT c."status", COUNT(*) AS "cnt"
FROM "FWBZ"."lighting_circuit" c
GROUP BY c."status"
ORDER BY "cnt" DESC
LIMIT 200
```

**Q4.2 照明设备监控**
```sql
SELECT c."id", c."circuit_name", c."circuit_code", c."status", c."comstat",
       c."area_id", a."area_name", c."start_time", c."operator_by", c."operator_time"
FROM "FWBZ"."lighting_circuit" c
LEFT JOIN "FWBZ"."lighting_area" a ON a."id" = c."area_id"
ORDER BY c."status", a."area_name", c."circuit_name"
LIMIT 500
```

**Q4.3 照明能耗统计**
```sql
SELECT a."area_name", c."circuit_name", c."status", c."all_duration"
FROM "FWBZ"."lighting_circuit" c
LEFT JOIN "FWBZ"."lighting_area" a ON a."id" = c."area_id"
ORDER BY c."all_duration" DESC
LIMIT 500
```

---

## 5. 会展服务

---

## 6. 场馆运营

**Q6.1 场馆客流**
```sql
SELECT vi."venue_name", f."today_in_count", f."today_now_count",
       f."max_count", f."max_time", f."average_duration", f."data_hour"
FROM "FWBZ"."table_venue_flow_hour" f
INNER JOIN "FWBZ"."table_venue_info" vi ON vi."id" = f."venue_id"
WHERE f."data_date" = TRUNC(SYSDATE)
  AND f."data_hour" = (
    SELECT MAX(f2."data_hour")
    FROM "FWBZ"."table_venue_flow_hour" f2
    WHERE f2."venue_id" = f."venue_id"
      AND f2."data_date" = TRUNC(SYSDATE)
  )
ORDER BY vi."id"
LIMIT 200
```

**Q6.2 场馆排期**
```sql
SELECT a."active_name", vi."venue_name", a."start_date",
       a."start_time", a."end_time", a."people_quantity", a."active_progress"
FROM "FWBZ"."table_activeMeet_info" a
LEFT JOIN "FWBZ"."table_venue_info" vi ON vi."id" = a."venue_id"
ORDER BY a."start_date" DESC
LIMIT 200
```

---

## 7. 设备管理

**Q7.1 查看设备列表，按照楼控设备，冷源设备，电表设备，安防设备分组查看**
```sql
SELECT '楼控设备' AS "category_name", COUNT(*) AS "cnt"
FROM "FWBZ"."device"
WHERE "device_type" = '2'
UNION ALL
SELECT '电表设备', COUNT(*)
FROM "FWBZ"."device"
WHERE "device_type" = '1'
UNION ALL
SELECT '冷源设备', COUNT(*)
FROM "FWBZ"."cold_source_device"
UNION ALL
SELECT '安防设备', COUNT(*)
FROM (
  SELECT "id" FROM "FWBZ"."table_camera_resource"
  UNION ALL
  SELECT "id" FROM "FWBZ"."table_door_resource"
  UNION ALL
  SELECT "id" FROM "FWBZ"."table_acs_device"
) sec
```

**Q7.2 查看楼控设备**
```sql
SELECT d."id", d."device_code", d."device_name", d."category_id",
       ec."category_name", d."run_state", d."last_gather_time", d."space_id"
FROM "FWBZ"."device" d
LEFT JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
WHERE d."device_type" = '2'
ORDER BY ec."category_name", d."device_name"
LIMIT 500
```


**Q7.3 查看冷源设备**
```sql
SELECT d."id", d."device_code", d."device_name", d."category_id",
       cc."category_name", d."status", d."last_time"
FROM "FWBZ"."cold_source_device" d
LEFT JOIN "FWBZ"."cold_source_equipment_category" cc ON cc."id" = d."category_id"
ORDER BY cc."category_name", d."device_name"
LIMIT 500
```

**Q7.4 查看电表设备**
```sql
SELECT d."id", d."device_code", d."device_name", d."category_id",
       ec."category_name", d."run_state", d."last_gather_time", d."space_id"
FROM "FWBZ"."device" d
LEFT JOIN "FWBZ"."equipment_category" ec ON ec."id" = d."category_id"
WHERE d."device_type" = '1'
ORDER BY ec."category_name", d."device_name"
LIMIT 500
```

**Q7.5 查看安防设备**
```sql
SELECT * FROM (
  SELECT
    '摄像头' AS "category_name",
    c."id",
    c."name" AS "device_name",
    c."index_code",
    CASE
      WHEN c."online" = 1 THEN '在线'
      WHEN c."online" = 0 THEN '离线'
      ELSE '未知'
    END AS "online",
    NVL(c."region_name", c."install_location") AS "region_name",
    CASE c."camera_type"
      WHEN 0 THEN '枪机'
      WHEN 1 THEN '半球'
      WHEN 2 THEN '快球'
      WHEN 3 THEN '带云台枪机'
      ELSE '摄像头'
    END AS "device_type"
  FROM "FWBZ"."table_camera_resource" c
  ORDER BY c."online" DESC, c."name"
  LIMIT 200
) 
UNION ALL
SELECT * FROM (
  SELECT
    '门禁' AS "category_name",
    d."id",
    d."name" AS "device_name",
    d."index_code",
    CASE
      WHEN CAST(d."door_state" AS VARCHAR) = '3' THEN '离线'
      WHEN d."door_state" IS NULL THEN '未知'
      ELSE '在线'
    END AS "online",
    d."region_name",
    '门禁点' AS "device_type"
  FROM "FWBZ"."table_door_resource" d
  ORDER BY d."name"
  LIMIT 200
) door
UNION ALL
SELECT * FROM (
  SELECT
    '门禁控制器' AS "category_name",
    a."id",
    a."name" AS "device_name",
    a."index_code",
    CASE
      WHEN CAST(a."online" AS VARCHAR) IN ('1', '在线') THEN '在线'
      WHEN CAST(a."online" AS VARCHAR) IN ('0', '离线') THEN '离线'
      ELSE '未知'
    END AS "online",
    a."region_name",
    NVL(a."dev_type_desc", '未知型号') AS "device_type"
  FROM "FWBZ"."table_acs_device" a
  ORDER BY a."online" DESC, a."name"
  LIMIT 200
) ctl
```

**Q7.6 查看设备模型**
```sql
SELECT m."id", m."model_name", m."category_id", ec."category_name"
FROM "FWBZ"."device_model" m
LEFT JOIN "FWBZ"."equipment_category" ec ON ec."id" = m."category_id"
ORDER BY m."id"
LIMIT 200
```

---

## 8. 故障告警

**Q8.1 报警概览**
```sql
SELECT "alarm_status", "device_name" ,"space_name" , "alarm_content" , "alarm_category_name" ,"alarm_level_name"  FROM "FWBZ"."alarm_record"
LIMIT 200
```

**Q8.2 报警处理详细查询**
```sql
SELECT a."id", a."device_name", a."space_name", a."alarm_category_name",
       a."alarm_level_name", a."alarm_status", a."alarm_time",
       a."point_name", a."value", a."condition_value", a."charge_person_name"
FROM "FWBZ"."alarm_record" a
ORDER BY a."alarm_status", a."alarm_time" DESC
LIMIT 500
```

---

## 9. 物联网

---

## 11. AI运行报告
