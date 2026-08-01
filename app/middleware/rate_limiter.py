"""Per-API-key sliding-window rate limiter for GeoFile Toolkit.

Uses slowapi (a Limits/Flask-Limiter port for Starlette/FastAPI) with
an in-memory storage backend.

Configuration (environment variables):
    GEOFILE_RATE_LIMIT   – requests allowed per window  (default: 60)
    GEOFILE_RATE_WINDOW  – window size in seconds       (default: 60)

The key function extracts the X-API-Key header so that limits are
tracked per key rather than per IP address.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

_RATE_LIMIT_COUNT = int(os.environ.get("GEOFILE_RATE_LIMIT", "60"))
_RATE_WINDOW_SECS = int(os.environ.get("GEOFILE_RATE_WINDOW", "60"))

# Human-readable limit string consumed by slowapi decorators.
RATE_LIMIT_STRING = f"{_RATE_LIMIT_COUNT}/{_RATE_WINDOW_SECS}second"


def _key_from_api_key(request: Request) -> str:
    """Return the X-API-Key header value, falling back to remote IP.

    Using the API key as the rate-limit bucket ensures that different
    clients behind the same NAT do not share a quota, and that a single
    client cannot escape limits by rotating IPs.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return api_key
    return get_remote_address(request)


limiter = Limiter(key_func=_key_from_api_key)
