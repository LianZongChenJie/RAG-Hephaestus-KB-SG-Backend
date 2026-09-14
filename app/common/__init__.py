"""共用基础设施：配置、达梦、模型、日志、健康检查。"""
from app.common.config import get_settings
from app.common.database import close_db, init_db, save_access_log
from app.common.dameng import (
    close_dameng,
    execute_query,
    execute_scalar,
    health_check as dameng_health_check,
)
from app.common.ollama import OllamaClient

__all__ = [
    "get_settings",
    "init_db",
    "close_db",
    "save_access_log",
    "OllamaClient",
    "execute_query",
    "execute_scalar",
    "close_dameng",
    "dameng_health_check",
]
