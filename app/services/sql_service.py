"""SQL 生成服务"""
import logging
import re
from typing import List, Optional, Tuple

from app.core.config import get_settings
from app.core.ollama import OllamaClient
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """你是一个专业的达梦数据库 SQL 生成专家。

数据库信息：
- 类型：Dameng (08.01.448)
- 字符集：UTF-8
- 默认 Schema：FWBZ

重要规则：
1. 所有表名和字段名必须用双引号包裹，如 "FWBZ"."table_name"
2. 日期函数使用达梦兼容语法
3. 分页使用 LIMIT 和 OFFSET
4. 返回的 SQL 必须只包含 SELECT 语句（禁止 INSERT/UPDATE/DELETE）
5. 理解常见业务术语的别名（如"报警类别"对应 alarm_category）
6. 如果问题涉及时间范围，优先使用最近的 7 天作为默认范围

请根据用户的问题，参考以下表结构信息生成准确的 SQL 查询语句。
只返回 SQL 语句，不要额外的解释。如果无法确定查询意图，返回解释说明。
"""

USER_TEMPLATE = """表结构信息：
{schema_info}

历史对话：
{history}

当前问题：{question}

请生成对应的 SQL 查询语句："""


class SQLService:
    """SQL 生成服务"""

    def __init__(self):
        self.ollama = OllamaClient()

    def build_prompt(self, question: str, history: List[ChatMessage]) -> Tuple[str, str]:
        """构建 SQL 生成的 prompt"""
        schema_info = self._extract_schema_info()
        history_text = self._format_history(history)

        user_prompt = USER_TEMPLATE.format(
            schema_info=schema_info,
            history=history_text,
            question=question,
        )
        return SYSTEM_PROMPT, user_prompt

    def _extract_schema_info(self) -> str:
        """提取表结构信息用于生成 prompt"""
        query_config = settings.query_config
        if not query_config:
            return "未找到表结构配置"

        lines = []
        db_info = query_config.get("database", {})
        lines.append(f"数据库: {db_info.get('name', 'N/A')}")
        lines.append(f"Schema: {db_info.get('schema', 'FWBZ')}")
        lines.append("")

        tables = query_config.get("tables", {})
        for table_name, table_info in tables.items():
            lines.append(f"【{table_info.get('name', table_name)}】 - {table_info.get('description', '')}")
            fields = table_info.get("fields", {})
            for field_name, field_info in fields.items():
                desc = field_info.get("desc", "")
                ftype = field_info.get("type", "")
                flags = []
                if field_info.get("searchable"):
                    flags.append("可搜索")
                if field_info.get("filterable"):
                    flags.append("可筛选")
                if field_info.get("groupable"):
                    flags.append("可分组")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                lines.append(f"  - {field_name}: {ftype} - {desc}{flag_str}")
            lines.append("")

        return "\n".join(lines)

    def _format_history(self, history: List[ChatMessage]) -> str:
        """格式化历史对话"""
        if not history:
            return "（无历史对话）"

        lines = []
        for msg in history:
            role = "用户" if msg.role == "user" else "助手"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    def extract_sql(self, response: str) -> Tuple[str, Optional[str]]:
        """从模型回复中提取 SQL 和说明"""
        # 尝试提取 ```sql ... ``` 包裹的 SQL
        sql_pattern = r"```sql\s*(.*?)\s*```"
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            sql = match.group(1).strip()
            explanation = response.replace(match.group(0), "").strip()
            if explanation:
                return sql, explanation
            return sql, None

        # 如果没有代码块，检查是否包含 SELECT 语句
        select_pattern = r"(SELECT\s+.*?)(?:;|$)"
        match = re.search(select_pattern, response, re.DOTALL | re.IGNORECASE)

        if match:
            sql = match.group(1).strip()
            parts = response.split(sql, 1)
            if len(parts) > 1 and len(parts[0].strip()) > 10:
                return sql, parts[0].strip()
            return sql, None

        # 没有识别到 SQL，返回原内容作为说明
        return "", response.strip()

    async def generate_sql(self, question: str, history: List[ChatMessage]) -> Tuple[str, Optional[str]]:
        """调用大模型生成 SQL"""
        system_prompt, user_prompt = self.build_prompt(question, history)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info("生成 SQL，问题: %s", question[:100])

        payload = self.ollama.build_sql_payload(messages)
        response_text = await self.ollama.chat(payload)

        return self.extract_sql(response_text)
