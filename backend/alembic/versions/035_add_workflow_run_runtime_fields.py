"""Add workflow run runtime fields

Revision ID: 035_workflow_run_runtime
Revises: 034_add_workflow_lifecycle
Create Date: 2026-07-05
"""

import sqlalchemy as sa

from alembic import op

revision = "035_workflow_run_runtime"
down_revision = "034_add_workflow_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflow_runs", sa.Column("retry_of_run_id", sa.String(), nullable=True)
    )
    op.add_column(
        "workflow_runs", sa.Column("locked_by", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "workflow_runs", sa.Column("lock_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "workflow_runs", sa.Column("cancel_requested_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "workflow_runs", sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "redaction_policy",
            sa.String(length=32),
            nullable=False,
            server_default="default",
        ),
    )
    op.add_column(
        "workflow_runs", sa.Column("budget_limit_cents", sa.Integer(), nullable=True)
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "estimated_cost_cents", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "workflow_runs",
        sa.Column(
            "actual_cost_cents", sa.Integer(), nullable=False, server_default="0"
        ),
    )

    op.create_foreign_key(
        "fk_workflow_runs_retry_of_run_id",
        "workflow_runs",
        "workflow_runs",
        ["retry_of_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_workflow_runs_cancelled_by_user_id",
        "workflow_runs",
        "users",
        ["cancelled_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_workflow_runs_retry_of_run_id", "workflow_runs", ["retry_of_run_id"]
    )
    op.create_index(
        "ix_workflow_runs_cancelled_by_user_id",
        "workflow_runs",
        ["cancelled_by_user_id"],
    )
    op.create_index(
        "ix_workflow_runs_status_lock", "workflow_runs", ["status", "lock_expires_at"]
    )


def downgrade():
    op.drop_index("ix_workflow_runs_status_lock", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_cancelled_by_user_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_retry_of_run_id", table_name="workflow_runs")
    op.drop_constraint(
        "fk_workflow_runs_cancelled_by_user_id", "workflow_runs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_workflow_runs_retry_of_run_id", "workflow_runs", type_="foreignkey"
    )
    op.drop_column("workflow_runs", "actual_cost_cents")
    op.drop_column("workflow_runs", "estimated_cost_cents")
    op.drop_column("workflow_runs", "budget_limit_cents")
    op.drop_column("workflow_runs", "redaction_policy")
    op.drop_column("workflow_runs", "cancelled_by_user_id")
    op.drop_column("workflow_runs", "cancel_requested_at")
    op.drop_column("workflow_runs", "lock_expires_at")
    op.drop_column("workflow_runs", "locked_by")
    op.drop_column("workflow_runs", "retry_of_run_id")
