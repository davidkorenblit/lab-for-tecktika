import logging
from typing import Any

from fastapi import Header, HTTPException, status
import jwt
from jwt import PyJWKClient, PyJWTError
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []


_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        tenant_id = settings.azure_tenant_id or "common"
        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def get_expected_issuer() -> str:
    tenant_id = settings.azure_tenant_id or "common"
    return f"https://login.microsoftonline.com/{tenant_id}/v2.0"


def get_expected_audiences() -> list[str]:
    client_id = settings.azure_client_id_api
    if not client_id:
        return []
    return [client_id, f"api://{client_id}"]


def validate_token(token: str) -> dict[str, Any]:
    """
    Validates a Microsoft Entra ID JWT Bearer token using JWKS.
    Checks issuer, audience, and scope (access_as_user).
    """
    client = get_jwks_client()
    expected_issuer = get_expected_issuer()
    expected_audiences = get_expected_audiences()

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=expected_issuer,
            audience=expected_audiences,
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": bool(expected_audiences),
            },
        )
    except PyJWTError as exc:
        logger.warning(f"JWT validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Validate scope if present
    scopes = payload.get("scp", "").split()
    if scopes and "access_as_user" not in scopes:
        logger.warning("Token missing access_as_user scope")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: access_as_user scope required",
        )

    return payload


def extract_user_from_payload(payload: dict[str, Any]) -> AuthenticatedUser:
    user_id = (
        payload.get("oid")
        or payload.get("sub")
        or payload.get("preferred_username")
        or "unknown-user"
    )
    email = payload.get("email") or payload.get("preferred_username") or payload.get("upn")
    name = payload.get("name")
    roles = payload.get("roles", [])

    return AuthenticatedUser(
        user_id=str(user_id),
        email=str(email) if email else None,
        name=str(name) if name else None,
        roles=roles if isinstance(roles, list) else [str(roles)],
    )


def get_default_dev_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="local-dev",
        email="dev@localhost",
        name="Local Developer",
        roles=["authenticated"],
    )


async def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """
    FastAPI dependency for authenticating incoming requests.
    Supports MSAL Bearer token with full JWKS verification,
    as well as a safe Local Dev mode when running locally.
    """
    is_local = settings.environment.lower() in ("local", "dev", "test")

    if not authorization:
        if is_local:
            return get_default_dev_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        if is_local:
            return get_default_dev_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme. Expected Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Local dev token bypass (e.g. VITE_AUTH_DEV_TOKEN)
    if is_local and token in ("dev-token", "local-dev", "test-token"):
        return get_default_dev_user()

    try:
        payload = validate_token(token)
        return extract_user_from_payload(payload)
    except HTTPException:
        if is_local:
            logger.info("Local environment: falling back to dev user after token error")
            return get_default_dev_user()
        raise
