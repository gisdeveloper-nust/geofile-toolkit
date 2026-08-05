"""API key generation and in-memory storage for GeoFile Toolkit.

Keys are stored in a module-level dict (keyed by the raw key string)
with associated metadata. On startup, any keys listed in the
``GEOFILE_API_KEYS`` environment variable (comma-separated) are
pre-loaded so operators can inject keys without hitting the HTTP
endpoint.

Key format: ``gftk_<32-hex-chars>``  (128-bit entropy).
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from threading import Lock
from typing import TypedDict


class KeyRecord(TypedDict):
    """Metadata stored alongside every API key."""

    key: str
    label: str
    created_at: str  # ISO-8601 UTC
    request_count: int
    last_used_at: str | None
    total_bytes_processed: int
    endpoint_counts: dict[str, int]


_KEY_PREFIX = "gftk_"
_KEY_HEX_BYTES = 16  # 128-bit → 32 hex chars

# In-process key store: {raw_key: KeyRecord}
_store: dict[str, KeyRecord] = {}
_store_lock = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bootstrap_from_env() -> None:
    """Pre-load keys supplied via the GEOFILE_API_KEYS env var."""
    raw = os.environ.get("GEOFILE_API_KEYS", "").strip()
    if not raw:
        return
    for raw_key in raw.split(","):
        raw_key = raw_key.strip()
        if raw_key and raw_key not in _store:
            _store[raw_key] = KeyRecord(
                key=raw_key,
                label="env-bootstrap",
                created_at=_now_iso(),
                request_count=0,
                last_used_at=None,
                total_bytes_processed=0,
                endpoint_counts={},
            )


_bootstrap_from_env()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_key(label: str = "") -> KeyRecord:
    """Generate, store, and return a new API key record."""
    raw = _KEY_PREFIX + secrets.token_hex(_KEY_HEX_BYTES)
    record: KeyRecord = KeyRecord(
        key=raw,
        label=label or "unnamed",
        created_at=_now_iso(),
        request_count=0,
        last_used_at=None,
        total_bytes_processed=0,
        endpoint_counts={},
    )
    _store[raw] = record
    return record


def is_valid(key: str) -> bool:
    """Return True if *key* is present in the key store."""
    return key in _store


def list_keys() -> list[KeyRecord]:
    """Return all stored key records (keys not redacted)."""
    return list(_store.values())


def revoke_key(key: str) -> bool:
    """Remove *key* from the store.  Returns True if it existed."""
    return _store.pop(key, None) is not None


def record_usage(api_key: str, endpoint: str, bytes_processed: int) -> None:
    """Record one authenticated processing request for an API key."""
    if bytes_processed < 0:
        raise ValueError("bytes_processed cannot be negative")
    with _store_lock:
        record = _store.get(api_key)
        if record is None:
            raise KeyError("Unknown API key")
        record["request_count"] += 1
        record["last_used_at"] = _now_iso()
        record["total_bytes_processed"] += bytes_processed
        counts = record["endpoint_counts"]
        counts[endpoint] = counts.get(endpoint, 0) + 1


def get_usage(api_key: str) -> dict:
    """Return a copy of the usage totals associated with an API key."""
    with _store_lock:
        record = _store.get(api_key)
        if record is None:
            raise KeyError("Unknown API key")
        return {
            "total_requests": record["request_count"],
            "last_used_at": record["last_used_at"],
            "total_bytes_processed": record["total_bytes_processed"],
            "by_endpoint": dict(record["endpoint_counts"]),
        }
