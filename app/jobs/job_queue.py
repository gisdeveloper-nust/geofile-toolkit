"""Async job queue model for GeoFile Toolkit.

Jobs are stored in a thread-safe in-memory dict. A ``ThreadPoolExecutor``
runs the actual work so geopandas/fiona (which are not async-native) can
run without blocking the event loop.

Job lifecycle:
    pending → processing → complete
                        ↘ failed

Each job record is a plain dict so it can be serialised directly to JSON
without a database.

Configuration:
    GEOFILE_JOB_WORKERS  – max thread-pool workers (default: 4)
    GEOFILE_JOB_TTL      – seconds before a finished job expires (default: 3600)
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Literal

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MAX_WORKERS = int(os.environ.get("GEOFILE_JOB_WORKERS", "4"))
_JOB_TTL_SECS = int(os.environ.get("GEOFILE_JOB_TTL", "3600"))

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

JobStatus = Literal["pending", "processing", "complete", "failed"]


class JobRecord:
    """Mutable container for a single async job."""

    __slots__ = (
        "id",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "result",
        "error",
        "_lock",
    )

    def __init__(self, job_id: str) -> None:
        self.id: str = job_id
        self.status: JobStatus = "pending"
        self.created_at: str = _now_iso()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.result: Any = None
        self.error: str | None = None
        self._lock = threading.Lock()

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict safe for JSON encoding."""
        with self._lock:
            return {
                "job_id": self.id,
                "status": self.status,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "result": self.result,
                "error": self.error,
            }


# ---------------------------------------------------------------------------
# Store + executor (module-level singletons)
# ---------------------------------------------------------------------------

_store: dict[str, JobRecord] = {}
_store_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def submit_job(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Submit *fn* to the thread pool and return the new job ID.

    The callable is executed in a background thread.  Its return value
    becomes ``job.result``; any exception becomes ``job.error``.

    Args:
        fn:      The callable to run.  Must be picklable or defined at
                 module level (standard ``ThreadPoolExecutor`` rules).
        *args:   Positional arguments forwarded to *fn*.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        A UUID4 string that callers can poll via ``get_job``.
    """
    job_id = str(uuid.uuid4())
    record = JobRecord(job_id)

    with _store_lock:
        _store[job_id] = record

    future: Future[Any] = _executor.submit(_run_job, record, fn, args, kwargs)
    # Suppress unobserved-future warnings; errors are captured in the record.
    future.add_done_callback(lambda _f: None)

    return job_id


def _run_job(
    record: JobRecord,
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Execute *fn* and update *record* with the outcome."""
    with record._lock:
        record.status = "processing"
        record.started_at = _now_iso()

    try:
        result = fn(*args, **kwargs)
        with record._lock:
            record.status = "complete"
            record.finished_at = _now_iso()
            record.result = result
    except Exception as exc:  # noqa: BLE001
        with record._lock:
            record.status = "failed"
            record.finished_at = _now_iso()
            record.error = f"{type(exc).__name__}: {exc}"


def get_job(job_id: str) -> JobRecord | None:
    """Return the ``JobRecord`` for *job_id*, or ``None`` if not found."""
    with _store_lock:
        return _store.get(job_id)


def purge_expired_jobs() -> int:
    """Remove finished jobs older than ``_JOB_TTL_SECS``.

    Returns the number of jobs purged.
    """
    now = datetime.now(timezone.utc)
    expired: list[str] = []

    with _store_lock:
        for job_id, record in _store.items():
            with record._lock:
                if record.status in ("complete", "failed") and record.finished_at:
                    finished = datetime.fromisoformat(record.finished_at)
                    age_secs = (now - finished).total_seconds()
                    if age_secs >= _JOB_TTL_SECS:
                        expired.append(job_id)
        for job_id in expired:
            del _store[job_id]

    return len(expired)


def job_store_snapshot() -> list[dict[str, Any]]:
    """Return a snapshot of all job records as plain dicts."""
    with _store_lock:
        return [record.to_dict() for record in _store.values()]
