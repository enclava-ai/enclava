"""Workflow domain contracts shared by services and APIs."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkflowDefinitionStatus(str, Enum):
    """Lifecycle state for a workflow definition."""

    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class WorkflowVersionStatus(str, Enum):
    """Lifecycle state for a workflow version."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class WorkflowTriggerType(str, Enum):
    """Supported workflow trigger families."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"
    API = "api"


class WorkflowRunStatus(str, Enum):
    """Durable workflow run state."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    SKIPPED = "skipped"


class WorkflowHealthState(str, Enum):
    """Operations-console workflow health state."""

    HEALTHY = "healthy"
    DISABLED = "disabled"
    RUNNING = "running"
    FAILED = "failed"
    MISSED = "missed"
    NO_SCHEDULE = "no_schedule"


class WorkflowStepRunStatus(str, Enum):
    """Durable workflow step run state."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class WorkflowConcurrencyPolicy(str, Enum):
    """Controls what happens when a workflow is already running."""

    SKIP_IF_RUNNING = "skip_if_running"
    QUEUE_AFTER_CURRENT = "queue_after_current"
    ALLOW_PARALLEL = "allow_parallel"


class WorkflowMisfirePolicy(str, Enum):
    """Controls missed schedule behavior after downtime or scheduler lag."""

    SKIP = "skip"
    RUN_ONCE = "run_once"
    CATCH_UP = "catch_up"


class WorkflowRedactionPolicy(str, Enum):
    """Controls persisted input/output redaction behavior."""

    DEFAULT = "default"
    STRICT = "strict"
    NONE = "none"


class WorkflowRetryPolicy(BaseModel):
    """Retry policy attached to a workflow step."""

    max_attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: int = Field(default=0, ge=0, le=86400)


class WorkflowRuntimePolicy(BaseModel):
    """Runtime policy shared by all runs of a workflow version."""

    concurrency_policy: WorkflowConcurrencyPolicy = (
        WorkflowConcurrencyPolicy.SKIP_IF_RUNNING
    )
    timeout_seconds: int = Field(default=1800, ge=1)
    budget_limit_cents: Optional[int] = Field(default=None, ge=0)
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT


class WorkflowTriggerDefinition(BaseModel):
    """Trigger contract embedded in a workflow definition document."""

    type: WorkflowTriggerType = WorkflowTriggerType.MANUAL
    cron: Optional[str] = None
    timezone: Optional[str] = None
    misfire_policy: WorkflowMisfirePolicy = WorkflowMisfirePolicy.RUN_ONCE
    catchup_limit: Optional[int] = Field(default=None, ge=0, le=100)
    event_name: Optional[str] = None
    api_slug: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("cron", "timezone", "event_name", "api_slug")
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional string fields."""
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_trigger_requirements(self) -> "WorkflowTriggerDefinition":
        """Ensure trigger-specific required fields are present."""
        if self.type == WorkflowTriggerType.SCHEDULE:
            if not self.cron:
                raise ValueError("schedule triggers require cron")
            if not self.timezone:
                raise ValueError("schedule triggers require timezone")
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            from croniter import croniter

            if not croniter.is_valid(self.cron):
                raise ValueError("schedule triggers require a valid cron")
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(
                    "schedule triggers require a valid IANA timezone"
                ) from exc

        if self.type == WorkflowTriggerType.EVENT and not self.event_name:
            raise ValueError("event triggers require event_name")

        if self.type == WorkflowTriggerType.API and not self.api_slug:
            raise ValueError("api triggers require api_slug")

        return self


class WorkflowStepDefinition(BaseModel):
    """Step contract embedded in a workflow definition document."""

    key: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=3, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    config: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    retry: WorkflowRetryPolicy = Field(default_factory=WorkflowRetryPolicy)
    timeout_seconds: Optional[int] = Field(default=None, ge=1)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        """Require stable identifier-style step keys."""
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", value):
            raise ValueError(
                "step key must start with a letter and contain only letters, "
                "numbers, underscores, or hyphens"
            )

        return value

    @field_validator("type")
    @classmethod
    def validate_step_type(cls, value: str) -> str:
        """Require namespaced step types such as rag.query."""
        if "." not in value:
            raise ValueError("step type must be namespaced, for example rag.query")

        return value


