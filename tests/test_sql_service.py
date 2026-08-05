"""SQL 生成服务测试"""
import pytest
from app.schemas.chat import ChatMessage
from app.services.sql_service import SQLService


class TestSQLService:
    """SQLService 单元测试"""

    def setup_method(self):
        self.service = SQLService()

    def test_extract_sql_with_code_block(self):
        """测试从代码块中提取 SQL"""
        response = """根据你的问题，我生成以下 SQL：

```sql
SELECT * FROM "FWBZ"."alarm_record" WHERE "alarm_status" = '1'
```

这是查询所有未处理告警的语句。
"""
        sql, explanation = self.service.extract_sql(response)
        assert sql == 'SELECT * FROM "FWBZ"."alarm_record" WHERE "alarm_status" = \'1\''
        assert "根据你的问题" in explanation

    def test_extract_sql_without_code_block(self):
        """测试从普通文本中提取 SQL"""
        response = """SELECT "alarm_level_name", COUNT(*) AS cnt FROM "FWBZ"."alarm_record" GROUP BY "alarm_level_name";"""
        sql, explanation = self.service.extract_sql(response)
        assert "alarm_level_name" in sql
        assert "SELECT" in sql

    def test_extract_sql_no_select(self):
        """测试无法提取 SQL 的情况"""
        response = "抱歉，我无法理解你的问题。"
        sql, explanation = self.service.extract_sql(response)
        assert sql == ""
        assert "无法理解" in explanation

    def test_format_history(self):
        """测试格式化历史对话"""
        history = [
            ChatMessage(role="user", content="查询告警"),
            ChatMessage(role="assistant", content="好的，这里是告警信息"),
        ]
        result = self.service._format_history(history)
        assert "用户: 查询告警" in result
        assert "助手: 好的，这里是告警信息" in result

    def test_format_history_empty(self):
        """测试空历史"""
        result = self.service._format_history([])
        assert "（无历史对话）" in result
