"""Tests for built-in workflow step handler execution."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowRedactionPolicy,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowService,
)
from app.services.workflows.steps import WorkflowStepExecutionError


class FakeRAGService:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents
        self.calls: list[dict[str, Any]] = []

    async def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        return self.documents


class FakeAgentService:
    def __init__(self, *, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if len(self.calls) <= self.failures_before_success:
            raise RuntimeError("temporary agent failure")

        return {
            "message": "summary ready",
            "usage": {"total_tokens": 12},
            "actual_cost_cents": 2,
        }


class AlwaysFailingAgentService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        raise RuntimeError("permanent agent failure")


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


def _definition(
    steps: list[dict[str, Any]],
    *,
    redaction_policy: WorkflowRedactionPolicy = WorkflowRedactionPolicy.DEFAULT,
    budget_limit_cents: int | None = None,
) -> WorkflowDefinitionDocument:
    runtime: dict[str, Any] = {"redaction_policy": redaction_policy.value}
    if budget_limit_cents is not None:
        runtime["budget_limit_cents"] = budget_limit_cents
    return WorkflowDefinitionDocument(runtime=runtime, steps=steps)


async def _published_workflow(
    test_db, actor: dict[str, Any], definition: WorkflowDefinitionDocument
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Executable workflow",
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
        WorkflowManualRunRequest(input_data={"topic": "new docs"}),
        actor,
    )
    await test_db.commit()
    return run


@pytest.mark.asyncio
async def test_execute_success_persists_steps_outputs_and_artifacts(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    rag = FakeRAGService([{"title": "Doc", "score": 0.91}])
    agent = FakeAgentService()
    notifications = FakeNotificationService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            rag_service=rag,
            agent_service=agent,
            notification_service=notifications,
        )
    )
    definition = _definition(
        [
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query RAG",
                "config": {
                    "collection_id": "1",
                    "query": "{{ input.topic }}",
                    "limit": 2,
                },
            },
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize {{ docs }}",
                    "input_mapping": {"docs": "query.documents"},
                    "estimated_cost_cents": 1,
                },
            },
            {
                "key": "notify",
                "type": "notify.in_app",
                "name": "Notify owner",
                "config": {
                    "recipients": ["{{ owner_user_id }}"],
                    "title_template": "Workflow complete",
                    "body_template": "{{ summarize.message }}",
                },
            },
        ]
    )
    queued = await _queued_run(test_db, actor, definition, runtime)

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert [step.status for step in reloaded.steps] == [
        WorkflowStepRunStatus.SUCCEEDED,
        WorkflowStepRunStatus.SUCCEEDED,
        WorkflowStepRunStatus.SUCCEEDED,
    ]
    assert reloaded.output_data.value["outputs"]["summarize"]["message"] == (
        "summary ready"
    )
    assert reloaded.actual_cost_cents == 2
    assert rag.calls[0]["collection_id"] == 1
    assert agent.calls[0]["prompt"] == "Summarize [{'title': 'Doc', 'score': 0.91}]"
    assert notifications.calls[0]["body"] == "summary ready"
    assert {
        artifact.artifact_type for step in reloaded.steps for artifact in step.artifacts
    } == {"json", "summary", "notification"}
    assert {event.event_type for event in reloaded.events}.issuperset(
        {"rag_query_completed", "agent_run_completed", "notification_created"}
    )


@pytest.mark.asyncio
async def test_no_results_condition_skips_remaining_steps(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    rag = FakeRAGService([])
    agent = FakeAgentService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(rag_service=rag, agent_service=agent)
    )
    definition = _definition(
        [
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query RAG",
                "config": {"collection_id": "1", "query": "recent docs"},
            },
            {
                "key": "no_results",
                "type": "condition.no_results_skip",
                "name": "Skip empty results",
                "config": {"input_step_key": "query", "path": "documents"},
            },
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize",
                },
            },
        ]
    )
    queued = await _queued_run(test_db, actor, definition, runtime)

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SKIPPED
    assert [(step.step_key, step.status) for step in reloaded.steps] == [
        ("query", WorkflowStepRunStatus.SUCCEEDED),
        ("no_results", WorkflowStepRunStatus.SUCCEEDED),
        ("summarize", WorkflowStepRunStatus.SKIPPED),
    ]
    assert agent.calls == []
    assert reloaded.output_data.value["skipped_after_step"] == "no_results"


@pytest.mark.asyncio
async def test_step_retry_succeeds_after_transient_failure(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    agent = FakeAgentService(failures_before_success=1)
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=agent)
    )
    definition = _definition(
        [
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize input",
                },
                "retry": {"max_attempts": 2},
            }
        ]
    )
    queued = await _queued_run(test_db, actor, definition, runtime)

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert len(agent.calls) == 2
    assert [(step.attempt, step.status) for step in reloaded.steps] == [
        (1, WorkflowStepRunStatus.RETRYING),
        (2, WorkflowStepRunStatus.SUCCEEDED),
    ]
    assert "step_retrying" in {event.event_type for event in reloaded.events}


@pytest.mark.asyncio
async def test_handler_failure_marks_run_failed(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            agent_service=AlwaysFailingAgentService()
        )
    )
    definition = _definition(
        [
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize input",
                },
            }
        ]
    )
    queued = await _queued_run(test_db, actor, definition, runtime)

    with pytest.raises(WorkflowStepExecutionError, match="permanent agent failure"):
        await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, queued.id, actor)

    assert reloaded.status == WorkflowRunStatus.FAILED
    assert reloaded.error == "permanent agent failure"
    assert reloaded.steps[0].status == WorkflowStepRunStatus.FAILED
    assert reloaded.steps[0].error == "permanent agent failure"


@pytest.mark.asyncio
async def test_budget_guardrail_fails_before_agent_call(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    agent = FakeAgentService()
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=agent)
    )
    definition = _definition(
        [
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize input",
                    "estimated_cost_cents": 1,
                },
            }
        ],
        budget_limit_cents=0,
    )
    queued = await _queued_run(test_db, actor, definition, runtime)

    with pytest.raises(WorkflowStepExecutionError, match="budget limit exceeded"):
        await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, queued.id, actor)

    assert agent.calls == []
    assert reloaded.status == WorkflowRunStatus.FAILED
    assert reloaded.error == "workflow budget limit exceeded"
    assert reloaded.steps[0].status == WorkflowStepRunStatus.FAILED


@pytest.mark.asyncio
async def test_strict_redaction_hides_step_payloads_and_artifacts(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    definition = _definition(
        [
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {
                    "agent_id": "agent-1",
                    "prompt_template": "Summarize {{ input.secret }}",
                },
            }
        ],
        redaction_policy=WorkflowRedactionPolicy.STRICT,
    )
    workflow = await _published_workflow(test_db, actor, definition)
    queued = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={"secret": "hide me"}),
        actor,
    )
    await test_db.commit()

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert reloaded.input_data.redacted is True
    assert reloaded.input_data.value is None
    assert reloaded.output_data.value is None
    assert reloaded.steps[0].input_data.value is None
    assert reloaded.steps[0].output_data.value is None
    assert reloaded.steps[0].artifacts[0].data.value is None
