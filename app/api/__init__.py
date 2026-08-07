"""API 路由层"""
from app.api.ai_report import router as ai_report_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.sql_gen import router as sql_gen_router

__all__ = ["chat_router", "health_router", "sql_gen_router", "ai_report_router"]
