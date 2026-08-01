"""FastAPI security dependency for API-key verification.

Usage::

    from app.auth.dependencies import verify_api_key

    @app.get("/protected", dependencies=[Depends(verify_api_key)])
    def protected() -> dict:
        ...

The key is expected in the ``X-API-Key`` request header.

* Missing header  → **401 Unauthorized**
* Unknown key     → **401 Unauthorized**

The dependency returns the validated raw key string so route handlers
can use it (e.g. for per-key rate limiting or audit logging).
"""

from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.auth.api_key import is_valid

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> str:
    """Validate ``X-API-Key`` header.  Raises 401 on failure."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Supply it via the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not is_valid(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
