"""聊天相关数据模型"""
from typing import List, Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings

settings = get_settings()


class ChatMessage(BaseModel):
    """对话消息"""
    role: Literal["system", "user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    """聊天流请求"""
    messages: List[ChatMessage] = Field(min_length=1)
    temperature: float = Field(
        default=settings.model_defaults.temperature,
        ge=0,
        le=2
    )
    num_ctx: int = Field(
        default=settings.model_defaults.num_ctx,
        ge=512,
        le=8192
    )
