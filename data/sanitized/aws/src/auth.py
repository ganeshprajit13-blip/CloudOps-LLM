"""
Optional Cognito JWT authentication middleware.

Active when COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID env vars are set.
Skipped entirely for local development (env vars unset).

Uses a pure-ASGI middleware (not BaseHTTPMiddleware) to avoid buffering
streaming responses, which is critical for SSE endpoints.
"""

import json
import logging
import os
from functools import lru_cache

import jwt  # PyJWT
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Paths that skip authentication
AUTH_EXEMPT_PATHS = {"/api/health", "/api/health/deep"}


def is_auth_enabled() -> bool:
    """Check if Cognito auth env vars are configured.

    Reads env vars at call time (not import time) so that tests can
    set them after import and so that hot-reloading picks up changes.
    """
    return bool(
        os.environ.get("COGNITO_USER_POOL_ID")
        and os.environ.get("COGNITO_APP_CLIENT_ID")
    )


def _get_env(name: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.environ.get(name, default)


@lru_cache(maxsize=1)
def _get_jwks_client() -> jwt.PyJWKClient:
    """Fetch and cache the JWKS from Cognito.

    PyJWKClient handles key rotation internally via cache_keys=True.
    The lru_cache ensures we only create one client instance.
    """
    pool_id = _get_env("COGNITO_USER_POOL_ID")
    region = _get_env("AWS_REGION", "us-east-1")
    jwks_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    )
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def verify_token(token: str) -> dict:
    """Verify a Cognito JWT and return its claims.

    Validates signature, expiry, issuer, audience, and token_use.
    """
    client_id = _get_env("COGNITO_APP_CLIENT_ID")
    pool_id = _get_env("COGNITO_USER_POOL_ID")
    region = _get_env("AWS_REGION", "us-east-1")

    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=(f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"),
        options={"require": ["exp", "iss", "sub", "token_use"]},
    )

    # Verify token type — only accept access tokens
    token_use = claims.get("token_use")
    if token_use != "access":  # nosec B105 - Cognito token_use claim value, not a credential
        raise jwt.InvalidTokenError(f"Expected token_use 'access', got '{token_use}'")

    return claims


def _json_401(detail: str) -> tuple[int, list, bytes]:
    """Build a 401 JSON response as raw ASGI parts."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    return 401, headers, body


class CognitoAuthMiddleware:
    """Pure-ASGI middleware that validates Cognito JWTs.

    Unlike BaseHTTPMiddleware, this does NOT buffer the response body,
    so SSE/streaming responses pass through without being held in memory.

    Only active when added to the app. Skips auth for exempt paths and
    CORS preflight (OPTIONS) requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        # Allow health checks and CORS preflight through
        if path in AUTH_EXEMPT_PATHS or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode(
            "utf-8", errors="replace"
        )

        if not auth_value.startswith("Bearer "):
            await self._send_401(send, "Missing or invalid Authorization header")
            return

        token = auth_value[7:]  # Strip "Bearer "
        try:
            verify_token(token)
        except jwt.ExpiredSignatureError:
            await self._send_401(send, "Token expired")
            return
        except jwt.InvalidTokenError:
            logger.warning("JWT validation failed for request to %s", path)
            await self._send_401(send, "Invalid token")
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _send_401(send: Send, detail: str) -> None:
        """Send a 401 JSON response via raw ASGI."""
        status, headers, body = _json_401(detail)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