class WorkflowDefinitionDocument(BaseModel):
    """Versioned workflow definition stored with published workflow versions."""

    schema_version: int = Field(default=1, ge=1)
    trigger: WorkflowTriggerDefinition = Field(
        default_factory=WorkflowTriggerDefinition
    )
    runtime: WorkflowRuntimePolicy = Field(default_factory=WorkflowRuntimePolicy)
    steps: List[WorkflowStepDefinition] = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_step_graph(self) -> "WorkflowDefinitionDocument":
        """Validate v1 linear step ordering and unique keys."""
        seen: set[str] = set()

        for step in self.steps:
            if step.key in seen:
                raise ValueError(f"duplicate step key: {step.key}")

            for dependency in step.depends_on:
                if dependency not in seen:
                    raise ValueError(
                        f"step {step.key} depends on unknown or later step: "
                        f"{dependency}"
                    )

            seen.add(step.key)

        return self


class WorkflowStepCatalogEntry(BaseModel):
    """Metadata describing a workflow step type available to builders."""

    type: str
    display_name: str
    description: str
    category: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    supports_retry: bool = True
    supports_test: bool = False
    estimated_cost_kind: Optional[str] = None
    enabled: bool = True
    disabled_reason: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_catalog_type(cls, value: str) -> str:
        """Require catalog entries to use namespaced step types."""
        if "." not in value:
            raise ValueError("step catalog type must be namespaced")

        return value


class WorkflowTemplate(BaseModel):
    """Reusable workflow seed presented by the builder."""

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str
    definition: WorkflowDefinitionDocument
    tags: List[str] = Field(default_factory=list)
    required_placeholders: List[str] = Field(default_factory=list)
    builder_category: Optional[str] = None
    available_for_authoring: bool = True
    unavailable_reason: Optional[str] = None


class WorkflowDefinitionCreate(BaseModel):
    """Request body for creating a workflow draft."""

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    definition: WorkflowDefinitionDocument
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinitionUpdate(BaseModel):
    """Request body for updating a workflow draft."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    definition: Optional[WorkflowDefinitionDocument] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class WorkflowLifecycleAction(BaseModel):
    """Optional metadata attached to workflow lifecycle actions."""

    reason: Optional[str] = Field(default=None, max_length=1000)


class WorkflowVersionSummary(BaseModel):
    """Published workflow version summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    status: WorkflowVersionStatus
    created_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


class WorkflowTriggerSummary(BaseModel):
    """Persisted trigger summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    trigger_type: WorkflowTriggerType
    enabled: bool
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    misfire_policy: Optional[str] = None
    next_run_at: Optional[datetime] = None


class WorkflowSchedulePreviewRequest(BaseModel):
    """Request body for cron/timezone schedule preview."""

    cron: str = Field(min_length=1, max_length=120)
    timezone: str = Field(min_length=1, max_length=80)
    count: int = Field(default=5, ge=1, le=20)
    start_at: Optional[datetime] = None

    @field_validator("cron", "timezone")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """Normalize required string fields."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class WorkflowSchedulePreviewItem(BaseModel):
    """One schedule preview fire time."""

    run_at: datetime
    local_time: str
    timezone: str


class WorkflowSchedulePreviewResponse(BaseModel):
    """Schedule preview response."""

    cron: str
    timezone: str
    next_runs: List[WorkflowSchedulePreviewItem]


class WorkflowScheduledRunSummary(BaseModel):
    """Run created or skipped by a scheduler tick."""

    workflow_id: str
    trigger_id: str
    scheduled_fire_at: datetime
    run_id: Optional[str] = None
    status: str
    reason: Optional[str] = None


