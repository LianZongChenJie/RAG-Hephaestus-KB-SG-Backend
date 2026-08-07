"""
FastAPI 后端入口
代理 Ollama Chat API，提供 SSE 流式对话与 SQL 生成功能。
访问记录写入 PostgreSQL。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai_report_router, chat_router, health_router, sql_gen_router
from app.core import close_db, init_db
from app.core.config import get_settings

settings = get_settings()

# 配置日志
logging.basicConfig(level=settings.logging.level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.app.title,
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(sql_gen_router)
app.include_router(ai_report_router)


@app.get("/")
async def root() -> dict[str, Any]:
    """根路径"""
    return {
        "name": settings.app.title,
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=True,
    )
