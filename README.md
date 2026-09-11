# Hephaestus RAG 后端

首钢会展小镇智慧园区问答服务。FastAPI 对外提供接口，业务数据在达梦 `FWBZ`，大模型本机走云上 Qwen、105 走 Ollama。

产品上有两条互不替代的入口：

| 入口 | 接口 | 实现 | 用途 |
|---|---|---|---|
| 聊天窗口 | `POST /api/chat-stream` | `app/services/chat_service.py` | SSE 对话：问题清单匹配 → SQL → 表/图/总结，或闲聊 |
| 界面接口 | `/api/generate-sql` 等 | `app/services/sql_service.py` | 页面直接生成/执行 SQL、出报告，不走问题清单 |

后续问答逻辑调整默认只动聊天窗口这一条。

## 项目结构

```
├── main.py                 # 启动入口
├── app/
│   ├── api/                # 路由：chat / sql_gen / ai_report / health
│   ├── core/               # 配置、达梦、LLM、访问日志、SQL 安全门
│   ├── services/           # 业务：聊天、SQL 生成、AI 报告、问题匹配
│   ├── schemas/            # 请求/响应模型
│   └── middlewares/        # 访问日志中间件
├── config/
│   ├── config.yaml         # 105 生产配置（入库）
│   ├── local.yaml.example  # 本机覆盖模板（复制为 local.yaml）
│   ├── FWBZ问题清单.md     # 聊天：标准问题 → Q-ID
│   ├── FWBZ问答手册.md     # 聊天：Q-ID → SQL 范式
│   ├── FWBZ问题分类速查.md
│   └── FWBZ_strut.sql      # 达梦表结构，聊天 SQL 白名单来源
├── prompts/match.md        # 聊天 TF-IDF 后的匹配 prompt（生产默认未开 LLM 二次）
├── scripts/
│   ├── create_hephaestus_tables.py  # 达梦 Hephaestus 6 张表 + 中文注释
│   ├── seed_meta_nl.py              # 从 strut 灌元数据（聊天尚未读取）
│   └── debug/                       # 一次性调试脚本，不参与服务启动
├── docs/
│   ├── hephaestus_tables.md         # 6 张 Hephaestus 表字段说明
│   └── API接口文档.md
├── tests/
└── requirements.txt
```

macOS 无 `dmpython` wheel，达梦走 JDBC（`app/core/dameng_jdbc.py` + `drivers/DmJdbcDriver18.jar`）。Linux/Windows 用 `dmpython`。

## 聊天窗口在做什么

路由：`app/api/chat.py` → `ChatService.stream_chat`（`app/services/chat_service.py`）。  
请求体是对话 `messages`，取最后一条用户问题。响应为 SSE，前端按 `type` 渲染。

没有向量检索。`hephaestus_meta_nl_*` 已在达梦建表灌数，**本链路尚未读取**。

### 分支顺序

**1. 能耗公式拦截（最先，跳过问题清单）**

问题同时像「能源介质 / 能介」或「电 + 水/气/热」，并且像「累计能耗 / 总能耗 / 综合能耗」时，走 `_handle_energy_query`：

- 从问句解析时间（本月默认，支持上月、最近 N 天、今年、去年）
- 读 `metering_point.true_formula`、`energy_medium_manage`、`data_day`
- 在 Python 里按公式求值，再推表格/图表/总结

目的是避免这类题走 LLM 匹配超时。手册里若有同类 Q-ID，当前也会被这条抢走。

**2. 命中问题清单 → 查库（主路径）**

`qa_matcher` + `keyword_matcher` 对照 `config/FWBZ问题清单.md`：

- 中文单字/二字 + 英文数字做 TF-IDF 余弦，取 top-3
- 问句含子串「你好、天气、Python」等黑名单 → 直接判未匹配（整句闲聊）
- top-1 分数 &lt; 0.15 → 未匹配
- 生产默认 `llm_timeout=0`，**不做 LLM 二次挑选**，直接用 TF-IDF top-1 的 Q-ID
- 主路径只要 `best_qid` 非空就算命中（不用 0.6 置信度阈值）

命中后：

1. `sql_template_loader` 从 `config/FWBZ问答手册.md` 取该 Q-ID 的 SQL 范式  
2. LLM 按用户原话改造范式（时间、设备名等），**不原样执行手册 SQL**  
3. Prompt 还塞入启动时解析的整份 `config/FWBZ_strut.sql`（100+ 张表），并按关键词猜「可能相关表」  
4. 最多生成 3 次；失败把校验错误回灌 prompt  
5. 生成后再做引号、ORDER/WHERE、假列、GROUP BY 等字符串修补  
6. `app/core/sql_guard.py`：只允许 SELECT，禁止多语句，没有分页则补 `LIMIT 500/200`  
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

知识文件：`FWBZ问题清单.md`（Q-ID）、`FWBZ问答手册.md`（范式）、`FWBZ_strut.sql`（列名对错）。  
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

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 健康 | GET | `/api/health` | 服务与模型探测 |
| 聊天窗口 | POST | `/api/chat-stream` | SSE 对话 |
| 界面 | POST | `/api/generate-sql` | 自然语言生成 SQL |
| 界面 | POST | `/api/device/sql` | 按设备生成 SQL |
| 界面 | POST | `/api/generate-report-sql` | 报告用 SQL |
| 界面 | POST | `/api/generate-suggestions` | 建议问法 |
| 界面 | POST | `/api/execute-sql` | 执行 SELECT |
| 界面 | POST | `/api/report/full` | 完整报告 |
| 报告 | * | `/api/ai-report/*` | 运行/能耗/故障/碳排报告与历史 |

更细的字段见 `docs/API接口文档.md`。

## 测试

```bash
pytest tests/
```
