"""Tests for authenticated workflow API/event trigger firing."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.models.workflow import WorkflowRun
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowTriggerFireRequest,
)
from app.services.workflows import (
    WorkflowPermissionError,
    WorkflowService,
    WorkflowTriggerFireService,
)


def _actor(user_id: int, *, permissions: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": permissions or [],
    }


def _definition(
    *,
    trigger: dict[str, Any],
) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        trigger=trigger,
        runtime={"concurrency_policy": "allow_parallel", "budget_limit_cents": 25},
        steps=[
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize {{ input.payload.topic }}",
                    "estimated_cost_cents": 1,
                },
            }
        ],
    )


async def _published_workflow(
    test_db,
    actor: dict[str, Any],
    *,
    name: str,
    trigger: dict[str, Any],
    enable: bool = True,
):
    service = WorkflowService()
    created = await service.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name=name,
            definition=_definition(trigger=trigger),
        ),
        actor,
    )
    await service.publish_definition(test_db, created.id, actor)
    if enable:
        created = await service.enable_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


async def _runs_for_workflow(test_db, workflow_id: str) -> list[WorkflowRun]:
    result = await test_db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.asc())
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_api_trigger_fire_creates_queued_run_and_is_idempotent(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _published_workflow(
        test_db,
        actor,
        name="API trigger workflow",
        trigger={"type": "api", "api_slug": "nightly-summary"},
    )
    service = WorkflowTriggerFireService()

    first = await service.fire_api_trigger(
        test_db,
        "nightly-summary",
        WorkflowTriggerFireRequest(
            input_data={"topic": "new docs"},
            idempotency_key="deploy-1",
        ),
        actor,
    )
    duplicate = await service.fire_api_trigger(
        test_db,
        "nightly-summary",
        WorkflowTriggerFireRequest(
            input_data={"topic": "new docs"},
            idempotency_key="deploy-1",
        ),
        actor,
    )
    await test_db.commit()
    runs = await _runs_for_workflow(test_db, workflow.id)

    assert first.created_runs == 1
    assert first.runs[0].status == "created"
    assert first.runs[0].idempotency_key == (f"api:{first.runs[0].trigger_id}:deploy-1")
    assert duplicate.duplicate_runs == 1
    assert duplicate.runs[0].run_id == first.runs[0].run_id
    assert len(runs) == 1
    assert runs[0].trigger_type == "api"
    assert runs[0].input_data["trigger"]["api_slug"] == "nightly-summary"
    assert runs[0].input_data["payload"] == {"topic": "new docs"}


@pytest.mark.asyncio
async def test_event_trigger_fire_creates_runs_for_matching_workflows(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    first = await _published_workflow(
        test_db,
        actor,
        name="First event workflow",
        trigger={"type": "event", "event_name": "rag.documents.indexed"},
    )
    second = await _published_workflow(
        test_db,
        actor,
        name="Second event workflow",
        trigger={"type": "event", "event_name": "rag.documents.indexed"},
    )
    service = WorkflowTriggerFireService()

    result = await service.fire_event_trigger(
        test_db,
        "rag.documents.indexed",
        WorkflowTriggerFireRequest(
            input_data={"collection_id": "1"},
            idempotency_key="batch-1",
        ),
        actor,
    )
    await test_db.commit()

    assert result.created_runs == 2
    assert {item.workflow_id for item in result.runs} == {first.id, second.id}
    assert all(item.trigger_type.value == "event" for item in result.runs)


@pytest.mark.asyncio
async def test_disabled_trigger_returns_skipped_metadata(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    workflow = await _published_workflow(
        test_db,
        actor,
        name="Disabled API workflow",
        trigger={"type": "api", "api_slug": "disabled-api"},
        enable=False,
    )
    service = WorkflowTriggerFireService()

    result = await service.fire_api_trigger(
        test_db,
        "disabled-api",
        WorkflowTriggerFireRequest(idempotency_key="once"),
        actor,
    )
    await test_db.commit()
    runs = await _runs_for_workflow(test_db, workflow.id)

    assert result.created_runs == 0
    assert result.skipped_triggers == 1
    assert result.runs[0].reason == "workflow_inactive"
    assert runs == []


@pytest.mark.asyncio
async def test_trigger_fire_requires_owner_admin_manage_or_trigger_permission(
    test_db, test_user
) -> None:
    owner = _actor(int(test_user["id"]))
    await _published_workflow(
        test_db,
        owner,
        name="Private API workflow",
        trigger={"type": "api", "api_slug": "private-api"},
    )
    service = WorkflowTriggerFireService()

    with pytest.raises(WorkflowPermissionError):
        await service.fire_api_trigger(
            test_db,
            "private-api",
            WorkflowTriggerFireRequest(idempotency_key="denied"),
            _actor(999),
        )

    allowed = await service.fire_api_trigger(
        test_db,
        "private-api",
        WorkflowTriggerFireRequest(idempotency_key="allowed"),
        {
            "id": None,
            "email": "automation@example.com",
            "role": "user",
            "permissions": ["workflow.trigger"],
        },
    )

    assert allowed.created_runs == 1
