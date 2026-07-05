"""Add workflow lifecycle tables

Revision ID: 034_add_workflow_lifecycle
Revises: 033_remove_chatbots
Create Date: 2026-07-05
"""

import sqlalchemy as sa

from alembic import op

revision = "034_add_workflow_lifecycle"
down_revision = "033_remove_chatbots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflow_definitions",
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="draft"
        ),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column("draft_definition", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column("current_version_id", sa.String(), nullable=True),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column(
            "latest_version_number", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "workflow_definitions",
        sa.Column("last_published_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "workflow_definitions", sa.Column("archived_at", sa.DateTime(), nullable=True)
    )
    op.create_index(
        "ix_workflow_definitions_status", "workflow_definitions", ["status"]
    )
    op.create_index(
        "ix_workflow_definitions_owner_user_id",
        "workflow_definitions",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_workflow_definitions_current_version_id",
        "workflow_definitions",
        ["current_version_id"],
    )

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="published"
        ),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("definition_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("published_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "version_number", name="uq_workflow_version_number"
        ),
    )
    op.create_index(
        "ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"]
    )
    op.create_index(
        "ix_workflow_versions_created_by_user_id",
        "workflow_versions",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_workflow_versions_published_by_user_id",
        "workflow_versions",
        ["published_by_user_id"],
    )
    op.create_index("ix_workflow_versions_status", "workflow_versions", ["status"])
    op.create_index(
        "ix_workflow_versions_workflow_status",
        "workflow_versions",
        ["workflow_id", "status"],
    )

    op.create_table(
        "workflow_triggers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("cron_expression", sa.String(length=120), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=True),
        sa.Column("misfire_policy", sa.String(length=32), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_fire_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["workflow_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_triggers_workflow_id", "workflow_triggers", ["workflow_id"]
    )
    op.create_index(
        "ix_workflow_triggers_version_id", "workflow_triggers", ["version_id"]
    )
    op.create_index(
        "ix_workflow_triggers_trigger_type", "workflow_triggers", ["trigger_type"]
    )
    op.create_index("ix_workflow_triggers_enabled", "workflow_triggers", ["enabled"])
    op.create_index(
        "ix_workflow_triggers_next_run_at", "workflow_triggers", ["next_run_at"]
    )
    op.create_index(
        "ix_workflow_triggers_due", "workflow_triggers", ["enabled", "next_run_at"]
    )
    op.create_index(
        "ix_workflow_triggers_workflow_type",
        "workflow_triggers",
        ["workflow_id", "trigger_type"],
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("trigger_id", sa.String(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="queued"
        ),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["workflow_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["trigger_id"], ["workflow_triggers.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    op.create_index("ix_workflow_runs_version_id", "workflow_runs", ["version_id"])
    op.create_index("ix_workflow_runs_trigger_id", "workflow_runs", ["trigger_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index(
        "ix_workflow_runs_requested_by_user_id",
        "workflow_runs",
        ["requested_by_user_id"],
    )
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])
    op.create_index(
        "ix_workflow_runs_workflow_status", "workflow_runs", ["workflow_id", "status"]
    )
    op.create_index(
        "ix_workflow_runs_version_created",
        "workflow_runs",
        ["version_id", "created_at"],
    )

    op.create_table(
        "workflow_step_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_key", sa.String(length=80), nullable=False),
        sa.Column("step_type", sa.String(length=120), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_data", sa.JSON(), nullable=True),
        sa.Column("output_data", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "step_key", "attempt", name="uq_step_run_attempt"
        ),
    )
    op.create_index("ix_workflow_step_runs_run_id", "workflow_step_runs", ["run_id"])
    op.create_index("ix_workflow_step_runs_status", "workflow_step_runs", ["status"])
    op.create_index(
        "ix_workflow_step_runs_run_status", "workflow_step_runs", ["run_id", "status"]
    )

    op.create_table(
        "workflow_artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_run_id", sa.String(), nullable=True),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("storage_uri", sa.String(length=1024), nullable=True),
        sa.Column(
            "redaction_policy",
            sa.String(length=32),
            nullable=False,
            server_default="default",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["step_run_id"], ["workflow_step_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_artifacts_run_id", "workflow_artifacts", ["run_id"])
    op.create_index(
        "ix_workflow_artifacts_step_run_id", "workflow_artifacts", ["step_run_id"]
    )
    op.create_index(
        "ix_workflow_artifacts_created_at", "workflow_artifacts", ["created_at"]
    )
    op.create_index(
        "ix_workflow_artifacts_run_type",
        "workflow_artifacts",
        ["run_id", "artifact_type"],
    )

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("step_run_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column(
            "severity", sa.String(length=20), nullable=False, server_default="info"
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflow_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["workflow_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["step_run_id"], ["workflow_step_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_events_workflow_id", "workflow_events", ["workflow_id"]
    )
    op.create_index("ix_workflow_events_version_id", "workflow_events", ["version_id"])
    op.create_index("ix_workflow_events_run_id", "workflow_events", ["run_id"])
    op.create_index(
        "ix_workflow_events_step_run_id", "workflow_events", ["step_run_id"]
    )
    op.create_index("ix_workflow_events_event_type", "workflow_events", ["event_type"])
    op.create_index(
        "ix_workflow_events_created_by_user_id",
        "workflow_events",
        ["created_by_user_id"],
    )
    op.create_index("ix_workflow_events_created_at", "workflow_events", ["created_at"])
    op.create_index(
        "ix_workflow_events_workflow_created",
        "workflow_events",
        ["workflow_id", "created_at"],
    )
    op.create_index(
        "ix_workflow_events_run_created", "workflow_events", ["run_id", "created_at"]
    )


def downgrade():
    op.drop_index("ix_workflow_events_run_created", table_name="workflow_events")
    op.drop_index("ix_workflow_events_workflow_created", table_name="workflow_events")
    op.drop_index("ix_workflow_events_created_at", table_name="workflow_events")
    op.drop_index("ix_workflow_events_created_by_user_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_event_type", table_name="workflow_events")
    op.drop_index("ix_workflow_events_step_run_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_run_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_version_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_workflow_id", table_name="workflow_events")
    op.drop_table("workflow_events")

    op.drop_index("ix_workflow_artifacts_run_type", table_name="workflow_artifacts")
    op.drop_index("ix_workflow_artifacts_created_at", table_name="workflow_artifacts")
    op.drop_index("ix_workflow_artifacts_step_run_id", table_name="workflow_artifacts")
    op.drop_index("ix_workflow_artifacts_run_id", table_name="workflow_artifacts")
    op.drop_table("workflow_artifacts")

    op.drop_index("ix_workflow_step_runs_run_status", table_name="workflow_step_runs")
    op.drop_index("ix_workflow_step_runs_status", table_name="workflow_step_runs")
    op.drop_index("ix_workflow_step_runs_run_id", table_name="workflow_step_runs")
    op.drop_table("workflow_step_runs")

    op.drop_index("ix_workflow_runs_version_created", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_created_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_requested_by_user_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_trigger_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_version_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index("ix_workflow_triggers_workflow_type", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_due", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_next_run_at", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_enabled", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_trigger_type", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_version_id", table_name="workflow_triggers")
    op.drop_index("ix_workflow_triggers_workflow_id", table_name="workflow_triggers")
    op.drop_table("workflow_triggers")

    op.drop_index(
        "ix_workflow_versions_workflow_status", table_name="workflow_versions"
    )
    op.drop_index("ix_workflow_versions_status", table_name="workflow_versions")
    op.drop_index(
        "ix_workflow_versions_published_by_user_id", table_name="workflow_versions"
    )
    op.drop_index(
        "ix_workflow_versions_created_by_user_id", table_name="workflow_versions"
    )
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")

    op.drop_index(
        "ix_workflow_definitions_current_version_id", table_name="workflow_definitions"
    )
    op.drop_index(
        "ix_workflow_definitions_owner_user_id", table_name="workflow_definitions"
    )
    op.drop_index("ix_workflow_definitions_status", table_name="workflow_definitions")
    op.drop_column("workflow_definitions", "archived_at")
    op.drop_column("workflow_definitions", "last_published_at")
    op.drop_column("workflow_definitions", "tags")
    op.drop_column("workflow_definitions", "latest_version_number")
    op.drop_column("workflow_definitions", "current_version_id")
    op.drop_column("workflow_definitions", "draft_definition")
    op.drop_column("workflow_definitions", "owner_user_id")
    op.drop_column("workflow_definitions", "status")
