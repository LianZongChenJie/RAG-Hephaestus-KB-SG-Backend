-- AI报告历史记录表
-- 用于存储生成的AI报告，方便统计报告数量和查看报告内容

DROP TABLE IF EXISTS "FWBZ"."ai_report_history";

CREATE TABLE "FWBZ"."ai_report_history" (
    "id" BIGINT NOT NULL AUTO_INCREMENT,
    "report_type" VARCHAR(50) NOT NULL COMMENT '报告类型: run/predict/energy/fault',
    "title" VARCHAR(500) NOT NULL COMMENT '报告标题',
    "content" CLOB COMMENT '报告完整内容(JSON格式)',
    "summary" VARCHAR(1000) COMMENT '报告摘要',
    "time_range" VARCHAR(20) NOT NULL COMMENT '时间范围: day/week/month/quarter/year',
    "target_id" BIGINT COMMENT '目标ID(设备ID等)',
    "target_name" VARCHAR(255) COMMENT '目标名称',
    "scope" VARCHAR(50) COMMENT '范围类型: all/zone/device',
    "query_params" TEXT COMMENT '查询参数(JSON格式)',
    "query_data" TEXT COMMENT '原始查询数据(JSON格式)',
    "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY ("id")
);

-- 创建索引
CREATE INDEX "idx_report_type" ON "FWBZ"."ai_report_history" ("report_type");
CREATE INDEX "idx_time_range" ON "FWBZ"."ai_report_history" ("time_range");
CREATE INDEX "idx_created_at" ON "FWBZ"."ai_report_history" ("created_at");
CREATE INDEX "idx_target_name" ON "FWBZ"."ai_report_history" ("target_name");

COMMENT ON TABLE "FWBZ"."ai_report_history" IS 'AI报告历史记录表';
COMMENT ON COLUMN "FWBZ"."ai_report_history"."report_type" IS '报告类型: run-运行报告, predict-预测报告, energy-节能报告, fault-故障分析报告';
COMMENT ON COLUMN "FWBZ"."ai_report_history"."title" IS '报告标题';
COMMENT ON COLUMN "FWBZ"."ai_report_history"."content" IS '报告完整内容(JSON格式)';
COMMENT ON COLUMN "FWBZ"."ai_report_history"."summary" IS '报告摘要(前500字符)';
COMMENT ON COLUMN "FWBZ"."ai_report_history"."time_range" IS '时间范围: day-日报, week-周报, month-月报, quarter-季度报告, year-年度报告';
