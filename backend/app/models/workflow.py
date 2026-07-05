"""Workflow persistence models."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base, utc_now


def _uuid() -> str:
    return str(uuid.uuid4())


class WorkflowEventSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class WorkflowArtifactType(str, Enum):
    SUMMARY = "summary"
    JSON = "json"
    EXTRACTION_RESULT = "extraction_result"
    NOTIFICATION = "notification"
    FILE_REFERENCE = "file_reference"


class WorkflowDefinition(Base):
    """Mutable workflow lifecycle record.

    The table name already exists in the consolidated migration with a smaller
    legacy shape. New columns are additive and old columns remain mapped for
    compatibility with deployed databases.
    """

    __tablename__ = "workflow_definitions"

    id = Column(String, primary_key=True, default=_uuid)

    # Legacy columns retained from migration 000.
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=True, default="1.0.0")
    steps = Column(JSON, nullable=False, default=list)
    variables = Column(JSON, nullable=True, default=dict)
    legacy_metadata = Column("metadata", JSON, nullable=True, default=dict)
    timeout = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=True, default=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # v1.1 lifecycle columns.
    status = Column(String(32), nullable=False, default="draft", index=True)
    owner_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    draft_definition = Column(JSON, nullable=False, default=dict)
    current_version_id = Column(String, nullable=True, index=True)
    latest_version_number = Column(Integer, nullable=False, default=0)
    tags = Column(JSON, nullable=False, default=list)
    last_published_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

    owner = relationship("User", foreign_keys=[owner_user_id])
    versions = relationship(
        "WorkflowVersion",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowVersion.version_number",
    )
    triggers = relationship(
        "WorkflowTrigger",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    runs = relationship("WorkflowRun", back_populates="workflow")
    events = relationship("WorkflowEvent", back_populates="workflow")
    approvals = relationship("WorkflowApproval", back_populates="workflow")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "owner_user_id": self.owner_user_id,
            "current_version_id": self.current_version_id,
            "latest_version_number": self.latest_version_number,
            "is_active": bool(self.is_active),
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_published_at": (
                self.last_published_at.isoformat() if self.last_published_at else None
            ),
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


class LegacyWorkflowExecution(Base):
    """Legacy execution table retained for metadata/drop ordering."""

    __tablename__ = "workflow_executions"

    id = Column(String, primary_key=True)
    workflow_id = Column(
        String, ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    status = Column(String, nullable=True)
    current_step = Column(String, nullable=True)
    input_data = Column(JSON, nullable=True)
    context = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    executed_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class LegacyWorkflowStepLog(Base):
    """Legacy step log table retained for metadata/drop ordering."""

    __tablename__ = "workflow_step_logs"

    id = Column(String, primary_key=True)
    execution_id = Column(
        String, ForeignKey("workflow_executions.id"), nullable=False, index=True
    )
    step_id = Column(String, nullable=False)
    step_name = Column(String(255), nullable=False)
    step_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, nullable=True)


class WorkflowVersion(Base):
    """Immutable published workflow definition snapshot."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "version_number", name="uq_workflow_version_number"
        ),
        Index("ix_workflow_versions_workflow_status", "workflow_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    workflow_id = Column(
        String,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="published", index=True)
    definition = Column(JSON, nullable=False)
    definition_checksum = Column(String(64), nullable=False)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=utc_now)
    published_at = Column(DateTime, default=utc_now)

    workflow = relationship("WorkflowDefinition", back_populates="versions")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    published_by = relationship("User", foreign_keys=[published_by_user_id])
    triggers = relationship("WorkflowTrigger", back_populates="version")
    runs = relationship("WorkflowRun", back_populates="version")
    events = relationship("WorkflowEvent", back_populates="version")


