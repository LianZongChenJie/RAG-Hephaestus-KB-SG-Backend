"""Pydantic 数据模型"""
from app.schemas.chat import ChatMessage, ChatStreamRequest
from app.schemas.sql import GenerateSQLRequest, GenerateSQLResponse

__all__ = [
    "ChatMessage",
    "ChatStreamRequest",
    "GenerateSQLRequest",
    "GenerateSQLResponse",
]
