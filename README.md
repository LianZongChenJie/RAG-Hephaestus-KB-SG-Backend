# Hephaestus RAG 后端

首钢会展小镇智慧园区后端。FastAPI 对外提供接口，业务数据在达梦 `FWBZ`，大模型本机走云上 Qwen、105 走 Ollama。

本服务同时给 **两套前端** 用。网关常见地址 `http://10.168.56.101:7004`，回源本服务（105 上为 `:8000`）。

| 前端 | 仓库 | 本服务提供的接口 |
|---|---|---|
| 聊天窗口（RAG 一体机） | `RAG一体机/codeFrontend` | `POST /api/chat-stream` |
| 小镇服务保障平台 | `会展小镇服务保障平台/SGAI_FWBZ_Frontend` | `/api/ai-report/*` |

共用：`GET /api/health`（服务与模型探测，检查工程是否可用）。

问答逻辑只动聊天窗口这一条。报告页只动 `ai-report`。`/api/generate-sql` 等仍挂着，但现网保障平台前端未走这条。

## 项目结构

```
├── main.py                 # 启动入口（同一进程挂两套路由）
├── app/
│   ├── common/             # 共用：配置、达梦、Ollama、日志、健康检查、中间件
│   ├── chat/               # 聊天窗口：/api/chat-stream
│   ├── report/             # 小镇服务保障平台：/api/ai-report/*
│   └── legacy/             # 遗留 SQL 生成接口（现网保障平台未用）
├── config/
│   ├── config.yaml         # 105 生产配置（入库）
│   ├── local.yaml.example  # 本机覆盖模板（复制为 local.yaml）
│   ├── FWBZ保障平台问题清单.md  # 聊天匹配：保障平台菜单问法
│   ├── FWBZ保障平台问答手册.md  # 聊天：上述 Q-ID → SQL 范式
│   ├── FWBZ问题清单.md     # 旧清单（按库表章节，现网聊天已不读）
│   ├── FWBZ问答手册.md     # 旧范式（按库表章节，现网聊天已不读）
│   ├── FWBZ问题分类速查.md
│   └── FWBZ_strut.sql      # 达梦表结构，聊天 SQL 白名单来源
├── prompts/match.md        # 聊天 TF-IDF 后的匹配 prompt（生产默认未开 LLM 二次）
├── scripts/
│   ├── create_hephaestus_tables.py  # 达梦 Hephaestus 6 张表 + 中文注释
│   └── seed_meta_nl.py              # 达梦字典 + 问答手册 SQL 金标，灌 hephaestus_meta_nl_*
├── docs/
│   ├── hephaestus_tables.md         # 6 张 Hephaestus 表字段说明
│   └── API接口文档.md
├── tests/
└── requirements.txt
```

macOS 无 `dmpython` wheel，达梦走 JDBC（`app/common/dameng_jdbc.py` + `drivers/DmJdbcDriver18.jar`）。Linux/Windows 用 `dmpython`。

## 聊天窗口在做什么

路由：`app/chat/api.py` → `ChatService.stream_chat`（`app/chat/chat_service.py`）。  
请求体是对话 `messages`，取最后一条用户问题。响应为 SSE，前端按 `type` 渲染。

没有向量检索。聊天读达梦 `hephaestus_meta_nl_*`（表/列/关系/同义词）来选图表维度、指标和 JOIN。

### 分支顺序

**1. 能耗公式拦截（最先，跳过问题清单）**

问题同时像「能源介质 / 能介」或「电 + 水/气/热」，并且像「累计能耗 / 总能耗 / 综合能耗」时，走 `_handle_energy_query`：

- 从问句解析时间（本月默认，支持上月、最近 N 天、今年、去年）
- 读 `metering_point.true_formula`、`energy_medium_manage`、`data_day`
- 在 Python 里按公式求值，再推表格/图表/总结

目的是避免这类题走 LLM 匹配超时。手册里若有同类 Q-ID，当前也会被这条抢走。

**2. 命中问题清单 → 查库（主路径）**

`qa_matcher` + `keyword_matcher` 对照 `config/FWBZ保障平台问题清单.md`：

- 中文单字/二字 + 英文数字做 TF-IDF 余弦，取 top-3
- 问句含子串「你好、天气、Python」等黑名单 → 直接判未匹配（整句闲聊）
- top-1 分数 &lt; 0.15 → 未匹配
- 生产默认 `llm_timeout=0`，**不做 LLM 二次挑选**，直接用 TF-IDF top-1 的 Q-ID
- 主路径只要 `best_qid` 非空就算命中（不用 0.6 置信度阈值）

命中后：

1. `sql_template_loader` 从 `config/FWBZ保障平台问答手册.md` 取该 Q-ID 的 SQL 范式  
2. LLM 按用户原话改造范式（时间、设备名等），**不原样执行手册 SQL**  
3. Prompt 还塞入启动时解析的整份 `config/FWBZ_strut.sql`（100+ 张表），并按关键词猜「可能相关表」  
4. 最多生成 3 次；失败把校验错误回灌 prompt  
5. 生成后再做引号、ORDER/WHERE、假列、GROUP BY 等字符串修补  
6. `app/common/sql_guard.py`：只允许 SELECT，禁止多语句，没有分页则补 `LIMIT 500/200`  
7. `validate_sql_columns` 对照 strut 拦臆造列，然后达梦执行  

