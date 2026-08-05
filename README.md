# Hephaestus RAG 后端

基于 FastAPI + Ollama 的 RAG 聊天后端，支持 SSE 流式对话和自然语言 SQL 生成，访问记录写入 PostgreSQL。

## 技术栈

- **FastAPI** — 高性能异步 Web 框架
- **Ollama** — 本地大模型推理服务（qwen3.5:9b）
- **PostgreSQL** — 访问日志存储
- **httpx** — 异步 HTTP 客户端

## 项目结构

```
RAG-Hephaestus-KB-SG-Backend/
├── app/
│   ├── api/              # API 路由层
│   │   ├── chat.py       # SSE 流式聊天接口
│   │   ├── health.py     # 健康检查接口
│   │   └── sql_gen.py    # 自然语言 SQL 生成接口
│   ├── core/             # 核心模块
│   │   ├── config.py     # 配置管理（yaml + query.json）
│   │   ├── database.py   # PostgreSQL 连接与日志写入
│   │   └── ollama.py     # Ollama API 客户端封装
│   ├── schemas/          # Pydantic 数据模型
│   │   ├── chat.py       # 聊天请求/响应模型
│   │   └── sql.py        # SQL 生成模型
│   └── services/         # 业务逻辑层
│       ├── chat_service.py   # 聊天服务（流式 + 日志）
│       └── sql_service.py    # SQL 生成服务（表结构 → prompt → SQL）
├── config/
│   ├── config.yaml       # 主配置（Ollama、数据库、模型参数）
│   └── query.json        # 数据库表结构定义（自然语言查询规则库）
├── scripts/              # 辅助脚本
├── tests/               # 测试用例
└── main.py              # 入口文件
```

## 快速开始

### 环境要求

- Python 3.9+
- Ollama 服务运行中（模型：qwen3.5:9b）
- PostgreSQL 数据库

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config/config.yaml`：

```yaml
ollama:
  chat_url: "http://<Ollama服务器IP>:11434/api/chat"
  tags_url: "http://<Ollama服务器IP>:11434/api/tags"
  model: "qwen3.5:9b"

database:
  host: "<PostgreSQL地址>"
  port: 5432
  user: "postgres"
  password: "<密码>"
  name: "Hephaestus"
```

编辑 `config/query.json` 定义数据库表结构，供 SQL 生成使用。

### 3. 启动服务

```bash
python main.py
```

服务默认运行在 `http://0.0.0.0:8000`，支持热重载。

## API 接口

启动后访问 http://localhost:8000/docs 查看完整的 Swagger 文档。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务基本信息 |
| `/api/health` | GET | 健康检查（探测 Ollama 是否可用） |
| `/api/chat-stream` | POST | SSE 流式聊天 |
| `/api/generate-sql` | POST | 自然语言生成 SQL 语句 |

### 聊天接口示例

```bash
curl -X POST http://localhost:8000/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.6,
    "num_ctx": 2048
  }'
```

### SQL 生成接口示例

```bash
curl -X POST http://localhost:8000/api/generate-sql \
  -H "Content-Type: application/json" \
  -d '{
    "question": "查询最近一周的告警记录",
    "history": []
  }'
```

## query.json 表结构配置

`query.json` 是 SQL 生成的核心配置，定义数据库的表结构、字段含义、关联关系和常用 SQL 模板。

```json
{
  "database": { "type": "Dameng", "schema": "FWBZ" },
  "tables": {
    "alarm_record": {
      "name": "alarm_record",
      "aliases": ["告警记录", "报警记录", "告警历史"],
      "description": "告警记录表",
      "fields": {
        "alarm_time": { "type": "TIMESTAMP(6)", "desc": "告警时间", "time_field": true },
        "alarm_category_name": { "type": "VARCHAR(255)", "desc": "告警类别名称", "filterable": true },
        "alarm_level_name": { "type": "VARCHAR(255)", "desc": "告警级别", "filterable": true },
        "alarm_status": { "type": "VARCHAR(1)", "desc": "状态【1-未处理，2-已消除】" }
      }
    }
  }
}
```

详细配置说明请参考 query.json 内注释。

## 开发

### 代码规范

- **API → Service → Core** 三层架构
- 业务逻辑不放在 API 层
- 配置集中管理，不硬编码
- 使用 Pydantic 做请求/响应校验

### 运行测试

```bash
pytest tests/
```

### Ollama 远程部署注意事项

如果 Ollama 不在本机，需要：

1. 服务器上设置环境变量允许远程访问：
   ```bash
   export OLLAMA_HOST=0.0.0.0
   ollama serve
   ```

2. 确认防火墙放行了 `11434` 端口

3. `config.yaml` 中 Ollama 地址改为服务器 IP
