import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def enable_explicit_test_auth_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "allow_local_auth_bypass", True)
