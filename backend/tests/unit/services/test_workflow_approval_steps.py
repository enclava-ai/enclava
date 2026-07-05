"""Tests for workflow approval pause/resume behavior."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from app.services.workflows import (
    WorkflowRunPermissionError,
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowService,
    create_default_step_registry,
)


class FakeRAGService:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls += 1
        return [{"title": "Doc"}]


class FakeAgentService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "message": f"approved summary: {kwargs['prompt']}",
            "usage": {"total_tokens": 4},
            "actual_cost_cents": 1,
        }


def _actor(
    user_id: int, *, permissions: list[str] | None = None, admin: bool = False
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "admin" if admin else "user",
        "is_superuser": admin,
        "permissions": ["*"] if admin else permissions or [],
    }


def _definition(*, allow_requester_approval: bool = True) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        steps=[
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query",
                "config": {"collection_id": "1", "query": "new docs"},
            },
            {
                "key": "approval",
                "type": "approval.request",
                "name": "Approval",
                "config": {
                    "title_template": "Approve {{ query.count }} docs",
                    "body_template": "Run {{ run_id }} is waiting.",
                    "allow_requester_approval": allow_requester_approval,
                    "approved_label": "Continue",
                    "rejected_label": "Stop",
                },
            },
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Decision {{ approval.status }} for {{ query.count }} docs",
                },
            },
        ]
    )


def _branch_then_approval_definition() -> WorkflowDefinitionDocument:
    definition = _definition()
    steps = [step.model_dump(mode="json") for step in definition.steps]
    steps.insert(
        1,
        {
            "key": "branch",
            "type": "condition.branch",
            "name": "Branch",
            "config": {
                "input_step_key": "query",
                "path": "count",
                "operator": "greater_than",
                "value": 0,
                "matched_label": "Has docs",
                "not_matched_label": "No docs",
                "matched_skip_step_keys": ["notify"],
                "not_matched_skip_step_keys": [],
            },
        },
    )
    steps.insert(
        3,
        {
            "key": "notify",
            "type": "notify.in_app",
            "name": "Notify",
            "config": {
                "recipients": ["1"],
                "title_template": "Workflow update",
            },
        },
    )
    return WorkflowDefinitionDocument(steps=steps)


async def _published_workflow(
    test_db, actor: dict[str, Any], definition: WorkflowDefinitionDocument
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(name="Approval workflow", definition=definition),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


async def _queued_run(
    test_db,
    actor: dict[str, Any],
    runtime: WorkflowRuntimeService,
    definition: WorkflowDefinitionDocument,
):
    workflow = await _published_workflow(test_db, actor, definition)
    run = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor,
    )
    await test_db.commit()
    return run


@pytest.mark.asyncio
async def test_approval_catalog_entry_is_enabled() -> None:
    entry = create_default_step_registry().get("approval.request")

    assert entry is not None
    assert entry.enabled is True
    assert entry.supports_retry is False


@pytest.mark.asyncio
async def test_approval_step_pauses_and_approve_resumes_after_step(
    test_db, test_user
) -> None:
    owner = _actor(int(test_user["id"]))
    rag = FakeRAGService()
    agent = FakeAgentService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=rag,
            agent_service=agent,
        )
    )
    queued = await _queued_run(test_db, owner, runtime, _definition())

    paused = await runtime.execute_run(test_db, queued.id, actor=owner)
    await test_db.commit()

    assert paused.status == WorkflowRunStatus.PAUSED
    assert paused.approvals[0].status == "pending"
    assert paused.approvals[0].title == "Approve 1 docs"
    assert [step.step_key for step in paused.steps] == ["query", "approval"]
    assert rag.calls == 1
    assert agent.calls == []

    approved = await runtime.resolve_approval(
        test_db,
        paused.id,
        owner,
        approved=True,
        comment="looks good",
    )
    await test_db.commit()

    assert approved.status == WorkflowRunStatus.SUCCEEDED
    assert rag.calls == 1
    assert len(agent.calls) == 1
    assert [(step.step_key, step.status) for step in approved.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("approval", WorkflowStepRunStatus.SUCCEEDED),
        ("summarize", WorkflowStepRunStatus.SUCCEEDED),
    ]
    assert approved.approvals[0].status == "approved"
    assert approved.output_data.value["outputs"]["approval"]["status"] == "approved"
    event_types = {event.event_type for event in approved.events}
    assert {
        "approval_requested",
        "run_paused",
        "approval_approved",
        "run_resumed",
    }.issubset(event_types)


@pytest.mark.asyncio
async def test_approval_resume_preserves_prior_branch_skips(test_db, test_user) -> None:
    owner = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService(),
            agent_service=FakeAgentService(),
        )
    )
    queued = await _queued_run(
        test_db,
        owner,
        runtime,
        _branch_then_approval_definition(),
    )
    paused = await runtime.execute_run(test_db, queued.id, actor=owner)
    await test_db.commit()

    approved = await runtime.resolve_approval(
        test_db,
        paused.id,
        owner,
        approved=True,
        comment="continue",
    )
    await test_db.commit()

    assert approved.status == WorkflowRunStatus.SUCCEEDED
    assert [(step.step_key, step.status) for step in approved.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("branch", WorkflowStepRunStatus.SUCCEEDED),
        ("approval", WorkflowStepRunStatus.SUCCEEDED),
        ("notify", WorkflowStepRunStatus.SKIPPED),
        ("summarize", WorkflowStepRunStatus.SUCCEEDED),
    ]


@pytest.mark.asyncio
async def test_approval_rejection_skips_remaining_steps(test_db, test_user) -> None:
    owner = _actor(int(test_user["id"]))
    agent = FakeAgentService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService(),
            agent_service=agent,
        )
    )
    queued = await _queued_run(test_db, owner, runtime, _definition())
    paused = await runtime.execute_run(test_db, queued.id, actor=owner)
    await test_db.commit()

    rejected = await runtime.resolve_approval(
        test_db,
        paused.id,
        owner,
        approved=False,
        comment="not needed",
    )
    await test_db.commit()

    assert rejected.status == WorkflowRunStatus.SKIPPED
    assert agent.calls == []
    assert [(step.step_key, step.status) for step in rejected.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("approval", WorkflowStepRunStatus.SUCCEEDED),
        ("summarize", WorkflowStepRunStatus.SKIPPED),
    ]
    assert rejected.approvals[0].status == "rejected"
    assert rejected.output_data.value["approval_status"] == "rejected"
    assert "approval_rejected" in {event.event_type for event in rejected.events}


@pytest.mark.asyncio
async def test_approval_requires_permission(test_db, test_user) -> None:
    owner = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService(),
            agent_service=FakeAgentService(),
        )
    )
    queued = await _queued_run(test_db, owner, runtime, _definition())
    paused = await runtime.execute_run(test_db, queued.id, actor=owner)
    await test_db.commit()

    reader = _actor(9999, permissions=["workflow.read"])

    with pytest.raises(WorkflowRunPermissionError):
        await runtime.resolve_approval(
            test_db,
            paused.id,
            reader,
            approved=True,
        )


@pytest.mark.asyncio
async def test_cancel_paused_run_cancels_pending_approval(test_db, test_user) -> None:
    owner = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService(),
            agent_service=FakeAgentService(),
        )
    )
    queued = await _queued_run(test_db, owner, runtime, _definition())
    paused = await runtime.execute_run(test_db, queued.id, actor=owner)
    await test_db.commit()

    cancelled = await runtime.request_cancel_run(
        test_db,
        paused.id,
        owner,
        reason="operator stopped",
    )
    await test_db.commit()

    assert cancelled.status == WorkflowRunStatus.CANCELLED
    assert cancelled.approvals[0].status == "cancelled"
