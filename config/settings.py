"""
配置模块已迁移至 app/core/config.py
请使用新的导入方式：
    from app.core.config import get_settings
"""
from app.core.config import get_settings

__all__ = ["get_settings"]
