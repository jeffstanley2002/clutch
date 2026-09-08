"""Small deployment authentication boundary for the public API surface."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request

API_KEY_HEADER = "X-Clutch-API-Key"  # pragma: allowlist secret


def authorize_request(request: Request) -> None:
    """Require a constant-time API-key match when deployment auth is enabled."""

    expected = os.getenv("CLUTCH_API_KEY", "").strip()
    require_auth = _auth_required()
    if not expected and not require_auth:
        return
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API authentication is required but not configured",
        )
    presented = request.headers.get(API_KEY_HEADER, "")
    if not presented or not secrets.compare_digest(presented, expected):
        raise HTTPException(
            status_code=401,
            detail="invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def _auth_required() -> bool:
    raw = os.getenv("CLUTCH_REQUIRE_AUTH", "false").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", ""}:
        return False
    raise HTTPException(
        status_code=503,
        detail="API authentication configuration is invalid",
    )
