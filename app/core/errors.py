import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_ctx_var

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    status_code = 500
    code = "application_error"


async def _application_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, ApplicationError):
        raise TypeError("Application error handler received an unexpected exception")
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=str(exc),
    )


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise TypeError("HTTP error handler received an unexpected exception")
    if isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = "Request failed"
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code="http_error",
        message=message,
        headers=exc.headers,
    )


async def _validation_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise TypeError("Validation error handler received an unexpected exception")
    details: list[dict[str, Any]] = [
        {
            "location": list(error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _error_response(
        request=request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=details,
    )


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled request exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _error_response(
        request=request,
        status_code=500,
        code="internal_server_error",
        message="An unexpected error occurred",
    )


def _error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details

    request_id = getattr(request.state, "request_id", None) or request_id_ctx_var.get()
    response_headers = dict(headers or {})
    if request_id is not None:
        response_headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status_code,
        content={"error": error, "request_id": request_id},
        headers=response_headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, _application_error_handler)
    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
