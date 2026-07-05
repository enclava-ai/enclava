"""Tests for workflow scheduler service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import select

from app.models.workflow import WorkflowRun, WorkflowTrigger
from app.schemas.workflow import (
    WorkflowConcurrencyPolicy,
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowMisfirePolicy,
    WorkflowRunStatus,
    WorkflowSchedulePreviewRequest,
)
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowSchedulerService,
    WorkflowService,
)


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"scheduled {kwargs['prompt']}",
            "usage": {"total_tokens": 5},
            "actual_cost_cents": 1,
        }


def _actor(user_id: int) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": [],
    }


def _scheduled_definition(
    *,
    cron: str = "0 2 * * *",
    timezone_name: str = "UTC",
    misfire_policy: WorkflowMisfirePolicy = WorkflowMisfirePolicy.RUN_ONCE,
    concurrency_policy: WorkflowConcurrencyPolicy = (
        WorkflowConcurrencyPolicy.SKIP_IF_RUNNING
    ),
) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        trigger={
            "type": "schedule",
            "cron": cron,
            "timezone": timezone_name,
            "misfire_policy": misfire_policy.value,
        },
        runtime={"concurrency_policy": concurrency_policy.value},
        steps=[
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize schedule",
                },
            }
        ],
    )


async def _active_scheduled_workflow(
    test_db,
    actor: dict[str, Any],
    definition: WorkflowDefinitionDocument | None = None,
):
    service = WorkflowService()
    created = await service.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Scheduled workflow",
            definition=definition or _scheduled_definition(),
        ),
        actor,
    )
    await service.publish_definition(test_db, created.id, actor)
    enabled = await service.enable_definition(test_db, created.id, actor)
    await test_db.commit()
    return enabled


async def _current_trigger(test_db, workflow_id: str) -> WorkflowTrigger:
    result = await test_db.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_schedule_preview_uses_cron_and_timezone() -> None:
    service = WorkflowSchedulerService()
    preview = service.preview_schedule(
        WorkflowSchedulePreviewRequest(
            cron="0 2 * * *",
            timezone="UTC",
            count=5,
            start_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        )
    )

    assert [item.run_at for item in preview.next_runs] == [
        datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 3, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 4, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc),
    ]
    assert all(item.timezone == "UTC" for item in preview.next_runs)


@pytest.mark.asyncio
async def test_publish_and_enable_schedule_sets_next_run(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(test_db, actor)
    trigger = await _current_trigger(test_db, workflow.id)

    assert trigger.enabled is True
    assert trigger.next_run_at is not None
    assert trigger.cron_expression == "0 2 * * *"


@pytest.mark.asyncio
async def test_due_run_creation_is_idempotent(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(test_db, actor)
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    now = due_at + timedelta(minutes=1)
    trigger.next_run_at = due_at
    await test_db.commit()
    scheduler = WorkflowSchedulerService()

    first = await scheduler.create_due_runs(test_db, now=now)
    trigger.next_run_at = due_at
    duplicate = await scheduler.create_due_runs(test_db, now=now)
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
    )
    runs = result.scalars().all()

    assert first.created_runs == 1
    assert duplicate.duplicate_runs == 1
    assert len(runs) == 1
    assert runs[0].trigger_id == trigger.id
    assert runs[0].trigger_type == "schedule"


@pytest.mark.asyncio
async def test_skip_if_running_concurrency_skips_due_run(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(test_db, actor)
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    trigger.next_run_at = due_at
    runtime = WorkflowRuntimeService()
    await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor=actor,
    )
    await test_db.commit()
    scheduler = WorkflowSchedulerService(runtime)

    result = await scheduler.create_due_runs(test_db, now=due_at + timedelta(minutes=1))
    await test_db.commit()

    assert result.created_runs == 0
    assert result.skipped_triggers == 1
    assert result.runs[0].reason == "workflow_already_running"


@pytest.mark.asyncio
async def test_queue_after_current_creates_due_run_with_active_run(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(
        test_db,
        actor,
        _scheduled_definition(
            concurrency_policy=WorkflowConcurrencyPolicy.QUEUE_AFTER_CURRENT
        ),
    )
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    trigger.next_run_at = due_at
    runtime = WorkflowRuntimeService()
    await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor=actor,
    )
    await test_db.commit()
    scheduler = WorkflowSchedulerService(runtime)

    result = await scheduler.create_due_runs(test_db, now=due_at + timedelta(minutes=1))
    await test_db.commit()

    run_result = await test_db.execute(
        select(WorkflowRun).where(
            WorkflowRun.workflow_id == workflow.id,
            WorkflowRun.trigger_type == "schedule",
        )
    )
    scheduled_run = run_result.scalar_one()

    assert result.created_runs == 1
    assert scheduled_run.status == WorkflowRunStatus.QUEUED.value


@pytest.mark.asyncio
async def test_skip_misfire_policy_advances_without_run(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(
        test_db,
        actor,
        _scheduled_definition(misfire_policy=WorkflowMisfirePolicy.SKIP),
    )
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    now = due_at + timedelta(hours=2)
    trigger.next_run_at = due_at
    await test_db.commit()
    scheduler = WorkflowSchedulerService()

    result = await scheduler.create_due_runs(test_db, now=now)
    await test_db.commit()

    assert result.created_runs == 0
    assert trigger.next_run_at is not None
    assert trigger.next_run_at > now


@pytest.mark.asyncio
async def test_catch_up_misfire_policy_creates_missed_runs(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(
        test_db,
        actor,
        _scheduled_definition(
            misfire_policy=WorkflowMisfirePolicy.CATCH_UP,
            concurrency_policy=WorkflowConcurrencyPolicy.ALLOW_PARALLEL,
        ),
    )
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    now = datetime(2026, 1, 4, 2, 1)
    trigger.next_run_at = due_at
    await test_db.commit()
    scheduler = WorkflowSchedulerService()

    result = await scheduler.create_due_runs(test_db, now=now)
    await test_db.commit()

    run_result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
    )
    runs = run_result.scalars().all()

    assert result.created_runs == 4
    assert len(runs) == 4
    assert trigger.next_run_at is not None
    assert trigger.next_run_at > now


@pytest.mark.asyncio
async def test_scheduler_tick_executes_created_runs(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(
        test_db,
        actor,
        _scheduled_definition(
            concurrency_policy=WorkflowConcurrencyPolicy.ALLOW_PARALLEL
        ),
    )
    trigger = await _current_trigger(test_db, workflow.id)
    due_at = datetime(2026, 1, 1, 2, 0)
    trigger.next_run_at = due_at
    await test_db.commit()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    scheduler = WorkflowSchedulerService(runtime)

    result = await scheduler.run_tick(
        test_db,
        now=due_at + timedelta(minutes=1),
        execute_limit=5,
    )
    await test_db.commit()

    run_result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
    )
    run = run_result.scalar_one()

    assert result.created_runs == 1
    assert result.executed_runs == 1
    assert run.status == WorkflowRunStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_scheduler_tick_recovers_stale_locks_before_execution(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _active_scheduled_workflow(test_db, actor)
    runtime = WorkflowRuntimeService()
    queued = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor=actor,
    )
    await runtime.claim_next_run(test_db, worker_id="crashed-worker")
    run_result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.id == queued.id)
    )
    run = run_result.scalar_one()
    run.lock_expires_at = datetime(2026, 1, 1, 1, 30)
    await test_db.commit()
    scheduler = WorkflowSchedulerService(runtime)

    result = await scheduler.run_tick(
        test_db,
        now=datetime(2026, 1, 1, 2, 0),
        create_limit=10,
        execute_limit=0,
    )
    await test_db.commit()

    refreshed = await test_db.get(WorkflowRun, queued.id)

    assert result.stale_locks_recovered == 1
    assert refreshed.status == WorkflowRunStatus.FAILED.value
    assert refreshed.locked_by is None
    assert refreshed.lock_expires_at is None
