# -*- coding: utf-8 -*-
"""在新版接口边界记录安全诊断，不改变原异常、响应或业务流程。"""

import json
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .services.cron.managed.diagnostics import format_management_error

logger = logging.getLogger(__name__)


def _identifier(value: Any) -> str:
    """只接受短标识符，防止换行注入及意外输出任意正文。"""
    if isinstance(value, str) and re.fullmatch(
        r"[a-zA-Z0-9_.:-]{1,128}",
        value,
    ):
        return value
    return "-"


def _error_code(value: Any) -> str:
    if isinstance(value, str) and re.fullmatch(
        r"(?:cron|swe|workflow|invalid|conflicting|agent)_[a-z0-9_]{1,120}",
        value,
    ):
        return value
    return "omitted_non_code_detail"


def _response_metadata(response: Response) -> dict:
    """只读取非流式错误 JSON 的有限白名单字段，不记录原始内容。"""
    if not isinstance(response, JSONResponse) or len(response.body) > 65536:
        return {}
    try:
        body = json.loads(response.body)
    except (ValueError, UnicodeError):
        return {}
    if not isinstance(body, dict):
        return {}
    operation = body.get("operation")
    if isinstance(operation, dict):
        return {
            key: operation.get(key)
            for key in ("operation_id", "job_id", "stage", "error_code")
        }
    return {"error_code": body.get("detail")}


def _context(request: Request, metadata: dict) -> str:
    """不读取请求正文、查询参数或认证 Header。"""
    values = {
        "request_id": request.headers.get("x-request-id"),
        "trace_id": request.headers.get("x-b3-traceid"),
    }
    for key in (
        "job_id",
        "operation_id",
        "task_id",
        "batch_id",
        "execution_id",
    ):
        values[key] = request.path_params.get(key)
    for key in ("operation_id", "job_id", "stage"):
        if metadata.get(key) is not None:
            values[key] = metadata[key]
    return " ".join(
        f"{key}={_identifier(value)}" for key, value in values.items()
    )


def _log_failure(
    request: Request,
    route: str,
    status: int,
    metadata: dict,
    error: Exception | None = None,
) -> None:
    try:
        logger.log(
            logging.ERROR if status >= 500 else logging.WARNING,
            "Scheduler 接口失败 method=%s route=%s http_status=%s "
            "error_code=%s %s\n%s",
            request.method,
            route,
            status,
            _error_code(metadata.get("error_code")),
            _context(request, metadata),
            (
                format_management_error(error)
                if error
                else "no_exception_receipt"
            ),
        )
    except Exception:  # pylint: disable=broad-except
        # 诊断输出失败不得覆盖原业务异常或改变原响应。
        return


class LoggedAPIRoute(APIRoute):
    """覆盖依赖、参数校验和业务出口；不消费 SSE 等流式响应。"""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def logged_handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except Exception as error:
                status = 500
                detail = None
                if isinstance(error, HTTPException):
                    status, detail = error.status_code, error.detail
                elif isinstance(error, RequestValidationError):
                    status = 422
                _log_failure(
                    request,
                    self.path,
                    status,
                    {"error_code": detail},
                    error,
                )
                raise
            if response.status_code >= 400:
                _log_failure(
                    request,
                    self.path,
                    response.status_code,
                    _response_metadata(response),
                )
            return response

        return logged_handler
