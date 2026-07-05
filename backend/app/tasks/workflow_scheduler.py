"""Workflow scheduler background task."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.db.database import async_session_factory, utc_now
from app.schemas.workflow import (
    WorkflowSchedulerStatusResponse,
    WorkflowSchedulerTickResponse,
)
from app.services.workflows import WorkflowSchedulerService

logger = logging.getLogger(__name__)


class WorkflowSchedulerTask:
    """Asyncio scheduler that creates due workflow runs and executes queued work."""

    DEFAULT_TICK_SECONDS = 60
    DEFAULT_CREATE_LIMIT = 50
    DEFAULT_EXECUTE_LIMIT = 5

    def __init__(
        self,
        *,
        tick_seconds: int = DEFAULT_TICK_SECONDS,
        create_limit: int = DEFAULT_CREATE_LIMIT,
        execute_limit: int = DEFAULT_EXECUTE_LIMIT,
        service: Optional[WorkflowSchedulerService] = None,
    ) -> None:
        self.tick_seconds = tick_seconds
        self.create_limit = create_limit
        self.execute_limit = execute_limit
        self.service = service or WorkflowSchedulerService()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.last_tick_at: Optional[datetime] = None
        self.last_result: Optional[WorkflowSchedulerTickResponse] = None

    async def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            logger.warning("WorkflowSchedulerTask already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("WorkflowSchedulerTask started (tick=%ds)", self.tick_seconds)

    async def stop(self) -> None:
        """Stop the background scheduler loop."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WorkflowSchedulerTask stopped")

    async def tick_now(self) -> WorkflowSchedulerTickResponse:
        """Run one scheduler tick immediately."""
        async with async_session_factory() as db:
            try:
                result = await self.service.run_tick(
                    db,
                    create_limit=self.create_limit,
                    execute_limit=self.execute_limit,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        self.last_tick_at = utc_now()
        self.last_result = result
        return result

    def status(self) -> WorkflowSchedulerStatusResponse:
        """Return current in-process scheduler status."""
        return WorkflowSchedulerStatusResponse(
            running=self._running,
            tick_seconds=self.tick_seconds,
            last_tick_at=self.last_tick_at,
            last_result=self.last_result,
        )

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick_now()
            except Exception:
                logger.exception("Unexpected error in workflow scheduler tick")
            await asyncio.sleep(self.tick_seconds)


workflow_scheduler = WorkflowSchedulerTask()
