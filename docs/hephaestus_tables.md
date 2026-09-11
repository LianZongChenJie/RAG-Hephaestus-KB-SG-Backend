# Hephaestus 达梦表说明

Schema：`FWBZ`  
建表脚本：`scripts/create_hephaestus_tables.py`  
灌数脚本：`scripts/seed_meta_nl.py`

---

## 1. hephaestus_meta_nl_table（NL-SQL 表清单）

| 字段 | 中文解释 |
|---|---|
| id | 主键 |
| schema_name | 物理库 schema，固定 FWBZ |
| table_name | 物理表名，生成 SQL 必须原样使用 |
| name_en | 英文业务名，用于匹配 |
| name_cn | 中文业务名，用于匹配 |
| aliases | 纠正列：中英文对不上用户说法时补充，逗号分隔；禁止当作 SQL 表名 |
| topic | 业务域，如能耗、告警、设备、客流 |
| description | 表用途，可写入 prompt |
| pk_columns | 主键列，逗号分隔 |
| time_grain | 时间粒度：real / minute / hour / day / month / year，维表为空 |
| nl_enabled | 1 允许 NL-SQL，0 排除 |
| priority | 同 topic 下越小越优先召回 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

---

## 2. hephaestus_meta_nl_column（NL-SQL 字段清单）

| 字段 | 中文解释 |
|---|---|
| id | 主键 |
| table_id | 所属表，对应 hephaestus_meta_nl_table.id |
| column_name | 物理列名，生成 SQL 必须原样使用 |
| name_en | 英文业务名，用于匹配 |
| name_cn | 中文业务名，用于匹配 |
| aliases | 纠正列：中英文不够时补充；禁止当作 SQL 列名 |
| data_type | 达梦类型原文 |
| is_pk | 1 主键，0 否 |
| is_fk | 1 外键，0 否 |
| role | 字段角色：pk / fk / time / metric / dim / status / name / id / other |
| unit | 单位，如 kWh、元、次 |
| enum_values | 枚举说明，如 1=启用,0=禁用 |
| nl_enabled | 1 允许出现在生成 SQL 中，0 排除 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

---

## 3. hephaestus_meta_nl_relation（NL-SQL 推荐 JOIN）

推荐写法：`from.col = to.col`

| 字段 | 中文解释 |
|---|---|
| id | 主键 |
| from_table_id | 来源表，对应 hephaestus_meta_nl_table.id |
| from_column | 来源物理列名 |
| to_table_id | 目标表，对应 hephaestus_meta_nl_table.id |
| to_column | 目标物理列名 |
| join_type | JOIN 类型：LEFT 或 INNER |
| description | 关系说明 |
| nl_enabled | 1 允许使用该 JOIN，0 排除 |

---

## 4. hephaestus_meta_nl_synonym（用户说法映射）

把用户口头说法映射到表或字段；生成 SQL 仍只用物理名。

| 字段 | 中文解释 |
|---|---|
| id | 主键 |
| phrase | 用户可能说的词或短句 |
| target_type | 目标类型：table 或 column |
| target_id | table 时对应 hephaestus_meta_nl_table.id；column 时对应 hephaestus_meta_nl_column.id |
| weight | 权重，越大越优先 |

---

## 5. hephaestus_chat_access_logs（对话访问日志）

| 字段 | 中文解释 |
|---|---|
| id | 主键，自增 |
| question | 用户问题 |
| access_time | 访问时间 |
| token_count | 总 token 数 |
| prompt_tokens | prompt token 数 |
| completion_tokens | 补全 token 数 |
| response | 模型回复内容 |
| model | 模型名 |
| client_ip | 客户端 IP |
| user_agent | User-Agent |
| created_at | 记录写入时间 |

现网 `/api/chat-stream` 结束后由 `app/core/database.py` 写入本表。

---

## 6. hephaestus_rag_chunks（RAG 文本块）

达梦无 pgvector，`embedding` 存 JSON 浮点数组。

| 字段 | 中文解释 |
|---|---|
| id | 主键，自增 |
| chunk_id | 业务唯一 ID，如 Q2.3、TBL_alarm_record |
| type | 块类型：question / sql_template / schema |
| topic | 业务类目，如能耗、告警 |
| title | 短标题 |
| content | 原始文本 |
| metadata | JSON 附加信息 |
| embedding | 向量 JSON 数组，检索需应用层计算 |
| created_at | 创建时间 |
| updated_at | 更新时间 |