class WorkflowSchedulerTickResponse(BaseModel):
    """Scheduler tick summary."""

    created_runs: int = 0
    skipped_triggers: int = 0
    duplicate_runs: int = 0
    executed_runs: int = 0
    failed_runs: int = 0
    next_tick_at: Optional[datetime] = None
    runs: List[WorkflowScheduledRunSummary] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class WorkflowSchedulerStatusResponse(BaseModel):
    """In-process scheduler status."""

    running: bool
    tick_seconds: int
    last_tick_at: Optional[datetime] = None
    last_result: Optional[WorkflowSchedulerTickResponse] = None


class WorkflowDefinitionListItem(BaseModel):
    """Workflow item returned from list endpoints."""

    id: str
    name: str
    description: Optional[str] = None
    status: WorkflowDefinitionStatus
    owner_user_id: Optional[int] = None
    current_version_id: Optional[str] = None
    latest_version_number: int
    is_active: bool
    trigger_type: WorkflowTriggerType
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None


class WorkflowDefinitionDetail(WorkflowDefinitionListItem):
    """Workflow detail returned from lifecycle APIs."""

    draft_definition: WorkflowDefinitionDocument
    metadata: Dict[str, Any] = Field(default_factory=dict)
    versions: List[WorkflowVersionSummary] = Field(default_factory=list)
    triggers: List[WorkflowTriggerSummary] = Field(default_factory=list)


class WorkflowValidationErrorItem(BaseModel):
    """Actionable workflow validation error returned to the builder."""

    path: str
    message: str
    severity: str = "error"
    code: Optional[str] = None
    step_key: Optional[str] = None
    step_index: Optional[int] = None


class WorkflowValidationResponse(BaseModel):
    """Definition validation response."""

    valid: bool
    definition: Optional[WorkflowDefinitionDocument] = None
    errors: List[WorkflowValidationErrorItem] = Field(default_factory=list)


class WorkflowManualRunRequest(BaseModel):
    """Request body for creating a manual workflow run."""

    input_data: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=160)
    execute_now: bool = False


class WorkflowRunAction(BaseModel):
    """Optional metadata for run actions such as cancel or retry."""

    reason: Optional[str] = Field(default=None, max_length=1000)


class WorkflowRedactedPayload(BaseModel):
    """Input/output payload wrapper that records redaction state."""

    redacted: bool
    policy: WorkflowRedactionPolicy
    value: Optional[Any] = None


class WorkflowEventSummary(BaseModel):
    """Workflow run event shown in timelines."""

    id: str
    event_type: str
    severity: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None


class WorkflowArtifactSummary(BaseModel):
    """Workflow artifact metadata shown in run detail."""

    id: str
    step_run_id: Optional[str] = None
    artifact_type: str
    name: str
    data: Optional[WorkflowRedactedPayload] = None
    storage_uri: Optional[str] = None
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT
    created_at: Optional[datetime] = None


class WorkflowStepRunDetail(BaseModel):
    """Persisted workflow step run detail."""

    id: str
    step_key: str
    step_type: str
    status: WorkflowStepRunStatus
    attempt: int
    input_data: WorkflowRedactedPayload
    output_data: WorkflowRedactedPayload
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    artifacts: List[WorkflowArtifactSummary] = Field(default_factory=list)


class WorkflowRunSummary(BaseModel):
    """Workflow run summary returned from list/create endpoints."""

    id: str
    workflow_id: str
    workflow_name: Optional[str] = None
    version_id: str
    version_number: Optional[int] = None
    status: WorkflowRunStatus
    trigger_type: WorkflowTriggerType
    requested_by_user_id: Optional[int] = None
    retry_of_run_id: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    budget_limit_cents: Optional[int] = None
    estimated_cost_cents: int = 0
    actual_cost_cents: int = 0


class WorkflowOperationsTotals(BaseModel):
    """Aggregate counts for the workflow operations console."""

    total: int = 0
    active: int = 0
    disabled: int = 0
    running: int = 0
    failed: int = 0
    missed: int = 0


