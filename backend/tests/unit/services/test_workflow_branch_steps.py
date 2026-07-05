"""Tests for branch workflow step execution and validation."""

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
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowService,
    create_default_step_registry,
)


class FakeRAGService:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    async def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.documents


class FakeAgentService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "message": "summary ready",
            "usage": {"total_tokens": 12},
            "actual_cost_cents": 2,
        }


class FakeNotificationService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_notification(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "notification-1"


def _actor(user_id: int) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": [],
    }


def _definition(steps: list[dict[str, Any]]) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(steps=steps)


async def _published_workflow(
    test_db, actor: dict[str, Any], definition: WorkflowDefinitionDocument
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Branch workflow",
            definition=definition,
        ),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


async def _queued_run(
    test_db,
    actor: dict[str, Any],
    definition: WorkflowDefinitionDocument,
    runtime: WorkflowRuntimeService,
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


def _query_step() -> dict[str, Any]:
    return {
        "key": "query",
        "type": "rag.query",
        "name": "Query",
        "config": {"collection_id": "1", "query": "recent docs"},
    }


def _summarize_step() -> dict[str, Any]:
    return {
        "key": "summarize",
        "type": "agent.run",
        "name": "Summarize",
        "config": {
            "agent_id": "agent-1",
            "prompt_template": "Summarize {{ query.count }} docs",
        },
    }


def _notify_step() -> dict[str, Any]:
    return {
        "key": "notify",
        "type": "notify.in_app",
        "name": "Notify",
        "config": {
            "recipients": ["1"],
            "title_template": "Workflow update",
            "body_template": "{{ branch.selected_label }}",
        },
    }


@pytest.mark.asyncio
async def test_branch_catalog_entry_is_enabled() -> None:
    entry = create_default_step_registry().get("condition.branch")

    assert entry is not None
    assert entry.enabled is True
    assert entry.supports_retry is False


@pytest.mark.asyncio
async def test_matched_branch_skips_only_configured_target(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    agent = FakeAgentService()
    notifications = FakeNotificationService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService([{"title": "Doc"}]),
            agent_service=agent,
            notification_service=notifications,
        )
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            [
                _query_step(),
                {
                    "key": "branch",
                    "type": "condition.branch",
                    "name": "Branch",
                    "config": {
                        "input_step_key": "query",
                        "path": "count",
                        "operator": "greater_than",
                        "value": 0,
                        "matched_label": "Has results",
                        "not_matched_label": "No results",
                        "matched_skip_step_keys": ["notify"],
                        "not_matched_skip_step_keys": [],
                    },
                },
                _notify_step(),
                _summarize_step(),
            ]
        ),
        runtime,
    )

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert [(step.step_key, step.status) for step in reloaded.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("branch", WorkflowStepRunStatus.SUCCEEDED),
        ("notify", WorkflowStepRunStatus.SKIPPED),
        ("summarize", WorkflowStepRunStatus.SUCCEEDED),
    ]
    assert notifications.calls == []
    assert len(agent.calls) == 1
    branch_output = reloaded.output_data.value["outputs"]["branch"]
    assert branch_output["matched"] is True
    assert branch_output["selected_label"] == "Has results"
    assert branch_output["skipped_step_keys"] == ["notify"]
    event_types = {event.event_type for event in reloaded.events}
    assert "branch_evaluated" in event_types
    skip_event = next(
        event
        for event in reloaded.events
        if event.event_type == "step_skipped" and event.data["step_key"] == "notify"
    )
    assert skip_event.data["source_step_key"] == "branch"
    assert "Branch branch selected Has results" in skip_event.data["reason"]


@pytest.mark.asyncio
async def test_not_matched_branch_skips_only_configured_target(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    agent = FakeAgentService()
    notifications = FakeNotificationService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=FakeRAGService([]),
            agent_service=agent,
            notification_service=notifications,
        )
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            [
                _query_step(),
                {
                    "key": "branch",
                    "type": "condition.branch",
                    "name": "Branch",
                    "config": {
                        "input_step_key": "query",
                        "path": "count",
                        "operator": "greater_than",
                        "value": 0,
                        "matched_label": "Has results",
                        "not_matched_label": "No results",
                        "matched_skip_step_keys": [],
                        "not_matched_skip_step_keys": ["summarize"],
                    },
                },
                _summarize_step(),
                _notify_step(),
            ]
        ),
        runtime,
    )

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert [(step.step_key, step.status) for step in reloaded.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("branch", WorkflowStepRunStatus.SUCCEEDED),
        ("summarize", WorkflowStepRunStatus.SKIPPED),
        ("notify", WorkflowStepRunStatus.SUCCEEDED),
    ]
    assert agent.calls == []
    assert len(notifications.calls) == 1
    branch_output = reloaded.output_data.value["outputs"]["branch"]
    assert branch_output["matched"] is False
    assert branch_output["selected_label"] == "No results"
    assert branch_output["skipped_step_keys"] == ["summarize"]


@pytest.mark.asyncio
async def test_branch_validation_rejects_invalid_configurations() -> None:
    service = WorkflowService()

    async def validate(branch_config: dict[str, Any]) -> list[dict[str, Any]]:
        response = await service.validate_workflow_payload(
            {
                "trigger": {"type": "manual"},
                "steps": [
                    _query_step(),
                    {
                        "key": "branch",
                        "type": "condition.branch",
                        "name": "Branch",
                        "config": branch_config,
                    },
                    _summarize_step(),
                ],
            }
        )
        return [error.model_dump() for error in response.errors]

    missing_input = await validate({"operator": "exists"})
    unknown_operator = await validate(
        {"input_step_key": "query", "operator": "between"}
    )
    missing_value = await validate({"input_step_key": "query", "operator": "equals"})
    missing_target = await validate(
        {
            "input_step_key": "query",
            "operator": "exists",
            "matched_skip_step_keys": ["missing"],
        }
    )
    self_target = await validate(
        {
            "input_step_key": "query",
            "operator": "exists",
            "matched_skip_step_keys": ["branch"],
        }
    )
    earlier_target = await validate(
        {
            "input_step_key": "query",
            "operator": "exists",
            "not_matched_skip_step_keys": ["query"],
        }
    )

    assert missing_input[0]["path"] == "steps[1].config.input_step_key"
    assert unknown_operator[0]["code"] == "invalid_step_config"
    assert missing_value[0]["path"] == "steps[1].config.value"
    assert missing_target[0]["path"] == "steps[1].config.matched_skip_step_keys[0]"
    assert self_target[0]["path"] == "steps[1].config.matched_skip_step_keys[0]"
    assert earlier_target[0]["path"] == (
        "steps[1].config.not_matched_skip_step_keys[0]"
    )


@pytest.mark.asyncio
async def test_valid_branch_definition_passes_validation() -> None:
    response = await WorkflowService().validate_workflow_payload(
        {
            "trigger": {"type": "manual"},
            "steps": [
                _query_step(),
                {
                    "key": "branch",
                    "type": "condition.branch",
                    "name": "Branch",
                    "config": {
                        "input_step_key": "query",
                        "path": "count",
                        "operator": "greater_than",
                        "value": 0,
                        "matched_skip_step_keys": ["summarize"],
                        "not_matched_skip_step_keys": [],
                    },
                },
                _summarize_step(),
            ],
        }
    )

    assert response.valid is True
    assert response.errors == []
