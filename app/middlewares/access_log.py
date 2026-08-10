"""请求访问日志中间件

功能：
- 记录接口访问的请求参数（middleware 层）
- 记录接口返回的参数（endpoint 通过 inject_response 注入）
- 记录访问者 IP
- 记录接口响应时间
"""
import json
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger

logger = get_logger("access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """访问日志中间件"""

    # 流式接口路径前缀，跳过 body 读取
    STREAMING_PATHS = ("/api/chat-stream", "/api/chat/stream")

    async def dispatch(self, request: Request, call_next: Callable):
        """处理请求并记录日志"""
        client_ip = self._get_client_ip(request)
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)

        # 读取请求体
        request_body = None
        is_streaming = any(path.startswith(p) for p in self.STREAMING_PATHS)
        if method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    try:
                        request_body = json.loads(body)
                    except json.JSONDecodeError:
                        request_body = body.decode("utf-8", errors="ignore")

                    if is_streaming:
                        try:
                            request.state._body_json = json.loads(body)
                        except Exception:
                            request.state._body_json = None
                    else:
                        # 非流式：重建 receive 让 endpoint 重新读 body
                        async def receive():
                            return {"type": "http.request", "body": body}
                        request._receive = receive
            except Exception:
                request_body = None

        start_time = time.time()

        if is_streaming:
            # 流式 SSE 接口跳过，endpoint 自行记日志
            response = await call_next(request)
            return response

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"请求处理异常: {e}")
            raise

        duration = time.time() - start_time

        # 优先读 endpoint 通过 inject_response 注入的响应体
        response_body = getattr(request.state, "_response_body", None)

        self._log_access(
            client_ip=client_ip,
            method=method,
            path=path,
            query_params=query_params,
            request_body=request_body,
            response_body=response_body,
            status_code=status_code,
            duration=duration,
        )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"

    def _log_access(
        self,
        client_ip: str,
        method: str,
        path: str,
        query_params: dict,
        request_body: dict | str | None,
        response_body: dict | None,
        status_code: int,
        duration: float,
    ):
        """记录访问日志"""
        sensitive_fields = ["password", "token", "secret", "key", "authorization"]

        def mask_sensitive(data: dict) -> dict:
            if not isinstance(data, dict):
                return data
            masked = {}
            for k, v in data.items():
                if any(s in k.lower() for s in sensitive_fields):
                    masked[k] = "***"
                else:
                    masked[k] = v
            return masked

        if request_body and isinstance(request_body, dict):
            request_body = mask_sensitive(request_body)
            if "messages" in request_body and isinstance(request_body["messages"], list):
                msgs = request_body["messages"]
                user_msgs = [m for m in msgs if isinstance(m, dict) and m.get("role") == "user"]
                if user_msgs:
                    request_body["messages"] = [user_msgs[-1]]
                    if len(msgs) > 1:
                        request_body["_truncated"] = f"共{len(msgs)}条消息，已截断"

        if response_body and isinstance(response_body, dict):
            response_body = mask_sensitive(response_body)

        log_data = {
            "ip": client_ip,
            "method": method,
            "path": path,
            "query": query_params if query_params else None,
            "request": request_body,
            "response": response_body,
            "status": status_code,
            "duration_ms": round(duration * 1000, 2),
        }

        if status_code >= 500:
            logger.error(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")
        elif status_code >= 400:
            logger.warning(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")
        else:
            logger.info(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")


def inject_response(request: Request, data: dict):
    """
    供 endpoint 调用的工具函数：将响应体注入 request.state，
    middleware 读取后写入日志。

    用法：
        @router.get("/xxx")
        async def xxx(request: Request) -> SomeResponse:
            result = await do_something()
            inject_response(request, result.model_dump())
            return result
    """
    request.state._response_body = data


async def log_api_call(
    endpoint: str,
    params: dict | None,
    result: dict | None,
    error: str | None = None
):
    """手动记录 API 调用日志（用于非中间件场景）"""
    log_data = {
        "endpoint": endpoint,
        "params": params,
        "result": result,
        "error": error
    }

    if error:
        logger.error(f"API调用失败: {json.dumps(log_data, ensure_ascii=False, default=str)}")
    else:
        logger.info(f"API调用成功: {json.dumps(log_data, ensure_ascii=False, default=str)}")
