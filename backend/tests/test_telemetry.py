import json
import logging
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.telemetry import (
    CorrelationIdMiddleware,
    StructuredJsonFormatter,
    get_correlation_id,
    set_correlation_id,
    setup_telemetry,
)


def test_correlation_id_context() -> None:
    set_correlation_id("test_cid_123")
    assert get_correlation_id() == "test_cid_123"


def test_structured_json_formatter() -> None:
    formatter = StructuredJsonFormatter()
    set_correlation_id("cid_abc")

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test log message"
    assert parsed["correlation_id"] == "cid_abc"


def test_correlation_id_middleware_attaches_header() -> None:
    app = FastAPI()
    setup_telemetry(app)

    @app.get("/test-endpoint")
    def sample():
        return {"status": "ok"}

    client = TestClient(app)

    # Without incoming correlation ID, one is generated
    res = client.get("/test-endpoint")
    assert res.status_code == 200
    assert "X-Correlation-ID" in res.headers
    assert res.headers["X-Correlation-ID"].startswith("cid_")

    # With caller-supplied correlation ID, it is preserved
    res2 = client.get(
        "/test-endpoint", headers={"X-Correlation-ID": "caller_cid_999"}
    )
    assert res2.status_code == 200
    assert res2.headers["X-Correlation-ID"] == "caller_cid_999"
