"""SQL 生成接口"""
import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.schemas.sql import GenerateSQLRequest, GenerateSQLResponse
from app.services.sql_service import SQLService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["SQL 生成"])


@router.post("/generate-sql", response_model=GenerateSQLResponse)
async def generate_sql(body: GenerateSQLRequest) -> GenerateSQLResponse:
    """
    根据用户问题和历史上下文，调用大模型生成 SQL 语句。

    - 读取 config/query.json 获取数据库表结构
    - 结合历史对话理解上下文
    - 返回生成的 SQL 及其说明
    """
    try:
        sql_service = SQLService()
        sql, explanation = await sql_service.generate_sql(
            body.question,
            body.history,
        )

        return GenerateSQLResponse(
            sql=sql,
            explanation=explanation,
        )

    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="无法连接 Ollama，请确认已执行 ollama serve 且端口 11434 可用",
        )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama 响应超时，请稍后重试",
        )
    except Exception as exc:
        logger.exception("SQL 生成失败")
        raise HTTPException(
            status_code=500,
            detail=f"SQL 生成失败: {str(exc)}",
        )
