"""Workflow service facade and lifecycle operations."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from pydantic import ValidationError
from sqlalchemy import Select, func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import utc_now
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowTrigger,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDetail,
    WorkflowDefinitionDocument,
    WorkflowDefinitionListItem,
    WorkflowDefinitionStatus,
    WorkflowDefinitionUpdate,
    WorkflowLifecycleAction,
    WorkflowStepCatalogEntry,
    WorkflowTemplate,
    WorkflowTriggerSummary,
    WorkflowTriggerType,
    WorkflowValidationErrorItem,
    WorkflowValidationResponse,
    WorkflowVersionStatus,
    WorkflowVersionSummary,
)
from app.services.audit_service import log_audit_event

from .registry import StepRegistry, create_default_step_registry
from .templates import get_workflow_template, list_workflow_templates


@dataclass
class WorkflowRuntimeDependencies:
    """Optional runtime dependencies used by future workflow execution phases."""

    agent_service: Optional[Any] = None
    rag_service: Optional[Any] = None
    extract_service: Optional[Any] = None
    connector_service: Optional[Any] = None
    notification_service: Optional[Any] = None
    audit_service: Optional[Any] = None
    budget_service: Optional[Any] = None


class WorkflowServiceError(Exception):
    """Base workflow service error."""


class WorkflowNotFoundError(WorkflowServiceError):
    """Workflow was not found or is not visible to the actor."""


class WorkflowPermissionError(WorkflowServiceError):
    """Actor lacks permission for the requested workflow action."""


class WorkflowValidationError(WorkflowServiceError):
    """Workflow data failed domain validation."""

    def __init__(self, message: str, details: Optional[list[dict[str, Any]]] = None):
        super().__init__(message)
        self.details = details or []


class WorkflowService:
    """Facade for workflow contracts, catalog lookup, and lifecycle operations."""

    def __init__(
        self,
        dependencies: Optional[WorkflowRuntimeDependencies] = None,
        step_registry: Optional[StepRegistry] = None,
    ) -> None:
        self.dependencies = dependencies or WorkflowRuntimeDependencies()
        self.step_registry = step_registry or create_default_step_registry()

    def validate_definition(
        self, definition: WorkflowDefinitionDocument | dict[str, Any]
    ) -> WorkflowDefinitionDocument:
        """Validate and normalize a workflow definition document."""
        if isinstance(definition, WorkflowDefinitionDocument):
            return definition.model_copy(deep=True)

        return WorkflowDefinitionDocument.model_validate(definition)

    def list_step_catalog(self) -> list[WorkflowStepCatalogEntry]:
        """Return workflow step catalog entries."""
        return self.step_registry.list()

    def get_step_catalog(self, step_type: str) -> WorkflowStepCatalogEntry:
        """Return a single workflow step catalog entry."""
        return self.step_registry.require(step_type)

    def list_templates(self) -> list[WorkflowTemplate]:
        """Return available workflow template seeds."""
        return list_workflow_templates()

    def get_template(self, template_id: str) -> WorkflowTemplate:
        """Return a workflow template seed by id."""
        return get_workflow_template(template_id)

    async def create_definition(
        self,
        db: AsyncSession,
        payload: WorkflowDefinitionCreate,
        actor: Mapping[str, Any],
    ) -> WorkflowDefinitionDetail:
        """Create a mutable workflow draft."""
        definition = self.validate_definition(payload.definition)
        actor_id = _actor_id(actor)
        now = utc_now()

        workflow = WorkflowDefinition(
            name=payload.name,
            description=payload.description,
            draft_definition=definition.model_dump(mode="json"),
            steps=[step.model_dump(mode="json") for step in definition.steps],
            variables={},
            legacy_metadata=payload.metadata,
            status=WorkflowDefinitionStatus.DRAFT.value,
            owner_user_id=actor_id,
            created_by=str(actor_id or actor.get("email") or "system"),
            is_active=False,
            tags=payload.tags,
            created_at=now,
            updated_at=now,
        )
        db.add(workflow)
        await db.flush()
        await self._record_audit(
            db,
            actor,
            "workflow_create",
            workflow,
            details={"status": workflow.status},
        )
        await db.flush()
        return self._to_detail(workflow)

    async def update_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        payload: WorkflowDefinitionUpdate,
        actor: Mapping[str, Any],
    ) -> WorkflowDefinitionDetail:
        """Update a mutable workflow draft."""
        workflow = await self._get_workflow(db, workflow_id, actor, for_update=True)
        self._require_manage(workflow, actor)
        old_values = _workflow_state_snapshot(workflow)

        if payload.name is not None:
            workflow.name = payload.name
        if payload.description is not None:
            workflow.description = payload.description
        if payload.definition is not None:
            definition = self.validate_definition(payload.definition)
            workflow.draft_definition = definition.model_dump(mode="json")
            workflow.steps = [step.model_dump(mode="json") for step in definition.steps]
        if payload.tags is not None:
            workflow.tags = payload.tags
        if payload.metadata is not None:
            workflow.legacy_metadata = payload.metadata

        workflow.updated_at = utc_now()
        await self._record_audit(
            db,
            actor,
            "workflow_update",
            workflow,
            old_values=old_values,
            new_values=_workflow_state_snapshot(workflow),
        )
        await db.flush()
        return self._to_detail(workflow)

    async def validate_workflow_payload(
        self, definition: WorkflowDefinitionDocument | dict[str, Any]
    ) -> WorkflowValidationResponse:
        """Validate a workflow definition and return API-friendly errors."""
        try:
            normalized = self.validate_definition(definition)
        except ValidationError as exc:
            return WorkflowValidationResponse(
                valid=False, errors=_pydantic_validation_errors(exc)
            )
        except ValueError as exc:
            return WorkflowValidationResponse(
                valid=False,
                errors=[
                    WorkflowValidationErrorItem(
                        path="definition",
                        message=str(exc),
                        code="value_error",
                    )
                ],
            )

        errors = self._catalog_validation_errors(normalized)
        return WorkflowValidationResponse(
            valid=len(errors) == 0,
            definition=normalized,
            errors=errors,
        )

    async def publish_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        action: Optional[WorkflowLifecycleAction] = None,
    ) -> WorkflowDefinitionDetail:
        """Publish the current draft as a new immutable version."""
        workflow = await self._get_workflow(db, workflow_id, actor, for_update=True)
        self._require_manage(workflow, actor)
        definition = self._validated_draft(workflow)
        self._require_supported_definition(definition)

        version_number = workflow.latest_version_number + 1
        definition_json = definition.model_dump(mode="json")
        now = utc_now()
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=version_number,
            status=WorkflowVersionStatus.PUBLISHED.value,
            definition=definition_json,
            definition_checksum=_checksum(definition_json),
            created_by_user_id=_actor_id(actor),
            published_by_user_id=_actor_id(actor),
            created_at=now,
            published_at=now,
        )
        db.add(version)
        await db.flush()

        workflow.current_version_id = version.id
        workflow.latest_version_number = version_number
        workflow.last_published_at = now
        workflow.updated_at = now
        if workflow.status == WorkflowDefinitionStatus.DRAFT.value:
            workflow.status = WorkflowDefinitionStatus.DISABLED.value
            workflow.is_active = False

        trigger = self._trigger_for_version(workflow, version, definition)
        db.add(trigger)
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                version_id=version.id,
                event_type="workflow_published",
                message=f"Workflow published as version {version_number}",
                data={"version_number": version_number},
                created_by_user_id=_actor_id(actor),
                created_at=now,
            )
        )
        await self._record_audit(
            db,
            actor,
            "workflow_publish",
            workflow,
            details={
                "version_id": version.id,
                "version_number": version_number,
                "reason": action.reason if action else None,
            },
        )
        await db.flush()
        return await self.get_definition(db, workflow.id, actor)

    async def enable_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        action: Optional[WorkflowLifecycleAction] = None,
    ) -> WorkflowDefinitionDetail:
        """Enable a published workflow."""
        workflow = await self._get_workflow(db, workflow_id, actor, for_update=True)
        self._require_manage(workflow, actor)
        if not workflow.current_version_id:
            raise WorkflowValidationError("workflow must be published before enabling")

        old_values = _workflow_state_snapshot(workflow)
        workflow.status = WorkflowDefinitionStatus.ACTIVE.value
        workflow.is_active = True
        workflow.updated_at = utc_now()
        await self._set_current_trigger_enabled(db, workflow, True)
        await self._record_lifecycle_change(
            db, actor, "workflow_enable", workflow, old_values, action
        )
        return await self.get_definition(db, workflow.id, actor)

    async def disable_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        action: Optional[WorkflowLifecycleAction] = None,
    ) -> WorkflowDefinitionDetail:
        """Disable a workflow without deleting it."""
        workflow = await self._get_workflow(db, workflow_id, actor, for_update=True)
        self._require_manage(workflow, actor)
        old_values = _workflow_state_snapshot(workflow)
        workflow.status = WorkflowDefinitionStatus.DISABLED.value
        workflow.is_active = False
        workflow.updated_at = utc_now()
        await self._set_current_trigger_enabled(db, workflow, False)
        await self._record_lifecycle_change(
            db, actor, "workflow_disable", workflow, old_values, action
        )
        return await self.get_definition(db, workflow.id, actor)

    async def archive_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        action: Optional[WorkflowLifecycleAction] = None,
    ) -> WorkflowDefinitionDetail:
        """Archive a workflow using soft-delete semantics."""
        workflow = await self._get_workflow(db, workflow_id, actor, for_update=True)
        self._require_manage(workflow, actor)
        old_values = _workflow_state_snapshot(workflow)
        workflow.status = WorkflowDefinitionStatus.ARCHIVED.value
        workflow.is_active = False
        workflow.archived_at = utc_now()
        workflow.updated_at = workflow.archived_at
        await self._set_current_trigger_enabled(db, workflow, False)
        await self._record_lifecycle_change(
            db, actor, "workflow_archive", workflow, old_values, action
        )
        return await self.get_definition(db, workflow.id, actor, include_archived=True)

    async def list_definitions(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
        *,
        include_archived: bool = False,
        status: Optional[WorkflowDefinitionStatus] = None,
    ) -> list[WorkflowDefinitionListItem]:
        """List workflow definitions visible to the actor."""
        stmt = select(WorkflowDefinition).options(
            selectinload(WorkflowDefinition.triggers)
        )
        if not include_archived:
            stmt = stmt.where(
                WorkflowDefinition.status != WorkflowDefinitionStatus.ARCHIVED.value
            )
        if status is not None:
            stmt = stmt.where(WorkflowDefinition.status == status.value)
        if not _can_read_all(actor):
            stmt = stmt.where(WorkflowDefinition.owner_user_id == _actor_id(actor))

        stmt = stmt.order_by(WorkflowDefinition.updated_at.desc())
        result = await db.execute(stmt)
        return [self._to_list_item(workflow) for workflow in result.scalars().all()]

    async def get_definition(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        *,
        include_archived: bool = False,
    ) -> WorkflowDefinitionDetail:
        """Return a workflow detail visible to the actor."""
        workflow = await self._get_workflow(
            db, workflow_id, actor, include_archived=include_archived
        )
        return self._to_detail(workflow)

    async def count_definitions(self, db: AsyncSession) -> int:
        """Return the number of non-archived workflow definitions."""
        result = await db.execute(
            select(func.count())
            .select_from(WorkflowDefinition)
            .where(WorkflowDefinition.status != WorkflowDefinitionStatus.ARCHIVED.value)
        )
        return int(result.scalar_one() or 0)

    async def _get_workflow(
        self,
        db: AsyncSession,
        workflow_id: str,
        actor: Mapping[str, Any],
        *,
        include_archived: bool = False,
        for_update: bool = False,
    ) -> WorkflowDefinition:
        stmt: Select[tuple[WorkflowDefinition]] = (
            select(WorkflowDefinition)
            .options(
                selectinload(WorkflowDefinition.versions),
                selectinload(WorkflowDefinition.triggers),
            )
            .where(WorkflowDefinition.id == workflow_id)
        )
        if not include_archived:
            stmt = stmt.where(
                WorkflowDefinition.status != WorkflowDefinitionStatus.ARCHIVED.value
            )
        if for_update:
            stmt = stmt.with_for_update()

        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if workflow is None or not self._can_read(workflow, actor):
            raise WorkflowNotFoundError("workflow not found")
        return workflow

    def _validated_draft(
        self, workflow: WorkflowDefinition
    ) -> WorkflowDefinitionDocument:
        try:
            return self.validate_definition(workflow.draft_definition)
        except ValidationError as exc:
            raise WorkflowValidationError(
                "workflow draft is invalid", details=exc.errors()
            ) from exc

    def _require_supported_definition(
        self, definition: WorkflowDefinitionDocument
    ) -> None:
        errors = self._catalog_validation_errors(definition)
        if errors:
            raise WorkflowValidationError(
                "workflow draft has unsupported steps",
                details=[error.model_dump(mode="json") for error in errors],
            )

    def _catalog_validation_errors(
        self, definition: WorkflowDefinitionDocument
    ) -> list[WorkflowValidationErrorItem]:
        errors: list[WorkflowValidationErrorItem] = []
        for index, step in enumerate(definition.steps):
            entry = self.step_registry.get(step.type)
            if entry is None:
                errors.append(
                    WorkflowValidationErrorItem(
                        path=f"steps[{index}].type",
                        message=f"Unknown workflow step type: {step.type}",
                        code="unknown_step_type",
                        step_key=step.key,
                        step_index=index,
                    )
                )
                continue

            if not entry.enabled:
                reason = entry.disabled_reason or "step type is unavailable"
                errors.append(
                    WorkflowValidationErrorItem(
                        path=f"steps[{index}].type",
                        message=f"{step.type} is not available: {reason}",
                        code="disabled_step_type",
                        step_key=step.key,
                        step_index=index,
                    )
                )

            required_fields = entry.config_schema.get("required", [])
            if not isinstance(required_fields, list):
                continue
            for field in required_fields:
                if not isinstance(field, str):
                    continue
                value = step.config.get(field)
                if value is None or value == "" or value == [] or value == {}:
                    errors.append(
                        WorkflowValidationErrorItem(
                            path=f"steps[{index}].config.{field}",
                            message=f"{step.type} requires config field {field}",
                            code="missing_step_config",
                            step_key=step.key,
                            step_index=index,
                        )
                    )
                elif _contains_template_placeholder(value):
                    errors.append(
                        WorkflowValidationErrorItem(
                            path=f"steps[{index}].config.{field}",
                            message=(
                                f"{step.type} config field {field} has an "
                                "unresolved template placeholder"
                            ),
                            code="unresolved_placeholder",
                            step_key=step.key,
                            step_index=index,
                        )
                    )

            if step.type == "extract.run_template":
                errors.extend(_extract_step_validation_errors(step, index))
            if step.type == "condition.branch":
                errors.extend(
                    _branch_step_validation_errors(step, index, definition.steps)
                )
        return errors

    def _trigger_for_version(
        self,
        workflow: WorkflowDefinition,
        version: WorkflowVersion,
        definition: WorkflowDefinitionDocument,
    ) -> WorkflowTrigger:
        trigger = definition.trigger
        next_run_at = None
        if (
            trigger.type == WorkflowTriggerType.SCHEDULE
            and trigger.cron
            and trigger.timezone
        ):
            from .scheduler import calculate_next_run_at

            next_run_at = calculate_next_run_at(trigger.cron, trigger.timezone)

        return WorkflowTrigger(
            workflow_id=workflow.id,
            version_id=version.id,
            trigger_type=trigger.type.value,
            config=trigger.model_dump(mode="json"),
            cron_expression=trigger.cron,
            timezone=trigger.timezone,
            misfire_policy=trigger.misfire_policy.value,
            enabled=workflow.status == WorkflowDefinitionStatus.ACTIVE.value,
            next_run_at=next_run_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    async def _set_current_trigger_enabled(
        self, db: AsyncSession, workflow: WorkflowDefinition, enabled: bool
    ) -> None:
        if not workflow.current_version_id:
            return
        result = await db.execute(
            select(WorkflowTrigger).where(
                WorkflowTrigger.workflow_id == workflow.id,
                WorkflowTrigger.version_id == workflow.current_version_id,
            )
        )
        for trigger in result.scalars().all():
            trigger.enabled = enabled
            if (
                enabled
                and trigger.trigger_type == WorkflowTriggerType.SCHEDULE.value
                and trigger.cron_expression
                and trigger.timezone
            ):
                from .scheduler import calculate_next_run_at

                trigger.next_run_at = calculate_next_run_at(
                    trigger.cron_expression,
                    trigger.timezone,
                    after=utc_now(),
                )
            trigger.updated_at = utc_now()

    def _can_read(self, workflow: WorkflowDefinition, actor: Mapping[str, Any]) -> bool:
        return _can_read_all(actor) or workflow.owner_user_id == _actor_id(actor)

    def _require_manage(
        self, workflow: WorkflowDefinition, actor: Mapping[str, Any]
    ) -> None:
        if _is_admin(actor) or workflow.owner_user_id == _actor_id(actor):
            return
        if _has_permission(actor, "workflow.manage"):
            return
        raise WorkflowPermissionError("workflow manage permission required")

    async def _record_lifecycle_change(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
        action: str,
        workflow: WorkflowDefinition,
        old_values: dict[str, Any],
        lifecycle_action: Optional[WorkflowLifecycleAction],
    ) -> None:
        await self._record_audit(
            db,
            actor,
            action,
            workflow,
            old_values=old_values,
            new_values=_workflow_state_snapshot(workflow),
            details={"reason": lifecycle_action.reason if lifecycle_action else None},
        )
        await db.flush()

    async def _record_audit(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
        action: str,
        workflow: WorkflowDefinition,
        *,
        details: Optional[dict[str, Any]] = None,
        old_values: Optional[dict[str, Any]] = None,
        new_values: Optional[dict[str, Any]] = None,
    ) -> None:
        audit_details = details.copy() if details else {}
        if old_values is not None:
            audit_details["old_values"] = old_values
        if new_values is not None:
            audit_details["new_values"] = new_values
        await log_audit_event(
            db,
            user_id=str(_actor_id(actor)) if _actor_id(actor) is not None else None,
            action=action,
            resource_type="workflow",
            resource_id=workflow.id,
            details=audit_details,
            success=True,
            severity="info",
        )

    def _to_list_item(self, workflow: WorkflowDefinition) -> WorkflowDefinitionListItem:
        current_trigger = _current_trigger(workflow)
        if current_trigger:
            trigger_type = WorkflowTriggerType(current_trigger.trigger_type)
        else:
            try:
                trigger_type = self.validate_definition(
                    workflow.draft_definition
                ).trigger.type
            except (ValidationError, ValueError):
                trigger_type = WorkflowTriggerType.MANUAL

        return WorkflowDefinitionListItem(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            status=WorkflowDefinitionStatus(workflow.status),
            owner_user_id=workflow.owner_user_id,
            current_version_id=workflow.current_version_id,
            latest_version_number=workflow.latest_version_number,
            is_active=bool(workflow.is_active),
            trigger_type=trigger_type,
            tags=workflow.tags or [],
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            last_published_at=workflow.last_published_at,
            archived_at=workflow.archived_at,
        )

    def _to_detail(self, workflow: WorkflowDefinition) -> WorkflowDefinitionDetail:
        item = self._to_list_item(workflow)
        return WorkflowDefinitionDetail(
            **item.model_dump(),
            draft_definition=self.validate_definition(workflow.draft_definition),
            metadata=workflow.legacy_metadata or {},
            versions=[
                WorkflowVersionSummary(
                    id=version.id,
                    version_number=version.version_number,
                    status=WorkflowVersionStatus(version.status),
                    created_at=version.created_at,
                    published_at=version.published_at,
                )
                for version in sorted(
                    _loaded_collection(workflow, "versions"),
                    key=lambda item: item.version_number,
                )
            ],
            triggers=[
                WorkflowTriggerSummary(
                    id=trigger.id,
                    trigger_type=WorkflowTriggerType(trigger.trigger_type),
                    enabled=trigger.enabled,
                    cron_expression=trigger.cron_expression,
                    timezone=trigger.timezone,
                    misfire_policy=trigger.misfire_policy,
                    next_run_at=trigger.next_run_at,
                )
                for trigger in _loaded_collection(workflow, "triggers")
            ],
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


_SEED_PLACEHOLDER_RE = re.compile(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}")

_BRANCH_OPERATORS = {
    "exists",
    "empty",
    "non_empty",
    "equals",
    "not_equals",
    "contains",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "truthy",
    "falsy",
}

_BRANCH_VALUE_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
}


def _contains_template_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_SEED_PLACEHOLDER_RE.search(value))
    if isinstance(value, list):
        return any(_contains_template_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_template_placeholder(item) for item in value.values())
    return False


def _extract_step_validation_errors(
    step: Any, step_index: int
) -> list[WorkflowValidationErrorItem]:
    errors: list[WorkflowValidationErrorItem] = []
    source = step.config.get("document_source") or (
        "previous_step" if step.config.get("input_step_key") else "rag_filter"
    )
    if source == "rag_filter":
        _append_required_config_error(
            errors, step, step_index, "collection_id", step.config.get("collection_id")
        )
    elif source == "previous_step":
        _append_required_config_error(
            errors,
            step,
            step_index,
            "input_step_key",
            step.config.get("input_step_key"),
        )
    else:
        errors.append(
            WorkflowValidationErrorItem(
                path=f"steps[{step_index}].config.document_source",
                message=f"extract.run_template has unknown document_source: {source}",
                code="invalid_step_config",
                step_key=step.key,
                step_index=step_index,
            )
        )

    context = step.config.get("context")
    if isinstance(context, str) and context.strip():
        try:
            parsed = json.loads(context)
        except json.JSONDecodeError:
            errors.append(
                WorkflowValidationErrorItem(
                    path=f"steps[{step_index}].config.context",
                    message="extract.run_template context must be valid JSON",
                    code="invalid_step_config",
                    step_key=step.key,
                    step_index=step_index,
                )
            )
        else:
            if not isinstance(parsed, dict):
                errors.append(
                    WorkflowValidationErrorItem(
                        path=f"steps[{step_index}].config.context",
                        message="extract.run_template context must be a JSON object",
                        code="invalid_step_config",
                        step_key=step.key,
                        step_index=step_index,
                    )
                )
    return errors


def _branch_step_validation_errors(
    step: Any, step_index: int, steps: list[Any]
) -> list[WorkflowValidationErrorItem]:
    errors: list[WorkflowValidationErrorItem] = []
    step_index_by_key = {candidate.key: index for index, candidate in enumerate(steps)}
    input_step_key = step.config.get("input_step_key")
    if input_step_key not in (None, "", [], {}) and not _contains_template_placeholder(
        input_step_key
    ):
        input_index = step_index_by_key.get(str(input_step_key))
        if input_index is None:
            _append_invalid_config_error(
                errors,
                step,
                step_index,
                "input_step_key",
                f'Branch "{step.key}" references an unknown input step',
            )
        elif input_index >= step_index:
            _append_invalid_config_error(
                errors,
                step,
                step_index,
                "input_step_key",
                f'Branch "{step.key}" references a later step',
            )

    operator = str(step.config.get("operator") or "").strip()
    if operator:
        if operator not in _BRANCH_OPERATORS:
            _append_invalid_config_error(
                errors,
                step,
                step_index,
                "operator",
                f"condition.branch has unsupported operator: {operator}",
            )
        elif operator in _BRANCH_VALUE_OPERATORS:
            _append_required_config_error(
                errors, step, step_index, "value", step.config.get("value")
            )

    for field in ("matched_skip_step_keys", "not_matched_skip_step_keys"):
        targets = step.config.get(field, [])
        if targets in (None, ""):
            continue
        if not isinstance(targets, list):
            _append_invalid_config_error(
                errors,
                step,
                step_index,
                field,
                f"condition.branch config field {field} must be an array of step keys",
            )
            continue

        seen: set[str] = set()
        for target_index, target_key in enumerate(targets):
            target_path = f"{field}[{target_index}]"
            if not isinstance(target_key, str) or not target_key:
                _append_invalid_config_error(
                    errors,
                    step,
                    step_index,
                    target_path,
                    f"condition.branch config field {field} must contain step keys",
                )
                continue
            if target_key in seen:
                _append_invalid_config_error(
                    errors,
                    step,
                    step_index,
                    target_path,
                    f'Branch "{step.key}" references duplicate target step',
                )
                continue
            seen.add(target_key)

            target_step_index = step_index_by_key.get(target_key)
            if target_step_index is None:
                _append_invalid_config_error(
                    errors,
                    step,
                    step_index,
                    target_path,
                    f'Branch "{step.key}" references an unknown target step',
                )
                continue
            if target_step_index <= step_index:
                _append_invalid_config_error(
                    errors,
                    step,
                    step_index,
                    target_path,
                    f'Branch "{step.key}" references an earlier step',
                )
    return errors


def _append_required_config_error(
    errors: list[WorkflowValidationErrorItem],
    step: Any,
    step_index: int,
    field: str,
    value: Any,
) -> None:
    if value is None or value == "" or value == [] or value == {}:
        errors.append(
            WorkflowValidationErrorItem(
                path=f"steps[{step_index}].config.{field}",
                message=f"{step.type} requires config field {field}",
                code="missing_step_config",
                step_key=step.key,
                step_index=step_index,
            )
        )
    elif _contains_template_placeholder(value):
        errors.append(
            WorkflowValidationErrorItem(
                path=f"steps[{step_index}].config.{field}",
                message=(
                    f"{step.type} config field {field} has an unresolved "
                    "template placeholder"
                ),
                code="unresolved_placeholder",
                step_key=step.key,
                step_index=step_index,
            )
        )


def _append_invalid_config_error(
    errors: list[WorkflowValidationErrorItem],
    step: Any,
    step_index: int,
    field: str,
    message: str,
) -> None:
    errors.append(
        WorkflowValidationErrorItem(
            path=f"steps[{step_index}].config.{field}",
            message=message,
            code="invalid_step_config",
            step_key=step.key,
            step_index=step_index,
        )
    )


def _checksum(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _workflow_state_snapshot(workflow: WorkflowDefinition) -> dict[str, Any]:
    return {
        "status": workflow.status,
        "is_active": bool(workflow.is_active),
        "current_version_id": workflow.current_version_id,
        "latest_version_number": workflow.latest_version_number,
    }


def _pydantic_validation_errors(
    exc: ValidationError,
) -> list[WorkflowValidationErrorItem]:
    return [
        WorkflowValidationErrorItem(
            path=_format_validation_path(error.get("loc", ())),
            message=str(error.get("msg") or "validation error"),
            code=str(error.get("type") or "validation_error"),
        )
        for error in exc.errors()
    ]


def _format_validation_path(location: Any) -> str:
    if not isinstance(location, (list, tuple)) or not location:
        return "definition"

    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
            continue
        if path:
            path += "."
        path += str(part)
    return path or "definition"


def _current_trigger(workflow: WorkflowDefinition) -> Optional[WorkflowTrigger]:
    triggers = _loaded_collection(workflow, "triggers")
    if workflow.current_version_id:
        for trigger in triggers:
            if trigger.version_id == workflow.current_version_id:
                return trigger
    return triggers[-1] if triggers else None


def _loaded_collection(instance: Any, attribute_name: str) -> list[Any]:
    state = sa_inspect(instance)
    if attribute_name in state.unloaded:
        return []
    return list(getattr(instance, attribute_name) or [])
