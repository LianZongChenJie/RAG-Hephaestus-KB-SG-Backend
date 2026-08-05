"""
数据库模块已迁移至 app/core/database.py
请使用新的导入方式：
    from app.core.database import init_db, close_db, save_access_log
"""
from app.core.database import close_db, init_db, save_access_log

__all__ = ["init_db", "close_db", "save_access_log"]
