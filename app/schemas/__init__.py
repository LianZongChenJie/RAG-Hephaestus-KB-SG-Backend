"""Pydantic 数据模型"""
from app.schemas.chat import ChatMessage, ChatStreamRequest
from app.schemas.sql import (
    GenerateSQLRequest,
    GenerateSQLResponse,
    GenerateReportSQLRequest,
    GenerateReportSQLResponse,
    ReportMetricItem,
    ReportType,
)

__all__ = [
    "ChatMessage",
    "ChatStreamRequest",
    "GenerateSQLRequest",
    "GenerateSQLResponse",
    "GenerateReportSQLRequest",
    "GenerateReportSQLResponse",
    "ReportMetricItem",
    "ReportType",
]
