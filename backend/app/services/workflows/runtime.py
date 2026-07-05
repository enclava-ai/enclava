"""Workflow runtime service for durable manual runs."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping, Optional

from sqlalchemy import Select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import utc_now
from app.models.workflow import (
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowArtifactSummary,
    WorkflowDefinitionDocument,
    WorkflowDefinitionStatus,
    WorkflowEventSummary,
    WorkflowManualRunRequest,
    WorkflowRedactedPayload,
    WorkflowRedactionPolicy,
    WorkflowRunDetail,
    WorkflowRunStatus,
    WorkflowRunSummary,
    WorkflowStepRunDetail,
    WorkflowStepRunStatus,
    WorkflowTriggerType,
)
from app.services.audit_service import log_audit_event

from .service import WorkflowRuntimeDependencies
from .steps import (
    WorkflowStepContext,
    WorkflowStepEventSpec,
    WorkflowStepExecutionError,
    WorkflowStepHandler,
    create_default_step_handlers,
)


class WorkflowRuntimeError(Exception):
    """Base workflow runtime error."""


class WorkflowRunNotFoundError(WorkflowRuntimeError):
    """Workflow run was not found or is not visible to the actor."""


class WorkflowRunPermissionError(WorkflowRuntimeError):
    """Actor lacks permission for the requested run action."""


class WorkflowRunValidationError(WorkflowRuntimeError):
    """Requested run action is invalid."""


class WorkflowRunConflictError(WorkflowRuntimeError):
    """Requested run action conflicts with current run state."""


class WorkflowRuntimeService:
    """Coordinates durable workflow run state and in-process step execution."""

    def __init__(
        self,
        dependencies: Optional[WorkflowRuntimeDependencies] = None,
        step_handlers: Optional[Mapping[str, WorkflowStepHandler]] = None,
    ) -> None:
        self.dependencies = dependencies or WorkflowRuntimeDependencies()
        self.step_handlers = dict(
            step_handlers or create_default_step_handlers(self.dependencies)
        )

    async def create_manual_run(
        self,
        db: AsyncSession,
        workflow_id: str,
        payload: WorkflowManualRunRequest,
        actor: Mapping[str, Any],
    ) -> WorkflowRunDetail:
        """Create a queued manual run from the current published workflow version."""
        workflow = await self._get_workflow_for_run(db, workflow_id, actor)
        self._require_manage(workflow, actor)
        version = _current_version(workflow)
        if version is None:
            raise WorkflowRunValidationError(
                "workflow must be published before it can be run"
            )

        definition = version.definition or {}
        runtime = definition.get("runtime") or {}
        now = utc_now()
        run = WorkflowRun(
            workflow_id=workflow.id,
            version_id=version.id,
            trigger_type=WorkflowTriggerType.MANUAL.value,
            idempotency_key=payload.idempotency_key,
            input_data=payload.input_data,
            status=WorkflowRunStatus.QUEUED.value,
            requested_by_user_id=_actor_id(actor),
            queued_at=now,
            created_at=now,
            updated_at=now,
            redaction_policy=runtime.get(
                "redaction_policy", WorkflowRedactionPolicy.DEFAULT.value
            ),
            budget_limit_cents=runtime.get("budget_limit_cents"),
            estimated_cost_cents=0,
            actual_cost_cents=0,
        )
        db.add(run)
        await db.flush()
        await self.append_event(
            db,
            run,
            "run_queued",
            "Manual workflow run queued",
            actor=actor,
            data={"workflow_id": workflow.id, "version_number": version.version_number},
        )
        await self._record_audit(db, actor, "workflow_run_create", run)
        await db.flush()
        return await self.get_run_detail(db, run.id, actor)

    async def get_run_detail(
        self,
        db: AsyncSession,
        run_id: str,
        actor: Mapping[str, Any],
    ) -> WorkflowRunDetail:
        """Return a visible run detail."""
        run = await self._get_run(db, run_id, actor=actor)
        return self._to_detail(run)

    async def list_workflow_runs(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        *,
        limit: int = 50,
    ) -> list[WorkflowRunSummary]:
        """List recent runs for a visible workflow."""
        workflow = await self._get_workflow_for_run(db, workflow_id, actor)
        stmt: Select[tuple[WorkflowRun]] = (
            select(WorkflowRun)
            .options(
                selectinload(WorkflowRun.workflow),
                selectinload(WorkflowRun.version),
            )
            .where(WorkflowRun.workflow_id == workflow.id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [self._to_summary(run) for run in result.scalars().all()]

    async def retry_run(
        self,
        db: AsyncSession,
        run_id: str,
        actor: Mapping[str, Any],
        *,
        reason: Optional[str] = None,
    ) -> WorkflowRunDetail:
        """Create a new queued run from an existing terminal run."""
        original = await self._get_run(db, run_id, actor=actor, for_update=True)
        self._require_manage(original.workflow, actor)
        status = WorkflowRunStatus(original.status)
        if status not in {
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.SKIPPED,
        }:
            raise WorkflowRunConflictError(
                "only failed, cancelled, or skipped runs can be retried"
            )

        now = utc_now()
        retry = WorkflowRun(
            workflow_id=original.workflow_id,
            version_id=original.version_id,
            trigger_type=WorkflowTriggerType.MANUAL.value,
            input_data=original.input_data or {},
            status=WorkflowRunStatus.QUEUED.value,
            requested_by_user_id=_actor_id(actor),
            retry_of_run_id=original.id,
            queued_at=now,
            created_at=now,
            updated_at=now,
            redaction_policy=original.redaction_policy,
            budget_limit_cents=original.budget_limit_cents,
            estimated_cost_cents=0,
            actual_cost_cents=0,
        )
        db.add(retry)
        await db.flush()
        await self.append_event(
            db,
            retry,
            "run_retried",
            "Workflow run retry queued",
            actor=actor,
            data={"retry_of_run_id": original.id, "reason": reason},
        )
        await self._record_audit(
            db,
            actor,
            "workflow_run_retry",
            retry,
            details={"retry_of_run_id": original.id, "reason": reason},
        )
        await db.flush()
        loaded = await self._get_run(db, retry.id, actor=actor)
        return self._to_detail(loaded)

    async def claim_next_run(
        self,
        db: AsyncSession,
        *,
        worker_id: str,
        lock_seconds: int = 300,
    ) -> Optional[WorkflowRunDetail]:
        """Claim the oldest queued run for one worker."""
        stmt: Select[tuple[WorkflowRun]] = (
            select(WorkflowRun)
            .where(WorkflowRun.status == WorkflowRunStatus.QUEUED.value)
            .order_by(
                WorkflowRun.queued_at.asc().nulls_last(), WorkflowRun.created_at.asc()
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            return None

        now = utc_now()
        run.status = WorkflowRunStatus.RUNNING.value
        run.started_at = now
        run.updated_at = now
        run.locked_by = worker_id
        run.lock_expires_at = now + timedelta(seconds=lock_seconds)
        await self.append_event(
            db,
            run,
            "run_claimed",
            "Workflow run claimed by worker",
            data={"worker_id": worker_id},
        )
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=None, for_update=False)
        return self._to_detail(loaded)

    async def execute_run(
        self,
        db: AsyncSession,
        run_id: str,
        *,
        worker_id: str = "manual",
        actor: Optional[Mapping[str, Any]] = None,
    ) -> WorkflowRunDetail:
        """Execute a queued or running workflow run in-process."""
        run = await self._get_run(db, run_id, actor=actor, for_update=True)
        if actor is not None:
            self._require_manage(run.workflow, actor)
        if WorkflowRunStatus(run.status) == WorkflowRunStatus.QUEUED:
            run = await self._claim_run(db, run, worker_id=worker_id)
        elif WorkflowRunStatus(run.status) != WorkflowRunStatus.RUNNING:
            raise WorkflowRunConflictError("only queued or running runs can execute")

        definition = WorkflowDefinitionDocument.model_validate(run.version.definition)
        previous_outputs: dict[str, dict[str, Any]] = {}
        for index, step in enumerate(definition.steps):
            if run.cancel_requested_at:
                return await self._mark_run_cancelled(db, run, "Run cancelled")

            result = await self._execute_step_with_retries(
                db, run, definition, step, previous_outputs, actor
            )
            previous_outputs[step.key] = result.output_data
            if result.skip_remaining:
                await self._mark_remaining_steps_skipped(
                    db, run, definition.steps[index + 1 :]
                )
                return await self.complete_run(
                    db,
                    run,
                    output_data={
                        "skipped": True,
                        "skipped_after_step": step.key,
                        "outputs": previous_outputs,
                    },
                    status=WorkflowRunStatus.SKIPPED,
                )

        return await self.complete_run(
            db, run, output_data={"outputs": previous_outputs}
        )

    async def create_step_run(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        *,
        step_key: str,
        step_type: str,
        input_data: Optional[dict[str, Any]] = None,
        attempt: int = 1,
        status: WorkflowStepRunStatus = WorkflowStepRunStatus.PENDING,
    ) -> WorkflowStepRun:
        """Create a persisted step run row."""
        now = utc_now()
        step_run = WorkflowStepRun(
            run_id=run.id,
            step_key=step_key,
            step_type=step_type,
            status=status.value,
            attempt=attempt,
            input_data=input_data,
            started_at=now if status == WorkflowStepRunStatus.RUNNING else None,
            created_at=now,
            updated_at=now,
        )
        db.add(step_run)
        await db.flush()
        await self.append_event(
            db,
            run,
            "step_created",
            f"Step {step_key} created",
            step_run=step_run,
            data={"step_key": step_key, "step_type": step_type, "attempt": attempt},
        )
        return step_run

    async def create_artifact(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        *,
        artifact_type: str,
        name: str,
        data: Optional[dict[str, Any]] = None,
        step_run: Optional[WorkflowStepRun] = None,
        storage_uri: Optional[str] = None,
        redaction_policy: Optional[str] = None,
    ) -> WorkflowArtifact:
        """Create a persisted workflow artifact."""
        artifact = WorkflowArtifact(
            run_id=run.id,
            step_run_id=step_run.id if step_run else None,
            artifact_type=artifact_type,
            name=name,
            data=data,
            storage_uri=storage_uri,
            redaction_policy=redaction_policy or run.redaction_policy,
            created_at=utc_now(),
        )
        db.add(artifact)
        await db.flush()
        await self.append_event(
            db,
            run,
            "artifact_created",
            f"Artifact created: {name}",
            step_run=step_run,
            data={"artifact_id": artifact.id, "artifact_type": artifact_type},
        )
        return artifact

    async def complete_run(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        *,
        output_data: Optional[dict[str, Any]] = None,
        status: WorkflowRunStatus = WorkflowRunStatus.SUCCEEDED,
    ) -> WorkflowRunDetail:
        """Mark a running run terminal and successful-like."""
        if status not in {WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.SKIPPED}:
            raise WorkflowRunValidationError("complete_run requires a success status")
        now = utc_now()
        run.status = status.value
        run.output_data = output_data
        run.completed_at = now
        run.updated_at = now
        run.locked_by = None
        run.lock_expires_at = None
        await self.append_event(db, run, f"run_{status.value}", f"Run {status.value}")
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=None)
        return self._to_detail(loaded)

    async def fail_run(
        self, db: AsyncSession, run: WorkflowRun, *, error: str
    ) -> WorkflowRunDetail:
        """Mark a run failed with a persisted error."""
        now = utc_now()
        run.status = WorkflowRunStatus.FAILED.value
        run.error = error
        run.completed_at = now
        run.updated_at = now
        run.locked_by = None
        run.lock_expires_at = None
        await self.append_event(
            db,
            run,
            "run_failed",
            "Run failed",
            severity="error",
            data={"error": error},
        )
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=None)
        return self._to_detail(loaded)

    async def _claim_run(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        *,
        worker_id: str,
        lock_seconds: int = 300,
    ) -> WorkflowRun:
        now = utc_now()
        run.status = WorkflowRunStatus.RUNNING.value
        run.started_at = now
        run.updated_at = now
        run.locked_by = worker_id
        run.lock_expires_at = now + timedelta(seconds=lock_seconds)
        await self.append_event(
            db,
            run,
            "run_claimed",
            "Workflow run claimed by worker",
            data={"worker_id": worker_id},
        )
        await db.flush()
        return run

    async def _execute_step_with_retries(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        definition: WorkflowDefinitionDocument,
        step: Any,
        previous_outputs: dict[str, dict[str, Any]],
        actor: Optional[Mapping[str, Any]],
    ) -> Any:
        handler = self.step_handlers.get(step.type)
        if handler is None:
            error = f"unknown workflow step type: {step.type}"
            step_run = await self.create_step_run(
                db,
                run,
                step_key=step.key,
                step_type=step.type,
                status=WorkflowStepRunStatus.FAILED,
            )
            await self._fail_step_run(db, run, step_run, error)
            await self.fail_run(db, run, error=error)
            raise WorkflowStepExecutionError(error)

        max_attempts = step.retry.max_attempts
        last_error: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            step_run = await self.create_step_run(
                db,
                run,
                step_key=step.key,
                step_type=step.type,
                input_data={
                    "config": step.config,
                    "previous_outputs": previous_outputs,
                },
                attempt=attempt,
                status=WorkflowStepRunStatus.RUNNING,
            )
            context = WorkflowStepContext(
                db=db,
                run=run,
                definition=definition,
                step=step,
                previous_outputs=previous_outputs,
                dependencies=self.dependencies,
                actor=actor,
            )
            estimate = handler.estimate_cost_cents(context)
            if (
                run.budget_limit_cents is not None
                and (run.actual_cost_cents or 0) + estimate > run.budget_limit_cents
            ):
                last_error = "workflow budget limit exceeded"
                await self._fail_step_run(db, run, step_run, last_error)
                await self.fail_run(db, run, error=last_error)
                raise WorkflowStepExecutionError(last_error)

            try:
                result = await handler.execute(context)
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_attempts:
                    await self._retry_step_run(db, run, step_run, last_error, attempt)
                    continue
                await self._fail_step_run(db, run, step_run, last_error)
                await self.fail_run(db, run, error=last_error)
                raise WorkflowStepExecutionError(last_error) from exc

            await self._complete_step_run(db, run, step_run, result)
            return result

        raise WorkflowStepExecutionError(last_error or "workflow step failed")

    async def _complete_step_run(
        self, db: AsyncSession, run: WorkflowRun, step_run: WorkflowStepRun, result: Any
    ) -> None:
        now = utc_now()
        step_run.status = WorkflowStepRunStatus.SUCCEEDED.value
        step_run.output_data = result.output_data
        step_run.completed_at = now
        step_run.updated_at = now
        step_run.duration_ms = _duration_ms(step_run.started_at, now)
        run.estimated_cost_cents = (run.estimated_cost_cents or 0) + (
            result.estimated_cost_cents or 0
        )
        run.actual_cost_cents = (run.actual_cost_cents or 0) + (
            result.actual_cost_cents or 0
        )
        run.updated_at = now
        await self.append_event(
            db,
            run,
            "step_succeeded",
            f"Step {step_run.step_key} succeeded",
            step_run=step_run,
            data={"step_key": step_run.step_key, "attempt": step_run.attempt},
        )
        for artifact in result.artifacts:
            await self.create_artifact(
                db,
                run,
                step_run=step_run,
                artifact_type=artifact.artifact_type,
                name=artifact.name,
                data=artifact.data,
                storage_uri=artifact.storage_uri,
                redaction_policy=artifact.redaction_policy,
            )
        for event in result.events:
            await self._append_step_event(db, run, step_run, event)
        await db.flush()

    async def _retry_step_run(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        step_run: WorkflowStepRun,
        error: str,
        attempt: int,
    ) -> None:
        now = utc_now()
        step_run.status = WorkflowStepRunStatus.RETRYING.value
        step_run.error = error
        step_run.completed_at = now
        step_run.updated_at = now
        step_run.duration_ms = _duration_ms(step_run.started_at, now)
        await self.append_event(
            db,
            run,
            "step_retrying",
            f"Step {step_run.step_key} failed; retrying",
            severity="warning",
            step_run=step_run,
            data={"step_key": step_run.step_key, "attempt": attempt, "error": error},
        )
        await db.flush()

    async def _fail_step_run(
        self, db: AsyncSession, run: WorkflowRun, step_run: WorkflowStepRun, error: str
    ) -> None:
        now = utc_now()
        step_run.status = WorkflowStepRunStatus.FAILED.value
        step_run.error = error
        step_run.completed_at = now
        step_run.updated_at = now
        step_run.duration_ms = _duration_ms(step_run.started_at, now)
        await self.append_event(
            db,
            run,
            "step_failed",
            f"Step {step_run.step_key} failed",
            severity="error",
            step_run=step_run,
            data={"step_key": step_run.step_key, "error": error},
        )
        await db.flush()

    async def _mark_remaining_steps_skipped(
        self, db: AsyncSession, run: WorkflowRun, steps: list[Any]
    ) -> None:
        for step in steps:
            step_run = await self.create_step_run(
                db,
                run,
                step_key=step.key,
                step_type=step.type,
                status=WorkflowStepRunStatus.SKIPPED,
            )
            step_run.completed_at = utc_now()
            await self.append_event(
                db,
                run,
                "step_skipped",
                f"Step {step.key} skipped",
                step_run=step_run,
                data={"step_key": step.key},
            )
        await db.flush()

    async def _mark_run_cancelled(
        self, db: AsyncSession, run: WorkflowRun, message: str
    ) -> WorkflowRunDetail:
        now = utc_now()
        run.status = WorkflowRunStatus.CANCELLED.value
        run.completed_at = now
        run.updated_at = now
        run.locked_by = None
        run.lock_expires_at = None
        await self.append_event(db, run, "run_cancelled", message)
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=None)
        return self._to_detail(loaded)

    async def _append_step_event(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        step_run: WorkflowStepRun,
        event: WorkflowStepEventSpec,
    ) -> None:
        await self.append_event(
            db,
            run,
            event.event_type,
            event.message,
            severity=event.severity,
            step_run=step_run,
            data=event.data,
        )

    async def request_cancel_run(
        self,
        db: AsyncSession,
        run_id: str,
        actor: Mapping[str, Any],
        *,
        reason: Optional[str] = None,
    ) -> WorkflowRunDetail:
        """Request cancellation for a queued or running run."""
        run = await self._get_run(db, run_id, actor=actor, for_update=True)
        self._require_manage(run.workflow, actor)
        status = WorkflowRunStatus(run.status)
        if status in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.SKIPPED,
        }:
            raise WorkflowRunConflictError("terminal workflow runs cannot be cancelled")

        now = utc_now()
        run.cancel_requested_at = now
        run.cancelled_by_user_id = _actor_id(actor)
        run.updated_at = now
        if status == WorkflowRunStatus.QUEUED:
            run.status = WorkflowRunStatus.CANCELLED.value
            run.completed_at = now
            event_type = "run_cancelled"
            message = "Queued run cancelled"
        else:
            event_type = "run_cancel_requested"
            message = "Run cancellation requested"
        await self.append_event(
            db,
            run,
            event_type,
            message,
            actor=actor,
            data={"reason": reason},
        )
        await self._record_audit(
            db,
            actor,
            "workflow_run_cancel",
            run,
            details={"reason": reason, "status": run.status},
        )
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=actor)
        return self._to_detail(loaded)

    async def append_event(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        event_type: str,
        message: str,
        *,
        severity: str = "info",
        data: Optional[dict[str, Any]] = None,
        actor: Optional[Mapping[str, Any]] = None,
        step_run: Optional[WorkflowStepRun] = None,
    ) -> WorkflowEvent:
        """Append a workflow event tied to a run."""
        event = WorkflowEvent(
            workflow_id=run.workflow_id,
            version_id=run.version_id,
            run_id=run.id,
            step_run_id=step_run.id if step_run else None,
            event_type=event_type,
            severity=severity,
            message=message,
            data=data or {},
            created_by_user_id=_actor_id(actor or {}),
            created_at=utc_now(),
        )
        db.add(event)
        return event

    def redact_payload(
        self, value: Any, policy: str | WorkflowRedactionPolicy
    ) -> WorkflowRedactedPayload:
        """Return a redacted payload wrapper for API detail responses."""
        redaction_policy = WorkflowRedactionPolicy(policy)
        if value is None:
            return WorkflowRedactedPayload(
                redacted=False, policy=redaction_policy, value=None
            )
        if redaction_policy == WorkflowRedactionPolicy.NONE:
            return WorkflowRedactedPayload(
                redacted=False, policy=redaction_policy, value=value
            )
        if redaction_policy == WorkflowRedactionPolicy.STRICT:
            return WorkflowRedactedPayload(
                redacted=True, policy=redaction_policy, value=None
            )

        redacted, changed = _redact_default(value)
        return WorkflowRedactedPayload(
            redacted=changed, policy=redaction_policy, value=redacted
        )

    async def _get_workflow_for_run(
        self, db: AsyncSession, workflow_id: str, actor: Mapping[str, Any]
    ) -> WorkflowDefinition:
        stmt: Select[tuple[WorkflowDefinition]] = (
            select(WorkflowDefinition)
            .options(selectinload(WorkflowDefinition.versions))
            .where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.status != WorkflowDefinitionStatus.ARCHIVED.value,
            )
        )
        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if workflow is None or not self._can_read(workflow, actor):
            raise WorkflowRunNotFoundError("workflow not found")
        return workflow

    async def _get_run(
        self,
        db: AsyncSession,
        run_id: str,
        *,
        actor: Optional[Mapping[str, Any]],
        for_update: bool = False,
    ) -> WorkflowRun:
        stmt: Select[tuple[WorkflowRun]] = (
            select(WorkflowRun)
            .options(
                selectinload(WorkflowRun.workflow),
                selectinload(WorkflowRun.version),
                selectinload(WorkflowRun.step_runs).selectinload(
                    WorkflowStepRun.artifacts
                ),
                selectinload(WorkflowRun.artifacts),
                selectinload(WorkflowRun.events),
            )
            .where(WorkflowRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise WorkflowRunNotFoundError("workflow run not found")
        if actor is not None and not self._can_read_run(run, actor):
            raise WorkflowRunNotFoundError("workflow run not found")
        return run

    def _can_read(self, workflow: WorkflowDefinition, actor: Mapping[str, Any]) -> bool:
        return _can_read_all(actor) or workflow.owner_user_id == _actor_id(actor)

    def _can_read_run(self, run: WorkflowRun, actor: Mapping[str, Any]) -> bool:
        if _can_read_all(actor):
            return True
        actor_id = _actor_id(actor)
        return (
            run.requested_by_user_id == actor_id
            or run.workflow.owner_user_id == actor_id
        )

    def _require_manage(
        self, workflow: WorkflowDefinition, actor: Mapping[str, Any]
    ) -> None:
        if _is_admin(actor) or workflow.owner_user_id == _actor_id(actor):
            return
        if _has_permission(actor, "workflow.manage"):
            return
        raise WorkflowRunPermissionError("workflow manage permission required")

    async def _record_audit(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
        action: str,
        run: WorkflowRun,
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        await log_audit_event(
            db,
            user_id=str(_actor_id(actor)) if _actor_id(actor) is not None else None,
            action=action,
            resource_type="workflow_run",
            resource_id=run.id,
            details=details or {},
            success=True,
            severity="info",
        )

    def _to_summary(self, run: WorkflowRun) -> WorkflowRunSummary:
        version = run.version if "version" not in sa_inspect(run).unloaded else None
        workflow = run.workflow if "workflow" not in sa_inspect(run).unloaded else None
        return WorkflowRunSummary(
            id=run.id,
            workflow_id=run.workflow_id,
            workflow_name=workflow.name if workflow else None,
            version_id=run.version_id,
            version_number=version.version_number if version else None,
            status=WorkflowRunStatus(run.status),
            trigger_type=WorkflowTriggerType(run.trigger_type),
            requested_by_user_id=run.requested_by_user_id,
            retry_of_run_id=run.retry_of_run_id,
            queued_at=run.queued_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
            duration_ms=_duration_ms(run.started_at or run.queued_at, run.completed_at),
            budget_limit_cents=run.budget_limit_cents,
            estimated_cost_cents=run.estimated_cost_cents or 0,
            actual_cost_cents=run.actual_cost_cents or 0,
        )

    def _to_detail(self, run: WorkflowRun) -> WorkflowRunDetail:
        summary = self._to_summary(run)
        policy = WorkflowRedactionPolicy(run.redaction_policy)
        artifacts = [
            self._artifact_summary(artifact)
            for artifact in sorted(
                _loaded_collection(run, "artifacts"), key=lambda item: item.created_at
            )
        ]
        steps = [
            self._step_summary(step, policy)
            for step in sorted(
                _loaded_collection(run, "step_runs"),
                key=lambda item: (item.created_at, item.step_key, item.attempt),
            )
        ]
        events = [
            WorkflowEventSummary(
                id=event.id,
                event_type=event.event_type,
                severity=event.severity,
                message=event.message,
                data=event.data or {},
                created_by_user_id=event.created_by_user_id,
                created_at=event.created_at,
            )
            for event in sorted(
                _loaded_collection(run, "events"), key=lambda item: item.created_at
            )
        ]
        return WorkflowRunDetail(
            **summary.model_dump(),
            trigger_id=run.trigger_id,
            idempotency_key=run.idempotency_key,
            input_data=self.redact_payload(run.input_data, policy),
            output_data=self.redact_payload(run.output_data, policy),
            error=run.error,
            locked_by=run.locked_by,
            lock_expires_at=run.lock_expires_at,
            cancel_requested_at=run.cancel_requested_at,
            cancelled_by_user_id=run.cancelled_by_user_id,
            redaction_policy=policy,
            steps=steps,
            artifacts=artifacts,
            events=events,
        )

    def _step_summary(
        self, step: WorkflowStepRun, policy: WorkflowRedactionPolicy
    ) -> WorkflowStepRunDetail:
        artifacts = [
            self._artifact_summary(artifact)
            for artifact in sorted(
                _loaded_collection(step, "artifacts"), key=lambda item: item.created_at
            )
        ]
        return WorkflowStepRunDetail(
            id=step.id,
            step_key=step.step_key,
            step_type=step.step_type,
            status=WorkflowStepRunStatus(step.status),
            attempt=step.attempt,
            input_data=self.redact_payload(step.input_data, policy),
            output_data=self.redact_payload(step.output_data, policy),
            error=step.error,
            started_at=step.started_at,
            completed_at=step.completed_at,
            duration_ms=step.duration_ms
            or _duration_ms(step.started_at, step.completed_at),
            artifacts=artifacts,
        )

    def _artifact_summary(self, artifact: WorkflowArtifact) -> WorkflowArtifactSummary:
        policy = WorkflowRedactionPolicy(artifact.redaction_policy)
        return WorkflowArtifactSummary(
            id=artifact.id,
            step_run_id=artifact.step_run_id,
            artifact_type=artifact.artifact_type,
            name=artifact.name,
            data=self.redact_payload(artifact.data, policy),
            storage_uri=artifact.storage_uri,
            redaction_policy=policy,
            created_at=artifact.created_at,
        )


def _actor_id(actor: Mapping[str, Any]) -> Optional[int]:
    value = actor.get("id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_admin(actor: Mapping[str, Any]) -> bool:
    if actor.get("is_superuser"):
        return True
    return actor.get("role") in {"admin", "super_admin"}


def _can_read_all(actor: Mapping[str, Any]) -> bool:
    return (
        _is_admin(actor)
        or _has_permission(actor, "workflow.read")
        or _has_permission(actor, "workflow.manage")
    )


def _has_permission(actor: Mapping[str, Any], permission: str) -> bool:
    permissions = actor.get("permissions") or []
    if permissions == "*":
        return True
    if isinstance(permissions, dict):
        permissions = permissions.get("granted", [])
    aliases = {
        permission,
        permission.replace(":", "."),
        permission.replace(".", ":"),
    }
    return "*" in permissions or any(alias in permissions for alias in aliases)


def _current_version(workflow: WorkflowDefinition) -> Optional[WorkflowVersion]:
    if not workflow.current_version_id:
        return None
    for version in _loaded_collection(workflow, "versions"):
        if version.id == workflow.current_version_id:
            return version
    return None


def _loaded_collection(instance: Any, attribute_name: str) -> list[Any]:
    state = sa_inspect(instance)
    if attribute_name in state.unloaded:
        return []
    return list(getattr(instance, attribute_name) or [])


def _duration_ms(start: Any, end: Any) -> Optional[int]:
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


_SECRET_KEY_PARTS = {
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
}


def _redact_default(value: Any) -> tuple[Any, bool]:
    if isinstance(value, Mapping):
        changed = False
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SECRET_KEY_PARTS):
                redacted[str(key)] = "[redacted]"
                changed = True
                continue
            item_value, item_changed = _redact_default(item)
            redacted[str(key)] = item_value
            changed = changed or item_changed
        return redacted, changed
    if isinstance(value, list):
        changed = False
        items = []
        for item in value:
            item_value, item_changed = _redact_default(item)
            items.append(item_value)
            changed = changed or item_changed
        return items, changed
    return value, False
