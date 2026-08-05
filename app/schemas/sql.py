"""SQL 生成相关数据模型"""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.chat import ChatMessage


class GenerateSQLRequest(BaseModel):
    """SQL 生成请求"""
    question: str = Field(..., description="用户的问题")
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="历史对话上下文"
    )


class GenerateSQLResponse(BaseModel):
    """SQL 生成响应"""
    sql: str = Field(..., description="生成的 SQL 语句")
    explanation: Optional[str] = Field(
        None,
        description="SQL 说明（如有）"
    )
