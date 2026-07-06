"""Release criteria regression tests for workflow automation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.workflow import WorkflowRun, WorkflowTrigger
from app.schemas.workflow import (
    WorkflowConcurrencyPolicy,
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowDefinitionUpdate,
    WorkflowManualRunRequest,
    WorkflowMisfirePolicy,
    WorkflowRedactionPolicy,
    WorkflowRunStatus,
)
from app.services.workflows import (
    WorkflowRunNotFoundError,
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowSchedulerService,
    WorkflowService,
)
from app.services.workflows.steps import WorkflowStepExecutionError


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"release summary: {kwargs['prompt']}",
            "usage": {"total_tokens": 9},
            "actual_cost_cents": 2,
        }


def _actor(
    user_id: int,
    *,
    admin: bool = False,
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "is_superuser": admin,
        "role": "admin" if admin else "user",
        "permissions": ["*"] if admin else permissions or [],
    }


def _agent_definition(
    prompt: str = "Summarize {{ input.topic }}",
    *,
    trigger: dict[str, Any] | None = None,
    budget_limit_cents: int | None = 20,
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT,
    estimated_cost_cents: int = 1,
) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        trigger=trigger or {"type": "manual"},
        runtime={
            "budget_limit_cents": budget_limit_cents,
            "redaction_policy": redaction_policy.value,
            "concurrency_policy": WorkflowConcurrencyPolicy.SKIP_IF_RUNNING.value,
        },
        steps=[
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": prompt,
                    "estimated_cost_cents": estimated_cost_cents,
                },
            }
        ],
    )


async def _published_workflow(
    test_db,
    actor: dict[str, Any],
    definition: WorkflowDefinitionDocument,
    *,
    name: str = "Release workflow",
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(name=name, definition=definition),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


async def _current_trigger(test_db, workflow_id: str) -> WorkflowTrigger:
    result = await test_db.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_wf_test_01_versions_redaction_artifacts_and_permissions(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    lifecycle = WorkflowService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Release snapshot workflow",
            definition=_agent_definition("Version 1 {{ input.topic }}"),
        ),
        actor,
    )
    published_v1 = await lifecycle.publish_definition(test_db, created.id, actor)
    queued = await runtime.create_manual_run(
        test_db,
        created.id,
        WorkflowManualRunRequest(
            input_data={
                "topic": "new documents",
                "Authorization": "Bearer secret-token",
            }
        ),
        actor,
    )
    executed = await runtime.execute_run(
        test_db, queued.id, worker_id="release-test", actor=actor
    )
    await lifecycle.update_definition(
        test_db,
        created.id,
        WorkflowDefinitionUpdate(
            definition=_agent_definition("Version 2 {{ input.topic }}")
        ),
        actor,
    )
    published_v2 = await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()

    old_run = await runtime.get_run_detail(test_db, executed.id, actor)
    other_user = User(
        email="wf-release-other@example.com",
        username="wf-release-other",
        hashed_password="test",
        is_active=True,
    )
    test_db.add(other_user)
    await test_db.flush()

    serialized_input = json.dumps(old_run.input_data.model_dump(mode="json"))
    artifact_names = {artifact.name for artifact in old_run.artifacts}

    assert published_v1.latest_version_number == 1
    assert published_v2.latest_version_number == 2
    assert old_run.version_number == 1
    assert old_run.status == WorkflowRunStatus.SUCCEEDED
    assert old_run.input_data.redacted is True
    assert "secret-token" not in serialized_input
    assert "[redacted]" in serialized_input
    assert "summarize-summary" in artifact_names
    assert old_run.actual_cost_cents == 2
    with pytest.raises(WorkflowRunNotFoundError):
        await runtime.get_run_detail(test_db, old_run.id, _actor(int(other_user.id)))


@pytest.mark.asyncio
async def test_wf_test_01_budget_failure_retry_and_cancel_paths(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    workflow = await _published_workflow(
        test_db,
        actor,
        _agent_definition(
            budget_limit_cents=0,
            estimated_cost_cents=5,
        ),
        name="Budget release workflow",
    )

    queued = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={"topic": "budget"}),
        actor,
    )
    with pytest.raises(WorkflowStepExecutionError, match="budget limit exceeded"):
        await runtime.execute_run(
            test_db, queued.id, worker_id="release-test", actor=actor
        )
    failed = await runtime.get_run_detail(test_db, queued.id, actor)
    retry = await runtime.retry_run(test_db, failed.id, actor, reason="release retry")
    cancellable = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={"topic": "cancel"}),
        actor,
    )
    cancelled = await runtime.request_cancel_run(
        test_db,
        cancellable.id,
        actor,
        reason="release cancel",
    )
    await test_db.commit()

    original_after_retry = await runtime.get_run_detail(test_db, failed.id, actor)

    assert failed.status == WorkflowRunStatus.FAILED
    assert failed.error == "workflow budget limit exceeded"
    assert retry.status == WorkflowRunStatus.QUEUED
    assert retry.retry_of_run_id == failed.id
    assert original_after_retry.status == WorkflowRunStatus.FAILED
    assert cancelled.status == WorkflowRunStatus.CANCELLED
    assert cancelled.completed_at is not None


@pytest.mark.asyncio
async def test_wf_test_01_scheduler_idempotency_under_repeated_due_ticks(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    lifecycle = WorkflowService()
    workflow = await _published_workflow(
        test_db,
        actor,
        _agent_definition(
            trigger={
                "type": "schedule",
                "cron": "0 2 * * *",
                "timezone": "UTC",
                "misfire_policy": WorkflowMisfirePolicy.RUN_ONCE.value,
            }
        ),
        name="Idempotent release schedule",
    )
    await lifecycle.enable_definition(test_db, workflow.id, actor)
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    trigger.next_run_at = due_at
    await test_db.commit()

    scheduler = WorkflowSchedulerService()
    first = await scheduler.create_due_runs(test_db, now=due_at + timedelta(minutes=1))
    trigger.next_run_at = due_at
    second = await scheduler.create_due_runs(test_db, now=due_at + timedelta(minutes=1))
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
    )
    runs = result.scalars().all()

    assert first.created_runs == 1
    assert second.duplicate_runs == 1
    assert len(runs) == 1
    assert runs[0].trigger_type == "schedule"
    assert runs[0].idempotency_key is not None
