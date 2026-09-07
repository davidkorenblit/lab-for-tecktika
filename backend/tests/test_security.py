from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    extract_user_from_payload,
    get_current_user,
    get_default_dev_user,
    get_expected_audiences,
    get_expected_issuer,
    validate_token,
)


def test_default_dev_user() -> None:
    user = get_default_dev_user()
    assert user.user_id == "local-dev"
    assert user.email == "dev@localhost"
    assert "authenticated" in user.roles


def test_extract_user_from_payload() -> None:
    payload = {
        "oid": "user_abc_123",
        "email": "alice@contoso.com",
        "name": "Alice Smith",
        "roles": ["Admin"],
    }
    user = extract_user_from_payload(payload)
    assert user.user_id == "user_abc_123"
    assert user.email == "alice@contoso.com"
    assert user.name == "Alice Smith"
    assert user.roles == ["Admin"]


def test_extract_user_fallback_sub() -> None:
    payload = {
        "sub": "sub_456",
        "preferred_username": "bob@contoso.com",
    }
    user = extract_user_from_payload(payload)
    assert user.user_id == "sub_456"
    assert user.email == "bob@contoso.com"


@pytest.mark.anyio
async def test_get_current_user_local_no_token() -> None:
    with patch.object(settings, "environment", "local"):
        user = await get_current_user(authorization=None)
        assert user.user_id == "local-dev"


@pytest.mark.anyio
async def test_get_current_user_local_dev_token() -> None:
    with patch.object(settings, "environment", "local"):
        user = await get_current_user(authorization="Bearer dev-token")
        assert user.user_id == "local-dev"


@pytest.mark.anyio
async def test_get_current_user_production_missing_token() -> None:
    with patch.object(settings, "environment", "production"):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=None)
        assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_user_production_invalid_scheme() -> None:
    with patch.object(settings, "environment", "production"):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization="Basic dXNlcjpwYXNz")
        assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_get_current_user_valid_token() -> None:
    fake_payload = {
        "oid": "msal_user_999",
        "email": "user@example.com",
        "name": "Verified User",
        "scp": "access_as_user",
    }

    with (
        patch("app.core.security.validate_token", return_value=fake_payload),
        patch.object(settings, "environment", "production"),
    ):
        user = await get_current_user(authorization="Bearer valid.jwt.token")
        assert user.user_id == "msal_user_999"
        assert user.email == "user@example.com"
        assert user.name == "Verified User"


def test_validate_token_missing_scope() -> None:
    mock_jwk_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = "public_key"
    mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with (
        patch("app.core.security.get_jwks_client", return_value=mock_jwk_client),
        patch("jwt.decode", return_value={"oid": "u1", "scp": "some_other_scope"}),
    ):
        with pytest.raises(HTTPException) as exc_info:
            validate_token("some.token")
        assert exc_info.value.status_code == 403
        assert "access_as_user" in exc_info.value.detail


def test_expected_audiences() -> None:
    with patch.object(settings, "azure_client_id_api", "client_123"):
        audiences = get_expected_audiences()
        assert "client_123" in audiences
        assert "api://client_123" in audiences
