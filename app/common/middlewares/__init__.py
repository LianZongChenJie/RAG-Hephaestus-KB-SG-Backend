"""共用中间件。"""
from app.common.middlewares.access_log import AccessLogMiddleware

__all__ = ["AccessLogMiddleware"]
