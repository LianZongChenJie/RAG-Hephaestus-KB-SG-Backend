"""健康检查接口"""
from typing import Any

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.ollama import OllamaClient
from app.middlewares.access_log import inject_response

router = APIRouter(tags=["健康检查"])
settings = get_settings()


@router.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    """健康检查，并探测 Ollama 是否可达"""
    ollama = OllamaClient()
    ollama_ok, detail, model_ready = await ollama.check_health()

    data = {
        "ok": True,
        "ollama": ollama_ok,
        "model": ollama.model,
        "model_ready": model_ready,
        "mode": "qwen9b-gpu-fast",
        "detail": detail,
    }
    inject_response(request, data)
    return data
