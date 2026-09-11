#!/usr/bin/env python3
"""在达梦创建 Hephaestus 6 张表，并写入表/字段中文注释。

本机: python3.10 scripts/create_hephaestus_tables.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("COPYFILE_DISABLE", "1")

from app.core.dameng import close_dameng, execute_query, get_dameng_connection
from app.core.logger import get_logger

logger = get_logger("create_hephaestus_tables")

SCHEMA = "FWBZ"

TABLE_NAMES = (
    "hephaestus_meta_nl_table",
    "hephaestus_meta_nl_column",
    "hephaestus_meta_nl_relation",
    "hephaestus_meta_nl_synonym",
    "hephaestus_chat_access_logs",
    "hephaestus_rag_chunks",
)

TABLE_COMMENTS = {
    "hephaestus_meta_nl_table": "NL-SQL 表清单",
    "hephaestus_meta_nl_column": "NL-SQL 字段清单",
    "hephaestus_meta_nl_relation": "NL-SQL 推荐 JOIN：from.col = to.col",
    "hephaestus_meta_nl_synonym": "用户说法映射到表或字段；生成 SQL 仍只用物理名",
    "hephaestus_chat_access_logs": "RAG 对话访问日志",
    "hephaestus_rag_chunks": "RAG 文本块；达梦无 pgvector，embedding 存 JSON 浮点数组",
}

COLUMN_COMMENTS = {
    "hephaestus_meta_nl_table": {
        "id": "主键",
        "schema_name": "物理库 schema，固定 FWBZ",
        "table_name": "物理表名，生成 SQL 必须原样使用",
        "name_en": "英文业务名，用于匹配",
        "name_cn": "中文业务名，用于匹配",
        "aliases": "纠正列：中英文对不上用户说法时补充，逗号分隔；禁止当作 SQL 表名",
        "topic": "业务域，如能耗、告警、设备、客流",
        "description": "表用途，可写入 prompt",
        "pk_columns": "主键列，逗号分隔",
        "time_grain": "时间粒度：real / minute / hour / day / month / year，维表为空",
        "nl_enabled": "1 允许 NL-SQL，0 排除",
        "priority": "同 topic 下越小越优先召回",
        "created_at": "创建时间",
        "updated_at": "更新时间",
    },
    "hephaestus_meta_nl_column": {
        "id": "主键",
        "table_id": "所属表，对应 hephaestus_meta_nl_table.id",
        "column_name": "物理列名，生成 SQL 必须原样使用",
        "name_en": "英文业务名，用于匹配",
        "name_cn": "中文业务名，用于匹配",
        "aliases": "纠正列：中英文不够时补充；禁止当作 SQL 列名",
        "data_type": "达梦类型原文",
        "is_pk": "1 主键，0 否",
        "is_fk": "1 外键，0 否",
        "role": "字段角色：pk / fk / time / metric / dim / status / name / id / other",
        "unit": "单位，如 kWh、元、次",
        "enum_values": "枚举说明，如 1=启用,0=禁用",
        "nl_enabled": "1 允许出现在生成 SQL 中，0 排除",
        "created_at": "创建时间",
        "updated_at": "更新时间",
    },
    "hephaestus_meta_nl_relation": {
        "id": "主键",
        "from_table_id": "来源表，对应 hephaestus_meta_nl_table.id",
        "from_column": "来源物理列名",
        "to_table_id": "目标表，对应 hephaestus_meta_nl_table.id",
        "to_column": "目标物理列名",
        "join_type": "JOIN 类型：LEFT 或 INNER",
        "description": "关系说明",
        "nl_enabled": "1 允许使用该 JOIN，0 排除",
    },
    "hephaestus_meta_nl_synonym": {
        "id": "主键",
        "phrase": "用户可能说的词或短句",
        "target_type": "目标类型：table 或 column",
        "target_id": "table 时对应 hephaestus_meta_nl_table.id；column 时对应 hephaestus_meta_nl_column.id",
        "weight": "权重，越大越优先",
    },
    "hephaestus_chat_access_logs": {
        "id": "主键，自增",
        "question": "用户问题",
        "access_time": "访问时间",
        "token_count": "总 token 数",
        "prompt_tokens": "prompt token 数",
        "completion_tokens": "补全 token 数",
        "response": "模型回复内容",
        "model": "模型名",
        "client_ip": "客户端 IP",
        "user_agent": "User-Agent",
        "created_at": "记录写入时间",
    },
    "hephaestus_rag_chunks": {
        "id": "主键，自增",
        "chunk_id": "业务唯一 ID，如 Q2.3、TBL_alarm_record",
        "type": "块类型：question / sql_template / schema",
        "topic": "业务类目，如能耗、告警",
        "title": "短标题",
        "content": "原始文本",
        "metadata": "JSON 附加信息",
        "embedding": "向量 JSON 数组，检索需应用层计算",
        "created_at": "创建时间",
        "updated_at": "更新时间",
    },
}

CREATE_SQLS = [
    """
    CREATE TABLE "FWBZ"."hephaestus_meta_nl_table" (
        "id"            BIGINT NOT NULL,
        "schema_name"   VARCHAR(64)   DEFAULT 'FWBZ' NOT NULL,
        "table_name"    VARCHAR(128)  NOT NULL,
        "name_en"       VARCHAR(255)  NOT NULL,
        "name_cn"       VARCHAR(255)  NOT NULL,
        "aliases"       VARCHAR(500),
        "topic"         VARCHAR(64),
        "description"   VARCHAR(1000),
        "pk_columns"    VARCHAR(255),
        "time_grain"    VARCHAR(32),
        "nl_enabled"    VARCHAR(1)    DEFAULT '1' NOT NULL,
        "priority"      INT           DEFAULT 100,
        "created_at"    TIMESTAMP     DEFAULT SYSDATE,
        "updated_at"    TIMESTAMP     DEFAULT SYSDATE,
        CONSTRAINT "pk_hephaestus_meta_nl_table" PRIMARY KEY ("id"),
        CONSTRAINT "uk_hephaestus_meta_nl_table" UNIQUE ("schema_name", "table_name")
    )
    """,
    """
    CREATE TABLE "FWBZ"."hephaestus_meta_nl_column" (
        "id"            BIGINT NOT NULL,
        "table_id"      BIGINT        NOT NULL,
        "column_name"   VARCHAR(128)  NOT NULL,
        "name_en"       VARCHAR(255)  NOT NULL,
        "name_cn"       VARCHAR(255)  NOT NULL,
        "aliases"       VARCHAR(500),
        "data_type"     VARCHAR(128),
        "is_pk"         VARCHAR(1)    DEFAULT '0' NOT NULL,
        "is_fk"         VARCHAR(1)    DEFAULT '0' NOT NULL,
        "role"          VARCHAR(32),
        "unit"          VARCHAR(32),
        "enum_values"   VARCHAR(500),
        "nl_enabled"    VARCHAR(1)    DEFAULT '1' NOT NULL,
        "created_at"    TIMESTAMP     DEFAULT SYSDATE,
        "updated_at"    TIMESTAMP     DEFAULT SYSDATE,
        CONSTRAINT "pk_hephaestus_meta_nl_column" PRIMARY KEY ("id"),
        CONSTRAINT "uk_hephaestus_meta_nl_column" UNIQUE ("table_id", "column_name")
    )
    """,
    """
    CREATE TABLE "FWBZ"."hephaestus_meta_nl_relation" (
        "id"             BIGINT NOT NULL,
        "from_table_id"  BIGINT        NOT NULL,
        "from_column"    VARCHAR(128)  NOT NULL,
        "to_table_id"    BIGINT        NOT NULL,
        "to_column"      VARCHAR(128)  NOT NULL,
        "join_type"      VARCHAR(16)   DEFAULT 'LEFT' NOT NULL,
        "description"    VARCHAR(500),
        "nl_enabled"     VARCHAR(1)    DEFAULT '1' NOT NULL,
        CONSTRAINT "pk_hephaestus_meta_nl_relation" PRIMARY KEY ("id"),
        CONSTRAINT "uk_hephaestus_meta_nl_relation" UNIQUE ("from_table_id", "from_column", "to_table_id", "to_column")
    )
    """,
    """
    CREATE TABLE "FWBZ"."hephaestus_meta_nl_synonym" (
        "id"          BIGINT NOT NULL,
        "phrase"      VARCHAR(255) NOT NULL,
        "target_type" VARCHAR(16)  NOT NULL,
        "target_id"   BIGINT       NOT NULL,
        "weight"      INT          DEFAULT 1 NOT NULL,
        CONSTRAINT "pk_hephaestus_meta_nl_synonym" PRIMARY KEY ("id"),
        CONSTRAINT "uk_hephaestus_meta_nl_synonym" UNIQUE ("phrase", "target_type", "target_id")
    )
    """,
    """
    CREATE TABLE "FWBZ"."hephaestus_chat_access_logs" (
        "id"                BIGINT IDENTITY(1,1) NOT NULL,
        "question"          CLOB         NOT NULL,
        "access_time"       TIMESTAMP    NOT NULL,
        "token_count"       INT,
        "prompt_tokens"     INT,
        "completion_tokens" INT,
        "response"          CLOB,
        "model"             VARCHAR(128),
        "client_ip"         VARCHAR(64),
        "user_agent"        VARCHAR(1000),
        "created_at"        TIMESTAMP    DEFAULT SYSDATE,
        CONSTRAINT "pk_hephaestus_chat_access_logs" PRIMARY KEY ("id")
    )
    """,
    """
    CREATE TABLE "FWBZ"."hephaestus_rag_chunks" (
        "id"          BIGINT IDENTITY(1,1) NOT NULL,
        "chunk_id"    VARCHAR(128)  NOT NULL,
        "type"        VARCHAR(32)   NOT NULL,
        "topic"       VARCHAR(64),
        "title"       VARCHAR(500),
        "content"     CLOB          NOT NULL,
        "metadata"    CLOB,
        "embedding"   CLOB,
        "created_at"  TIMESTAMP     DEFAULT SYSDATE,
        "updated_at"  TIMESTAMP     DEFAULT SYSDATE,
        CONSTRAINT "pk_hephaestus_rag_chunks" PRIMARY KEY ("id"),
        CONSTRAINT "uk_hephaestus_rag_chunks_chunk_id" UNIQUE ("chunk_id")
    )
    """,
]

INDEX_SQLS = [
    'CREATE INDEX "idx_hephaestus_meta_nl_table_topic" ON "FWBZ"."hephaestus_meta_nl_table" ("topic", "nl_enabled")',
    'CREATE INDEX "idx_hephaestus_meta_nl_column_role" ON "FWBZ"."hephaestus_meta_nl_column" ("role", "nl_enabled")',
    'CREATE INDEX "idx_hephaestus_meta_nl_synonym_phrase" ON "FWBZ"."hephaestus_meta_nl_synonym" ("phrase")',
    'CREATE INDEX "idx_hephaestus_meta_nl_synonym_target" ON "FWBZ"."hephaestus_meta_nl_synonym" ("target_type", "target_id")',
    'CREATE INDEX "idx_hephaestus_chat_access_logs_time" ON "FWBZ"."hephaestus_chat_access_logs" ("access_time")',
    'CREATE INDEX "idx_hephaestus_chat_access_logs_model" ON "FWBZ"."hephaestus_chat_access_logs" ("model")',
    'CREATE INDEX "idx_hephaestus_rag_chunks_type" ON "FWBZ"."hephaestus_rag_chunks" ("type")',
    'CREATE INDEX "idx_hephaestus_rag_chunks_topic" ON "FWBZ"."hephaestus_rag_chunks" ("topic")',
]


def lit(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run(sql: str) -> None:
    conn = get_dameng_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        if hasattr(conn, "commit"):
            conn.commit()
    finally:
        cur.close()


def table_exists(name: str) -> bool:
    try:
        execute_query('SELECT 1 FROM "FWBZ"."%s" WHERE 1=0' % name)
        return True
    except Exception:
        return False


def ensure_tables() -> None:
    for name in TABLE_NAMES:
        if table_exists(name):
            logger.info("表已存在: %s", name)
            continue
        logger.info("创建表: %s", name)
        ddl = [s for s in CREATE_SQLS if f'"{name}"' in s][0]
        run(ddl)
        print("已创建 %s" % name)
    for sql in INDEX_SQLS:
        try:
            run(sql)
        except Exception as exc:
            logger.info("索引跳过: %s", exc)


def apply_comments() -> None:
    for table, comment in TABLE_COMMENTS.items():
        sql = 'COMMENT ON TABLE "FWBZ"."%s" IS %s' % (table, lit(comment))
        try:
            run(sql)
        except Exception as exc:
            logger.warning("表注释失败 %s: %s", table, exc)
            print("表注释失败 %s: %s" % (table, exc))
    for table, cols in COLUMN_COMMENTS.items():
        for col, comment in cols.items():
            sql = 'COMMENT ON COLUMN "FWBZ"."%s"."%s" IS %s' % (table, col, lit(comment))
            try:
                run(sql)
            except Exception as exc:
                logger.warning("字段注释失败 %s.%s: %s", table, col, exc)
                print("字段注释失败 %s.%s: %s" % (table, col, exc))
    print("中文注释已写入")


def main() -> None:
    print("连接达梦，创建 Hephaestus 6 张表并写入中文注释 ...")
    ensure_tables()
    apply_comments()
    for name in TABLE_NAMES:
        ok = table_exists(name)
        print("%s: %s" % (name, "OK" if ok else "缺失"))
    close_dameng()


if __name__ == "__main__":
    main()
