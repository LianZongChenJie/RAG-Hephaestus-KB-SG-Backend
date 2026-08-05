# Hephaestus RAG 后端

基于 FastAPI + Ollama 的 RAG 聊天后端，支持 SSE 流式对话和 SQL 生成。

## 项目结构

```
├── app/
│   ├── api/          # API 路由层
│   ├── core/         # 核心配置和客户端
│   ├── schemas/      # Pydantic 数据模型
│   └── services/     # 业务逻辑层
├── config/           # 配置文件
├── scripts/          # 脚本
├── tests/            # 测试
└── main.py           # 入口文件
```

## 快速开始

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置：
- 编辑 `config/config.yaml` 设置数据库、Ollama 等配置
- 编辑 `config/query.json` 设置数据库表结构

3. 启动服务：
```bash
python main.py
```

## API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger 文档。

### 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/chat-stream` | POST | SSE 流式聊天 |
| `/api/generate-sql` | POST | SQL 生成 |

## 开发

### 运行测试
```bash
pytest tests/
```

### 代码规范
- 分层清晰：API → Service → Core
- 业务逻辑不放在 API 层
- 配置集中管理，不硬编码
