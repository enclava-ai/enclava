"""Tests for workflow runtime core service."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.workflow import WorkflowRun
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowDefinitionUpdate,
    WorkflowManualRunRequest,
    WorkflowRedactionPolicy,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from app.services.workflows import WorkflowRuntimeService, WorkflowService


def _actor(user_id: int, *, admin: bool = False) -> dict:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "is_superuser": admin,
        "role": "admin" if admin else "user",
        "permissions": ["*"] if admin else [],
    }


def _definition(
    query: str = "Summarize new docs",
    *,
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT,
    budget_limit_cents: int | None = None,
) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        runtime={
            "redaction_policy": redaction_policy.value,
            "budget_limit_cents": budget_limit_cents,
        },
        steps=[
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query collection",
                "config": {"collection_id": "collection-1", "query": query},
            }
        ],
    )


async def _published_workflow(test_db, actor: dict, **definition_kwargs):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Manual runtime workflow",
            definition=_definition(**definition_kwargs),
        ),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


@pytest.mark.asyncio
async def test_manual_run_uses_published_version_snapshot(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    lifecycle = WorkflowService()
    runtime = WorkflowRuntimeService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Snapshot workflow", definition=_definition("v1")
        ),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await lifecycle.update_definition(
        test_db,
        created.id,
        WorkflowDefinitionUpdate(definition=_definition("v2")),
        actor,
    )
    await test_db.commit()

    detail = await runtime.create_manual_run(
        test_db,
        created.id,
        WorkflowManualRunRequest(input_data={"api_key": "secret"}),
        actor,
    )
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowRun)
        .options(selectinload(WorkflowRun.version))
        .where(WorkflowRun.id == detail.id)
    )
    run = result.scalar_one()

    assert detail.status == WorkflowRunStatus.QUEUED
    assert detail.version_number == 1
    assert run.version.definition["steps"][0]["config"]["query"] == "v1"
    assert detail.input_data.redacted is True
    assert detail.input_data.value["api_key"] == "[redacted]"


@pytest.mark.asyncio
async def test_claim_next_run_is_exclusive(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService()
    created = await _published_workflow(test_db, actor)
    run = await runtime.create_manual_run(
        test_db, created.id, WorkflowManualRunRequest(), actor
    )
    await test_db.commit()

    claimed = await runtime.claim_next_run(test_db, worker_id="worker-1")
    second_claim = await runtime.claim_next_run(test_db, worker_id="worker-2")
    await test_db.commit()

    assert claimed is not None
    assert claimed.id == run.id
    assert claimed.status == WorkflowRunStatus.RUNNING
    assert claimed.locked_by == "worker-1"
    assert claimed.lock_expires_at is not None
    assert second_claim is None


@pytest.mark.asyncio
async def test_runtime_events_artifacts_and_completion_persist(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService()
    created = await _published_workflow(test_db, actor)
    queued = await runtime.create_manual_run(
        test_db, created.id, WorkflowManualRunRequest(), actor
    )
    await test_db.commit()
    await runtime.claim_next_run(test_db, worker_id="worker-1")
    result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.id == queued.id)
    )
    run = result.scalar_one()
    step = await runtime.create_step_run(
        test_db,
        run,
        step_key="query",
        step_type="rag.query",
        input_data={"query": "docs"},
        status=WorkflowStepRunStatus.RUNNING,
    )
    await runtime.create_artifact(
        test_db,
        run,
        step_run=step,
        artifact_type="json",
        name="query-results",
        data={"documents": [{"title": "Doc"}]},
    )
    completed = await runtime.complete_run(
        test_db, run, output_data={"summary": "Done"}
    )
    await test_db.commit()

    reloaded = await runtime.get_run_detail(test_db, completed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert reloaded.duration_ms is not None
    assert reloaded.output_data.value == {"summary": "Done"}
    assert [step.step_key for step in reloaded.steps] == ["query"]
    assert reloaded.steps[0].artifacts[0].name == "query-results"
    assert {event.event_type for event in reloaded.events}.issuperset(
        {
            "run_queued",
            "run_claimed",
            "step_created",
            "artifact_created",
            "run_succeeded",
        }
    )


@pytest.mark.asyncio
async def test_cancel_marks_queued_and_running_runs(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService()
    created = await _published_workflow(test_db, actor)
    queued = await runtime.create_manual_run(
        test_db, created.id, WorkflowManualRunRequest(), actor
    )
    cancelled = await runtime.request_cancel_run(
        test_db, queued.id, actor, reason="operator request"
    )
    running_seed = await runtime.create_manual_run(
        test_db, created.id, WorkflowManualRunRequest(), actor
    )
    await test_db.commit()
    running = await runtime.claim_next_run(test_db, worker_id="worker-1")
    requested = await runtime.request_cancel_run(
        test_db, running_seed.id, actor, reason="stop after current step"
    )
    await test_db.commit()

    assert cancelled.status == WorkflowRunStatus.CANCELLED
    assert cancelled.completed_at is not None
    assert running is not None
    assert requested.status == WorkflowRunStatus.RUNNING
    assert requested.cancel_requested_at is not None
    assert requested.cancelled_by_user_id == int(test_user["id"])


def test_runtime_redaction_policies() -> None:
    runtime = WorkflowRuntimeService()
    default = runtime.redact_payload(
        {"safe": "ok", "nested": {"token": "secret", "count": 1}},
        WorkflowRedactionPolicy.DEFAULT,
    )
    strict = runtime.redact_payload({"safe": "hidden"}, WorkflowRedactionPolicy.STRICT)
    none = runtime.redact_payload({"api_key": "visible"}, WorkflowRedactionPolicy.NONE)

    assert default.redacted is True
    assert default.value == {
        "safe": "ok",
        "nested": {"token": "[redacted]", "count": 1},
    }
    assert strict.redacted is True
    assert strict.value is None
    assert none.redacted is False
    assert none.value == {"api_key": "visible"}
