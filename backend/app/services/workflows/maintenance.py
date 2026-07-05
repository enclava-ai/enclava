"""Workflow runtime maintenance and operator recovery actions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import utc_now
from app.models.workflow import WorkflowArtifact, WorkflowEvent, WorkflowRun
from app.schemas.workflow import (
    WorkflowRetentionPolicy,
    WorkflowRetentionResult,
    WorkflowRunStatus,
    WorkflowStaleLockRecoveredRun,
    WorkflowStaleLockRecoveryRequest,
    WorkflowStaleLockRecoveryResult,
)
from app.services.audit_service import log_audit_event

from .service import _actor_id


class WorkflowMaintenanceService:
    """Performs maintenance that must stay outside normal workflow execution."""

    async def recover_stale_locks(
        self,
        db: AsyncSession,
        payload: Optional[WorkflowStaleLockRecoveryRequest] = None,
        actor: Optional[Mapping[str, Any]] = None,
    ) -> WorkflowStaleLockRecoveryResult:
        """Fail expired running runs without re-entering step execution."""
        request = payload or WorkflowStaleLockRecoveryRequest()
        checked_at = _naive_utc(request.now or utc_now())
        expired_before = checked_at - timedelta(seconds=request.older_than_seconds)
        stmt: Select[tuple[WorkflowRun]] = (
            select(WorkflowRun)
            .where(
                WorkflowRun.status == WorkflowRunStatus.RUNNING.value,
                WorkflowRun.lock_expires_at.is_not(None),
                WorkflowRun.lock_expires_at <= expired_before,
            )
            .order_by(WorkflowRun.lock_expires_at.asc(), WorkflowRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(request.limit)
        )
        result = await db.execute(stmt)
        runs = list(result.scalars().all())
        recovered: list[WorkflowStaleLockRecoveredRun] = []
        reason = request.reason or "workflow lock expired"

        for run in runs:
            previous_locked_by = run.locked_by
            previous_lock_expires_at = run.lock_expires_at
            run.status = WorkflowRunStatus.FAILED.value
            run.error = reason
            run.completed_at = checked_at
            run.updated_at = checked_at
            run.locked_by = None
            run.lock_expires_at = None
            db.add(
                WorkflowEvent(
                    workflow_id=run.workflow_id,
                    version_id=run.version_id,
                    run_id=run.id,
                    event_type="run_stale_lock_recovered",
                    severity="warning",
                    message="Workflow run marked failed because its lock expired",
                    data={
                        "reason": reason,
                        "previous_locked_by": previous_locked_by,
                        "previous_lock_expires_at": (
                            previous_lock_expires_at.isoformat()
                            if previous_lock_expires_at
                            else None
                        ),
                    },
                    created_by_user_id=_actor_id(actor or {}),
                    created_at=checked_at,
                )
            )
            await log_audit_event(
                db,
                user_id=(
                    str(_actor_id(actor or {}))
                    if _actor_id(actor or {}) is not None
                    else None
                ),
                action="workflow_run_stale_lock_recovered",
                resource_type="workflow_run",
                resource_id=run.id,
                details={
                    "workflow_id": run.workflow_id,
                    "previous_locked_by": previous_locked_by,
                    "previous_lock_expires_at": (
                        previous_lock_expires_at.isoformat()
                        if previous_lock_expires_at
                        else None
                    ),
                    "reason": reason,
                },
                success=True,
                severity="warning",
            )
            recovered.append(
                WorkflowStaleLockRecoveredRun(
                    run_id=run.id,
                    workflow_id=run.workflow_id,
                    previous_locked_by=previous_locked_by,
                    previous_lock_expires_at=previous_lock_expires_at,
                    status=WorkflowRunStatus.FAILED,
                    reason=reason,
                )
            )

        await db.flush()
        return WorkflowStaleLockRecoveryResult(
            checked_at=checked_at,
            recovered_count=len(recovered),
            runs=recovered,
        )

    async def apply_retention_policy(
        self,
        db: AsyncSession,
        payload: Optional[WorkflowRetentionPolicy] = None,
        actor: Optional[Mapping[str, Any]] = None,
    ) -> WorkflowRetentionResult:
        """Prune verbose workflow events and artifact payloads by policy."""
        policy = payload or WorkflowRetentionPolicy()
        checked_at = _naive_utc(policy.now or utc_now())
        event_cutoff = _cutoff(checked_at, policy.event_retention_days)
        artifact_cutoff = _cutoff(checked_at, policy.artifact_retention_days)

        events_pruned = 0
        if event_cutoff is not None:
            event_ids = await self._eligible_event_ids(db, event_cutoff, policy.limit)
            events_pruned = len(event_ids)
            if event_ids and not policy.dry_run:
                await db.execute(
                    delete(WorkflowEvent).where(WorkflowEvent.id.in_(event_ids))
                )

        artifact_payloads_pruned = 0
        if artifact_cutoff is not None:
            artifacts = await self._eligible_artifacts(
                db, artifact_cutoff, policy.limit
            )
            artifact_payloads_pruned = len(artifacts)
            if artifacts and not policy.dry_run:
                for artifact in artifacts:
                    artifact.data = None
                    artifact.storage_uri = None

        if not policy.dry_run:
            await log_audit_event(
                db,
                user_id=(
                    str(_actor_id(actor or {}))
                    if _actor_id(actor or {}) is not None
                    else None
                ),
                action="workflow_retention_apply",
                resource_type="workflow",
                details={
                    "event_retention_days": policy.event_retention_days,
                    "artifact_retention_days": policy.artifact_retention_days,
                    "events_pruned": events_pruned,
                    "artifact_payloads_pruned": artifact_payloads_pruned,
                },
                success=True,
                severity="info",
            )

        await db.flush()
        return WorkflowRetentionResult(
            dry_run=policy.dry_run,
            checked_at=checked_at,
            event_cutoff=event_cutoff,
            artifact_cutoff=artifact_cutoff,
            events_pruned=events_pruned,
            artifact_payloads_pruned=artifact_payloads_pruned,
        )

    async def count_stale_locks(
        self,
        db: AsyncSession,
        *,
        now: Optional[datetime] = None,
    ) -> int:
        """Count expired locks that are still marked running."""
        checked_at = _naive_utc(now or utc_now())
        result = await db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(
                WorkflowRun.status == WorkflowRunStatus.RUNNING.value,
                WorkflowRun.lock_expires_at.is_not(None),
                WorkflowRun.lock_expires_at <= checked_at,
            )
        )
        return int(result.scalar_one() or 0)

    async def _eligible_event_ids(
        self,
        db: AsyncSession,
        cutoff: datetime,
        limit: int,
    ) -> list[str]:
        result = await db.execute(
            select(WorkflowEvent.id)
            .where(WorkflowEvent.created_at < cutoff)
            .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def _eligible_artifacts(
        self,
        db: AsyncSession,
        cutoff: datetime,
        limit: int,
    ) -> list[WorkflowArtifact]:
        result = await db.execute(
            select(WorkflowArtifact)
            .where(
                WorkflowArtifact.created_at < cutoff,
                or_(
                    WorkflowArtifact.data.is_not(None),
                    WorkflowArtifact.storage_uri.is_not(None),
                ),
            )
            .order_by(WorkflowArtifact.created_at.asc(), WorkflowArtifact.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


def _cutoff(now: datetime, days: Optional[int]) -> Optional[datetime]:
    if days is None:
        return None
    return now - timedelta(days=days)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
