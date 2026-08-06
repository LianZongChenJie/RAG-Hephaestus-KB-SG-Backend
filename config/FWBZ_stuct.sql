/*
 Navicat Premium Dump SQL

 Source Server         : 51_DM
 Source Server Type    : Dameng
 Source Server Version : 80000 (08.00.00)
 Source Host           : 192.168.204.51:5238
 Source Schema         : FWBZ

 Target Server Type    : Dameng
 Target Server Version : 80000 (08.00.00)
 File Encoding         : 65001

 Date: 06/08/2026 08:59:27
*/


-- ----------------------------
-- Table structure for alarm_category
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."alarm_category";
CREATE TABLE "FWBZ"."alarm_category" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "alarm_category_name" VARCHAR(255 CHAR) NOT NULL,
  "alarm_category_code" VARCHAR(255 CHAR) NOT NULL,
  "sort" INT NOT NULL,
  "status" VARCHAR(2 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."alarm_category"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."alarm_category"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."alarm_category"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."alarm_category"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."alarm_category"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."alarm_category"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."alarm_category"."alarm_category_name" IS '类别名称';
COMMENT ON COLUMN "FWBZ"."alarm_category"."alarm_category_code" IS '类别编号';
COMMENT ON COLUMN "FWBZ"."alarm_category"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."alarm_category"."status" IS '状态。启用：1；禁用：0；';
COMMENT ON TABLE "FWBZ"."alarm_category" IS '报警类别';

-- ----------------------------
-- Table structure for alarm_level
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."alarm_level";
CREATE TABLE "FWBZ"."alarm_level" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "alarm_level_code" VARCHAR(255 CHAR) NOT NULL,
  "alarm_level_name" VARCHAR(255 CHAR) NOT NULL,
  "sort" INT NOT NULL,
  "status" VARCHAR(2 CHAR) NOT NULL,
  "alarm_level_color" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."alarm_level"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."alarm_level"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."alarm_level"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."alarm_level"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."alarm_level"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."alarm_level"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."alarm_level"."alarm_level_code" IS '等级编号';
COMMENT ON COLUMN "FWBZ"."alarm_level"."alarm_level_name" IS '等级名称';
COMMENT ON COLUMN "FWBZ"."alarm_level"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."alarm_level"."status" IS '状态。启用：1；禁用：0';
COMMENT ON COLUMN "FWBZ"."alarm_level"."alarm_level_color" IS '告警颜色';
COMMENT ON TABLE "FWBZ"."alarm_level" IS '报警级别';

-- ----------------------------
-- Table structure for alarm_record
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."alarm_record";
CREATE TABLE "FWBZ"."alarm_record" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "alarm_rule_id" BIGINT,
  "device_id" BIGINT,
  "device_name" VARCHAR(255 CHAR),
  "space_id" BIGINT,
  "space_name" VARCHAR(255 CHAR),
  "alarm_content" TEXT,
  "alarm_time" TIMESTAMP,
  "alarm_category_id" BIGINT,
  "alarm_category_name" VARCHAR(255 CHAR),
  "alarm_level_id" BIGINT,
  "alarm_level_name" VARCHAR(255 CHAR),
  "charge_person" BIGINT,
  "charge_person_name" VARCHAR(255 CHAR),
  "alarm_status" VARCHAR(1 CHAR),
  "point_id" BIGINT,
  "point_name" VARCHAR(255 CHAR),
  "value" VARCHAR(255 CHAR),
  "condition_value" VARCHAR(255 CHAR),
  "operator" VARCHAR(255 CHAR),
  "time_granularity" VARCHAR(255 CHAR),
  "alarm_rule_point_id" BIGINT,
  "device_category_id" BIGINT,
  "alarm_level_color" VARCHAR(50),
  "event_id" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."alarm_record"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."alarm_record"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."alarm_record"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."alarm_record"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."alarm_record"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."alarm_record"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_rule_id" IS '告警规则ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."device_id" IS '设备ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."space_id" IS '空间ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_content" IS '告警内容';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_time" IS '告警时间';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_category_id" IS '告警类别ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_category_name" IS '告警类别名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_level_id" IS '告警级别ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_level_name" IS '告警级别名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."charge_person" IS '负责人ID';
COMMENT ON COLUMN "FWBZ"."alarm_record"."charge_person_name" IS '负责人名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_status" IS '告警状态【1-未处理，2-已消除】';
COMMENT ON COLUMN "FWBZ"."alarm_record"."point_id" IS '点位id';
COMMENT ON COLUMN "FWBZ"."alarm_record"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."alarm_record"."value" IS '告警值';
COMMENT ON COLUMN "FWBZ"."alarm_record"."condition_value" IS '阈值';
COMMENT ON COLUMN "FWBZ"."alarm_record"."operator" IS '条件';
COMMENT ON COLUMN "FWBZ"."alarm_record"."time_granularity" IS '时间粒度';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_rule_point_id" IS '告警规则点位id';
COMMENT ON COLUMN "FWBZ"."alarm_record"."device_category_id" IS '设备类别id';
COMMENT ON COLUMN "FWBZ"."alarm_record"."alarm_level_color" IS '报警级别颜色';
COMMENT ON COLUMN "FWBZ"."alarm_record"."event_id" IS '事件id';
COMMENT ON TABLE "FWBZ"."alarm_record" IS '告警记录表';

-- ----------------------------
-- Table structure for alarm_rule_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."alarm_rule_point";
CREATE TABLE "FWBZ"."alarm_rule_point" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "alarm_rule_id" BIGINT,
  "device_id" BIGINT NOT NULL,
  "device_name" VARCHAR(255 CHAR),
  "point_id" BIGINT,
  "point_name" VARCHAR(255 CHAR),
  "time_granularity" VARCHAR(50 CHAR),
  "operator" VARCHAR(10 CHAR) NOT NULL,
  "condition_value" VARCHAR(255 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."alarm_rule_id" IS '告警规则ID';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."device_id" IS '设备ID';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."point_id" IS '点位ID';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."time_granularity" IS '时间粒度（hour/day/month/year）';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."operator" IS '条件运算符（如 >, <, = 等）';
COMMENT ON COLUMN "FWBZ"."alarm_rule_point"."condition_value" IS '条件值';
COMMENT ON TABLE "FWBZ"."alarm_rule_point" IS '告警规则设备点位配置表';

-- ----------------------------
-- Table structure for alarm_rules
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."alarm_rules";
CREATE TABLE "FWBZ"."alarm_rules" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "rule_code" VARCHAR(255 CHAR),
  "rule_name" VARCHAR(255 CHAR),
  "alarm_category_id" BIGINT,
  "alarm_level_id" BIGINT,
  "frequency" INT,
  "frequency_unit" VARCHAR(50 CHAR),
  "point_type" VARCHAR(50 CHAR),
  "notice_user" VARCHAR(2000 CHAR),
  "enabled_status" VARCHAR(2 CHAR),
  "alarm_category_name" VARCHAR(255 CHAR),
  "alarm_level_name" VARCHAR(255 CHAR),
  "alarm_level_color" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."alarm_rules"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."rule_code" IS '规则编号';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."rule_name" IS '规则名称';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."alarm_category_id" IS '报警类别';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."alarm_level_id" IS '报警等级';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."frequency" IS '频率';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."frequency_unit" IS '频率单位';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."point_type" IS '报警点位类型（instant/accumulate）';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."notice_user" IS '通知用户ID';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."enabled_status" IS '启用状态【0-禁用，1-启用】';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."alarm_category_name" IS '报警类别名称';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."alarm_level_name" IS '报警级别名称';
COMMENT ON COLUMN "FWBZ"."alarm_rules"."alarm_level_color" IS '报警颜色';
COMMENT ON TABLE "FWBZ"."alarm_rules" IS '告警规则表';

-- ----------------------------
-- Table structure for building_control_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."building_control_point";
CREATE TABLE "FWBZ"."building_control_point" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "gateway_adr" VARCHAR(255 CHAR) NOT NULL,
  "bacnet_adr" VARCHAR(255 CHAR) NOT NULL,
  "value" VARCHAR(255 CHAR),
  "collection_time" TIMESTAMP,
  "content" VARCHAR(2000 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."building_control_point"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."building_control_point"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."building_control_point"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."building_control_point"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."building_control_point"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."building_control_point"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."building_control_point"."value" IS '采集值';
COMMENT ON COLUMN "FWBZ"."building_control_point"."collection_time" IS '采集时间';
COMMENT ON TABLE "FWBZ"."building_control_point" IS '楼宇控制点表';

-- ----------------------------
-- Table structure for building_control_point_history
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."building_control_point_history";
CREATE TABLE "FWBZ"."building_control_point_history" (
  "id" BIGINT NOT NULL,
  "point_id" BIGINT NOT NULL,
  "value" VARCHAR(255 CHAR),
  "collection_time" TIMESTAMP
)
;

-- ----------------------------
-- Table structure for business_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."business_config";
CREATE TABLE "FWBZ"."business_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "name" VARCHAR(255 CHAR),
  "config_key" VARCHAR(255 CHAR),
  "config_value" VARCHAR(2000 CHAR),
  "remark" VARCHAR(200)
)
;
COMMENT ON COLUMN "FWBZ"."business_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."business_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."business_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."business_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."business_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."business_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."business_config"."name" IS '业务说明';
COMMENT ON COLUMN "FWBZ"."business_config"."config_key" IS '唯一标识';
COMMENT ON COLUMN "FWBZ"."business_config"."config_value" IS '值';
COMMENT ON COLUMN "FWBZ"."business_config"."remark" IS '备注';
COMMENT ON TABLE "FWBZ"."business_config" IS '业务配置表';

-- ----------------------------
-- Table structure for carbon_emission_factor
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."carbon_emission_factor";
CREATE TABLE "FWBZ"."carbon_emission_factor" (
  "id" VARCHAR(36 CHAR) NOT NULL,
  "create_by" VARCHAR(50 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(50 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(64 CHAR),
  "carbon_factor_name" VARCHAR(32 CHAR),
  "coefficient" VARCHAR(32 CHAR),
  "unit" VARCHAR(32 CHAR),
  "sort" INT,
  "remark" VARCHAR(32 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."carbon_factor_name" IS '碳因子名称';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."coefficient" IS '系数';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."unit" IS '单位';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."carbon_emission_factor"."remark" IS '说明';

-- ----------------------------
-- Table structure for data_amend_log
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_amend_log";
CREATE TABLE "FWBZ"."data_amend_log" (
  "id" "bigint" NOT NULL,
  "device_id" "bigint",
  "hour_data_id" "bigint",
  "time" TIMESTAMP,
  "start_value" DECIMAL(22,6),
  "end_value" DECIMAL(22,6),
  "compute_value" DECIMAL(22,6),
  "original_value" DECIMAL(22,6),
  "value" DECIMAL(22,6),
  "update_by" VARCHAR(50),
  "update_time" TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."data_amend_log"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."hour_data_id" IS '小时能耗id';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."time" IS '时间';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."start_value" IS '起始值';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."end_value" IS '结束值';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."compute_value" IS '计算值';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."original_value" IS '修正前';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."value" IS '修正后';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."update_by" IS '修正人';
COMMENT ON COLUMN "FWBZ"."data_amend_log"."update_time" IS '修正时间';
COMMENT ON TABLE "FWBZ"."data_amend_log" IS '数据修正日志';

-- ----------------------------
-- Table structure for data_day
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_day";
CREATE TABLE "FWBZ"."data_day" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "value" DECIMAL(38,4),
  "time" TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."data_day"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."data_day"."value" IS '数值';
COMMENT ON COLUMN "FWBZ"."data_day"."time" IS '时间';
COMMENT ON TABLE "FWBZ"."data_day" IS '日数据';

-- ----------------------------
-- Table structure for data_hour
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_hour";
CREATE TABLE "FWBZ"."data_hour" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "value" DECIMAL(38,4),
  "time" TIMESTAMP,
  "start_value" DECIMAL(38,4),
  "end_value" DECIMAL(38,4),
  "compute_value" DECIMAL(38,4),
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP
)
;

-- ----------------------------
-- Table structure for data_minute
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_minute";
CREATE TABLE "FWBZ"."data_minute" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "time" TIMESTAMP,
  "start_value" DECIMAL(19,2),
  "end_value" DECIMAL(19,2),
  "value" DECIMAL(10,2)
)
;

-- ----------------------------
-- Table structure for data_month
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_month";
CREATE TABLE "FWBZ"."data_month" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "value" DECIMAL(38,4),
  "time" TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."data_month"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."data_month"."value" IS '数值';
COMMENT ON COLUMN "FWBZ"."data_month"."time" IS '时间';
COMMENT ON TABLE "FWBZ"."data_month" IS '月数据';

-- ----------------------------
-- Table structure for data_real
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_real";
CREATE TABLE "FWBZ"."data_real" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "value" DECIMAL(38,4),
  "time" TIMESTAMP
)
;

-- ----------------------------
-- Table structure for data_year
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."data_year";
CREATE TABLE "FWBZ"."data_year" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "value" DECIMAL(38,4),
  "time" TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."data_year"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."data_year"."value" IS '数值';
COMMENT ON COLUMN "FWBZ"."data_year"."time" IS '时间';
COMMENT ON TABLE "FWBZ"."data_year" IS '年数据';

-- ----------------------------
-- Table structure for device
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device";
CREATE TABLE "FWBZ"."device" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_code" VARCHAR(255 CHAR),
  "device_name" VARCHAR(255 CHAR),
  "category_id" BIGINT,
  "space_id" BIGINT,
  "magnification" DECIMAL(19,4),
  "automatic_algorithm" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT,
  "run_state" VARCHAR(255 CHAR),
  "model_id" BIGINT,
  "device_type" VARCHAR(2 CHAR),
  "last_gather_time" TIMESTAMP,
  "venue_id" BIGINT
)
;
COMMENT ON COLUMN "FWBZ"."device"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device"."device_code" IS '设备编号';
COMMENT ON COLUMN "FWBZ"."device"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."device"."category_id" IS '设备类别id';
COMMENT ON COLUMN "FWBZ"."device"."space_id" IS '空间位置id';
COMMENT ON COLUMN "FWBZ"."device"."magnification" IS '倍率';
COMMENT ON COLUMN "FWBZ"."device"."automatic_algorithm" IS '自动算法';
COMMENT ON COLUMN "FWBZ"."device"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."device"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."device"."run_state" IS '运行状态';
COMMENT ON COLUMN "FWBZ"."device"."model_id" IS '设备模型id';
COMMENT ON COLUMN "FWBZ"."device"."device_type" IS '设备分类。仪表：1；设备：2；';
COMMENT ON COLUMN "FWBZ"."device"."last_gather_time" IS '最后采集时间';
COMMENT ON COLUMN "FWBZ"."device"."venue_id" IS '场馆id';
COMMENT ON TABLE "FWBZ"."device" IS '设备基础信息';

-- ----------------------------
-- Table structure for device_251126
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_251126";
CREATE TABLE "FWBZ"."device_251126" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_code" VARCHAR(255 CHAR),
  "device_name" VARCHAR(255 CHAR),
  "category_id" BIGINT,
  "space_id" BIGINT,
  "magnification" DECIMAL(19,4),
  "automatic_algorithm" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT,
  "run_state" VARCHAR(255 CHAR),
  "model_id" BIGINT,
  "device_type" VARCHAR(2 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."device_251126"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_251126"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_251126"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_251126"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_251126"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_251126"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_251126"."device_code" IS '设备编号';
COMMENT ON COLUMN "FWBZ"."device_251126"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."device_251126"."category_id" IS '设备类别id';
COMMENT ON COLUMN "FWBZ"."device_251126"."space_id" IS '空间位置id';
COMMENT ON COLUMN "FWBZ"."device_251126"."magnification" IS '倍率';
COMMENT ON COLUMN "FWBZ"."device_251126"."automatic_algorithm" IS '自动算法';
COMMENT ON COLUMN "FWBZ"."device_251126"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."device_251126"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."device_251126"."run_state" IS '运行状态';
COMMENT ON COLUMN "FWBZ"."device_251126"."model_id" IS '设备模型id';
COMMENT ON COLUMN "FWBZ"."device_251126"."device_type" IS '设备分类。仪表：1；设备：2；';
COMMENT ON TABLE "FWBZ"."device_251126" IS '设备基础信息';

-- ----------------------------
-- Table structure for device_attribute
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute";
CREATE TABLE "FWBZ"."device_attribute" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_id" BIGINT,
  "attribute_name" VARCHAR(255 CHAR),
  "attribute_code" VARCHAR(255 CHAR),
  "unit" VARCHAR(255 CHAR),
  "readwrite_level" VARCHAR(255 CHAR),
  "sort" INT,
  "value" DECIMAL(19,4),
  "gather_time" TIMESTAMP,
  "acquisition_coding" VARCHAR(255 CHAR),
  "value_type" VARCHAR(50),
  "value_config" VARCHAR(2000)
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_attribute"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_attribute"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_attribute"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_attribute"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_attribute"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."device_attribute"."attribute_name" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."device_attribute"."attribute_code" IS '属性编码';
COMMENT ON COLUMN "FWBZ"."device_attribute"."unit" IS '单位';
COMMENT ON COLUMN "FWBZ"."device_attribute"."readwrite_level" IS '读写等级';
COMMENT ON COLUMN "FWBZ"."device_attribute"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."device_attribute"."value" IS '采集值';
COMMENT ON COLUMN "FWBZ"."device_attribute"."gather_time" IS '采集时间';
COMMENT ON COLUMN "FWBZ"."device_attribute"."acquisition_coding" IS '采集编码';
COMMENT ON COLUMN "FWBZ"."device_attribute"."value_type" IS '属性值类型';
COMMENT ON COLUMN "FWBZ"."device_attribute"."value_config" IS '属性值配置';
COMMENT ON TABLE "FWBZ"."device_attribute" IS '设备基础信息';

-- ----------------------------
-- Table structure for device_attribute_251201
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute_251201";
CREATE TABLE "FWBZ"."device_attribute_251201" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_id" BIGINT,
  "attribute_name" VARCHAR(255 CHAR),
  "attribute_code" VARCHAR(255 CHAR),
  "unit" VARCHAR(255 CHAR),
  "readwrite_level" VARCHAR(255 CHAR),
  "sort" INT,
  "value" DECIMAL(19,4),
  "gather_time" TIMESTAMP,
  "acquisition_coding" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."attribute_name" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."attribute_code" IS '属性编码';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."gather_time" IS '采集时间';
COMMENT ON COLUMN "FWBZ"."device_attribute_251201"."acquisition_coding" IS '采集编码';
COMMENT ON TABLE "FWBZ"."device_attribute_251201" IS '设备基础信息';

-- ----------------------------
-- Table structure for device_attribute_251209
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute_251209";
CREATE TABLE "FWBZ"."device_attribute_251209" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_id" BIGINT,
  "attribute_name" VARCHAR(255 CHAR),
  "attribute_code" VARCHAR(255 CHAR),
  "unit" VARCHAR(255 CHAR),
  "readwrite_level" VARCHAR(255 CHAR),
  "sort" INT,
  "value" DECIMAL(19,4),
  "gather_time" TIMESTAMP,
  "acquisition_coding" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."attribute_name" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."attribute_code" IS '属性编码';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."readwrite_level" IS '读写等级';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."gather_time" IS '采集时间';
COMMENT ON COLUMN "FWBZ"."device_attribute_251209"."acquisition_coding" IS '采集编码';
COMMENT ON TABLE "FWBZ"."device_attribute_251209" IS '设备基础信息';

-- ----------------------------
-- Table structure for device_attribute_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute_config";
CREATE TABLE "FWBZ"."device_attribute_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "label" VARCHAR(255 CHAR),
  "code" VARCHAR(255 CHAR),
  "sort" INT
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."label" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."code" IS '属性key';
COMMENT ON COLUMN "FWBZ"."device_attribute_config"."sort" IS '排序';
COMMENT ON TABLE "FWBZ"."device_attribute_config" IS '设备采集点位配置';

-- ----------------------------
-- Table structure for device_attribute_data
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute_data";
CREATE TABLE "FWBZ"."device_attribute_data" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_id" BIGINT,
  "attribute_id" BIGINT,
  "value" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."device_id" IS '设备ID';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."attribute_id" IS '属性ID';
COMMENT ON COLUMN "FWBZ"."device_attribute_data"."value" IS '值';
COMMENT ON TABLE "FWBZ"."device_attribute_data" IS '设备采集点位数据';

-- ----------------------------
-- Table structure for device_attribute_history
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_attribute_history";
CREATE TABLE "FWBZ"."device_attribute_history" (
  "id" BIGINT NOT NULL,
  "device_id" BIGINT,
  "attribute_id" BIGINT,
  "collection_time" TIMESTAMP(6),
  "value" DECIMAL(38,4)
)
;
COMMENT ON COLUMN "FWBZ"."device_attribute_history"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_attribute_history"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."device_attribute_history"."attribute_id" IS '属性id';
COMMENT ON COLUMN "FWBZ"."device_attribute_history"."collection_time" IS '采集时间';
COMMENT ON COLUMN "FWBZ"."device_attribute_history"."value" IS '属性值';
COMMENT ON TABLE "FWBZ"."device_attribute_history" IS '设备属性历史';

-- ----------------------------
-- Table structure for device_data_temp
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_data_temp";
CREATE TABLE "FWBZ"."device_data_temp" (
  "id" BIGINT NOT NULL,
  "time" VARCHAR(50),
  "device_code" BIGINT,
  "value" DECIMAL(38,4)
)
;

-- ----------------------------
-- Table structure for device_energy_consumption
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_energy_consumption";
CREATE TABLE "FWBZ"."device_energy_consumption" (
  "device_code" VARCHAR(50),
  "device_name" VARCHAR(100),
  "date" VARCHAR(50),
  "value" DECIMAL(22,2),
  "device_id" "bigint"
)
;
COMMENT ON TABLE "FWBZ"."device_energy_consumption" IS '临时历史数据导入';

-- ----------------------------
-- Table structure for device_model
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_model";
CREATE TABLE "FWBZ"."device_model" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "model_name" VARCHAR(255 CHAR),
  "category_id" BIGINT
)
;
COMMENT ON COLUMN "FWBZ"."device_model"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_model"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_model"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_model"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_model"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_model"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_model"."model_name" IS '模型名称';
COMMENT ON COLUMN "FWBZ"."device_model"."category_id" IS '专业id';
COMMENT ON TABLE "FWBZ"."device_model" IS '设备模型';

-- ----------------------------
-- Table structure for device_model_attribute
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_model_attribute";
CREATE TABLE "FWBZ"."device_model_attribute" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "model_id" BIGINT,
  "attribute_name" VARCHAR(255 CHAR),
  "unit" VARCHAR(255 CHAR),
  "attribute_code" VARCHAR(255 CHAR),
  "readwrite_level" VARCHAR(2 CHAR),
  "sort" INT,
  "value_type" VARCHAR(50),
  "value_config" VARCHAR(2000)
)
;
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."model_id" IS '模型id';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."attribute_name" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."unit" IS '单位';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."attribute_code" IS '属性编码';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."readwrite_level" IS '读写等级';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."value_type" IS '属性值类型';
COMMENT ON COLUMN "FWBZ"."device_model_attribute"."value_config" IS '属性值配置';
COMMENT ON TABLE "FWBZ"."device_model_attribute" IS '设备模型属性';

-- ----------------------------
-- Table structure for device_static_data
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_static_data";
CREATE TABLE "FWBZ"."device_static_data" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "device_id" BIGINT,
  "config_id" BIGINT,
  "value" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."device_static_data"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_static_data"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_static_data"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_static_data"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_static_data"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_static_data"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_static_data"."device_id" IS '设备id';
COMMENT ON COLUMN "FWBZ"."device_static_data"."config_id" IS '配置id';
COMMENT ON COLUMN "FWBZ"."device_static_data"."value" IS '值';
COMMENT ON TABLE "FWBZ"."device_static_data" IS '设备静态数据';

-- ----------------------------
-- Table structure for device_static_data_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_static_data_config";
CREATE TABLE "FWBZ"."device_static_data_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "type" VARCHAR(255 CHAR),
  "label" VARCHAR(255 CHAR),
  "value_type" VARCHAR(255 CHAR),
  "value_data" TEXT,
  "sort" INT
)
;
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."type" IS '类型。基本信息：base；技术参数：tech；服务厂商：vendor';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."label" IS '标签';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."value_type" IS '数据类型。文本输入框：input；下拉框：select；日期选择框：datePicker';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."value_data" IS '数据源';
COMMENT ON COLUMN "FWBZ"."device_static_data_config"."sort" IS '排序字段';
COMMENT ON TABLE "FWBZ"."device_static_data_config" IS '设备静态数据配置';

-- ----------------------------
-- Table structure for device_temp
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_temp";
CREATE TABLE "FWBZ"."device_temp" (
  "id" BIGINT NOT NULL,
  "device_name" VARCHAR(200),
  "device_code" VARCHAR(200),
  "device_new_code" VARCHAR(200),
  "device_id" BIGINT
)
;

-- ----------------------------
-- Table structure for device_temp_251126
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."device_temp_251126";
CREATE TABLE "FWBZ"."device_temp_251126" (
  "id" "bigint" NOT NULL,
  "device_name" VARCHAR(50)
)
;
COMMENT ON TABLE "FWBZ"."device_temp_251126" IS '设备信息临时表';

-- ----------------------------
-- Table structure for energy_analysis_benchmark
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_analysis_benchmark";
CREATE TABLE "FWBZ"."energy_analysis_benchmark" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "config_id" BIGINT NOT NULL,
  "label" VARCHAR(255 CHAR) NOT NULL,
  "value" VARCHAR(255 CHAR) NOT NULL,
  "operator" VARCHAR(10 CHAR) NOT NULL,
  "content" VARCHAR(255 CHAR),
  "sort" INT
)
;
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."config_id" IS '能效分析配置Id';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."label" IS '文本';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."value" IS '基准值';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."operator" IS '运算符';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."content" IS '提示信息';
COMMENT ON COLUMN "FWBZ"."energy_analysis_benchmark"."sort" IS '排序字段';

