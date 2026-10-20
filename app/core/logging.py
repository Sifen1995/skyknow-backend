import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to hold request_id across async execution contexts
request_id_ctx_var: ContextVar[str | None] = ContextVar(
    "request_id", default=None
)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_ctx_var.get(),
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Configures system-wide structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence verbose default loggers if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to inject or extract X-Request-ID for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx_var.set(req_id)

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id

        request_id_ctx_var.reset(token)
        return response