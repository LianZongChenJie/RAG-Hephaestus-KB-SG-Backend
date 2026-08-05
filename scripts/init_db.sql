-- ============================================
-- Hephaestus RAG 后端 - 数据库初始化脚本
-- ============================================
-- 运行方式: psql -U postgres -d Hephaestus -f init_db.sql

-- 访问日志表
CREATE TABLE IF NOT EXISTS chat_access_logs (
    id                  BIGSERIAL PRIMARY KEY,
    question            TEXT NOT NULL,
    access_time         TIMESTAMPTZ NOT NULL,
    token_count         INTEGER,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    response            TEXT,
    model               VARCHAR(128),
    client_ip           VARCHAR(64),
    user_agent          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_chat_access_logs_access_time
    ON chat_access_logs (access_time DESC);
CREATE INDEX IF NOT EXISTS idx_chat_access_logs_model
    ON chat_access_logs (model);

-- 注释
COMMENT ON TABLE chat_access_logs IS 'RAG 对话访问日志';
COMMENT ON COLUMN chat_access_logs.question IS '用户问题';
COMMENT ON COLUMN chat_access_logs.access_time IS '访问时间';
COMMENT ON COLUMN chat_access_logs.token_count IS '总 token 数';
COMMENT ON COLUMN chat_access_logs.response IS '模型回复内容';
