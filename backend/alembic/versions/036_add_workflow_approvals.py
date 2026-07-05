"""Add workflow approvals

Revision ID: 036_add_workflow_approvals
Revises: 035_workflow_run_runtime
Create Date: 2026-07-05
"""

import sqlalchemy as sa

from alembic import op

revision = "036_add_workflow_approvals"
down_revision = "035_workflow_run_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workflow_approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_run_id", sa.String(), nullable=True),
        sa.Column("step_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("approver_user_ids", sa.JSON(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_definitions.id"],
            name="fk_workflow_approvals_workflow_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_runs.id"],
            name="fk_workflow_approvals_run_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_step_runs.id"],
            name="fk_workflow_approvals_step_run_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_workflow_approvals_requested_by_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name="fk_workflow_approvals_resolved_by_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_approvals_run_status",
        "workflow_approvals",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_workflow_approvals_workflow_status",
        "workflow_approvals",
        ["workflow_id", "status"],
    )
    op.create_index(
        "ix_workflow_approvals_resolved_by_user_id",
        "workflow_approvals",
        ["resolved_by_user_id"],
    )
    op.create_index(
        "ix_workflow_approvals_requested_by_user_id",
        "workflow_approvals",
        ["requested_by_user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_workflow_approvals_requested_by_user_id",
        table_name="workflow_approvals",
    )
    op.drop_index(
        "ix_workflow_approvals_resolved_by_user_id",
        table_name="workflow_approvals",
    )
    op.drop_index(
        "ix_workflow_approvals_workflow_status",
        table_name="workflow_approvals",
    )
    op.drop_index(
        "ix_workflow_approvals_run_status",
        table_name="workflow_approvals",
    )
    op.drop_table("workflow_approvals")