class WorkflowOperationsRow(BaseModel):
    """One workflow row for the operations console."""

    id: str
    name: str
    description: Optional[str] = None
    status: WorkflowDefinitionStatus
    health: WorkflowHealthState
    owner_user_id: Optional[int] = None
    owner_label: Optional[str] = None
    latest_version_number: int = 0
    is_active: bool
    tags: List[str] = Field(default_factory=list)
    trigger_type: WorkflowTriggerType
    trigger_enabled: bool = False
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_fire_at: Optional[datetime] = None
    latest_run: Optional[WorkflowRunSummary] = None
    active_run: Optional[WorkflowRunSummary] = None
    latest_failed_run: Optional[WorkflowRunSummary] = None
    last_successful_run: Optional[WorkflowRunSummary] = None
    run_count: int = 0
    failure_count: int = 0
    budget_limit_cents: Optional[int] = None
    estimated_cost_cents: int = 0
    actual_cost_cents: int = 0
    updated_at: Optional[datetime] = None


class WorkflowOperationsResponse(BaseModel):
    """Workflow operations console payload."""

    workflows: List[WorkflowOperationsRow] = Field(default_factory=list)
    totals: WorkflowOperationsTotals = Field(default_factory=WorkflowOperationsTotals)


class WorkflowScheduleBoardRun(BaseModel):
    """One upcoming scheduled fire time shown on the schedule board."""

    workflow_id: str
    workflow_name: str
    trigger_id: str
    run_at: datetime
    local_time: str
    timezone: str
    health: WorkflowHealthState
    workflow_status: WorkflowDefinitionStatus
    trigger_enabled: bool


class WorkflowScheduleBoardGroup(BaseModel):
    """Grouped upcoming scheduled runs."""

    key: str
    label: str
    runs: List[WorkflowScheduleBoardRun] = Field(default_factory=list)


class WorkflowScheduleBoardItem(BaseModel):
    """One schedule row for the workflow schedule board."""

    workflow_id: str
    workflow_name: str
    description: Optional[str] = None
    status: WorkflowDefinitionStatus
    health: WorkflowHealthState
    owner_label: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    trigger_id: str
    trigger_enabled: bool
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    misfire_policy: Optional[str] = None
    next_run_at: Optional[datetime] = None
    last_fire_at: Optional[datetime] = None
    latest_run: Optional[WorkflowRunSummary] = None
    active_run: Optional[WorkflowRunSummary] = None
    latest_failed_run: Optional[WorkflowRunSummary] = None
    preview: List[WorkflowSchedulePreviewItem] = Field(default_factory=list)


class WorkflowScheduleBoardResponse(BaseModel):
    """Schedule board payload for the Workflows page."""

    schedules: List[WorkflowScheduleBoardItem] = Field(default_factory=list)
    groups: List[WorkflowScheduleBoardGroup] = Field(default_factory=list)


class WorkflowTemplateSummary(BaseModel):
    """Compact workflow template summary for operations tabs."""

    id: str
    name: str
    description: str
    trigger_type: WorkflowTriggerType
    step_count: int
    tags: List[str] = Field(default_factory=list)
    builder_category: Optional[str] = None
    available_for_authoring: bool = True
    unavailable_reason: Optional[str] = None


class WorkflowRunDetail(WorkflowRunSummary):
    """Workflow run detail returned by runtime APIs."""

    trigger_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    input_data: WorkflowRedactedPayload
    output_data: WorkflowRedactedPayload
    error: Optional[str] = None
    locked_by: Optional[str] = None
    lock_expires_at: Optional[datetime] = None
    cancel_requested_at: Optional[datetime] = None
    cancelled_by_user_id: Optional[int] = None
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT
    steps: List[WorkflowStepRunDetail] = Field(default_factory=list)
    artifacts: List[WorkflowArtifactSummary] = Field(default_factory=list)
    events: List[WorkflowEventSummary] = Field(default_factory=list)
