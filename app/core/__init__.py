"""核心配置模块"""
from app.core.config import get_settings
from app.core.database import close_db, init_db, save_access_log
from app.core.ollama import OllamaClient

__all__ = [
    "get_settings",
    "init_db",
    "close_db",
    "save_access_log",
    "OllamaClient",
]
