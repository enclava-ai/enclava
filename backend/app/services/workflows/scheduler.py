"""Workflow schedule calculation and due-run creation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import utc_now
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowTrigger,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowConcurrencyPolicy,
    WorkflowDefinitionDocument,
    WorkflowDefinitionStatus,
    WorkflowMisfirePolicy,
    WorkflowRedactionPolicy,
    WorkflowRunStatus,
    WorkflowScheduledRunSummary,
    WorkflowSchedulePreviewItem,
    WorkflowSchedulePreviewRequest,
    WorkflowSchedulePreviewResponse,
    WorkflowSchedulerTickResponse,
    WorkflowStaleLockRecoveryRequest,
    WorkflowTriggerType,
)
from app.services.audit_service import log_audit_event

from .maintenance import WorkflowMaintenanceService
from .runtime import (
    WorkflowRunConflictError,
    WorkflowRuntimeService,
)
from .steps import WorkflowStepExecutionError


class WorkflowSchedulerError(Exception):
    """Base scheduler error."""


class WorkflowScheduleValidationError(WorkflowSchedulerError):
    """Schedule cron/timezone validation failed."""


def calculate_next_run_at(
    cron_expression: str,
    timezone_name: str,
    *,
    after: Optional[datetime] = None,
) -> datetime:
    """Return the next fire time as naive UTC for database persistence."""
    zone = _timezone(timezone_name)
    if not croniter.is_valid(cron_expression):
        raise WorkflowScheduleValidationError("invalid cron expression")

    base_utc = _aware_utc(after or utc_now())
    base_local = base_utc.astimezone(zone)
    next_local = croniter(cron_expression, base_local).get_next(datetime)
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=zone)
    return _naive_utc(next_local)


class WorkflowSchedulerService:
    """Creates scheduled workflow runs and executes queued workflow work."""

    DEFAULT_MISFIRE_GRACE_SECONDS = 300
    DEFAULT_CATCHUP_LIMIT = 5

    def __init__(
        self,
        runtime_service: Optional[WorkflowRuntimeService] = None,
        maintenance_service: Optional[WorkflowMaintenanceService] = None,
    ) -> None:
        self.runtime_service = runtime_service or WorkflowRuntimeService()
        self.maintenance_service = maintenance_service or WorkflowMaintenanceService()

    def preview_schedule(
        self, payload: WorkflowSchedulePreviewRequest
    ) -> WorkflowSchedulePreviewResponse:
        """Preview future fire times for a cron/timezone pair."""
        zone = _timezone(payload.timezone)
        if not croniter.is_valid(payload.cron):
            raise WorkflowScheduleValidationError("invalid cron expression")

        base_utc = _aware_utc(payload.start_at or utc_now())
        base_local = base_utc.astimezone(zone)
        iterator = croniter(payload.cron, base_local)
        items: list[WorkflowSchedulePreviewItem] = []
        for _ in range(payload.count):
            local_time = iterator.get_next(datetime)
            if local_time.tzinfo is None:
                local_time = local_time.replace(tzinfo=zone)
            items.append(
                WorkflowSchedulePreviewItem(
                    run_at=_aware_utc(local_time),
                    local_time=local_time.isoformat(),
                    timezone=payload.timezone,
                )
            )

        return WorkflowSchedulePreviewResponse(
            cron=payload.cron,
            timezone=payload.timezone,
            next_runs=items,
        )

    async def run_tick(
        self,
        db: AsyncSession,
        *,
        now: Optional[datetime] = None,
        create_limit: int = 50,
        execute_limit: int = 5,
        worker_id: str = "workflow-scheduler",
    ) -> WorkflowSchedulerTickResponse:
        """Create due scheduled runs, then execute a bounded queued batch."""
        tick_now = _naive_utc(now or utc_now())
        recovered = await self.maintenance_service.recover_stale_locks(
            db,
            WorkflowStaleLockRecoveryRequest(
                limit=max(1, create_limit),
                now=tick_now,
                reason="workflow scheduler recovered expired lock",
            ),
        )
        result = await self.create_due_runs(db, now=tick_now, limit=create_limit)
        result.stale_locks_recovered = recovered.recovered_count
        executed, failed, errors = await self.execute_queued_runs(
            db,
            worker_id=worker_id,
            max_runs=execute_limit,
        )
        result.executed_runs += executed
        result.failed_runs += failed
        result.errors.extend(errors)
        result.next_tick_at = tick_now + timedelta(seconds=60)
        return result

    async def create_due_runs(
        self,
        db: AsyncSession,
        *,
        now: Optional[datetime] = None,
        limit: int = 50,
    ) -> WorkflowSchedulerTickResponse:
        """Create queued runs for enabled schedule triggers that are due."""
        tick_now = _naive_utc(now or utc_now())
        stmt: Select[tuple[WorkflowTrigger]] = (
            select(WorkflowTrigger)
            .options(
                selectinload(WorkflowTrigger.workflow),
                selectinload(WorkflowTrigger.version),
            )
            .where(
                WorkflowTrigger.enabled.is_(True),
                WorkflowTrigger.trigger_type == WorkflowTriggerType.SCHEDULE.value,
                WorkflowTrigger.next_run_at.is_not(None),
                WorkflowTrigger.next_run_at <= tick_now,
            )
            .order_by(WorkflowTrigger.next_run_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await db.execute(stmt)
        triggers = result.scalars().all()
        response = WorkflowSchedulerTickResponse()

        for trigger in triggers:
            try:
                await self._process_trigger(db, trigger, tick_now, response)
            except Exception as exc:
                response.errors.append(f"{trigger.id}: {exc}")

        await db.flush()
        return response

    async def execute_queued_runs(
        self,
        db: AsyncSession,
        *,
        worker_id: str,
        max_runs: int = 5,
    ) -> tuple[int, int, list[str]]:
        """Execute a bounded batch of queued runs."""
        if max_runs <= 0:
            return 0, 0, []

        result = await db.execute(
            select(WorkflowRun.id)
            .where(WorkflowRun.status == WorkflowRunStatus.QUEUED.value)
            .order_by(
                WorkflowRun.queued_at.asc().nulls_last(), WorkflowRun.created_at.asc()
            )
            .limit(max_runs)
        )
        run_ids = [row[0] for row in result.all()]
        executed = 0
        failed = 0
        errors: list[str] = []
        for run_id in run_ids:
            try:
                await self.runtime_service.execute_run(
                    db, run_id, worker_id=worker_id, actor=None
                )
                executed += 1
            except WorkflowStepExecutionError:
                failed += 1
            except WorkflowRunConflictError:
                continue
            except Exception as exc:
                failed += 1
                errors.append(f"{run_id}: {exc}")

        await db.flush()
        return executed, failed, errors

    async def _process_trigger(
        self,
        db: AsyncSession,
        trigger: WorkflowTrigger,
        now: datetime,
        response: WorkflowSchedulerTickResponse,
    ) -> None:
        workflow = trigger.workflow
        version = trigger.version
        if workflow is None or version is None:
            response.skipped_triggers += 1
            return
        if (
            workflow.status != WorkflowDefinitionStatus.ACTIVE.value
            or not workflow.is_active
        ):
            response.skipped_triggers += 1
            await self._append_schedule_event(
                db,
                workflow,
                version,
                trigger,
                "scheduled_run_skipped",
                "Scheduled run skipped because workflow is inactive",
                {"reason": "workflow_inactive"},
            )
            return

        definition = WorkflowDefinitionDocument.model_validate(version.definition)
        due_times, next_run_at = self._due_fire_times(trigger, definition, now)
        if not due_times:
            trigger.next_run_at = next_run_at
            trigger.updated_at = now
            return

        concurrency_policy = definition.runtime.concurrency_policy
        active_exists = False
        if concurrency_policy == WorkflowConcurrencyPolicy.SKIP_IF_RUNNING:
            active_exists = await self._workflow_has_active_run(db, workflow.id)

        for scheduled_fire_at in due_times:
            idempotency_key = _schedule_idempotency_key(trigger, scheduled_fire_at)
            existing = await db.execute(
                select(WorkflowRun.id).where(
                    WorkflowRun.idempotency_key == idempotency_key
                )
            )
            existing_run_id = existing.scalar_one_or_none()
            if existing_run_id:
                response.duplicate_runs += 1
                response.runs.append(
                    WorkflowScheduledRunSummary(
                        workflow_id=workflow.id,
                        trigger_id=trigger.id,
                        scheduled_fire_at=scheduled_fire_at,
                        run_id=existing_run_id,
                        status="duplicate",
                        reason="idempotency_key_exists",
                    )
                )
                trigger.last_fire_at = scheduled_fire_at
                continue

            if active_exists:
                response.skipped_triggers += 1
                response.runs.append(
                    WorkflowScheduledRunSummary(
                        workflow_id=workflow.id,
                        trigger_id=trigger.id,
                        scheduled_fire_at=scheduled_fire_at,
                        status="skipped",
                        reason="workflow_already_running",
                    )
                )
                await self._append_schedule_event(
                    db,
                    workflow,
                    version,
                    trigger,
                    "scheduled_run_skipped",
                    "Scheduled run skipped because workflow is already running",
                    {
                        "scheduled_fire_at": scheduled_fire_at.isoformat(),
                        "concurrency_policy": concurrency_policy.value,
                    },
                )
                trigger.last_fire_at = scheduled_fire_at
                continue

            run = await self._create_scheduled_run(
                db,
                workflow,
                version,
                trigger,
                definition,
                scheduled_fire_at,
                idempotency_key,
                now,
            )
            response.created_runs += 1
            response.runs.append(
                WorkflowScheduledRunSummary(
                    workflow_id=workflow.id,
                    trigger_id=trigger.id,
                    scheduled_fire_at=scheduled_fire_at,
                    run_id=run.id,
                    status="created",
                )
            )
            trigger.last_fire_at = scheduled_fire_at
            if concurrency_policy == WorkflowConcurrencyPolicy.SKIP_IF_RUNNING:
                active_exists = True

        trigger.next_run_at = next_run_at
        trigger.updated_at = now

    def _due_fire_times(
        self,
        trigger: WorkflowTrigger,
        definition: WorkflowDefinitionDocument,
        now: datetime,
    ) -> tuple[list[datetime], Optional[datetime]]:
        cron_expression = trigger.cron_expression or definition.trigger.cron
        timezone_name = trigger.timezone or definition.trigger.timezone
        if not cron_expression or not timezone_name:
            raise WorkflowScheduleValidationError("schedule trigger is incomplete")

        first_due = _naive_utc(trigger.next_run_at) if trigger.next_run_at else None
        if first_due is None:
            return [], calculate_next_run_at(cron_expression, timezone_name, after=now)
        if first_due > now:
            return [], first_due

        misfire_policy = WorkflowMisfirePolicy(
            trigger.misfire_policy or definition.trigger.misfire_policy.value
        )
        next_after_now = calculate_next_run_at(
            cron_expression, timezone_name, after=now
        )

        if misfire_policy == WorkflowMisfirePolicy.SKIP:
            grace_seconds = int(
                (trigger.config or {}).get(
                    "misfire_grace_seconds", self.DEFAULT_MISFIRE_GRACE_SECONDS
                )
            )
            if first_due < now - timedelta(seconds=grace_seconds):
                return [], next_after_now
            return [first_due], next_after_now

        if misfire_policy == WorkflowMisfirePolicy.RUN_ONCE:
            return [first_due], next_after_now

        catchup_limit = (
            definition.trigger.catchup_limit
            or (trigger.config or {}).get("catchup_limit")
            or self.DEFAULT_CATCHUP_LIMIT
        )
        catchup_limit = max(1, min(int(catchup_limit), 100))
        due_times = [first_due]
        cursor = first_due
        while len(due_times) < catchup_limit:
            cursor = calculate_next_run_at(cron_expression, timezone_name, after=cursor)
            if cursor > now:
                break
            due_times.append(cursor)
        return due_times, next_after_now

    async def _workflow_has_active_run(
        self, db: AsyncSession, workflow_id: str
    ) -> bool:
        active_statuses = {
            WorkflowRunStatus.QUEUED.value,
            WorkflowRunStatus.RUNNING.value,
            WorkflowRunStatus.PAUSED.value,
        }
        result = await db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.status.in_(active_statuses),
            )
        )
        return int(result.scalar_one() or 0) > 0

    async def _create_scheduled_run(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        version: WorkflowVersion,
        trigger: WorkflowTrigger,
        definition: WorkflowDefinitionDocument,
        scheduled_fire_at: datetime,
        idempotency_key: str,
        now: datetime,
    ) -> WorkflowRun:
        run = WorkflowRun(
            workflow_id=workflow.id,
            version_id=version.id,
            trigger_id=trigger.id,
            trigger_type=WorkflowTriggerType.SCHEDULE.value,
            idempotency_key=idempotency_key,
            input_data={
                "scheduled_fire_at": scheduled_fire_at.isoformat(),
                "trigger_id": trigger.id,
            },
            status=WorkflowRunStatus.QUEUED.value,
            queued_at=now,
            created_at=now,
            updated_at=now,
            redaction_policy=(
                definition.runtime.redaction_policy.value
                if definition.runtime.redaction_policy
                else WorkflowRedactionPolicy.DEFAULT.value
            ),
            budget_limit_cents=definition.runtime.budget_limit_cents,
            estimated_cost_cents=0,
            actual_cost_cents=0,
        )
        db.add(run)
        await db.flush()
        await self.runtime_service.append_event(
            db,
            run,
            "run_queued",
            "Scheduled workflow run queued",
            data={
                "trigger_id": trigger.id,
                "scheduled_fire_at": scheduled_fire_at.isoformat(),
            },
        )
        await self._record_schedule_audit(
            db,
            workflow,
            run,
            scheduled_fire_at,
        )
        return run

    async def _append_schedule_event(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        version: WorkflowVersion,
        trigger: WorkflowTrigger,
        event_type: str,
        message: str,
        data: dict[str, Any],
    ) -> None:
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                version_id=version.id,
                event_type=event_type,
                message=message,
                data={"trigger_id": trigger.id, **data},
                created_at=utc_now(),
            )
        )
        await db.flush()

    async def _record_schedule_audit(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        scheduled_fire_at: datetime,
    ) -> None:
        await log_audit_event(
            db,
            action="workflow_run_schedule",
            resource_type="workflow_run",
            resource_id=run.id,
            details={
                "workflow_id": workflow.id,
                "trigger_id": run.trigger_id,
                "scheduled_fire_at": scheduled_fire_at.isoformat(),
            },
            success=True,
            severity="info",
        )


def _timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise WorkflowScheduleValidationError("invalid timezone") from exc


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _schedule_idempotency_key(
    trigger: WorkflowTrigger, scheduled_fire_at: datetime
) -> str:
    return (
        f"workflow:{trigger.workflow_id}:trigger:{trigger.id}:"
        f"scheduled:{scheduled_fire_at.isoformat()}"
    )
