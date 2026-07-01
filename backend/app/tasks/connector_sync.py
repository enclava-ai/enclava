"""
Connector sync background task.

Provides:
  - ConnectorSyncScheduler  — asyncio-based scheduler that reads ConnectorSource
    rows from the DB and triggers syncs at their configured sync_frequency.
  - sync_connector_now()    — one-shot coroutine for manual/immediate syncs.

The scheduler starts as part of the FastAPI lifespan (wired in main.py).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.db.database import async_session_factory
from app.models.connector_source import ConnectorSource, ConnectorStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ISO 8601 duration parser (subset: PTxH, PTxM, PxD)
# ---------------------------------------------------------------------------

_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
    re.IGNORECASE,
)


def _parse_duration(iso_duration: str) -> timedelta:
    """Parse a simplified ISO 8601 duration string into a timedelta."""
    m = _DURATION_RE.fullmatch(iso_duration.strip())
    if not m:
        raise ValueError(f"Cannot parse duration: {iso_duration!r}")
    return timedelta(
        days=int(m.group("days") or 0),
        hours=int(m.group("hours") or 0),
        minutes=int(m.group("minutes") or 0),
        seconds=int(m.group("seconds") or 0),
    )


# ---------------------------------------------------------------------------
# One-shot sync helper
# ---------------------------------------------------------------------------


async def sync_connector_now(connector_id: int) -> dict:
    """
    Run a sync for *connector_id* immediately, using a fresh DB session.

    Returns a summary dict suitable for an API response.
    """
    async with async_session_factory() as db:
        from app.services.connector_sync_service import ConnectorSyncService

        service = ConnectorSyncService(db)
        job = await service.run_sync(connector_id)
        return job.to_dict()


# ---------------------------------------------------------------------------
# Periodic scheduler
# ---------------------------------------------------------------------------


class ConnectorSyncScheduler:
    """
    Asyncio-based periodic scheduler for connector syncs.

    On each tick (default: every 60 seconds) it checks which active
    connectors are due for a sync and fires them off concurrently.
    """

    DEFAULT_TICK_SECONDS = 60

    def __init__(self, tick_seconds: int = DEFAULT_TICK_SECONDS) -> None:
        self.tick_seconds = tick_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            logger.warning("ConnectorSyncScheduler already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ConnectorSyncScheduler started (tick=%ds)", self.tick_seconds)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ConnectorSyncScheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Unexpected error in connector sync scheduler tick")
            await asyncio.sleep(self.tick_seconds)

    async def _tick(self) -> None:
        """Find connectors due for a sync and fire them."""
        now = datetime.now(timezone.utc)

        async with async_session_factory() as db:
            stmt = select(ConnectorSource).where(
                ConnectorSource.is_active.is_(True),
                ConnectorSource.status != ConnectorStatus.PAUSED,
            )
            result = await db.execute(stmt)
            connectors = result.scalars().all()

        due = []
        for connector in connectors:
            try:
                freq = _parse_duration(connector.sync_frequency or "PT1H")
            except ValueError:
                logger.warning(
                    "Invalid sync_frequency %r for connector %d — skipping",
                    connector.sync_frequency,
                    connector.id,
                )
                continue

            last = connector.last_synced_at
            if last is None or (now - last) >= freq:
                due.append(connector.id)

        if not due:
            return

        logger.info("Connector sync scheduler: %d connector(s) due", len(due))
        await asyncio.gather(
            *[self._safe_sync(cid) for cid in due],
            return_exceptions=True,
        )

    async def _safe_sync(self, connector_id: int) -> None:
        """Run a single connector sync, swallowing exceptions so one failure
        doesn't block others."""
        try:
            await sync_connector_now(connector_id)
            logger.info("Connector %d sync completed", connector_id)
        except Exception:
            logger.exception("Connector %d sync failed", connector_id)


# Module-level singleton used by the FastAPI lifespan
connector_sync_scheduler = ConnectorSyncScheduler()
