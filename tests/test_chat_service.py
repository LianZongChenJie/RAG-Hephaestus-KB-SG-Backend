"""聊天服务测试"""
import pytest
from app.schemas.chat import ChatMessage, ChatStreamRequest
from app.services.chat_service import ChatService


class TestChatService:
    """ChatService 单元测试"""

    def setup_method(self):
        self.service = ChatService()

    def test_get_last_user_question(self):
        """测试获取最后一个用户问题"""
        messages = [
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="assistant", content="你好，有什么可以帮助你的？"),
            ChatMessage(role="user", content="查询告警记录"),
        ]
        result = self.service.get_last_user_question(messages)
        assert result == "查询告警记录"

    def test_get_last_user_question_empty(self):
        """测试只有一条消息的情况"""
        messages = [ChatMessage(role="user", content="单条消息")]
        result = self.service.get_last_user_question(messages)
        assert result == "单条消息"

    def test_build_payload(self):
        """测试构建请求 payload"""
        body = ChatStreamRequest(
            messages=[ChatMessage(role="user", content="你好")],
            temperature=0.7,
            num_ctx=2048,
        )
        payload = self.service.build_payload(body)

        assert payload["model"] is not None
        assert payload["stream"] is True
        assert payload["options"]["temperature"] == 0.7
        assert payload["options"]["num_ctx"] == 2048