-- ----------------------------
-- Table structure for energy_analysis_chart
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_analysis_chart";
CREATE TABLE "FWBZ"."energy_analysis_chart" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "config_id" BIGINT NOT NULL,
  "chart_name" VARCHAR(255 CHAR) NOT NULL,
  "chart_type" VARCHAR(50 CHAR) NOT NULL,
  "point_id" BIGINT NOT NULL,
  "sort" BIGINT,
  "unit" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."config_id" IS '能效分析配置id';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."chart_name" IS '图标名称';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."chart_type" IS '图表类型。饼：pie；柱状：bar；折线：line；堆叠柱状：stackedColumn；';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."point_id" IS '计量规则id';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."energy_analysis_chart"."unit" IS '单位';

-- ----------------------------
-- Table structure for energy_analysis_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_analysis_config";
CREATE TABLE "FWBZ"."energy_analysis_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "name" VARCHAR(255 CHAR) NOT NULL,
  "remark" VARCHAR(255 CHAR),
  "sort" INT,
  "status" VARCHAR(2 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."name" IS '名称';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."energy_analysis_config"."status" IS '状态。启用：1；禁用：0';

-- ----------------------------
-- Table structure for energy_attribute_management
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_attribute_management";
CREATE TABLE "FWBZ"."energy_attribute_management" (
  "id" VARCHAR(32 CHAR) NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "attribute_name" VARCHAR(255 CHAR),
  "attribute_type" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."attribute_name" IS '属性名称';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."attribute_type" IS '属性类别';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."energy_attribute_management"."remark" IS '说明';
COMMENT ON TABLE "FWBZ"."energy_attribute_management" IS '能源属性管理';

-- ----------------------------
-- Table structure for energy_flow_diagram_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_flow_diagram_config";
CREATE TABLE "FWBZ"."energy_flow_diagram_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "type" VARCHAR(255 CHAR),
  "node_name" VARCHAR(255 CHAR),
  "parent_id" BIGINT,
  "metering_point_id" BIGINT,
  "sort" INT
)
;
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."type" IS '类型。数据字典：energy_flow_type';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."node_name" IS '节点名称';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."parent_id" IS '父节点';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."metering_point_id" IS '计量点位';
COMMENT ON COLUMN "FWBZ"."energy_flow_diagram_config"."sort" IS '排序';
COMMENT ON TABLE "FWBZ"."energy_flow_diagram_config" IS '能流图配置';

-- ----------------------------
-- Table structure for energy_medium_manage
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_medium_manage";
CREATE TABLE "FWBZ"."energy_medium_manage" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "pid" BIGINT,
  "has_child" VARCHAR(10 CHAR),
  "code" VARCHAR(255 CHAR),
  "name" VARCHAR(255 CHAR),
  "standard_unit" BIGINT,
  "sort" INT,
  "time_sharing" VARCHAR(255 CHAR),
  "remark" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."pid" IS '父级节点';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."has_child" IS '是否有子节点';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."code" IS '能介编码';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."name" IS '能介名称';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."standard_unit" IS '标准单位';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."time_sharing" IS '分时计量';
COMMENT ON COLUMN "FWBZ"."energy_medium_manage"."remark" IS '说明';
COMMENT ON TABLE "FWBZ"."energy_medium_manage" IS '能介管理';

-- ----------------------------
-- Table structure for energy_price
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_price";
CREATE TABLE "FWBZ"."energy_price" (
  "id" VARCHAR(36 CHAR) NOT NULL,
  "create_by" VARCHAR(50 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(50 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(64 CHAR),
  "energy_medium" VARCHAR(32 CHAR),
  "unit_price" DECIMAL(10,5),
  "unit" VARCHAR(32 CHAR),
  "sort" INT,
  "remark" VARCHAR(32 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."energy_price"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_price"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_price"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_price"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_price"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_price"."energy_medium" IS '能源介质';
COMMENT ON COLUMN "FWBZ"."energy_price"."unit_price" IS '单价';
COMMENT ON COLUMN "FWBZ"."energy_price"."unit" IS '单位';
COMMENT ON COLUMN "FWBZ"."energy_price"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."energy_price"."remark" IS '说明';

-- ----------------------------
-- Table structure for energy_pricing_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."energy_pricing_config";
CREATE TABLE "FWBZ"."energy_pricing_config" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "category_id" BIGINT,
  "category" VARCHAR(255 CHAR),
  "billing_way" VARCHAR(255 CHAR),
  "fixed_unit_price" DECIMAL(18,2),
  "step1_max" DECIMAL(18,2),
  "step1_unit_price" DECIMAL(18,2),
  "step2_max" DECIMAL(18,2),
  "step2_min" DECIMAL(18,2),
  "step2_unit_price" DECIMAL(18,2),
  "step3_min" DECIMAL(18,2),
  "step3_unit_price" DECIMAL(18,2),
  "tip_price" DECIMAL(18,2),
  "peak_price" DECIMAL(18,2),
  "flat_price" DECIMAL(18,2),
  "valley_price" DECIMAL(18,2),
  "apply_months1" VARCHAR(255 CHAR),
  "tip_time_slot1" VARCHAR(255 CHAR),
  "peak_time_slot1" VARCHAR(255 CHAR),
  "flat_time_slot1" VARCHAR(255 CHAR),
  "valley_time_slot1" VARCHAR(255 CHAR),
  "apply_months2" VARCHAR(255 CHAR),
  "tip_time_slot2" VARCHAR(255 CHAR),
  "peak_time_slot2" VARCHAR(255 CHAR),
  "flat_time_slot2" VARCHAR(255 CHAR),
  "valley_time_slot2" VARCHAR(255 CHAR),
  "status" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."category_id" IS '仪表类别id';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."category" IS '类别。电：electricity；水：water；热：heating';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."billing_way" IS '计价方式 1-峰谷分时计价 2-固定计价 3-阶梯计价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."fixed_unit_price" IS '固定单价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step1_max" IS '阶梯计价-第一阶段-最大值';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step1_unit_price" IS '阶梯计价-第一阶段-单价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step2_max" IS '阶梯计价-第二阶段-最大值';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step2_min" IS '阶梯计价-第二阶段-最小值';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step2_unit_price" IS '阶梯计价-第二阶段-单价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step3_min" IS '阶梯计价-第三阶段-最小值';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."step3_unit_price" IS '阶梯计价-第三阶段-单价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."tip_price" IS '峰谷分时计价-尖电价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."peak_price" IS '峰谷分时计价-峰电价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."flat_price" IS '峰谷分时计价-平电价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."valley_price" IS '峰谷分时计价-谷电价';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."apply_months1" IS '峰谷分时计价-适用月份1';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."tip_time_slot1" IS '峰谷分时计价-尖时段1';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."peak_time_slot1" IS '峰谷分时计价-峰时段1';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."flat_time_slot1" IS '峰谷分时计价-平时段1';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."valley_time_slot1" IS '峰谷分时计价-谷时段1';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."apply_months2" IS '峰谷分时计价-适用月份2';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."tip_time_slot2" IS '峰谷分时计价-尖时段2';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."peak_time_slot2" IS '峰谷分时计价-峰时段2';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."flat_time_slot2" IS '峰谷分时计价-平时段2';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."valley_time_slot2" IS '峰谷分时计价-谷时段2';
COMMENT ON COLUMN "FWBZ"."energy_pricing_config"."status" IS '启用：1；禁用：0';

-- ----------------------------
-- Table structure for equipment_category
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."equipment_category";
CREATE TABLE "FWBZ"."equipment_category" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "pid" BIGINT,
  "has_child" VARCHAR(10 CHAR),
  "category_name" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT,
  "full_name" VARCHAR(255 CHAR),
  "full_id" VARCHAR(255 CHAR),
  "type" VARCHAR(2 CHAR),
  "master_id" VARCHAR(32)
)
;
COMMENT ON COLUMN "FWBZ"."equipment_category"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."equipment_category"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."equipment_category"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."equipment_category"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."equipment_category"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."equipment_category"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."equipment_category"."pid" IS '父级节点';
COMMENT ON COLUMN "FWBZ"."equipment_category"."has_child" IS '是否有子节点';
COMMENT ON COLUMN "FWBZ"."equipment_category"."category_name" IS '类别名称';
COMMENT ON COLUMN "FWBZ"."equipment_category"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."equipment_category"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."equipment_category"."full_name" IS '全称';
COMMENT ON COLUMN "FWBZ"."equipment_category"."full_id" IS '父级id';
COMMENT ON COLUMN "FWBZ"."equipment_category"."type" IS '分类。仪表：1；设备：2；';
COMMENT ON TABLE "FWBZ"."equipment_category" IS '设备类别';

-- ----------------------------
-- Table structure for gather_rule_config
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."gather_rule_config";
CREATE TABLE "FWBZ"."gather_rule_config" (
  "id" VARCHAR(32 CHAR) NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "gateway_code" VARCHAR(255 CHAR),
  "gateway_name" VARCHAR(255 CHAR),
  "gateway_type" VARCHAR(255 CHAR),
  "install_addr" BIGINT,
  "ip" VARCHAR(255 CHAR),
  "protocol" VARCHAR(255 CHAR),
  "state" VARCHAR(255 CHAR),
  "last_collection_time" TIMESTAMP,
  "frequency" INT
)
;
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."gateway_code" IS '网关编号';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."gateway_name" IS '网关名称';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."gateway_type" IS '网关类型';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."install_addr" IS '安装位置';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."ip" IS 'ip';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."protocol" IS '通讯协议';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."state" IS '状态';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."last_collection_time" IS '最后采集时间';
COMMENT ON COLUMN "FWBZ"."gather_rule_config"."frequency" IS '采集频率/s';
COMMENT ON TABLE "FWBZ"."gather_rule_config" IS '采集管理-规则标准';

-- ----------------------------
-- Table structure for lighting_area
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."lighting_area";
CREATE TABLE "FWBZ"."lighting_area" (
  "id" BIGINT NOT NULL,
  "area_name" VARCHAR(200),
  "area_code" VARCHAR(200),
  "status" VARCHAR(50),
  "sort" INT,
  "space" VARCHAR(50),
  "location" VARCHAR(200),
  "monitor_adr" VARCHAR(200),
  "remark" VARCHAR(50),
  "type" VARCHAR(50),
  "space_name" VARCHAR(50),
  "start_time" TIMESTAMP,
  "closing_time" VARCHAR(50),
  "all_duration" BIGINT,
  "open_code" VARCHAR(50),
  "close_code" VARCHAR(50),
  "rel_name" VARCHAR(50),
  "circuit_names" VARCHAR(200)
)
;
COMMENT ON COLUMN "FWBZ"."lighting_area"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."lighting_area"."area_name" IS '区域名称';
COMMENT ON COLUMN "FWBZ"."lighting_area"."area_code" IS '区域编码';
COMMENT ON COLUMN "FWBZ"."lighting_area"."status" IS '状态';
COMMENT ON COLUMN "FWBZ"."lighting_area"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."lighting_area"."space" IS '金安桥：1；一高炉：2';
COMMENT ON COLUMN "FWBZ"."lighting_area"."location" IS '位置信息';
COMMENT ON COLUMN "FWBZ"."lighting_area"."monitor_adr" IS '监控信息';
COMMENT ON COLUMN "FWBZ"."lighting_area"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."lighting_area"."type" IS '建筑：1、区域：2';
COMMENT ON COLUMN "FWBZ"."lighting_area"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."lighting_area"."start_time" IS '场景启动时间';
COMMENT ON COLUMN "FWBZ"."lighting_area"."closing_time" IS '场景关闭时间';
COMMENT ON COLUMN "FWBZ"."lighting_area"."all_duration" IS '开启时长，单位：秒';
COMMENT ON COLUMN "FWBZ"."lighting_area"."open_code" IS '场景开启码';
COMMENT ON COLUMN "FWBZ"."lighting_area"."close_code" IS '场景关闭码';
COMMENT ON COLUMN "FWBZ"."lighting_area"."rel_name" IS '关联名称';
COMMENT ON COLUMN "FWBZ"."lighting_area"."circuit_names" IS '包含回路';
COMMENT ON TABLE "FWBZ"."lighting_area" IS '照明-区域';

-- ----------------------------
-- Table structure for lighting_circuit
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."lighting_circuit";
CREATE TABLE "FWBZ"."lighting_circuit" (
  "id" BIGINT NOT NULL,
  "circuit_name" VARCHAR(50),
  "circuit_code" VARCHAR(50),
  "status" VARCHAR(50),
  "area_id" BIGINT,
  "start_time" TIMESTAMP,
  "closing_time" TIMESTAMP,
  "all_duration" BIGINT,
  "operator_by" VARCHAR(50),
  "operator_time" TIMESTAMP,
  "area_code" VARCHAR(50),
  "comstat" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."circuit_name" IS '回路名称';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."circuit_code" IS '回路编码';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."status" IS '状态。开启、关闭';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."area_id" IS '所在区域';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."start_time" IS '开启时间';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."closing_time" IS '关闭时间';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."all_duration" IS '开启总时长';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."operator_by" IS '操作人';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."operator_time" IS '操作时间';
COMMENT ON COLUMN "FWBZ"."lighting_circuit"."comstat" IS '通讯状态';
COMMENT ON TABLE "FWBZ"."lighting_circuit" IS '照明-回路';

-- ----------------------------
-- Table structure for lighting_operation_log
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."lighting_operation_log";
CREATE TABLE "FWBZ"."lighting_operation_log" (
  "id" BIGINT NOT NULL,
  "rel_type" VARCHAR(50) NOT NULL,
  "rel_id" BIGINT NOT NULL,
  "name" VARCHAR(200),
  "operation_type" VARCHAR(50),
  "operation_time" TIMESTAMP,
  "operation_by" VARCHAR(200)
)
;
COMMENT ON TABLE "FWBZ"."lighting_operation_log" IS '照明控制记录';

-- ----------------------------
-- Table structure for lighting_plan
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."lighting_plan";
CREATE TABLE "FWBZ"."lighting_plan" (
  "id" BIGINT NOT NULL,
  "plan_name" VARCHAR(50),
  "rel_type" VARCHAR(50),
  "rel_ids" VARCHAR(2000),
  "execution_time" TIME,
  "operation_type" VARCHAR(50),
  "status" VARCHAR(50),
  "version" BIGINT,
  "create_by" VARCHAR(50),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(50),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(50),
  "sort" INT
)
;
COMMENT ON COLUMN "FWBZ"."lighting_plan"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."plan_name" IS '计划名称';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."rel_type" IS '区域、回路';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."rel_ids" IS '关联id，多个以英文逗号分隔';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."execution_time" IS '执行时间';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."operation_type" IS '操作类型。开启、关闭';
COMMENT ON COLUMN "FWBZ"."lighting_plan"."sort" IS '排序字段，升序排列';
COMMENT ON TABLE "FWBZ"."lighting_plan" IS '照明计划';

-- ----------------------------
-- Table structure for lighting_plan_execution_time
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."lighting_plan_execution_time";
CREATE TABLE "FWBZ"."lighting_plan_execution_time" (
  "id" BIGINT NOT NULL,
  "plan_id" BIGINT NOT NULL,
  "execution_time" TIME,
  "start_date" DATE,
  "end_date" DATE,
  "enabled_week" VARCHAR(50),
  "version" VARCHAR(50)
)
;

-- ----------------------------
-- Table structure for linkage_front_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."linkage_front_point";
CREATE TABLE "FWBZ"."linkage_front_point" (
  "id" BIGINT NOT NULL,
  "linkage_strategy_id" BIGINT NOT NULL,
  "device_id" BIGINT NOT NULL,
  "device_name" VARCHAR(255 CHAR),
  "space_name" VARCHAR(255 CHAR),
  "point_id" BIGINT NOT NULL,
  "point_name" VARCHAR(255 CHAR),
  "operator" VARCHAR(10 CHAR) NOT NULL,
  "condition_value" VARCHAR(255 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."linkage_strategy_id" IS '联动控制策略主键';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."device_id" IS '设备主键';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."point_id" IS '点位id';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."operator" IS '运算符';
COMMENT ON COLUMN "FWBZ"."linkage_front_point"."condition_value" IS '条件值';
COMMENT ON TABLE "FWBZ"."linkage_front_point" IS '联动控制策略前置点位';

-- ----------------------------
-- Table structure for linkage_rear_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."linkage_rear_point";
CREATE TABLE "FWBZ"."linkage_rear_point" (
  "id" BIGINT NOT NULL,
  "linkage_strategy_id" BIGINT NOT NULL,
  "device_id" BIGINT NOT NULL,
  "device_name" VARCHAR(255 CHAR),
  "space_name" VARCHAR(255 CHAR),
  "point_id" BIGINT NOT NULL,
  "point_name" VARCHAR(255 CHAR),
  "condition_value" VARCHAR(255 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."linkage_strategy_id" IS '联动控制策略主键';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."device_id" IS '设备主键';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."point_id" IS '点位id';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."linkage_rear_point"."condition_value" IS '条件值';
COMMENT ON TABLE "FWBZ"."linkage_rear_point" IS '联动控制策略后置点位';

-- ----------------------------
-- Table structure for linkage_strategy
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."linkage_strategy";
CREATE TABLE "FWBZ"."linkage_strategy" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "strategy_code" VARCHAR(255 CHAR) NOT NULL,
  "strategy_name" VARCHAR(255 CHAR) NOT NULL,
  "strategy_target" VARCHAR(255 CHAR) NOT NULL,
  "front_device" VARCHAR(2000 CHAR) NOT NULL,
  "rear_device" VARCHAR(2000 CHAR) NOT NULL,
  "enabled_status" VARCHAR(2 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."strategy_code" IS '策略编码';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."strategy_name" IS '策略名称';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."strategy_target" IS '策略目标';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."front_device" IS '前置设备';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."rear_device" IS '后置设备';
COMMENT ON COLUMN "FWBZ"."linkage_strategy"."enabled_status" IS '启用状态。启用：1；禁用：0';
COMMENT ON TABLE "FWBZ"."linkage_strategy" IS '联动控制策略';

-- ----------------------------
-- Table structure for log_point_execute_record
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."log_point_execute_record";
CREATE TABLE "FWBZ"."log_point_execute_record" (
  "id" BIGINT NOT NULL,
  "strategy_execute_id" BIGINT,
  "point_id" BIGINT,
  "executed_time" TIMESTAMP,
  "device_id" BIGINT,
  "device_name" VARCHAR(255 CHAR),
  "condition_value" VARCHAR(255 CHAR),
  "point_name" VARCHAR(255 CHAR),
  "success_flag" VARCHAR(10 CHAR),
  "condition_remark" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."strategy_execute_id" IS '策略执行记录主键';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."point_id" IS '点位ID';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."executed_time" IS '执行时间';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."device_id" IS '设备ID';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."condition_value" IS '条件值';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."success_flag" IS '是否执行成功';
COMMENT ON COLUMN "FWBZ"."log_point_execute_record"."condition_remark" IS '条件值备注';
COMMENT ON TABLE "FWBZ"."log_point_execute_record" IS '点位执行记录表';

-- ----------------------------
-- Table structure for log_strategy_execute_record
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."log_strategy_execute_record";
CREATE TABLE "FWBZ"."log_strategy_execute_record" (
  "id" BIGINT NOT NULL,
  "business_type" VARCHAR(1 CHAR),
  "business_key" BIGINT,
  "success_flag" VARCHAR(50 CHAR),
  "description" TEXT,
  "executed_time" TIMESTAMP,
  "executed_by" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."business_type" IS '执行业务类型【0-模式化管理，1-联动策略】';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."business_key" IS '执行业务主键';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."success_flag" IS '是否执行成功【成功/失败/执行中】';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."description" IS '描述信息';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."executed_time" IS '执行时间';
COMMENT ON COLUMN "FWBZ"."log_strategy_execute_record"."executed_by" IS '执行人';
COMMENT ON TABLE "FWBZ"."log_strategy_execute_record" IS '策略执行记录表';

-- ----------------------------
-- Table structure for metering_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point";
CREATE TABLE "FWBZ"."metering_point" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP(6),
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP(6),
  "sys_org_code" VARCHAR(255 CHAR),
  "type" VARCHAR(255 CHAR),
  "node_code" VARCHAR(255 CHAR),
  "node_name" VARCHAR(255 CHAR),
  "parent_id" BIGINT,
  "sort" INT,
  "category_id" BIGINT,
  "space_id" BIGINT,
  "metering_unit" BIGINT,
  "formula" TEXT,
  "true_formula" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."metering_point"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."metering_point"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."metering_point"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."metering_point"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."metering_point"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."metering_point"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."metering_point"."type" IS '类型。数据字典：energy_flow_type';
COMMENT ON COLUMN "FWBZ"."metering_point"."node_code" IS '节点编号';
COMMENT ON COLUMN "FWBZ"."metering_point"."node_name" IS '节点名称';
COMMENT ON COLUMN "FWBZ"."metering_point"."parent_id" IS '父节点';
COMMENT ON COLUMN "FWBZ"."metering_point"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."metering_point"."category_id" IS '设备类别';
COMMENT ON COLUMN "FWBZ"."metering_point"."space_id" IS '空间位置';
COMMENT ON COLUMN "FWBZ"."metering_point"."metering_unit" IS '计量单位';
COMMENT ON COLUMN "FWBZ"."metering_point"."formula" IS '公式';
COMMENT ON COLUMN "FWBZ"."metering_point"."true_formula" IS '解析后公式（将点位编码替换为设备编码）';
COMMENT ON TABLE "FWBZ"."metering_point" IS '计量点位配置';

-- ----------------------------
-- Table structure for metering_point_2511201615
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_2511201615";
CREATE TABLE "FWBZ"."metering_point_2511201615" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "type" VARCHAR(255 CHAR),
  "node_code" VARCHAR(255 CHAR),
  "node_name" VARCHAR(255 CHAR),
  "parent_id" BIGINT,
  "sort" INT,
  "category_id" BIGINT,
  "space_id" BIGINT,
  "metering_unit" BIGINT,
  "formula" TEXT,
  "true_formula" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."type" IS '类型。数据字典：energy_flow_type';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."node_code" IS '节点编号';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."node_name" IS '节点名称';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."parent_id" IS '父节点';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."category_id" IS '设备类别';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."space_id" IS '空间位置';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."metering_unit" IS '计量单位';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."formula" IS '公式';
COMMENT ON COLUMN "FWBZ"."metering_point_2511201615"."true_formula" IS '解析后公式（将点位编码替换为设备编码）';
COMMENT ON TABLE "FWBZ"."metering_point_2511201615" IS '计量点位配置';

-- ----------------------------
-- Table structure for metering_point_cost_data_day
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_cost_data_day";
CREATE TABLE "FWBZ"."metering_point_cost_data_day" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(18,2),
  "cost" DECIMAL(18,2)
)
;

-- ----------------------------
-- Table structure for metering_point_cost_data_hour
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_cost_data_hour";
CREATE TABLE "FWBZ"."metering_point_cost_data_hour" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(18,2),
  "cost" DECIMAL(18,2)
)
;

-- ----------------------------
-- Table structure for metering_point_cost_data_month
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_cost_data_month";
CREATE TABLE "FWBZ"."metering_point_cost_data_month" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(18,2),
  "cost" DECIMAL(18,2)
)
;

-- ----------------------------
-- Table structure for metering_point_cost_data_year
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_cost_data_year";
CREATE TABLE "FWBZ"."metering_point_cost_data_year" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(18,2),
  "cost" DECIMAL(18,2)
)
;

-- ----------------------------
-- Table structure for metering_point_data_day
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_data_day";
CREATE TABLE "FWBZ"."metering_point_data_day" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(30,4)
)
;
COMMENT ON COLUMN "FWBZ"."metering_point_data_day"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."metering_point_data_day"."metering_point_id" IS '点位ID';
COMMENT ON COLUMN "FWBZ"."metering_point_data_day"."time" IS '时间';
COMMENT ON COLUMN "FWBZ"."metering_point_data_day"."value" IS '值';
COMMENT ON TABLE "FWBZ"."metering_point_data_day" IS '计量点日数据';

-- ----------------------------
-- Table structure for metering_point_data_hour
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_data_hour";
CREATE TABLE "FWBZ"."metering_point_data_hour" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(19,4)
)
;

-- ----------------------------
-- Table structure for metering_point_data_month
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_data_month";
CREATE TABLE "FWBZ"."metering_point_data_month" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(30,4)
)
;
COMMENT ON COLUMN "FWBZ"."metering_point_data_month"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."metering_point_data_month"."metering_point_id" IS '点位ID';
COMMENT ON COLUMN "FWBZ"."metering_point_data_month"."time" IS '时间';
COMMENT ON COLUMN "FWBZ"."metering_point_data_month"."value" IS '值';
COMMENT ON TABLE "FWBZ"."metering_point_data_month" IS '计量点月数据';

-- ----------------------------
-- Table structure for metering_point_data_year
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_data_year";
CREATE TABLE "FWBZ"."metering_point_data_year" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT,
  "time" TIMESTAMP,
  "value" DECIMAL(38,4)
)
;
COMMENT ON COLUMN "FWBZ"."metering_point_data_year"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."metering_point_data_year"."metering_point_id" IS '点位ID';
COMMENT ON COLUMN "FWBZ"."metering_point_data_year"."time" IS '时间';
COMMENT ON COLUMN "FWBZ"."metering_point_data_year"."value" IS '值';
COMMENT ON TABLE "FWBZ"."metering_point_data_year" IS '计量点年数据';

-- ----------------------------
-- Table structure for metering_point_rel
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."metering_point_rel";
CREATE TABLE "FWBZ"."metering_point_rel" (
  "id" BIGINT NOT NULL,
  "metering_point_id" BIGINT NOT NULL,
  "rel_id" BIGINT NOT NULL,
  "rel_type" VARCHAR(2 CHAR) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."metering_point_rel"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."metering_point_rel"."metering_point_id" IS '计量点ID';
COMMENT ON COLUMN "FWBZ"."metering_point_rel"."rel_id" IS '关联ID';
COMMENT ON COLUMN "FWBZ"."metering_point_rel"."rel_type" IS '关联类型。设备：1；计量点：2';
COMMENT ON TABLE "FWBZ"."metering_point_rel" IS '计量点关联设备点位';

-- ----------------------------
-- Table structure for patterning_execution_time
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."patterning_execution_time";
CREATE TABLE "FWBZ"."patterning_execution_time" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "patterning_id" BIGINT,
  "begin_date" DATE,
  "begin_time" TIME,
  "enabled_week" VARCHAR(255 CHAR),
  "end_date" DATE,
  "version" VARCHAR(50)
)
;
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."patterning_id" IS '模式化管理策略ID';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."begin_date" IS '策略起始日期';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."begin_time" IS '策略执行时间';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."enabled_week" IS '周策略执行日，例如：1,2,3 表示周一、周二、周三';
COMMENT ON COLUMN "FWBZ"."patterning_execution_time"."end_date" IS '策略结束日期';
COMMENT ON TABLE "FWBZ"."patterning_execution_time" IS '场景策略执行时间配置表';

-- ----------------------------
-- Table structure for patterning_point
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."patterning_point";
CREATE TABLE "FWBZ"."patterning_point" (
  "id" BIGINT NOT NULL,
  "pattern_strategy_id" BIGINT,
  "device_id" BIGINT,
  "device_code" VARCHAR(255 CHAR),
  "device_name" VARCHAR(255 CHAR),
  "space_id" BIGINT,
  "space_name" VARCHAR(255 CHAR),
  "condition_value" VARCHAR(255 CHAR),
  "point_name" VARCHAR(255 CHAR),
  "point_id" BIGINT
)
;
COMMENT ON COLUMN "FWBZ"."patterning_point"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."patterning_point"."pattern_strategy_id" IS '模式化策略主键';
COMMENT ON COLUMN "FWBZ"."patterning_point"."device_id" IS '设备主键';
COMMENT ON COLUMN "FWBZ"."patterning_point"."device_code" IS '设备编码';
COMMENT ON COLUMN "FWBZ"."patterning_point"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."patterning_point"."space_id" IS '空间主键';
COMMENT ON COLUMN "FWBZ"."patterning_point"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."patterning_point"."condition_value" IS '条件值';
COMMENT ON COLUMN "FWBZ"."patterning_point"."point_name" IS '点位名称';
COMMENT ON COLUMN "FWBZ"."patterning_point"."point_id" IS '点位ID';
COMMENT ON TABLE "FWBZ"."patterning_point" IS '场景策略设备点位表';

-- ----------------------------
-- Table structure for patterning_related
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."patterning_related";
CREATE TABLE "FWBZ"."patterning_related" (
  "id" BIGINT NOT NULL,
  "pre_association_id" BIGINT,
  "post_association_id" BIGINT,
  "post_association_name" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."patterning_related"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."patterning_related"."pre_association_id" IS '前关联主键';
COMMENT ON COLUMN "FWBZ"."patterning_related"."post_association_id" IS '后关联主键';
COMMENT ON COLUMN "FWBZ"."patterning_related"."post_association_name" IS '后关联策略名称';
COMMENT ON TABLE "FWBZ"."patterning_related" IS '场景策略关联关系表';

-- ----------------------------
-- Table structure for patterning_strategy
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."patterning_strategy";
CREATE TABLE "FWBZ"."patterning_strategy" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "strategy_code" VARCHAR(255 CHAR),
  "strategy_name" VARCHAR(255 CHAR),
  "strategy_scene" VARCHAR(255 CHAR),
  "strategy_target" VARCHAR(255 CHAR),
  "execute_device" VARCHAR(255 CHAR),
  "enabled_status" VARCHAR(1 CHAR),
  "composite_specialty_flag" VARCHAR(1 CHAR),
  "space_id" BIGINT,
  "space_name" VARCHAR(255 CHAR),
  "group_name" VARCHAR(255 CHAR),
  "group_id" BIGINT,
  "model_type" VARCHAR(50 CHAR),
  "professional_id" BIGINT,
  "professional_name" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."strategy_code" IS '策略编号';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."strategy_name" IS '策略名称';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."strategy_scene" IS '应用场景';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."strategy_target" IS '策略目的';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."execute_device" IS '执行设备/参数，描述';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."enabled_status" IS '启动状态【0禁用 ，1启用】';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."composite_specialty_flag" IS '是否为复合专业【0-否，1-是】';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."space_id" IS '空间主键';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."space_name" IS '空间名称';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."group_name" IS '分组名称';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."group_id" IS '分组主键';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."model_type" IS '模式类型【手动/自动】';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."professional_id" IS '专业ID';
COMMENT ON COLUMN "FWBZ"."patterning_strategy"."professional_name" IS '专业名称';
COMMENT ON TABLE "FWBZ"."patterning_strategy" IS '场景控制';

-- ----------------------------
-- Table structure for project
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."project";
CREATE TABLE "FWBZ"."project" (
  "id" VARCHAR(36 CHAR) NOT NULL,
  "project_name" VARCHAR(250 CHAR) NOT NULL,
  "project_establishment_time" TIMESTAMP,
  "project_cycle" INT,
  "project_budget" DECIMAL(10,0),
  "project_subject" VARCHAR(32 CHAR),
  "project_files" CLOB,
  "project_goal" CLOB,
  "point_id" BIGINT,
  "project_type" VARCHAR(255 CHAR),
  "full_point_id" VARCHAR(255 CHAR),
  "measurement_time" TIMESTAMP,
  "create_by" VARCHAR(50 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(50 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(64 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."project"."project_name" IS '项目名称';
COMMENT ON COLUMN "FWBZ"."project"."project_establishment_time" IS '立项时间';
COMMENT ON COLUMN "FWBZ"."project"."project_cycle" IS '项目周期（单位可以根据实际情况确定，月';
COMMENT ON COLUMN "FWBZ"."project"."project_budget" IS '项目预算';
COMMENT ON COLUMN "FWBZ"."project"."project_subject" IS '项目主体';
COMMENT ON COLUMN "FWBZ"."project"."project_files" IS '项目文件（可存储文件相关信息或路径等）';
COMMENT ON COLUMN "FWBZ"."project"."project_goal" IS '项目目标';
COMMENT ON COLUMN "FWBZ"."project"."point_id" IS '关联计量点位id';
COMMENT ON COLUMN "FWBZ"."project"."project_type" IS '项目类型';
COMMENT ON COLUMN "FWBZ"."project"."measurement_time" IS '节能计量启动时间';
COMMENT ON COLUMN "FWBZ"."project"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."project"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."project"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."project"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."project"."sys_org_code" IS '所属部门';

-- ----------------------------
-- Table structure for role_data_permission
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."role_data_permission";
CREATE TABLE "FWBZ"."role_data_permission" (
  "id" BIGINT NOT NULL,
  "role_code" VARCHAR(50),
  "permission_type" VARCHAR(50),
  "resource_id" BIGINT,
  "create_by" VARCHAR(50),
  "create_time" DATETIME(6),
  "update_by" VARCHAR(50),
  "update_time" DATETIME(6),
  "sys_org_code" VARCHAR(50)
)
;
COMMENT ON TABLE "FWBZ"."role_data_permission" IS '角色数据权限表';

-- ----------------------------
-- Table structure for space
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."space";
CREATE TABLE "FWBZ"."space" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "pid" BIGINT,
  "has_child" VARCHAR(10 CHAR),
  "space_name" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT,
  "full_name" VARCHAR(255 CHAR),
  "full_id" VARCHAR(255 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."space"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."space"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."space"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."space"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."space"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."space"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."space"."pid" IS '父级节点';
COMMENT ON COLUMN "FWBZ"."space"."has_child" IS '是否有子节点';
COMMENT ON COLUMN "FWBZ"."space"."space_name" IS '名称';
COMMENT ON COLUMN "FWBZ"."space"."sort" IS '排序字段';
COMMENT ON COLUMN "FWBZ"."space"."remark" IS '备注';
COMMENT ON COLUMN "FWBZ"."space"."full_name" IS '空间全称';
COMMENT ON COLUMN "FWBZ"."space"."full_id" IS '父级id';
COMMENT ON TABLE "FWBZ"."space" IS '空间位置';

-- ----------------------------
-- Table structure for standard_coal_coefficient
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."standard_coal_coefficient";
CREATE TABLE "FWBZ"."standard_coal_coefficient" (
  "id" VARCHAR(36 CHAR) NOT NULL,
  "create_by" VARCHAR(50 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(50 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(64 CHAR),
  "energy_medium" VARCHAR(32 CHAR),
  "unit" VARCHAR(32 CHAR),
  "eccsc" VARCHAR(32 CHAR),
  "ecf" VARCHAR(32 CHAR),
  "sort" INT,
  "remark" VARCHAR(32 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."energy_medium" IS '能源介质';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."unit" IS '单位';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."eccsc" IS '当量折算系数';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."ecf" IS '等价折算系数';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."standard_coal_coefficient"."remark" IS '说明';

-- ----------------------------
-- Table structure for sys_log
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."sys_log";
CREATE TABLE "FWBZ"."sys_log" (
  "id" VARCHAR(32 CHAR) NOT NULL,
  "log_type" INT,
  "log_content" CLOB,
  "operate_type" INT,
  "userid" VARCHAR(32 CHAR),
  "username" VARCHAR(100 CHAR),
  "ip" VARCHAR(100 CHAR),
  "method" VARCHAR(1000 CHAR),
  "request_url" VARCHAR(255 CHAR),
  "request_param" CLOB,
  "request_type" VARCHAR(10 CHAR),
  "cost_time" BIGINT,
  "create_by" VARCHAR(32 CHAR),
  "create_time" TIMESTAMP(6),
  "update_by" VARCHAR(32 CHAR),
  "update_time" TIMESTAMP(6),
  "tenant_id" INT,
  "client_type" VARCHAR(5 CHAR)
)
;
COMMENT ON COLUMN "FWBZ"."sys_log"."log_type" IS '日志类型（1登录日志，2操作日志, 3.租户操作日志）';
COMMENT ON COLUMN "FWBZ"."sys_log"."log_content" IS '日志内容';
COMMENT ON COLUMN "FWBZ"."sys_log"."operate_type" IS '操作类型';
COMMENT ON COLUMN "FWBZ"."sys_log"."userid" IS '操作用户账号';
COMMENT ON COLUMN "FWBZ"."sys_log"."username" IS '操作用户名称';
COMMENT ON COLUMN "FWBZ"."sys_log"."ip" IS 'IP';
COMMENT ON COLUMN "FWBZ"."sys_log"."method" IS '请求java方法';
COMMENT ON COLUMN "FWBZ"."sys_log"."request_url" IS '请求路径';
COMMENT ON COLUMN "FWBZ"."sys_log"."request_param" IS '请求参数';
COMMENT ON COLUMN "FWBZ"."sys_log"."request_type" IS '请求类型';
COMMENT ON COLUMN "FWBZ"."sys_log"."cost_time" IS '耗时';
COMMENT ON COLUMN "FWBZ"."sys_log"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."sys_log"."create_time" IS '创建时间';
COMMENT ON COLUMN "FWBZ"."sys_log"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."sys_log"."update_time" IS '更新时间';
COMMENT ON COLUMN "FWBZ"."sys_log"."tenant_id" IS '租户ID';
COMMENT ON COLUMN "FWBZ"."sys_log"."client_type" IS '客户端类型 pc:电脑端 app:手机端 h5:移动网页端';
COMMENT ON TABLE "FWBZ"."sys_log" IS '系统日志表';

-- ----------------------------
-- Table structure for table_acs_device
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_acs_device";
CREATE TABLE "FWBZ"."table_acs_device" (
  "id" BIGINT NOT NULL,
  "index_code" VARCHAR(64) NOT NULL,
  "resource_type" VARCHAR(32),
  "name" VARCHAR(128) NOT NULL,
  "parent_index_code" VARCHAR(64),
  "dev_type_code" VARCHAR(64),
  "dev_type_desc" VARCHAR(128),
  "device_code" VARCHAR(64),
  "manufacturer" VARCHAR(128),
  "region_index_code" VARCHAR(64),
  "region_path" VARCHAR(512),
  "treaty_type" VARCHAR(32),
  "card_capacity" INT,
  "finger_capacity" INT,
  "vein_capacity" INT,
  "face_capacity" INT,
  "door_capacity" INT,
  "deploy_id" VARCHAR(64),
  "net_zone_id" VARCHAR(64),
  "create_time" VARCHAR(32),
  "update_time" VARCHAR(32),
  "description" VARCHAR(512),
  "acs_reader_verify_mode_ability" VARCHAR(256),
  "region_name" VARCHAR(256),
  "region_path_name" VARCHAR(512),
  "ip" VARCHAR(64),
  "port" VARCHAR(16),
  "capability" VARCHAR(512),
  "dev_serial_num" VARCHAR(128),
  "data_version" VARCHAR(64),
  "gmt_create" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "online" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_acs_device"."id" IS '主键，自增';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."index_code" IS '资源唯一编码';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."resource_type" IS '资源类型';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."name" IS '资源名称';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."parent_index_code" IS '父级资源编号';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."dev_type_code" IS '门禁设备类型编码';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."dev_type_desc" IS '门禁设备类型型号';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."device_code" IS '主动设备编号';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."manufacturer" IS '厂商';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."region_index_code" IS '所属区域';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."region_path" IS '所属区域目录，以@符号分割，包含本节点';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."treaty_type" IS '接入协议';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."card_capacity" IS '设备卡容量';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."finger_capacity" IS '指纹容量';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."vein_capacity" IS '指静脉容量';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."face_capacity" IS '人脸容量';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."door_capacity" IS '门容量';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."deploy_id" IS '拨码';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."net_zone_id" IS '所属网域';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."create_time" IS '创建时间（设备侧上报）';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."update_time" IS '更新时间（设备侧上报）';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."description" IS '描述';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."acs_reader_verify_mode_ability" IS '支持认证方式，数据为十进制';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."region_name" IS '区域名称，@分隔，最大10级';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."region_path_name" IS '所属区域目录名，以"/"分隔';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."ip" IS '门禁设备IP';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."port" IS '门禁设备端口';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."capability" IS '设备能力集（含设备上的智能能力）';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."dev_serial_num" IS '设备序列号';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."data_version" IS '版本号';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."gmt_modified" IS '记录更新时间';
COMMENT ON COLUMN "FWBZ"."table_acs_device"."online" IS '在线状态，0离线，1在线';
COMMENT ON TABLE "FWBZ"."table_acs_device" IS '门禁设备资源表';

-- ----------------------------
-- Table structure for table_activeMeet_info
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_activeMeet_info";
CREATE TABLE "FWBZ"."table_activeMeet_info" (
  "id" BIGINT NOT NULL,
  "active_name" VARCHAR2(255) NOT NULL,
  "venue_id" BIGINT NOT NULL,
  "venue_floors" VARCHAR2(255),
  "start_date" DATE,
  "start_time" TIME,
  "end_time" TIME,
  "people_quantity" BIGINT,
  "create_by" VARCHAR2(255),
  "create_time" TIMESTAMP(6),
  "update_by" VARCHAR(255),
  "sys_org_code" VARCHAR2(255),
  "update_time" TIMESTAMP(6),
  "active_progress" DOUBLE DEFAULT 0
)
;
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."id" IS '主键id';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."active_name" IS '活动名称';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."venue_id" IS '场馆id';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."venue_floors" IS '活动层数';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."start_date" IS '开始日期';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."start_time" IS '开始时间';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."end_time" IS '结束时间';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."people_quantity" IS '预计人数';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."create_time" IS '创建时间';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."update_time" IS '更新时间';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_info"."active_progress" IS '进度';
COMMENT ON TABLE "FWBZ"."table_activeMeet_info" IS '活动信息表';

-- ----------------------------
-- Table structure for table_activeMeet_preparation_info
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_activeMeet_preparation_info";
CREATE TABLE "FWBZ"."table_activeMeet_preparation_info" (
  "active_meet_id" BIGINT,
  "active_meets_device_type_id" BIGINT,
  "preparation_value" BIGINT,
  "real_value" BIGINT,
  "status" TINYINT DEFAULT 0,
  "complete_time" DATETIME(6),
  "id" BIGINT NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."active_meet_id" IS '会议id';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."active_meets_device_type_id" IS '筹备设备id';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."preparation_value" IS '筹备数量';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."real_value" IS '在线数量';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."status" IS '状态，0：未完成，1已完成';
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_info"."complete_time" IS '完成时间';
COMMENT ON TABLE "FWBZ"."table_activeMeet_preparation_info" IS '会前筹备信息表';

-- ----------------------------
-- Table structure for table_activeMeet_preparation_type
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_activeMeet_preparation_type";
CREATE TABLE "FWBZ"."table_activeMeet_preparation_type" (
  "id" BIGINT NOT NULL,
  "type_name" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_activeMeet_preparation_type"."type_name" IS '筹备名称';
COMMENT ON TABLE "FWBZ"."table_activeMeet_preparation_type" IS '会前筹备类型';

-- ----------------------------
-- Table structure for table_activeMeets_device_type
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_activeMeets_device_type";
CREATE TABLE "FWBZ"."table_activeMeets_device_type" (
  "id" BIGINT NOT NULL,
  "type_id" BIGINT,
  "device_type_id" BIGINT,
  "device_type_name" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_activeMeets_device_type"."type_id" IS '筹备类型id';
COMMENT ON COLUMN "FWBZ"."table_activeMeets_device_type"."device_type_id" IS '设备类型id';
COMMENT ON COLUMN "FWBZ"."table_activeMeets_device_type"."device_type_name" IS '设备类型名称';
COMMENT ON TABLE "FWBZ"."table_activeMeets_device_type" IS '会前后背设备类型';

-- ----------------------------
-- Table structure for table_camera_resource
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_camera_resource";
CREATE TABLE "FWBZ"."table_camera_resource" (
  "id" BIGINT NOT NULL,
  "index_code" VARCHAR(64) NOT NULL,
  "resource_type" VARCHAR(32) DEFAULT NULL,
  "external_index_code" VARCHAR(64) DEFAULT NULL,
  "name" VARCHAR(128) DEFAULT NULL,
  "chan_num" INT DEFAULT NULL,
  "cascade_code" VARCHAR(64) DEFAULT NULL,
  "parent_index_code" VARCHAR(64) DEFAULT NULL,
  "longitude" DECIMAL(12,8) DEFAULT NULL,
  "latitude" DECIMAL(12,8) DEFAULT NULL,
  "elevation" VARCHAR(32) DEFAULT NULL,
  "camera_type" TINYINT DEFAULT NULL,
  "capability" VARCHAR(512) DEFAULT NULL,
  "record_location" VARCHAR(32) DEFAULT NULL,
  "channel_type" VARCHAR(16) DEFAULT NULL,
  "region_index_code" VARCHAR(64) DEFAULT NULL,
  "region_path" VARCHAR(512) DEFAULT NULL,
  "trans_type" TINYINT DEFAULT NULL,
  "treaty_type" VARCHAR(32) DEFAULT NULL,
  "install_location" VARCHAR(256) DEFAULT NULL,
  "create_time" DATETIME(6) DEFAULT NULL,
  "update_time" DATETIME(6) DEFAULT NULL,
  "dis_order" INT DEFAULT NULL,
  "resource_index_code" VARCHAR(64) DEFAULT NULL,
  "decode_tag" VARCHAR(32) DEFAULT NULL,
  "camera_relate_talk" VARCHAR(64) DEFAULT NULL,
  "region_name" VARCHAR(512) DEFAULT NULL,
  "region_path_name" VARCHAR(512) DEFAULT NULL,
  "gmt_create" DATETIME(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" DATETIME(6) DEFAULT CURRENT_TIMESTAMP,
  "online" TINYINT
)
;
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."index_code" IS '唯一编码';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."resource_type" IS '资源类型';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."external_index_code" IS '监控点国标编号';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."name" IS '资源名称';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."chan_num" IS '通道号，为级联监控点时该字段为空；本级监控点时非空';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."cascade_code" IS '级联编号';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."parent_index_code" IS '父级资源编号';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."longitude" IS '经度，精确到小数点后8位';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."latitude" IS '纬度，精确到小数点后8位';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."elevation" IS '海拔高度，单位：米';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."camera_type" IS '监控点类型：0-枪机，1-半球，2-快球，3-带云台枪机';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."capability" IS '能力集，详见附录A.44 设备能力集';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."record_location" IS '录像存储位置';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."channel_type" IS '通道子类型：analog-模拟通道，digital-数字通道，mirror-镜像通道，record-录播通道，zero-零通道';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."region_index_code" IS '所属区域';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."region_path" IS '所属区域目录，以@符号分割，包含本节点';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."trans_type" IS '传输协议：0-UDP，1-TCP';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."treaty_type" IS '接入协议，详见附录A.6 编码设备接入协议';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."install_location" IS '安装位置';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."create_time" IS '创建时间';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."update_time" IS '更新时间';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."dis_order" IS '数据在界面上的显示顺序';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."resource_index_code" IS '资源唯一编码';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."decode_tag" IS '解码模式';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."camera_relate_talk" IS '监控点关联对讲的唯一标志';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."region_name" IS '所属区域目录，由唯一标示组成，最大10级，格式：@根节点@子区域1@子区域2@';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."region_path_name" IS '区域目录名称，"/"分隔';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."gmt_modified" IS '记录更新时间';
COMMENT ON COLUMN "FWBZ"."table_camera_resource"."online" IS '在线状态，0离线，1在线';
COMMENT ON TABLE "FWBZ"."table_camera_resource" IS '监控点资源表';

-- ----------------------------
-- Table structure for table_door_event
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_door_event";
CREATE TABLE "FWBZ"."table_door_event" (
  "id" BIGINT NOT NULL,
  "event_id" VARCHAR(64) NOT NULL,
  "event_name" VARCHAR(128),
  "event_time" DATETIME(6) NOT NULL,
  "person_id" VARCHAR(64),
  "card_no" VARCHAR(64),
  "person_name" VARCHAR(128),
  "org_index_code" VARCHAR(64),
  "org_name" VARCHAR(256),
  "door_name" VARCHAR(128),
  "door_index_code" VARCHAR(64),
  "door_region_index_code" VARCHAR(64),
  "pic_uri" VARCHAR(512),
  "svr_index_code" VARCHAR(64),
  "event_type" INT,
  "in_and_out_type" SMALLINT,
  "reader_dev_index_code" VARCHAR(64),
  "reader_dev_name" VARCHAR(128),
  "dev_index_code" VARCHAR(64),
  "dev_name" VARCHAR(128),
  "identity_card_uri" VARCHAR(512),
  "receive_time" VARCHAR(64),
  "job_no" VARCHAR(64),
  "student_id" VARCHAR(64),
  "cert_no" VARCHAR(64),
  "gmt_create" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."table_door_event"."id" IS '主键，自增';
COMMENT ON COLUMN "FWBZ"."table_door_event"."event_id" IS '事件ID，唯一标识这个事件';
COMMENT ON COLUMN "FWBZ"."table_door_event"."event_name" IS '事件名称';
COMMENT ON COLUMN "FWBZ"."table_door_event"."event_time" IS '事件产生时间，ISO8601格式';
COMMENT ON COLUMN "FWBZ"."table_door_event"."person_id" IS '人员唯一编码';
COMMENT ON COLUMN "FWBZ"."table_door_event"."card_no" IS '卡号';
COMMENT ON COLUMN "FWBZ"."table_door_event"."person_name" IS '人员姓名';
COMMENT ON COLUMN "FWBZ"."table_door_event"."org_index_code" IS '人员所属组织编码';
COMMENT ON COLUMN "FWBZ"."table_door_event"."org_name" IS '人员所属组织名称';
COMMENT ON COLUMN "FWBZ"."table_door_event"."door_name" IS '门禁点名称';
COMMENT ON COLUMN "FWBZ"."table_door_event"."door_index_code" IS '门禁点编码';
COMMENT ON COLUMN "FWBZ"."table_door_event"."door_region_index_code" IS '门禁点所在区域编码';
COMMENT ON COLUMN "FWBZ"."table_door_event"."pic_uri" IS '抓拍图片地址（相对地址，需配合svr_index_code通过接口获取图片）';
COMMENT ON COLUMN "FWBZ"."table_door_event"."svr_index_code" IS '图片存储服务唯一标识（与pic_uri配对使用）';
COMMENT ON COLUMN "FWBZ"."table_door_event"."event_type" IS '事件类型';
COMMENT ON COLUMN "FWBZ"."table_door_event"."in_and_out_type" IS '进出类型：1-进 0-出 -1-未知';
COMMENT ON COLUMN "FWBZ"."table_door_event"."reader_dev_index_code" IS '读卡器唯一标识';
COMMENT ON COLUMN "FWBZ"."table_door_event"."reader_dev_name" IS '读卡器名称';
COMMENT ON COLUMN "FWBZ"."table_door_event"."dev_index_code" IS '控制器设备唯一标识';
COMMENT ON COLUMN "FWBZ"."table_door_event"."dev_name" IS '控制器设备名称';
COMMENT ON COLUMN "FWBZ"."table_door_event"."identity_card_uri" IS '身份证图片地址（相对地址，需通过接口获取图片）';
COMMENT ON COLUMN "FWBZ"."table_door_event"."receive_time" IS '事件入库时间，ISO8601格式';
COMMENT ON COLUMN "FWBZ"."table_door_event"."job_no" IS '工号';
COMMENT ON COLUMN "FWBZ"."table_door_event"."student_id" IS '学号';
COMMENT ON COLUMN "FWBZ"."table_door_event"."cert_no" IS '证件号码';
COMMENT ON COLUMN "FWBZ"."table_door_event"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_door_event"."gmt_modified" IS '记录更新时间';
COMMENT ON TABLE "FWBZ"."table_door_event" IS '门禁点事件表';

-- ----------------------------
-- Table structure for table_door_resource
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_door_resource";
CREATE TABLE "FWBZ"."table_door_resource" (
  "id" BIGINT NOT NULL,
  "index_code" VARCHAR(64) NOT NULL,
  "resource_type" VARCHAR(32),
  "name" VARCHAR(128) NOT NULL,
  "door_no" VARCHAR(64),
  "channel_no" VARCHAR(64),
  "parent_index_code" VARCHAR(64),
  "control_one_id" VARCHAR(64),
  "control_two_id" VARCHAR(64),
  "reader_in_id" VARCHAR(64),
  "reader_out_id" VARCHAR(64),
  "door_serial" INT,
  "treaty_type" VARCHAR(32),
  "region_index_code" VARCHAR(64),
  "region_path" VARCHAR(512),
  "create_time" VARCHAR(32),
  "update_time" VARCHAR(32),
  "description" VARCHAR(512),
  "channel_type" VARCHAR(32),
  "region_name" VARCHAR(256),
  "region_path_name" VARCHAR(512),
  "install_location" VARCHAR(256),
  "gmt_create" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "door_state" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_door_resource"."id" IS '主键，自增';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."index_code" IS '资源唯一编码';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."resource_type" IS '资源类型';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."name" IS '资源名称';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."door_no" IS '门禁点编号';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."channel_no" IS '通道号';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."parent_index_code" IS '父级资源编号';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."control_one_id" IS '一级控制器id';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."control_two_id" IS '二级控制器id';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."reader_in_id" IS '读卡器1（进方向）';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."reader_out_id" IS '读卡器2（出方向）';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."door_serial" IS '门序号';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."treaty_type" IS '接入协议';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."region_index_code" IS '所属区域';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."region_path" IS '所属区域目录，以@符号分割，包含本节点';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."create_time" IS '创建时间（设备侧上报）';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."update_time" IS '更新时间（设备侧上报）';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."description" IS '描述';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."channel_type" IS '通道类型，door：门禁点';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."region_name" IS '区域名称，@分隔，最大10级';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."region_path_name" IS '所属区域目录名，@分隔';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."install_location" IS '安装位置';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."gmt_modified" IS '记录更新时间';
COMMENT ON COLUMN "FWBZ"."table_door_resource"."door_state" IS '门状态，0 初始状态，1 开门状态，2关门状态，3离线状态';
COMMENT ON TABLE "FWBZ"."table_door_resource" IS '门禁点资源表';

-- ----------------------------
-- Table structure for table_event_notify
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_event_notify";
CREATE TABLE "FWBZ"."table_event_notify" (
  "id" BIGINT NOT NULL,
  "send_time" VARCHAR(64) NOT NULL,
  "ability" VARCHAR(64) NOT NULL,
  "event_id" VARCHAR(64) NOT NULL,
  "src_index" VARCHAR(64) NOT NULL,
  "src_type" VARCHAR(64) NOT NULL,
  "src_name" VARCHAR(128),
  "event_type" INT NOT NULL,
  "status" INT NOT NULL,
  "event_lvl" INT DEFAULT 0,
  "timeout" INT NOT NULL,
  "happen_time" VARCHAR(64) NOT NULL,
  "src_parent_index" VARCHAR(64),
  "event_data" CLOB,
  "gmt_create" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."table_event_notify"."id" IS '主键，自增';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."send_time" IS '事件从接收者（程序处理后）发出的时间，ISO8601格式';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."ability" IS '事件类别，如：视频事件';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."event_id" IS '事件唯一标识，同一事件若上报多次则eventId相同';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."src_index" IS '事件源编号，物理设备是资源编号';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."src_type" IS '事件源类型';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."src_name" IS '事件源名称';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."event_type" IS '事件类型，数值编码';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."status" IS '事件状态：0-瞬时 1-开始 2-停止 4-事件联动结果更新 5-事件图片异步上传';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."event_lvl" IS '事件等级：0-未配置 1-低 2-中 3-高（需配置事件联动才返回）';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."timeout" IS '脉冲超时时间，单位：秒';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."happen_time" IS '事件发生时间（设备时间），ISO8601格式';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."src_parent_index" IS '事件发生的事件源父设备编码';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."event_data" IS '事件其它扩展信息，JSON格式存储';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_event_notify"."gmt_modified" IS '记录更新时间';
COMMENT ON TABLE "FWBZ"."table_event_notify" IS '事件订阅通知表';

-- ----------------------------
-- Table structure for table_event_type
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_event_type";
CREATE TABLE "FWBZ"."table_event_type" (
  "id" BIGINT NOT NULL,
  "event_type" VARCHAR2(255),
  "event_code" VARCHAR2(255)
)
;
COMMENT ON TABLE "FWBZ"."table_event_type" IS '海康事件类型';

-- ----------------------------
-- Table structure for table_http_system
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_http_system";
CREATE TABLE "FWBZ"."table_http_system" (
  "id" BIGINT NOT NULL,
  "http_path" VARCHAR2(255),
  "system_id" BIGINT,
  "http_name" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_http_system"."http_path" IS '接口地址';
COMMENT ON COLUMN "FWBZ"."table_http_system"."system_id" IS '所属系统';
COMMENT ON COLUMN "FWBZ"."table_http_system"."http_name" IS '接口名称';
COMMENT ON TABLE "FWBZ"."table_http_system" IS '系统接口';

-- ----------------------------
-- Table structure for table_interface_history
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_interface_history";
CREATE TABLE "FWBZ"."table_interface_history" (
  "id" BIGINT NOT NULL,
  "system_id" BIGINT,
  "interface_path" VARCHAR2(255),
  "clinet_date" DATE,
  "clinet_time" TIME,
  "response_time" BIGINT,
  "data_size" DOUBLE
)
;
COMMENT ON COLUMN "FWBZ"."table_interface_history"."system_id" IS '所属系统';
COMMENT ON COLUMN "FWBZ"."table_interface_history"."interface_path" IS '接口地址';
COMMENT ON COLUMN "FWBZ"."table_interface_history"."clinet_date" IS '请求日期';
COMMENT ON COLUMN "FWBZ"."table_interface_history"."clinet_time" IS '请求时间';
COMMENT ON COLUMN "FWBZ"."table_interface_history"."response_time" IS '响应时间ms';
COMMENT ON COLUMN "FWBZ"."table_interface_history"."data_size" IS '数据大小kb';
COMMENT ON TABLE "FWBZ"."table_interface_history" IS '接口请求记录表';

-- ----------------------------
-- Table structure for table_interface_info
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_interface_info";
CREATE TABLE "FWBZ"."table_interface_info" (
  "id" BIGINT NOT NULL,
  "sys_name" VARCHAR2(255),
  "interface_path" VARCHAR2(255),
  "protocol_type_id" BIGINT,
  "state" TINYINT,
  "request_time" TIMESTAMP(3),
  "response_time" BIGINT,
  "create_by" VARCHAR2(50),
  "create_time" TIMESTAMP(3),
  "update_by" VARCHAR2(50),
  "update_time" TIMESTAMP(3),
  "sys_org_code" VARCHAR2(50),
  "test_path" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_interface_info"."sys_name" IS '系统名称';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."interface_path" IS '接口地址';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."protocol_type_id" IS '协议类型';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."state" IS '状态';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."request_time" IS '最后心跳时间';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."response_time" IS '响应时间(ms)';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."create_time" IS '创建时间';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."update_time" IS '更新时间';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."table_interface_info"."test_path" IS '测试地址';
COMMENT ON TABLE "FWBZ"."table_interface_info" IS '接口信息表';

-- ----------------------------
-- Table structure for table_parking_count
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_parking_count";
CREATE TABLE "FWBZ"."table_parking_count" (
  "id" BIGINT NOT NULL,
  "date" DATE,
  "today_entry_count" BIGINT,
  "current_in_count" BIGINT,
  "remaining_space_count" BIGINT,
  "average_parking_duration" DOUBLE
)
;
COMMENT ON COLUMN "FWBZ"."table_parking_count"."date" IS '日期';
COMMENT ON COLUMN "FWBZ"."table_parking_count"."today_entry_count" IS '今日进场车辆数';
COMMENT ON COLUMN "FWBZ"."table_parking_count"."current_in_count" IS '当前在场车辆数';
COMMENT ON COLUMN "FWBZ"."table_parking_count"."remaining_space_count" IS '剩余车位数';
COMMENT ON COLUMN "FWBZ"."table_parking_count"."average_parking_duration" IS '平均停车时长（小时）';
COMMENT ON TABLE "FWBZ"."table_parking_count" IS '停车统计表';

-- ----------------------------
-- Table structure for table_parking_record
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_parking_record";
CREATE TABLE "FWBZ"."table_parking_record" (
  "id" BIGINT NOT NULL,
  "park_time" VARCHAR(20),
  "park_date" DATE,
  "plate_no" VARCHAR(20),
  "park_type" VARCHAR(20),
  "parking_lot" VARCHAR(100),
  "direction" VARCHAR(20),
  "space_no" VARCHAR(30),
  "park_duration" VARCHAR(50),
  "gmt_create" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."table_parking_record"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."park_time" IS '时间，格式 HH24:MI:SS';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."park_date" IS '日期';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."plate_no" IS '车牌号';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."park_type" IS '类型，如进场、出场';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."parking_lot" IS '停车场名称';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."direction" IS '方向，如入口、出口';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."space_no" IS '车位号';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."park_duration" IS '停车时长，如 2小时30分钟';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_parking_record"."gmt_modified" IS '记录更新时间';
COMMENT ON TABLE "FWBZ"."table_parking_record" IS '停车记录表';

-- ----------------------------
-- Table structure for table_patrol_plan
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_patrol_plan";
CREATE TABLE "FWBZ"."table_patrol_plan" (
  "id" BIGINT NOT NULL,
  "plan_name" VARCHAR2(255),
  "patrol_route" VARCHAR2(255),
  "execution_cycle" TIME,
  "next_execution" VARCHAR2(255),
  "staus" TINYINT,
  "create_by" VARCHAR2(50),
  "create_time" TIMESTAMP(6),
  "update_by" VARCHAR2(50),
  "update_time" TIMESTAMP(6),
  "sys_org_code" VARCHAR2(50)
)
;
COMMENT ON COLUMN "FWBZ"."table_patrol_plan"."plan_name" IS '计划名称';
COMMENT ON COLUMN "FWBZ"."table_patrol_plan"."patrol_route" IS '巡更路线';
COMMENT ON COLUMN "FWBZ"."table_patrol_plan"."execution_cycle" IS '执行周期';
COMMENT ON COLUMN "FWBZ"."table_patrol_plan"."next_execution" IS '下次执行';
COMMENT ON COLUMN "FWBZ"."table_patrol_plan"."staus" IS '状态。1：启用，0：停用，2：运行中';
COMMENT ON TABLE "FWBZ"."table_patrol_plan" IS '巡更计划表';

-- ----------------------------
-- Table structure for table_patrolHistory
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_patrolHistory";
CREATE TABLE "FWBZ"."table_patrolHistory" (
  "id" BIGINT NOT NULL,
  "patrol_id" BIGINT,
  "run_time" DATETIME(6)
)
;
COMMENT ON TABLE "FWBZ"."table_patrolHistory" IS '巡更历史';

-- ----------------------------
-- Table structure for table_personnel_statistics
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_personnel_statistics";
CREATE TABLE "FWBZ"."table_personnel_statistics" (
  "id" BIGINT NOT NULL,
  "stat_date" DATE,
  "today_entry_count" BIGINT DEFAULT 0,
  "current_in_count" BIGINT DEFAULT 0,
  "recognition_record_count" BIGINT DEFAULT 0,
  "abnormal_warning_count" BIGINT DEFAULT 0,
  "gmt_create" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."stat_date" IS '统计日期';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."today_entry_count" IS '今日进场人数';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."current_in_count" IS '当前在场人数';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."recognition_record_count" IS '人员识别记录数';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."abnormal_warning_count" IS '异常行为预警数';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_personnel_statistics"."gmt_modified" IS '记录更新时间';
COMMENT ON TABLE "FWBZ"."table_personnel_statistics" IS '人员统计表';

-- ----------------------------
-- Table structure for table_plan_camera
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_plan_camera";
CREATE TABLE "FWBZ"."table_plan_camera" (
  "id" BIGINT NOT NULL,
  "plan_id" BIGINT NOT NULL,
  "index_code" VARCHAR2(255) NOT NULL
)
;
COMMENT ON COLUMN "FWBZ"."table_plan_camera"."plan_id" IS '巡更计划';
COMMENT ON COLUMN "FWBZ"."table_plan_camera"."index_code" IS '摄像头';

-- ----------------------------
-- Table structure for table_protocol_type_info
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_protocol_type_info";
CREATE TABLE "FWBZ"."table_protocol_type_info" (
  "id" BIGINT NOT NULL,
  "type_name" VARCHAR2(255),
  "create_by" VARCHAR2(50),
  "create_time" TIMESTAMP(6),
  "update_by" VARCHAR2(50),
  "update_time" TIMESTAMP(6),
  "sys_org_code" VARCHAR2(50)
)
;
COMMENT ON TABLE "FWBZ"."table_protocol_type_info" IS '接口协议信息表';

-- ----------------------------
-- Table structure for table_region_resource
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_region_resource";
CREATE TABLE "FWBZ"."table_region_resource" (
  "id" BIGINT NOT NULL,
  "index_code" VARCHAR(64) NOT NULL,
  "name" VARCHAR(128) DEFAULT NULL,
  "region_path" VARCHAR(512) DEFAULT NULL,
  "parent_index_code" VARCHAR(64) DEFAULT NULL,
  "available" INT DEFAULT NULL,
  "leaf" INT DEFAULT NULL,
  "cascade_code" VARCHAR(256) DEFAULT NULL,
  "cascade_type" TINYINT DEFAULT NULL,
  "catalog_type" TINYINT DEFAULT NULL,
  "external_index_code" VARCHAR(64) DEFAULT NULL,
  "parent_external_index_code" VARCHAR(64) DEFAULT NULL,
  "sort" INT DEFAULT NULL,
  "local_quantity" INT DEFAULT NULL,
  "total_quantity" INT DEFAULT NULL,
  "create_time" DATETIME(6) DEFAULT NULL,
  "update_time" DATETIME(6) DEFAULT NULL,
  "gmt_create" DATETIME(6) DEFAULT CURRENT_TIMESTAMP,
  "gmt_modified" DATETIME(6) DEFAULT CURRENT_TIMESTAMP
)
;
COMMENT ON COLUMN "FWBZ"."table_region_resource"."id" IS '主键ID';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."index_code" IS '区域编号';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."name" IS '区域名称';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."region_path" IS '区域完整目录，含本节点，/进行分割，上级节点在前';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."parent_index_code" IS '父区域唯一标识码';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."available" IS '是否有权限操作：1-有权限，0-无权限';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."leaf" IS '是否叶子节点：1-是叶子节点（该区域下未挂区域），0-不是叶子节点（该区域下挂有区域）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."cascade_code" IS '级联平台标识，多个级联编号以@分隔，本级区域默认值"0"';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."cascade_type" IS '区域标识：0-本级，1-级联，2-混合（下级推送给上级的本级点）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."catalog_type" IS '区域类型：0-国标区域，1-雪亮工程区域，2-司法行政区域，9-自定义区域，10-历史兼容普通区域，11-历史兼容级联区域，12-楼栋单元';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."external_index_code" IS '外码（如：国际码）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."parent_external_index_code" IS '父外码（如：国际码）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."sort" IS '同级区域顺序';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."local_quantity" IS '本区域资源数量（只统计本级挂的资源数量，不包含下级及下下级等）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."total_quantity" IS '本区域及下级区域资源数量（包含本级及下级）';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."create_time" IS '创建时间，ISO8601格式，如2018-07-26T21:30:08.322+08:00';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."update_time" IS '更新时间，ISO8601格式，如2018-07-26T21:30:08.322+08:00';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."gmt_create" IS '记录创建时间';
COMMENT ON COLUMN "FWBZ"."table_region_resource"."gmt_modified" IS '记录更新时间';
COMMENT ON TABLE "FWBZ"."table_region_resource" IS '区域资源表';

-- ----------------------------
-- Table structure for table_smoke_detector
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_smoke_detector";
CREATE TABLE "FWBZ"."table_smoke_detector" (
  "id" BIGINT NOT NULL,
  "device_name" VARCHAR2(255),
  "status" VARCHAR2(255),
  "device_type" VARCHAR2(255)
)
;
COMMENT ON COLUMN "FWBZ"."table_smoke_detector"."device_name" IS '设备名称';
COMMENT ON COLUMN "FWBZ"."table_smoke_detector"."status" IS '状态';
COMMENT ON COLUMN "FWBZ"."table_smoke_detector"."device_type" IS '设备类型，1：烟感，2，温感，3，光感，4消防栓';
COMMENT ON TABLE "FWBZ"."table_smoke_detector" IS '消防设备';

-- ----------------------------
-- Table structure for table_venue_flow
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_venue_flow";
CREATE TABLE "FWBZ"."table_venue_flow" (
  "data_date" DATE,
  "venue_id" BIGINT,
  "today_in_count" BIGINT,
  "today_now_count" BIGINT,
  "max_count" BIGINT,
  "max_time" TIME,
  "average_duration" DOUBLE,
  "id" BIGINT NOT NULL,
  "status" TINYINT
)
;
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."venue_id" IS '场馆id';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."today_in_count" IS '进场';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."today_now_count" IS '在场';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."max_count" IS '峰值';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."max_time" IS '峰值时间';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."average_duration" IS '平均时长';
COMMENT ON COLUMN "FWBZ"."table_venue_flow"."status" IS '状态';
COMMENT ON TABLE "FWBZ"."table_venue_flow" IS '各场馆客流统计';

-- ----------------------------
-- Table structure for table_venue_info
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_venue_info";
CREATE TABLE "FWBZ"."table_venue_info" (
  "id" BIGINT NOT NULL,
  "venue_name" VARCHAR2(50),
  "location" VARCHAR2(50),
  "orientation" VARCHAR2(20),
  "area" VARCHAR2(20),
  "ceiling_h" VARCHAR2(255),
  "lighting" VARCHAR2(255),
  "basic_facility" VARCHAR2(255),
  "buildable" TINYINT NOT NULL,
  "floors" BIGINT
)
;
COMMENT ON COLUMN "FWBZ"."table_venue_info"."venue_name" IS '场馆名称';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."location" IS '位置';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."orientation" IS '朝向';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."area" IS '建筑面积';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."ceiling_h" IS '层高';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."lighting" IS '采光条件';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."basic_facility" IS '基础情况';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."buildable" IS '可施工 1=是 0=否';
COMMENT ON COLUMN "FWBZ"."table_venue_info"."floors" IS '楼层';
COMMENT ON TABLE "FWBZ"."table_venue_info" IS '场馆基本信息';

-- ----------------------------
-- Table structure for table_visitor_flow
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."table_visitor_flow";
CREATE TABLE "FWBZ"."table_visitor_flow" (
  "id" BIGINT NOT NULL,
  "date" DATE,
  "today_count" BIGINT,
  "now_count" BIGINT,
  "max_count" BIGINT,
  "average_stop_duration" DOUBLE
)
;
COMMENT ON COLUMN "FWBZ"."table_visitor_flow"."date" IS '日期';
COMMENT ON COLUMN "FWBZ"."table_visitor_flow"."today_count" IS '今日客流';
COMMENT ON COLUMN "FWBZ"."table_visitor_flow"."now_count" IS '当前在场';
COMMENT ON COLUMN "FWBZ"."table_visitor_flow"."max_count" IS '峰值客流';
COMMENT ON COLUMN "FWBZ"."table_visitor_flow"."average_stop_duration" IS '平均时长（小时）';
COMMENT ON TABLE "FWBZ"."table_visitor_flow" IS '客流统计表';

-- ----------------------------
-- Table structure for unit_management
-- ----------------------------
DROP TABLE IF EXISTS "FWBZ"."unit_management";
CREATE TABLE "FWBZ"."unit_management" (
  "id" BIGINT NOT NULL,
  "create_by" VARCHAR(255 CHAR),
  "create_time" TIMESTAMP,
  "update_by" VARCHAR(255 CHAR),
  "update_time" TIMESTAMP,
  "sys_org_code" VARCHAR(255 CHAR),
  "code" VARCHAR(255 CHAR),
  "name" VARCHAR(255 CHAR),
  "english_ame" VARCHAR(255 CHAR),
  "sort" INT,
  "remark" TEXT
)
;
COMMENT ON COLUMN "FWBZ"."unit_management"."id" IS '主键';
COMMENT ON COLUMN "FWBZ"."unit_management"."create_by" IS '创建人';
COMMENT ON COLUMN "FWBZ"."unit_management"."create_time" IS '创建日期';
COMMENT ON COLUMN "FWBZ"."unit_management"."update_by" IS '更新人';
COMMENT ON COLUMN "FWBZ"."unit_management"."update_time" IS '更新日期';
COMMENT ON COLUMN "FWBZ"."unit_management"."sys_org_code" IS '所属部门';
COMMENT ON COLUMN "FWBZ"."unit_management"."code" IS '单位代码';
COMMENT ON COLUMN "FWBZ"."unit_management"."name" IS '单位名称';
COMMENT ON COLUMN "FWBZ"."unit_management"."english_ame" IS '英文名称';
COMMENT ON COLUMN "FWBZ"."unit_management"."sort" IS '排序';
COMMENT ON COLUMN "FWBZ"."unit_management"."remark" IS '说明';
COMMENT ON TABLE "FWBZ"."unit_management" IS '计量单位管理';

-- ----------------------------
-- Primary Key structure for table alarm_category
-- ----------------------------
ALTER TABLE "FWBZ"."alarm_category" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alarm_level
-- ----------------------------
ALTER TABLE "FWBZ"."alarm_level" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alarm_record
-- ----------------------------
ALTER TABLE "FWBZ"."alarm_record" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alarm_rule_point
-- ----------------------------
ALTER TABLE "FWBZ"."alarm_rule_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alarm_rules
-- ----------------------------
ALTER TABLE "FWBZ"."alarm_rules" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table building_control_point
-- ----------------------------
ALTER TABLE "FWBZ"."building_control_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table building_control_point
-- ----------------------------
ALTER TABLE "FWBZ"."building_control_point" ADD UNIQUE ("gateway_adr", "bacnet_adr");

-- ----------------------------
-- Primary Key structure for table building_control_point_history
-- ----------------------------
ALTER TABLE "FWBZ"."building_control_point_history" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table business_config
-- ----------------------------
ALTER TABLE "FWBZ"."business_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table business_config
-- ----------------------------
ALTER TABLE "FWBZ"."business_config" ADD UNIQUE ("config_key");

-- ----------------------------
-- Primary Key structure for table carbon_emission_factor
-- ----------------------------
ALTER TABLE "FWBZ"."carbon_emission_factor" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_amend_log
-- ----------------------------
ALTER TABLE "FWBZ"."data_amend_log" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_day
-- ----------------------------
ALTER TABLE "FWBZ"."data_day" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_hour
-- ----------------------------
ALTER TABLE "FWBZ"."data_hour" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_minute
-- ----------------------------
ALTER TABLE "FWBZ"."data_minute" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_month
-- ----------------------------
ALTER TABLE "FWBZ"."data_month" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table data_year
-- ----------------------------
ALTER TABLE "FWBZ"."data_year" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device
-- ----------------------------
ALTER TABLE "FWBZ"."device" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_251126
-- ----------------------------
ALTER TABLE "FWBZ"."device_251126" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute_251201
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute_251201" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute_251209
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute_251209" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute_config
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute_data
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute_data" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_attribute_history
-- ----------------------------
ALTER TABLE "FWBZ"."device_attribute_history" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_data_temp
-- ----------------------------
ALTER TABLE "FWBZ"."device_data_temp" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_model
-- ----------------------------
ALTER TABLE "FWBZ"."device_model" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_model_attribute
-- ----------------------------
ALTER TABLE "FWBZ"."device_model_attribute" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_static_data
-- ----------------------------
ALTER TABLE "FWBZ"."device_static_data" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_static_data_config
-- ----------------------------
ALTER TABLE "FWBZ"."device_static_data_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_temp
-- ----------------------------
ALTER TABLE "FWBZ"."device_temp" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table device_temp_251126
-- ----------------------------
ALTER TABLE "FWBZ"."device_temp_251126" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_analysis_benchmark
-- ----------------------------
ALTER TABLE "FWBZ"."energy_analysis_benchmark" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_analysis_chart
-- ----------------------------
ALTER TABLE "FWBZ"."energy_analysis_chart" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_analysis_config
-- ----------------------------
ALTER TABLE "FWBZ"."energy_analysis_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_attribute_management
-- ----------------------------
ALTER TABLE "FWBZ"."energy_attribute_management" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_flow_diagram_config
-- ----------------------------
ALTER TABLE "FWBZ"."energy_flow_diagram_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_medium_manage
-- ----------------------------
ALTER TABLE "FWBZ"."energy_medium_manage" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_price
-- ----------------------------
ALTER TABLE "FWBZ"."energy_price" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table energy_pricing_config
-- ----------------------------
ALTER TABLE "FWBZ"."energy_pricing_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table equipment_category
-- ----------------------------
ALTER TABLE "FWBZ"."equipment_category" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table gather_rule_config
-- ----------------------------
ALTER TABLE "FWBZ"."gather_rule_config" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table lighting_area
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_area" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table lighting_area
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_area" ADD UNIQUE ("area_code", "space");

-- ----------------------------
-- Primary Key structure for table lighting_circuit
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_circuit" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table lighting_operation_log
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_operation_log" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table lighting_plan
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_plan" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table lighting_plan_execution_time
-- ----------------------------
ALTER TABLE "FWBZ"."lighting_plan_execution_time" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table linkage_front_point
-- ----------------------------
ALTER TABLE "FWBZ"."linkage_front_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table linkage_rear_point
-- ----------------------------
ALTER TABLE "FWBZ"."linkage_rear_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table linkage_strategy
-- ----------------------------
ALTER TABLE "FWBZ"."linkage_strategy" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table log_point_execute_record
-- ----------------------------
ALTER TABLE "FWBZ"."log_point_execute_record" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table log_strategy_execute_record
-- ----------------------------
ALTER TABLE "FWBZ"."log_strategy_execute_record" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_2511201615
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_2511201615" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_cost_data_day
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_cost_data_day" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_cost_data_hour
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_cost_data_hour" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_cost_data_month
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_cost_data_month" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_cost_data_year
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_cost_data_year" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_data_day
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_data_day" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_data_hour
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_data_hour" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_data_month
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_data_month" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_data_year
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_data_year" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table metering_point_rel
-- ----------------------------
ALTER TABLE "FWBZ"."metering_point_rel" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table patterning_execution_time
-- ----------------------------
ALTER TABLE "FWBZ"."patterning_execution_time" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table patterning_execution_time
-- ----------------------------
ALTER TABLE "FWBZ"."patterning_execution_time" ADD UNIQUE ("patterning_id");

-- ----------------------------
-- Primary Key structure for table patterning_point
-- ----------------------------
ALTER TABLE "FWBZ"."patterning_point" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table patterning_related
-- ----------------------------
ALTER TABLE "FWBZ"."patterning_related" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table patterning_strategy
-- ----------------------------
ALTER TABLE "FWBZ"."patterning_strategy" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table project
-- ----------------------------
ALTER TABLE "FWBZ"."project" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table role_data_permission
-- ----------------------------
ALTER TABLE "FWBZ"."role_data_permission" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table space
-- ----------------------------
ALTER TABLE "FWBZ"."space" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table standard_coal_coefficient
-- ----------------------------
ALTER TABLE "FWBZ"."standard_coal_coefficient" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_acs_device
-- ----------------------------
ALTER TABLE "FWBZ"."table_acs_device" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_acs_device
-- ----------------------------
CREATE INDEX "FWBZ"."idx_acs_dev_dev_serial_num"
  ON "FWBZ"."table_acs_device" ("dev_serial_num" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_dev_type_code"
  ON "FWBZ"."table_acs_device" ("dev_type_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_device_code"
  ON "FWBZ"."table_acs_device" ("device_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_name"
  ON "FWBZ"."table_acs_device" ("name" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_net_zone_id"
  ON "FWBZ"."table_acs_device" ("net_zone_id" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_parent_index"
  ON "FWBZ"."table_acs_device" ("parent_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_dev_region_index"
  ON "FWBZ"."table_acs_device" ("region_index_code" ASC)
   UNUSABLE;
CREATE UNIQUE INDEX "FWBZ"."uk_acs_dev_index_code"
  ON "FWBZ"."table_acs_device" ("index_code" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_activeMeet_info
-- ----------------------------
ALTER TABLE "FWBZ"."table_activeMeet_info" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_activeMeet_preparation_info
-- ----------------------------
ALTER TABLE "FWBZ"."table_activeMeet_preparation_info" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_activeMeet_preparation_type
-- ----------------------------
ALTER TABLE "FWBZ"."table_activeMeet_preparation_type" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_activeMeets_device_type
-- ----------------------------
ALTER TABLE "FWBZ"."table_activeMeets_device_type" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_camera_resource
-- ----------------------------
ALTER TABLE "FWBZ"."table_camera_resource" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table table_camera_resource
-- ----------------------------
ALTER TABLE "FWBZ"."table_camera_resource" ADD UNIQUE ("index_code");

-- ----------------------------
-- Indexes structure for table table_camera_resource
-- ----------------------------
CREATE INDEX "FWBZ"."idx_external_index_code"
  ON "FWBZ"."table_camera_resource" ("external_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_name"
  ON "FWBZ"."table_camera_resource" ("name" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_parent_index_code"
  ON "FWBZ"."table_camera_resource" ("parent_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_region_index_code"
  ON "FWBZ"."table_camera_resource" ("region_index_code" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_door_event
-- ----------------------------
ALTER TABLE "FWBZ"."table_door_event" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_door_event
-- ----------------------------
CREATE INDEX "FWBZ"."idx_acs_event_card_no"
  ON "FWBZ"."table_door_event" ("card_no" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_dev_index"
  ON "FWBZ"."table_door_event" ("dev_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_door_index"
  ON "FWBZ"."table_door_event" ("door_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_door_region"
  ON "FWBZ"."table_door_event" ("door_region_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_event_time"
  ON "FWBZ"."table_door_event" ("event_time" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_event_type"
  ON "FWBZ"."table_door_event" ("event_type" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_in_and_out"
  ON "FWBZ"."table_door_event" ("in_and_out_type" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_job_no"
  ON "FWBZ"."table_door_event" ("job_no" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_org_index"
  ON "FWBZ"."table_door_event" ("org_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_person_id"
  ON "FWBZ"."table_door_event" ("person_id" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_acs_event_receive_time"
  ON "FWBZ"."table_door_event" ("receive_time" ASC)
   UNUSABLE;
CREATE UNIQUE INDEX "FWBZ"."uk_acs_event_event_id"
  ON "FWBZ"."table_door_event" ("event_id" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_door_resource
-- ----------------------------
ALTER TABLE "FWBZ"."table_door_resource" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_door_resource
-- ----------------------------
CREATE INDEX "FWBZ"."idx_door_control_one"
  ON "FWBZ"."table_door_resource" ("control_one_id" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_door_control_two"
  ON "FWBZ"."table_door_resource" ("control_two_id" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_door_door_no"
  ON "FWBZ"."table_door_resource" ("door_no" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_door_name"
  ON "FWBZ"."table_door_resource" ("name" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_door_parent_index"
  ON "FWBZ"."table_door_resource" ("parent_index_code" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_door_region_index"
  ON "FWBZ"."table_door_resource" ("region_index_code" ASC)
   UNUSABLE;
CREATE UNIQUE INDEX "FWBZ"."uk_door_index_code"
  ON "FWBZ"."table_door_resource" ("index_code" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_event_notify
-- ----------------------------
ALTER TABLE "FWBZ"."table_event_notify" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_event_notify
-- ----------------------------
CREATE INDEX "FWBZ"."idx_event_notify_event_type"
  ON "FWBZ"."table_event_notify" ("event_type" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_event_notify_happen_time"
  ON "FWBZ"."table_event_notify" ("happen_time" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_event_notify_send_time"
  ON "FWBZ"."table_event_notify" ("send_time" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_event_notify_src_index"
  ON "FWBZ"."table_event_notify" ("src_index" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_event_notify_src_parent"
  ON "FWBZ"."table_event_notify" ("src_parent_index" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_event_notify_status"
  ON "FWBZ"."table_event_notify" ("status" ASC)
   UNUSABLE;
CREATE UNIQUE INDEX "FWBZ"."uk_event_notify_id"
  ON "FWBZ"."table_event_notify" ("event_id" ASC, "happen_time" ASC)
   UNUSABLE;

-- ----------------------------
-- Triggers structure for table table_event_notify
-- ----------------------------
CREATE TRIGGER "FWBZ"."trg_event_notify_update" BEFORE UPDATE ON "FWBZ"."table_event_notify" FOR EACH ROW 
BEGIN
    :NEW."gmt_modified" := CURRENT_TIMESTAMP;
END;
/

-- ----------------------------
-- Primary Key structure for table table_event_type
-- ----------------------------
ALTER TABLE "FWBZ"."table_event_type" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_http_system
-- ----------------------------
ALTER TABLE "FWBZ"."table_http_system" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_interface_history
-- ----------------------------
ALTER TABLE "FWBZ"."table_interface_history" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_interface_info
-- ----------------------------
ALTER TABLE "FWBZ"."table_interface_info" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_parking_count
-- ----------------------------
ALTER TABLE "FWBZ"."table_parking_count" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_parking_record
-- ----------------------------
ALTER TABLE "FWBZ"."table_parking_record" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_parking_record
-- ----------------------------
CREATE INDEX "FWBZ"."idx_park_date"
  ON "FWBZ"."table_parking_record" ("park_date" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_park_parking_lot"
  ON "FWBZ"."table_parking_record" ("parking_lot" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_park_plate_no"
  ON "FWBZ"."table_parking_record" ("plate_no" ASC)
   UNUSABLE;
CREATE INDEX "FWBZ"."idx_park_space_no"
  ON "FWBZ"."table_parking_record" ("space_no" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_patrol_plan
-- ----------------------------
ALTER TABLE "FWBZ"."table_patrol_plan" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_patrolHistory
-- ----------------------------
ALTER TABLE "FWBZ"."table_patrolHistory" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_personnel_statistics
-- ----------------------------
ALTER TABLE "FWBZ"."table_personnel_statistics" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table table_personnel_statistics
-- ----------------------------
CREATE INDEX "FWBZ"."idx_personnel_stat_date"
  ON "FWBZ"."table_personnel_statistics" ("stat_date" ASC)
   UNUSABLE;
CREATE UNIQUE INDEX "FWBZ"."uk_personnel_stat_date"
  ON "FWBZ"."table_personnel_statistics" ("stat_date" ASC)
   UNUSABLE;

-- ----------------------------
-- Primary Key structure for table table_plan_camera
-- ----------------------------
ALTER TABLE "FWBZ"."table_plan_camera" ADD PRIMARY KEY ("id", "plan_id", "index_code");

-- ----------------------------
-- Primary Key structure for table table_protocol_type_info
-- ----------------------------
ALTER TABLE "FWBZ"."table_protocol_type_info" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_region_resource
-- ----------------------------
ALTER TABLE "FWBZ"."table_region_resource" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_smoke_detector
-- ----------------------------
ALTER TABLE "FWBZ"."table_smoke_detector" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_venue_flow
-- ----------------------------
ALTER TABLE "FWBZ"."table_venue_flow" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_venue_info
-- ----------------------------
ALTER TABLE "FWBZ"."table_venue_info" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table table_visitor_flow
-- ----------------------------
ALTER TABLE "FWBZ"."table_visitor_flow" ADD PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table unit_management
-- ----------------------------
ALTER TABLE "FWBZ"."unit_management" ADD PRIMARY KEY ("id");
