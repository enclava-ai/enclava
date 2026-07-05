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
    WorkflowApproval,
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowApprovalStatus,
    WorkflowApprovalSummary,
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
        return await self._execute_steps(
            db,
            run,
            definition,
            previous_outputs={},
            start_index=0,
            targeted_skips={},
            actor=actor,
        )

    async def _execute_steps(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        definition: WorkflowDefinitionDocument,
        *,
        previous_outputs: dict[str, dict[str, Any]],
        start_index: int,
        targeted_skips: dict[str, dict[str, str]],
        actor: Optional[Mapping[str, Any]],
    ) -> WorkflowRunDetail:
        """Execute an ordered definition slice from a stable step index."""
        for index, step in enumerate(definition.steps[start_index:], start=start_index):
            if run.cancel_requested_at:
                return await self._mark_run_cancelled(db, run, "Run cancelled")

            if step.key in targeted_skips:
                skip_info = targeted_skips[step.key]
                await self._mark_step_skipped(
                    db,
                    run,
                    step,
                    reason=skip_info["reason"],
                    source_step_key=skip_info["source_step_key"],
                )
                continue

            result = await self._execute_step_with_retries(
                db, run, definition, step, previous_outputs, actor
            )
            previous_outputs[step.key] = result.output_data
            if result.pause_run:
                return await self._pause_run_for_approval(
                    db,
                    run,
                    definition,
                    step,
                    result,
                    previous_outputs=previous_outputs,
                    targeted_skips=targeted_skips,
                    next_step_index=index + 1,
                    actor=actor,
                )
            for skip_step_key in result.skip_step_keys:
                targeted_skips.setdefault(
                    skip_step_key,
                    {
                        "reason": result.skip_reason or f"Skipped by step {step.key}",
                        "source_step_key": step.key,
                    },
                )
            if result.skip_remaining:
                await self._mark_remaining_steps_skipped(
                    db,
                    run,
                    definition.steps[index + 1 :],
                    reason=f"Step {step.key} requested remaining steps be skipped",
                    source_step_key=step.key,
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

    async def resolve_approval(
        self,
        db: AsyncSession,
        run_id: str,
        actor: Mapping[str, Any],
        *,
        approved: bool,
        comment: Optional[str] = None,
        worker_id: str = "approval-api",
    ) -> WorkflowRunDetail:
        """Approve or reject the pending approval for a paused run."""
        run = await self._get_run(db, run_id, actor=actor, for_update=True)
        if WorkflowRunStatus(run.status) != WorkflowRunStatus.PAUSED:
            raise WorkflowRunConflictError("only paused runs can resolve approval")

        approval = _pending_approval(run)
        if approval is None:
            raise WorkflowRunConflictError("paused run has no pending approval")

        self._require_approve(run, approval, actor)
        definition = WorkflowDefinitionDocument.model_validate(run.version.definition)
        pause_state = _pause_state(run)
        next_step_index = int(pause_state.get("next_step_index") or 0)
        previous_outputs = _coerce_outputs(pause_state.get("outputs"))
        targeted_skips = _coerce_targeted_skips(pause_state.get("targeted_skips"))
        resolved_output = {
            "status": (
                WorkflowApprovalStatus.APPROVED.value
                if approved
                else WorkflowApprovalStatus.REJECTED.value
            ),
            "approved": approved,
            "approval_id": approval.id,
            "step_key": approval.step_key,
            "comment": comment,
            "resolved_by_user_id": _actor_id(actor),
        }
        previous_outputs[approval.step_key] = resolved_output

        await self._resolve_approval_record(
            db,
            run,
            approval,
            approved=approved,
            comment=comment,
            resolved_output=resolved_output,
            actor=actor,
        )

        if approved:
            now = utc_now()
            run.status = WorkflowRunStatus.RUNNING.value
            run.output_data = {
                "resumed": True,
                "approval_id": approval.id,
                "approval_step_key": approval.step_key,
                "outputs": previous_outputs,
            }
            run.locked_by = worker_id
            run.lock_expires_at = now + timedelta(seconds=300)
            run.updated_at = now
            await self.append_event(
                db,
                run,
                "run_resumed",
                "Run resumed after approval",
                actor=actor,
                data={
                    "approval_id": approval.id,
                    "step_key": approval.step_key,
                    "next_step_index": next_step_index,
                },
            )
            await self._record_audit(
                db,
                actor,
                "workflow_run_approval_approved",
                run,
                details={"approval_id": approval.id, "comment": comment},
            )
            await db.flush()
            return await self._execute_steps(
                db,
                run,
                definition,
                previous_outputs=previous_outputs,
                start_index=next_step_index,
                targeted_skips=targeted_skips,
                actor=None,
            )

        await self._mark_remaining_steps_skipped(
            db,
            run,
            definition.steps[next_step_index:],
            reason=comment or f"Approval rejected at step {approval.step_key}",
            source_step_key=approval.step_key,
        )
        await self._record_audit(
            db,
            actor,
            "workflow_run_approval_rejected",
            run,
            details={"approval_id": approval.id, "comment": comment},
        )
        return await self.complete_run(
            db,
            run,
            output_data={
                "skipped": True,
                "approval_id": approval.id,
                "approval_step_key": approval.step_key,
                "approval_status": WorkflowApprovalStatus.REJECTED.value,
                "outputs": previous_outputs,
            },
            status=WorkflowRunStatus.SKIPPED,
        )

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

    async def _pause_run_for_approval(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        definition: WorkflowDefinitionDocument,
        step: Any,
        result: Any,
        *,
        previous_outputs: dict[str, dict[str, Any]],
        targeted_skips: dict[str, dict[str, str]],
        next_step_index: int,
        actor: Optional[Mapping[str, Any]],
    ) -> WorkflowRunDetail:
        request = result.approval_request
        if request is None:
            raise WorkflowRunValidationError(
                "approval pause requested without approval metadata"
            )

        now = utc_now()
        approval = WorkflowApproval(
            workflow_id=run.workflow_id,
            run_id=run.id,
            step_run_id=result.step_run_id,
            step_key=step.key,
            status=WorkflowApprovalStatus.PENDING.value,
            title=request.title,
            body=request.body,
            approver_user_ids=request.approver_user_ids,
            requested_by_user_id=_actor_id(actor or {}) or run.requested_by_user_id,
            approval_metadata={
                **(request.metadata or {}),
                "allow_requester_approval": request.allow_requester_approval,
                "next_step_index": next_step_index,
                "total_steps": len(definition.steps),
            },
            created_at=now,
            updated_at=now,
        )
        db.add(approval)
        await db.flush()

        run.status = WorkflowRunStatus.PAUSED.value
        run.output_data = {
            "paused": True,
            "approval_id": approval.id,
            "approval_step_key": step.key,
            "next_step_index": next_step_index,
            "outputs": previous_outputs,
            "targeted_skips": targeted_skips,
        }
        run.locked_by = None
        run.lock_expires_at = None
        run.updated_at = now
        await self.append_event(
            db,
            run,
            "approval_requested",
            f"Approval requested: {request.title}",
            actor=actor,
            data={
                "approval_id": approval.id,
                "step_key": step.key,
                "approver_user_ids": request.approver_user_ids,
            },
        )
        await self.append_event(
            db,
            run,
            "run_paused",
            "Run paused for approval",
            actor=actor,
            data={"approval_id": approval.id, "step_key": step.key},
        )
        await db.flush()
        loaded = await self._get_run(db, run.id, actor=None)
        return self._to_detail(loaded)

    async def _resolve_approval_record(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        approval: WorkflowApproval,
        *,
        approved: bool,
        comment: Optional[str],
        resolved_output: dict[str, Any],
        actor: Mapping[str, Any],
    ) -> None:
        now = utc_now()
        approval.status = (
            WorkflowApprovalStatus.APPROVED.value
            if approved
            else WorkflowApprovalStatus.REJECTED.value
        )
        approval.resolved_by_user_id = _actor_id(actor)
        approval.resolution_comment = comment
        approval.resolved_at = now
        approval.updated_at = now
        step_run = _step_run_for_approval(run, approval)
        if step_run is not None:
            step_run.status = WorkflowStepRunStatus.SUCCEEDED.value
            step_run.output_data = resolved_output
            step_run.completed_at = now
            step_run.updated_at = now
            step_run.duration_ms = _duration_ms(step_run.started_at, now)
        event_type = "approval_approved" if approved else "approval_rejected"
        await self.append_event(
            db,
            run,
            event_type,
            "Approval approved" if approved else "Approval rejected",
            actor=actor,
            step_run=step_run,
            data={
                "approval_id": approval.id,
                "step_key": approval.step_key,
                "comment": comment,
                "resolved_by_user_id": _actor_id(actor),
            },
        )
        await db.flush()

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
            result.step_run_id = step_run.id
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
        self,
        db: AsyncSession,
        run: WorkflowRun,
        steps: list[Any],
        *,
        reason: Optional[str] = None,
        source_step_key: Optional[str] = None,
    ) -> None:
        for step in steps:
            await self._mark_step_skipped(
                db,
                run,
                step,
                reason=reason,
                source_step_key=source_step_key,
            )
        await db.flush()

    async def _mark_step_skipped(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        step: Any,
        *,
        reason: Optional[str] = None,
        source_step_key: Optional[str] = None,
    ) -> None:
        step_run = await self.create_step_run(
            db,
            run,
            step_key=step.key,
            step_type=step.type,
            status=WorkflowStepRunStatus.SKIPPED,
        )
        now = utc_now()
        step_run.completed_at = now
        step_run.updated_at = now
        step_run.duration_ms = 0
        message = f"Step {step.key} skipped"
        if reason:
            message = f"{message}: {reason}"
        await self.append_event(
            db,
            run,
            "step_skipped",
            message,
            step_run=step_run,
            data={
                "step_key": step.key,
                "reason": reason,
                "source_step_key": source_step_key,
            },
        )

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
        elif status == WorkflowRunStatus.PAUSED:
            run.status = WorkflowRunStatus.CANCELLED.value
            run.completed_at = now
            event_type = "run_cancelled"
            message = "Paused run cancelled"
            self._cancel_pending_approvals(run, actor, reason)
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
                selectinload(WorkflowRun.approvals),
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

    def _require_approve(
        self,
        run: WorkflowRun,
        approval: WorkflowApproval,
        actor: Mapping[str, Any],
    ) -> None:
        actor_id = _actor_id(actor)
        workflow = run.workflow
        if _is_admin(actor) or workflow.owner_user_id == actor_id:
            return
        if _has_permission(actor, "workflow.manage"):
            return

        allow_requester_approval = bool(
            (approval.approval_metadata or {}).get("allow_requester_approval")
        )
        if (
            actor_id is not None
            and actor_id == run.requested_by_user_id
            and not allow_requester_approval
        ):
            raise WorkflowRunPermissionError(
                "requester self-approval is not allowed for this approval"
            )
        if _has_permission(actor, "workflow.approve"):
            return
        if actor_id is not None and actor_id in _approval_user_ids(approval):
            return
        raise WorkflowRunPermissionError("workflow approval permission required")

    def _cancel_pending_approvals(
        self,
        run: WorkflowRun,
        actor: Mapping[str, Any],
        reason: Optional[str],
    ) -> None:
        now = utc_now()
        for approval in _loaded_collection(run, "approvals"):
            if approval.status != WorkflowApprovalStatus.PENDING.value:
                continue
            approval.status = WorkflowApprovalStatus.CANCELLED.value
            approval.resolved_by_user_id = _actor_id(actor)
            approval.resolution_comment = reason
            approval.resolved_at = now
            approval.updated_at = now

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
        approvals = [
            self._approval_summary(approval)
            for approval in sorted(
                _loaded_collection(run, "approvals"), key=lambda item: item.created_at
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
            approvals=approvals,
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

    def _approval_summary(self, approval: WorkflowApproval) -> WorkflowApprovalSummary:
        return WorkflowApprovalSummary(
            id=approval.id,
            workflow_id=approval.workflow_id,
            run_id=approval.run_id,
            step_run_id=approval.step_run_id,
            step_key=approval.step_key,
            status=WorkflowApprovalStatus(approval.status),
            title=approval.title,
            body=approval.body,
            approver_user_ids=_approval_user_ids(approval),
            requested_by_user_id=approval.requested_by_user_id,
            resolved_by_user_id=approval.resolved_by_user_id,
            resolution_comment=approval.resolution_comment,
            metadata=approval.approval_metadata or {},
            created_at=approval.created_at,
            updated_at=approval.updated_at,
            resolved_at=approval.resolved_at,
        )


def _actor_id(actor: Mapping[str, Any]) -> Optional[int]:
    value = actor.get("id")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pending_approval(run: WorkflowRun) -> Optional[WorkflowApproval]:
    pending = [
        approval
        for approval in _loaded_collection(run, "approvals")
        if approval.status == WorkflowApprovalStatus.PENDING.value
    ]
    if not pending:
        return None
    return sorted(pending, key=lambda item: item.created_at)[0]


def _approval_user_ids(approval: WorkflowApproval) -> list[int]:
    values = approval.approver_user_ids or []
    user_ids: list[int] = []
    if not isinstance(values, list):
        return user_ids
    for value in values:
        try:
            user_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return user_ids


def _pause_state(run: WorkflowRun) -> dict[str, Any]:
    output = run.output_data or {}
    return output if isinstance(output, dict) else {}


def _coerce_outputs(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    outputs: dict[str, dict[str, Any]] = {}
    for key, output in value.items():
        if isinstance(key, str) and isinstance(output, dict):
            outputs[key] = output
    return outputs


def _coerce_targeted_skips(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    targeted_skips: dict[str, dict[str, str]] = {}
    for step_key, skip_info in value.items():
        if not isinstance(step_key, str) or not isinstance(skip_info, dict):
            continue
        reason = skip_info.get("reason")
        source_step_key = skip_info.get("source_step_key")
        if isinstance(reason, str) and isinstance(source_step_key, str):
            targeted_skips[step_key] = {
                "reason": reason,
                "source_step_key": source_step_key,
            }
    return targeted_skips


def _step_run_for_approval(
    run: WorkflowRun, approval: WorkflowApproval
) -> Optional[WorkflowStepRun]:
    step_runs = _loaded_collection(run, "step_runs")
    if approval.step_run_id:
        for step_run in step_runs:
            if step_run.id == approval.step_run_id:
                return step_run
    candidates = [item for item in step_runs if item.step_key == approval.step_key]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.created_at)[-1]


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
