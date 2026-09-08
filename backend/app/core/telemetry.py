import contextvars
import json
import logging
import os
import sys
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Context variable for request correlation tracking
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    return correlation_id_ctx.get() or "no-correlation-id"


def set_correlation_id(correlation_id: str) -> None:
    correlation_id_ctx.set(correlation_id)


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records as structured JSON including timestamp,
    severity, logger name, message, and correlation ID.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if present
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "levelname", "levelno", "lineno",
                "module", "msecs", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName",
            ) and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has an X-Correlation-ID for end-to-end tracing.
    If the caller provided one, it is preserved; otherwise a new UUID is minted.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cid = request.headers.get("X-Correlation-ID") or f"cid_{uuid4().hex[:12]}"
        token = correlation_id_ctx.set(cid)

        start_time = time.perf_counter()
        logger = logging.getLogger("app.telemetry")

        logger.info(
            f"HTTP {request.method} {request.url.path} started",
            extra={"method": request.method, "path": request.url.path},
        )

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Correlation-ID"] = cid

            logger.info(
                f"HTTP {request.method} {request.url.path} completed {response.status_code} in {elapsed_ms:.1f}ms",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed_ms, 2),
                },
            )
            return response
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"HTTP {request.method} {request.url.path} failed: {exc}",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(elapsed_ms, 2),
                },
            )
            raise
        finally:
            correlation_id_ctx.reset(token)


def setup_telemetry(app: FastAPI) -> None:
    """
    Configures structured logging and attaches correlation middleware to the app.
    Also enables Azure Application Insights if a connection string is provided.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup is called multiple times
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, StructuredJsonFormatter) for h in root_logger.handlers):
        root_logger.handlers = [handler]

    # Application Insights integration if configured
    appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if appinsights_conn:
        try:
            # Preferred: azure-monitor-opentelemetry (modern Azure SDK)
            from azure.monitor.opentelemetry import configure_azure_monitor
            configure_azure_monitor(connection_string=appinsights_conn)
            root_logger.info("Application Insights configured via azure-monitor-opentelemetry")
        except ImportError:
            try:
                # Fallback: opencensus-ext-azure (legacy)
                from opencensus.ext.azure.log_exporter import AzureLogHandler
                root_logger.addHandler(AzureLogHandler(connection_string=appinsights_conn))
                root_logger.info("Application Insights logging handler attached via opencensus-ext-azure")
            except ImportError:
                root_logger.warning(
                    "APPLICATIONINSIGHTS_CONNECTION_STRING is set but no exporter is installed. "
                    "Run: pip install azure-monitor-opentelemetry"
                )

    app.add_middleware(CorrelationIdMiddleware)
