"""Authenticated API and event trigger firing for workflows."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Optional

from pydantic import ValidationError
from sqlalchemy import func, select
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
    WorkflowRedactionPolicy,
    WorkflowRunStatus,
    WorkflowTriggerFireRequest,
    WorkflowTriggerFireResponse,
    WorkflowTriggerFireRunResult,
    WorkflowTriggerType,
)
from app.services.audit_service import log_audit_event

from .runtime import WorkflowRuntimeService
from .service import (
    WorkflowPermissionError,
    WorkflowValidationError,
    _actor_id,
    _has_permission,
    _is_admin,
)
from .steps import WorkflowStepExecutionError


class WorkflowTriggerFireService:
    """Create workflow runs from authenticated API/event trigger requests."""

    def __init__(
        self,
        runtime_service: Optional[WorkflowRuntimeService] = None,
    ) -> None:
        self.runtime_service = runtime_service or WorkflowRuntimeService()

    async def fire_api_trigger(
        self,
        db: AsyncSession,
        api_slug: str,
        payload: WorkflowTriggerFireRequest,
        actor: Mapping[str, Any],
    ) -> WorkflowTriggerFireResponse:
        """Fire one or more matching API triggers by slug."""
        key = _validate_fire_key(
            api_slug,
            pattern=_API_FIRE_SLUG_RE,
            label="API trigger slug",
        )
        return await self._fire_trigger(
            db,
            trigger_type=WorkflowTriggerType.API,
            key=key,
            config_field="api_slug",
            payload=payload,
            actor=actor,
        )

    async def fire_event_trigger(
        self,
        db: AsyncSession,
        event_name: str,
        payload: WorkflowTriggerFireRequest,
        actor: Mapping[str, Any],
    ) -> WorkflowTriggerFireResponse:
        """Fire matching event triggers by event name."""
        key = _validate_fire_key(
            event_name,
            pattern=_EVENT_FIRE_NAME_RE,
            label="Event trigger name",
        )
        return await self._fire_trigger(
            db,
            trigger_type=WorkflowTriggerType.EVENT,
            key=key,
            config_field="event_name",
            payload=payload,
            actor=actor,
        )

    async def _fire_trigger(
        self,
        db: AsyncSession,
        *,
        trigger_type: WorkflowTriggerType,
        key: str,
        config_field: str,
        payload: WorkflowTriggerFireRequest,
        actor: Mapping[str, Any],
    ) -> WorkflowTriggerFireResponse:
        response = WorkflowTriggerFireResponse(
            trigger_type=trigger_type,
            key=key,
        )
        triggers = await self._matching_triggers(
            db,
            trigger_type=trigger_type,
            config_field=config_field,
            key=key,
        )
        authorized = [
            trigger
            for trigger in triggers
            if trigger.workflow is not None and _can_fire(trigger.workflow, actor)
        ]
        if not authorized and triggers:
            raise WorkflowPermissionError("workflow trigger permission required")

        for trigger in authorized:
            await self._process_trigger(db, trigger, key, payload, actor, response)

        response.success = response.failed_runs == 0 and not response.errors
        await db.flush()
        return response

    async def _matching_triggers(
        self,
        db: AsyncSession,
        *,
        trigger_type: WorkflowTriggerType,
        config_field: str,
        key: str,
    ) -> list[WorkflowTrigger]:
        result = await db.execute(
            select(WorkflowTrigger)
            .options(
                selectinload(WorkflowTrigger.workflow),
                selectinload(WorkflowTrigger.version),
            )
            .where(WorkflowTrigger.trigger_type == trigger_type.value)
            .order_by(WorkflowTrigger.created_at.asc())
        )
        matches: list[WorkflowTrigger] = []
        for trigger in result.scalars().all():
            if _trigger_config_value(trigger, config_field) != key:
                continue
            workflow = trigger.workflow
            if (
                workflow is not None
                and workflow.current_version_id != trigger.version_id
            ):
                continue
            matches.append(trigger)
        return matches

    async def _process_trigger(
        self,
        db: AsyncSession,
        trigger: WorkflowTrigger,
        key: str,
        payload: WorkflowTriggerFireRequest,
        actor: Mapping[str, Any],
        response: WorkflowTriggerFireResponse,
    ) -> None:
        workflow = trigger.workflow
        version = trigger.version
        if workflow is None or version is None:
            response.skipped_triggers += 1
            response.runs.append(
                _run_result(
                    trigger,
                    status="skipped",
                    reason="trigger_missing_workflow_or_version",
                    idempotency_key=_derived_idempotency_key(
                        WorkflowTriggerType(trigger.trigger_type),
                        trigger.id,
                        payload.idempotency_key,
                    ),
                )
            )
            return

        now = utc_now()
        idempotency_key = _derived_idempotency_key(
            WorkflowTriggerType(trigger.trigger_type),
            trigger.id,
            payload.idempotency_key,
        )

        if (
            not trigger.enabled
            or workflow.status != WorkflowDefinitionStatus.ACTIVE.value
            or not workflow.is_active
        ):
            response.skipped_triggers += 1
            response.runs.append(
                _run_result(
                    trigger,
                    status="skipped",
                    reason="workflow_inactive",
                    idempotency_key=idempotency_key,
                )
            )
            await self._append_trigger_event(
                db,
                workflow,
                version,
                trigger,
                "trigger_run_skipped",
                "Trigger fire skipped because workflow is inactive",
                actor=actor,
                data={"reason": "workflow_inactive", "trigger_key": key},
            )
            return

        try:
            definition = WorkflowDefinitionDocument.model_validate(version.definition)
        except (ValidationError, ValueError) as exc:
            response.failed_runs += 1
            response.errors.append(f"{trigger.id}: {exc}")
            response.runs.append(
                _run_result(
                    trigger,
                    status="failed",
                    reason="workflow_definition_invalid",
                    idempotency_key=idempotency_key,
                )
            )
            return

        existing_run = await self._existing_run(db, idempotency_key)
        if existing_run is not None:
            trigger.last_fire_at = now
            trigger.updated_at = now
            response.duplicate_runs += 1
            response.runs.append(
                _run_result(
                    trigger,
                    status="duplicate",
                    run_id=existing_run.id,
                    reason="idempotency_key_exists",
                    idempotency_key=idempotency_key,
                )
            )
            return

        if (
            definition.runtime.concurrency_policy
            == WorkflowConcurrencyPolicy.SKIP_IF_RUNNING
            and await self._workflow_has_active_run(db, workflow.id)
        ):
            response.skipped_triggers += 1
            response.runs.append(
                _run_result(
                    trigger,
                    status="skipped",
                    reason="workflow_already_running",
                    idempotency_key=idempotency_key,
                )
            )
            await self._append_trigger_event(
                db,
                workflow,
                version,
                trigger,
                "trigger_run_skipped",
                "Trigger fire skipped because workflow is already running",
                actor=actor,
                data={
                    "reason": "workflow_already_running",
                    "trigger_key": key,
                    "concurrency_policy": definition.runtime.concurrency_policy.value,
                },
            )
            return

        run = await self._create_triggered_run(
            db,
            workflow,
            version,
            trigger,
            definition,
            key,
            payload,
            actor,
            idempotency_key,
        )
        trigger.last_fire_at = now
        trigger.updated_at = now
        result = _run_result(
            trigger,
            status="created",
            run_id=run.id,
            idempotency_key=idempotency_key,
        )
        response.created_runs += 1
        response.runs.append(result)

        if payload.execute_now:
            try:
                detail = await self.runtime_service.execute_run(
                    db,
                    run.id,
                    worker_id=f"trigger-{trigger.trigger_type}",
                    actor=None,
                )
            except WorkflowStepExecutionError as exc:
                response.failed_runs += 1
                response.errors.append(f"{run.id}: {exc}")
                result.status = WorkflowRunStatus.FAILED.value
                result.reason = str(exc)
            else:
                response.executed_runs += 1
                result.status = detail.status.value

    async def _existing_run(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> Optional[WorkflowRun]:
        result = await db.execute(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def _workflow_has_active_run(
        self, db: AsyncSession, workflow_id: str
    ) -> bool:
        result = await db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(
                WorkflowRun.workflow_id == workflow_id,
                WorkflowRun.status.in_(
                    {
                        WorkflowRunStatus.QUEUED.value,
                        WorkflowRunStatus.RUNNING.value,
                        WorkflowRunStatus.PAUSED.value,
                    }
                ),
            )
        )
        return int(result.scalar_one() or 0) > 0

    async def _create_triggered_run(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        version: WorkflowVersion,
        trigger: WorkflowTrigger,
        definition: WorkflowDefinitionDocument,
        key: str,
        payload: WorkflowTriggerFireRequest,
        actor: Mapping[str, Any],
        idempotency_key: str,
    ) -> WorkflowRun:
        now = utc_now()
        trigger_type = WorkflowTriggerType(trigger.trigger_type)
        run = WorkflowRun(
            workflow_id=workflow.id,
            version_id=version.id,
            trigger_id=trigger.id,
            trigger_type=trigger_type.value,
            idempotency_key=idempotency_key,
            input_data={
                "trigger": {
                    "type": trigger_type.value,
                    "trigger_id": trigger.id,
                    "api_slug": (
                        key if trigger_type == WorkflowTriggerType.API else None
                    ),
                    "event_name": (
                        key if trigger_type == WorkflowTriggerType.EVENT else None
                    ),
                },
                "payload": payload.input_data,
            },
            status=WorkflowRunStatus.QUEUED.value,
            requested_by_user_id=_actor_id(actor),
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
            f"{trigger_type.value.title()} workflow run queued",
            actor=actor,
            data={
                "trigger_id": trigger.id,
                "trigger_type": trigger_type.value,
                "trigger_key": key,
                "idempotency_key": idempotency_key,
            },
        )
        await self._record_trigger_audit(
            db,
            workflow,
            run,
            trigger_type,
            key,
            actor,
        )
        return run

    async def _append_trigger_event(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        version: WorkflowVersion,
        trigger: WorkflowTrigger,
        event_type: str,
        message: str,
        *,
        actor: Mapping[str, Any],
        data: dict[str, Any],
    ) -> None:
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                version_id=version.id,
                event_type=event_type,
                message=message,
                data={"trigger_id": trigger.id, **data},
                created_by_user_id=_actor_id(actor),
                created_at=utc_now(),
            )
        )
        await db.flush()

    async def _record_trigger_audit(
        self,
        db: AsyncSession,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        trigger_type: WorkflowTriggerType,
        key: str,
        actor: Mapping[str, Any],
    ) -> None:
        await log_audit_event(
            db,
            user_id=str(_actor_id(actor)) if _actor_id(actor) is not None else None,
            action=(
                "workflow_run_api_trigger"
                if trigger_type == WorkflowTriggerType.API
                else "workflow_run_event_trigger"
            ),
            resource_type="workflow_run",
            resource_id=run.id,
            details={
                "workflow_id": workflow.id,
                "trigger_id": run.trigger_id,
                "trigger_type": trigger_type.value,
                "trigger_key": key,
            },
            success=True,
            severity="info",
        )


def _can_fire(workflow: WorkflowDefinition, actor: Mapping[str, Any]) -> bool:
    if _is_admin(actor) or workflow.owner_user_id == _actor_id(actor):
        return True
    return _has_permission(actor, "workflow.manage") or _has_permission(
        actor, "workflow.trigger"
    )


def _validate_fire_key(value: str, *, pattern: re.Pattern[str], label: str) -> str:
    normalized = value.strip()
    if not normalized or not pattern.fullmatch(normalized):
        raise WorkflowValidationError(
            f"{label} is invalid",
            details=[
                {
                    "path": "trigger",
                    "message": f"{label} is invalid",
                    "code": "invalid_trigger_key",
                }
            ],
        )
    return normalized


def _trigger_config_value(trigger: WorkflowTrigger, config_field: str) -> Optional[str]:
    config = trigger.config or {}
    value = config.get(config_field)
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _derived_idempotency_key(
    trigger_type: WorkflowTriggerType,
    trigger_id: str,
    caller_key: str,
) -> str:
    raw = f"{trigger_type.value}:{trigger_id}:{caller_key}"
    if len(raw) <= 160:
        return raw
    digest = hashlib.sha256(caller_key.encode("utf-8")).hexdigest()
    return f"{trigger_type.value}:{trigger_id}:{digest}"


def _run_result(
    trigger: WorkflowTrigger,
    *,
    status: str,
    idempotency_key: str,
    run_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> WorkflowTriggerFireRunResult:
    return WorkflowTriggerFireRunResult(
        workflow_id=trigger.workflow_id,
        trigger_id=trigger.id,
        run_id=run_id,
        status=status,
        reason=reason,
        idempotency_key=idempotency_key,
        trigger_type=WorkflowTriggerType(trigger.trigger_type),
    )


_API_FIRE_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")
_EVENT_FIRE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