查到数据后依次推 SSE：`mode=db` → `sql` → `table` → `chart`（能画才发）→ `summary`。  
无数据或 SQL 失败则 `error` / 提示为空，然后 `done`。

**3. 未命中 → 闲聊（不查库）**

匹配器不可用、黑名单、TF-IDF 过低或没有 Q-ID 时，`mode=llm`，把用户 messages 原样交给模型流式输出 `message` token，不生成 SQL。

**4. 收尾**

无论成败，`finally` 里写一条 `FWBZ.hephaestus_chat_access_logs`（失败不影响对话）。

### SSE 事件

| type | 何时 |
|---|---|
| `mode` | detecting / db / llm，以及进度文案 |
| `sql` | 查库路径，生成的 SQL |
| `table` | Vue 表格 columns/rows |
| `chart` | ECharts option |
| `summary` | 查库路径的文字总结 |
| `message` | 闲聊路径的增量文本 |
| `error` | 失败 |
| `done` | 结束 |

知识文件：`FWBZ保障平台问题清单.md`（Q-ID）、`FWBZ保障平台问答手册.md`（范式）、`FWBZ_strut.sql`（列名对错）。  
`prompts/match.md` 仅在打开 LLM 二次匹配时使用，生产默认关闭。

## 配置

启动时先读 `config/config.yaml`，若存在 `config/local.yaml` 再覆盖。`local.yaml` 已 gitignore，**不要部署到 105**。

| 环境 | 配置 | LLM |
|---|---|---|
| 本机 | `config.yaml` + `local.yaml` | 云上 Qwen（OpenAI 兼容） |
| 105 | 仅 `config.yaml` | `http://10.61.13.137:11434` Ollama `qwen3.5:9b` |

达梦：`10.168.56.103:5236`，用户 `fwbz`，schema `FWBZ`。

本机首次：

```bash
cp config/local.yaml.example config/local.yaml
# 填入 api_key
```

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

默认 `http://0.0.0.0:8000`，Swagger：`http://localhost:8000/docs`。

达梦 Hephaestus 表（若尚未创建）：

```bash
python3.10 scripts/create_hephaestus_tables.py
python3.10 scripts/seed_meta_nl.py
```

## 接口一览

### 共用

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务与模型探测 |

### 第一部分：聊天窗口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat-stream` | SSE 对话（问题清单 → SQL → 表/图/总结，或闲聊） |

### 第二部分：小镇服务保障平台（`/api/ai-report`）

前端按页面拆成「先查数 / 再分析」或「历史回看」。实现在 `app/report/`。

**运行报告**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ai-report/stats` | 报告数量统计 |
| GET | `/api/ai-report/history` | 历史列表（`report_type=run`） |
| GET | `/api/ai-report/history/{id}` | 报告详情 |
| POST | `/api/ai-report/run` | 现生成运行报告（页面有入口，抓包可能未出现） |

**节能报告**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ai-report/venues` | 会展/场馆筛选 |
| GET | `/api/ai-report/history` | 历史列表（`report_type=energy`，可带 `time_range`） |
| GET | `/api/ai-report/history/{id}` | 报告详情 |
| POST | `/api/ai-report/energy` | 现生成节能报告 |

**预警分析**（前端目录名 predict，实际打故障接口）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ai-report/fault/query` | 只查故障数据（&lt;1s，不调 LLM） |
| POST | `/api/ai-report/fault/analyze` | 用上一接口数据做 LLM 分析（约 20–30s） |

**能效分析报告**

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ai-report/energy-analysis/query` | 只查能源系统数据 |
| POST | `/api/ai-report/energy-analysis/analyze` | 用上一接口数据做 LLM 分析 |

预警分析、能效分析共用「先 query 出表、再 analyze」：query 失败不要当模型问题；analyze 才走 Ollama。

更细的字段见 `docs/API接口文档.md`。

## 测试

单元测试：

```bash
python3.10 -m pytest tests/test_chart_meta.py tests/test_access_log.py tests/test_chat_service.py tests/test_sql_service.py
```

脚本式（直接跑，不走 pytest 收集）：

```bash
python3.10 tests/test_sql_guard.py
python3.10 tests/test_sql_validator.py
python3.10 tests/test_energy_verify.py
```

端到端评测（需本服务已启动）：

```bash
python3.10 tests/test_stream_chat_eval.py
```


原数据层图表如下：
hephaestus_meta_nl_table
hephaestus_meta_nl_column
hephaestus_meta_nl_relation
hephaestus_meta_nl_synonym
hephaestus_chat_access_logs
hephaestus_rag_chunks


本地模型：qwen3.8-flash。
服务器模型：Ollama 的 qwen3.5:9b。


服贸会小镇服务保障平台：
2. 智慧能源:能源管控,暖通管控,冷源管控,能源优化,数据统计分析,
3. 韧性安全:安防管理,门禁管理,
4. 照明控制:综合预览,设备监控,能耗统计,基础信息,控制日志,地图模式,
5. 会展服务:会前管理,会中管理,会后管理,
6. 场馆运营:场馆客流,场馆排期,
7. 设备管理:设备列表,设备模型,
8. 故障告警:报警处理,报警设置,
9. 物联网:接口平台,数据采集,运行保障,
11. AI运行报告:故障分析报告,运行报告,节能报告,预警分析报告,能效分析报告,