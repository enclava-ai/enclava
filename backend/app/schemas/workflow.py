"""Workflow domain contracts shared by services and APIs."""

from __future__ import annotations

import re
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
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    config_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    required_permissions: List[str] = Field(default_factory=list)
    supports_retry: bool = True
    supports_test: bool = False
    estimated_cost_kind: Optional[str] = None

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
