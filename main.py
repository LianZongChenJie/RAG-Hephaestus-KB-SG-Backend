"""
FastAPI 后端入口。

同一进程挂两套前端：
- 聊天窗口：POST /api/chat-stream
- 小镇服务保障平台：/api/ai-report/*
共用 GET /api/health。访问记录写入达梦 hephaestus_chat_access_logs。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat.api import router as chat_router
from app.common import close_db, init_db
from app.common.config import get_settings
from app.common.health import router as health_router
from app.common.logger import init_logging
from app.common.middlewares.access_log import AccessLogMiddleware
from app.legacy.api import router as sql_gen_router
from app.report.api import router as ai_report_router

settings = get_settings()

# 初始化日志系统（必须在其他日志操作之前）
init_logging()

# 配置日志
logging.basicConfig(level=settings.logging.level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    logger.info("应用启动中...")
    await init_db()
    logger.info("应用启动完成")
    yield
    logger.info("应用关闭中...")
    await close_db()
    logger.info("应用已关闭")


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

# 访问日志中间件
app.add_middleware(AccessLogMiddleware)

# 注册路由（URL 不变）
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(ai_report_router)
app.include_router(sql_gen_router)


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
