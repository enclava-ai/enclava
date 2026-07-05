"""Tests for workflow maintenance services."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.models.workflow import (
    WorkflowArtifact,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowRetentionPolicy,
    WorkflowStaleLockRecoveryRequest,
)
from app.services.workflows import (
    WorkflowMaintenanceService,
    WorkflowRuntimeService,
    WorkflowService,
)


def _actor(user_id: int) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": [],
    }


def _definition() -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        trigger={"type": "manual"},
        steps=[
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize maintenance",
                },
            }
        ],
    )


async def _published_workflow(test_db, actor: dict[str, Any]):
    service = WorkflowService()
    created = await service.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Maintenance workflow",
            definition=_definition(),
        ),
        actor,
    )
    await service.publish_definition(test_db, created.id, actor)
    enabled = await service.enable_definition(test_db, created.id, actor)
    await test_db.commit()
    return enabled


async def _current_version(test_db, workflow_id: str) -> WorkflowVersion:
    result = await test_db.execute(
        select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_recover_stale_locks_fails_only_expired_running_runs(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _published_workflow(test_db, actor)
    runtime = WorkflowRuntimeService()
    service = WorkflowMaintenanceService()

    stale_detail = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor,
    )
    await runtime.claim_next_run(test_db, worker_id="stale-worker")
    fresh_detail = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor,
    )
    await runtime.claim_next_run(test_db, worker_id="fresh-worker")
    result = await test_db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id.in_([stale_detail.id, fresh_detail.id])
        )
    )
    runs = {run.id: run for run in result.scalars().all()}
    stale = runs[stale_detail.id]
    fresh = runs[fresh_detail.id]
    stale.started_at = datetime(2026, 1, 1, 1, 0)
    stale.lock_expires_at = datetime(2026, 1, 1, 1, 30)
    fresh.lock_expires_at = datetime(2026, 1, 1, 3, 0)
    step_run = WorkflowStepRun(
        run_id=stale.id,
        step_key="summarize",
        step_type="agent.run",
        status="succeeded",
        attempt=1,
        output_data={"kept": True},
        created_at=datetime(2026, 1, 1, 1, 10),
        updated_at=datetime(2026, 1, 1, 1, 10),
    )
    test_db.add(step_run)
    await test_db.commit()

    recovery = await service.recover_stale_locks(
        test_db,
        WorkflowStaleLockRecoveryRequest(
            now=datetime(2026, 1, 1, 2, 0),
            reason="test stale lock",
        ),
        actor,
    )
    await test_db.commit()

    refreshed = await test_db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id.in_([stale_detail.id, fresh_detail.id])
        )
    )
    refreshed_runs = {run.id: run for run in refreshed.scalars().all()}
    event_result = await test_db.execute(
        select(WorkflowEvent).where(
            WorkflowEvent.run_id == stale_detail.id,
            WorkflowEvent.event_type == "run_stale_lock_recovered",
        )
    )
    step_result = await test_db.execute(
        select(WorkflowStepRun).where(WorkflowStepRun.id == step_run.id)
    )

    assert recovery.recovered_count == 1
    assert recovery.runs[0].run_id == stale_detail.id
    assert refreshed_runs[stale_detail.id].status == "failed"
    assert refreshed_runs[stale_detail.id].locked_by is None
    assert refreshed_runs[stale_detail.id].lock_expires_at is None
    assert refreshed_runs[fresh_detail.id].status == "running"
    assert refreshed_runs[fresh_detail.id].lock_expires_at == datetime(2026, 1, 1, 3, 0)
    assert event_result.scalar_one().data["previous_locked_by"] == "stale-worker"
    assert step_result.scalar_one().output_data == {"kept": True}


@pytest.mark.asyncio
async def test_retention_dry_run_and_apply_prunes_only_verbose_data(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _published_workflow(test_db, actor)
    version = await _current_version(test_db, workflow.id)
    run = WorkflowRun(
        workflow_id=workflow.id,
        version_id=version.id,
        trigger_type="manual",
        status="succeeded",
        queued_at=datetime(2026, 1, 1, 1, 0),
        started_at=datetime(2026, 1, 1, 1, 0),
        completed_at=datetime(2026, 1, 1, 1, 1),
        created_at=datetime(2026, 1, 1, 1, 0),
        updated_at=datetime(2026, 1, 1, 1, 1),
    )
    test_db.add(run)
    await test_db.flush()
    step_run = WorkflowStepRun(
        run_id=run.id,
        step_key="summarize",
        step_type="agent.run",
        status="succeeded",
        attempt=1,
        created_at=datetime(2026, 1, 1, 1, 0),
        updated_at=datetime(2026, 1, 1, 1, 1),
    )
    old_event = WorkflowEvent(
        workflow_id=workflow.id,
        version_id=version.id,
        run_id=run.id,
        event_type="old_verbose_event",
        message="Old event",
        data={"old": True},
        created_at=datetime(2026, 1, 1, 1, 0),
    )
    fresh_event = WorkflowEvent(
        workflow_id=workflow.id,
        version_id=version.id,
        run_id=run.id,
        event_type="fresh_verbose_event",
        message="Fresh event",
        data={"fresh": True},
        created_at=datetime(2026, 1, 9, 1, 0),
    )
    old_artifact = WorkflowArtifact(
        run_id=run.id,
        artifact_type="json",
        name="Old artifact",
        data={"secret": "payload"},
        storage_uri="s3://bucket/object",
        created_at=datetime(2026, 1, 1, 1, 0),
    )
    fresh_artifact = WorkflowArtifact(
        run_id=run.id,
        artifact_type="json",
        name="Fresh artifact",
        data={"keep": True},
        created_at=datetime(2026, 1, 9, 1, 0),
    )
    test_db.add_all([step_run, old_event, fresh_event, old_artifact, fresh_artifact])
    await test_db.commit()
    service = WorkflowMaintenanceService()
    policy = WorkflowRetentionPolicy(
        event_retention_days=2,
        artifact_retention_days=2,
        dry_run=True,
        now=datetime(2026, 1, 10, 1, 0),
    )

    dry_run = await service.apply_retention_policy(test_db, policy, actor)
    old_artifact_after_dry_run = await test_db.get(WorkflowArtifact, old_artifact.id)
    dry_run_artifact_data = old_artifact_after_dry_run.data
    apply_result = await service.apply_retention_policy(
        test_db,
        policy.model_copy(update={"dry_run": False}),
        actor,
    )
    await test_db.commit()

    old_event_after_apply = await test_db.get(WorkflowEvent, old_event.id)
    fresh_event_after_apply = await test_db.get(WorkflowEvent, fresh_event.id)
    old_artifact_after_apply = await test_db.get(WorkflowArtifact, old_artifact.id)
    fresh_artifact_after_apply = await test_db.get(WorkflowArtifact, fresh_artifact.id)
    durable_run = await test_db.get(WorkflowRun, run.id)
    durable_step = await test_db.get(WorkflowStepRun, step_run.id)
    durable_version = await test_db.get(WorkflowVersion, version.id)

    assert dry_run.dry_run is True
    assert dry_run.events_pruned == 1
    assert dry_run.artifact_payloads_pruned == 1
    assert dry_run_artifact_data == {"secret": "payload"}
    assert apply_result.events_pruned == 1
    assert apply_result.artifact_payloads_pruned == 1
    assert old_event_after_apply is None
    assert fresh_event_after_apply is not None
    assert old_artifact_after_apply is not None
    assert old_artifact_after_apply.data is None
    assert old_artifact_after_apply.storage_uri is None
    assert fresh_artifact_after_apply.data == {"keep": True}
    assert durable_run is not None
    assert durable_step is not None
    assert durable_version is not None
