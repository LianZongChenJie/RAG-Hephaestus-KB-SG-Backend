"""请求访问日志中间件

功能：
- 记录接口访问的请求参数
- 记录接口返回的参数
- 记录访问者 IP
- 记录接口响应时间
"""
import json
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logger import get_logger

logger = get_logger("access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """访问日志中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    # 流式接口路径前缀，跳过 body 读取以避免与流式 receive 冲突
    STREAMING_PATHS = ("/api/chat-stream", "/api/chat/stream")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        # 获取客户端 IP
        client_ip = self._get_client_ip(request)

        # 获取请求信息
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)

        # 记录请求体（仅对 POST/PUT/PATCH，且非流式接口）
        request_body = None
        is_streaming = any(path.startswith(p) for p in self.STREAMING_PATHS)
        if method in ["POST", "PUT", "PATCH"] and not is_streaming:
            try:
                body = await request.body()
                if body:
                    try:
                        request_body = json.loads(body)
                    except json.JSONDecodeError:
                        request_body = body.decode("utf-8", errors="ignore")
                    # 重新设置 body 以便后续处理
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
            except Exception:
                request_body = None

        # 记录开始时间
        start_time = time.time()
        
        # 处理请求
        response = None
        response_body = None
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # 尝试获取响应体
            response_body = await self._get_response_body(response)
            
        except Exception as e:
            logger.error(f"请求处理异常: {e}")
            raise
        finally:
            # 计算响应时间
            duration = time.time() - start_time
            
            # 记录日志
            self._log_access(
                client_ip=client_ip,
                method=method,
                path=path,
                query_params=query_params,
                request_body=request_body,
                response_body=response_body,
                status_code=status_code,
                duration=duration
            )
        
        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        # 优先从 X-Forwarded-For 获取（反向代理场景）
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # 其次从 X-Real-IP 获取
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 最后从连接获取
        if request.client:
            return request.client.host
        
        return "unknown"

    async def _get_response_body(self, response: Response) -> dict | None:
        """尝试获取响应体"""
        try:
            if hasattr(response, "body"):
                body = response.body
                if body:
                    try:
                        return json.loads(body)
                    except (json.JSONDecodeError, TypeError):
                        return {"raw": "非JSON响应或二进制数据"}
            return None
        except Exception:
            return None

    def _log_access(
        self,
        client_ip: str,
        method: str,
        path: str,
        query_params: dict,
        request_body: dict | str | None,
        response_body: dict | None,
        status_code: int,
        duration: float
    ):
        """记录访问日志"""
        # 脱敏处理：移除敏感字段
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
        
        if response_body and isinstance(response_body, dict):
            response_body = mask_sensitive(response_body)

        # 构建日志内容
        log_data = {
            "ip": client_ip,
            "method": method,
            "path": path,
            "query": query_params if query_params else None,
            "request": request_body,
            "response": response_body,
            "status": status_code,
            "duration_ms": round(duration * 1000, 2)
        }

        # 根据状态码选择日志级别
        if status_code >= 500:
            logger.error(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")
        elif status_code >= 400:
            logger.warning(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")
        else:
            logger.info(f"访问日志: {json.dumps(log_data, ensure_ascii=False, default=str)}")


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
