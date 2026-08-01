"""Job expiry and temp-file cleanup for GeoFile Toolkit.

Provides a FastAPI lifespan task that periodically calls
``purge_expired_jobs()`` from ``app.jobs.job_queue``.

The purge interval and TTL are configurable via env vars:
    GEOFILE_JOB_TTL           – seconds before a finished job expires   (default: 3600)
    GEOFILE_PURGE_INTERVAL    – seconds between purge passes           (default: 300)
"""

from __future__ import annotations

import asyncio
import logging
import os

from app.jobs.job_queue import purge_expired_jobs

logger = logging.getLogger(__name__)

_PURGE_INTERVAL_SECS = int(os.environ.get("GEOFILE_PURGE_INTERVAL", "300"))


async def periodic_job_purge() -> None:  # pragma: no cover
    """Async task that runs forever, purging expired jobs every interval."""
    while True:
        await asyncio.sleep(_PURGE_INTERVAL_SECS)
        try:
            purged = purge_expired_jobs()
            if purged:
                logger.info("Job purge: removed %d expired job(s).", purged)
        except Exception:  # noqa: BLE001
            logger.exception("Job purge failed unexpectedly.")