class WorkflowTrigger(Base):
    """Persisted trigger metadata for a workflow version."""

    __tablename__ = "workflow_triggers"
    __table_args__ = (
        Index("ix_workflow_triggers_due", "enabled", "next_run_at"),
        Index("ix_workflow_triggers_workflow_type", "workflow_id", "trigger_type"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    workflow_id = Column(
        String,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        String,
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    trigger_type = Column(String(32), nullable=False, index=True)
    config = Column(JSON, nullable=False, default=dict)
    cron_expression = Column(String(120), nullable=True)
    timezone = Column(String(80), nullable=True)
    misfire_policy = Column(String(32), nullable=True)
    enabled = Column(Boolean, nullable=False, default=False, index=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    last_fire_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    workflow = relationship("WorkflowDefinition", back_populates="triggers")
    version = relationship("WorkflowVersion", back_populates="triggers")
    runs = relationship("WorkflowRun", back_populates="trigger")


class WorkflowRun(Base):
    """Durable workflow run shell used by later execution phases."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_workflow_status", "workflow_id", "status"),
        Index("ix_workflow_runs_version_created", "version_id", "created_at"),
        Index("ix_workflow_runs_status_lock", "status", "lock_expires_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    workflow_id = Column(
        String,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        String,
        ForeignKey("workflow_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trigger_id = Column(
        String,
        ForeignKey("workflow_triggers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(String(32), nullable=False, default="queued", index=True)
    trigger_type = Column(String(32), nullable=False)
    idempotency_key = Column(String(160), nullable=True, unique=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    requested_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    retry_of_run_id = Column(
        String,
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    locked_by = Column(String(120), nullable=True)
    lock_expires_at = Column(DateTime, nullable=True)
    cancel_requested_at = Column(DateTime, nullable=True)
    cancelled_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    redaction_policy = Column(String(32), nullable=False, default="default")
    budget_limit_cents = Column(Integer, nullable=True)
    estimated_cost_cents = Column(Integer, nullable=False, default=0)
    actual_cost_cents = Column(Integer, nullable=False, default=0)
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    workflow = relationship("WorkflowDefinition", back_populates="runs")
    version = relationship("WorkflowVersion", back_populates="runs")
    trigger = relationship("WorkflowTrigger", back_populates="runs")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    retry_of = relationship(
        "WorkflowRun", remote_side=[id], foreign_keys=[retry_of_run_id]
    )
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_user_id])
    step_runs = relationship(
        "WorkflowStepRun", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts = relationship(
        "WorkflowArtifact", back_populates="run", cascade="all, delete-orphan"
    )
    events = relationship(
        "WorkflowEvent", back_populates="run", cascade="all, delete-orphan"
    )
    approvals = relationship(
        "WorkflowApproval", back_populates="run", cascade="all, delete-orphan"
    )


class WorkflowStepRun(Base):
    """Durable state for one workflow step attempt."""

    __tablename__ = "workflow_step_runs"
    __table_args__ = (
        UniqueConstraint("run_id", "step_key", "attempt", name="uq_step_run_attempt"),
        Index("ix_workflow_step_runs_run_status", "run_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(
        String,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key = Column(String(80), nullable=False)
    step_type = Column(String(120), nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    attempt = Column(Integer, nullable=False, default=1)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    run = relationship("WorkflowRun", back_populates="step_runs")
    artifacts = relationship("WorkflowArtifact", back_populates="step_run")
    events = relationship("WorkflowEvent", back_populates="step_run")
    approvals = relationship("WorkflowApproval", back_populates="step_run")


class WorkflowApproval(Base):
    """Human approval request attached to a paused workflow run."""

    __tablename__ = "workflow_approvals"
    __table_args__ = (
        Index("ix_workflow_approvals_run_status", "run_id", "status"),
        Index("ix_workflow_approvals_workflow_status", "workflow_id", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    workflow_id = Column(
        String,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        String,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_run_id = Column(
        String,
        ForeignKey("workflow_step_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    step_key = Column(String(80), nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    approver_user_ids = Column(JSON, nullable=False, default=list)
    requested_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolution_comment = Column(Text, nullable=True)
    approval_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    resolved_at = Column(DateTime, nullable=True)

    workflow = relationship("WorkflowDefinition", back_populates="approvals")
    run = relationship("WorkflowRun", back_populates="approvals")
    step_run = relationship("WorkflowStepRun", back_populates="approvals")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])


class WorkflowArtifact(Base):
    """Workflow output artifact metadata."""

    __tablename__ = "workflow_artifacts"
    __table_args__ = (
        Index("ix_workflow_artifacts_run_type", "run_id", "artifact_type"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    run_id = Column(
        String,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_run_id = Column(
        String,
        ForeignKey("workflow_step_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    data = Column(JSON, nullable=True)
    storage_uri = Column(String(1024), nullable=True)
    redaction_policy = Column(String(32), nullable=False, default="default")
    created_at = Column(DateTime, default=utc_now, index=True)

    run = relationship("WorkflowRun", back_populates="artifacts")
    step_run = relationship("WorkflowStepRun", back_populates="artifacts")


class WorkflowEvent(Base):
    """Structured workflow lifecycle/run event."""

    __tablename__ = "workflow_events"
    __table_args__ = (
        Index("ix_workflow_events_workflow_created", "workflow_id", "created_at"),
        Index("ix_workflow_events_run_created", "run_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    workflow_id = Column(
        String,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        String,
        ForeignKey("workflow_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id = Column(
        String,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    step_run_id = Column(
        String,
        ForeignKey("workflow_step_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(80), nullable=False, index=True)
    severity = Column(
        String(20), nullable=False, default=WorkflowEventSeverity.INFO.value
    )
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=False, default=dict)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=utc_now, index=True)

    workflow = relationship("WorkflowDefinition", back_populates="events")
    version = relationship("WorkflowVersion", back_populates="events")
    run = relationship("WorkflowRun", back_populates="events")
    step_run = relationship("WorkflowStepRun", back_populates="events")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
