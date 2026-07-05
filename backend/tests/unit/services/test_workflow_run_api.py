"""Tests for internal workflow run API endpoints."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.internal_v1 import workflows as workflows_api
from app.core.security import get_current_user
from app.db.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.services.workflows import WorkflowRuntimeDependencies, WorkflowRuntimeService


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"processed {kwargs['prompt']}",
            "usage": {"total_tokens": 8},
            "actual_cost_cents": 2,
        }


def _actor(user_id: int, email: str, username: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": email,
        "username": username,
        "is_superuser": False,
        "is_active": True,
        "role": "user",
        "permissions": [],
    }


def _workflow_payload(name: str = "Manual execution workflow") -> dict[str, Any]:
    return {
        "name": name,
        "definition": {
            "runtime": {
                "redaction_policy": "default",
                "budget_limit_cents": 10,
            },
            "steps": [
                {
                    "key": "summarize",
                    "type": "agent.run",
                    "name": "Summarize",
                    "config": {
                        "agent_id": "agent-1",
                        "prompt_template": "Summarize {{ input.topic }}",
                        "estimated_cost_cents": 1,
                    },
                }
            ],
        },
    }


def _branch_workflow_payload() -> dict[str, Any]:
    return {
        "name": "Branch execution workflow",
        "definition": {
            "runtime": {
                "redaction_policy": "default",
                "budget_limit_cents": 10,
            },
            "steps": [
                {
                    "key": "seed",
                    "type": "agent.run",
                    "name": "Seed",
                    "config": {
                        "agent_id": "agent-1",
                        "prompt_template": "Seed {{ input.topic }}",
                        "estimated_cost_cents": 1,
                    },
                },
                {
                    "key": "branch",
                    "type": "condition.branch",
                    "name": "Branch",
                    "config": {
                        "input_step_key": "seed",
                        "path": "message",
                        "operator": "contains",
                        "value": "processed",
                        "matched_label": "Processed",
                        "not_matched_label": "Not processed",
                        "matched_skip_step_keys": ["notify"],
                        "not_matched_skip_step_keys": [],
                    },
                },
                {
                    "key": "notify",
                    "type": "notify.in_app",
                    "name": "Notify",
                    "config": {
                        "recipients": ["1"],
                        "title_template": "Workflow update",
                    },
                },
            ],
        },
    }


@pytest_asyncio.fixture
async def workflow_run_client(test_db, test_user, monkeypatch):
    owner = _actor(
        int(test_user["id"]),
        test_user["email"],
        test_user["username"],
    )
    state = {"actor": owner}

    async def override_get_db():
        yield test_db

    async def override_get_current_user():
        return state["actor"]

    monkeypatch.setattr(
        workflows_api,
        "runtime_service",
        WorkflowRuntimeService(
            dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
        ),
    )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, state, owner
    finally:
        app.dependency_overrides.clear()


async def _create_published_workflow(
    client: AsyncClient, payload: dict[str, Any] | None = None
) -> str:
    create_response = await client.post(
        "/api-internal/v1/workflows/", json=payload or _workflow_payload()
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish", json={}
    )
    assert publish_response.status_code == 200
    return workflow_id


@pytest.mark.asyncio
async def test_run_api_creates_executes_and_serializes_detail(
    workflow_run_client, test_db
) -> None:
    client, _, _ = workflow_run_client
    workflow_id = await _create_published_workflow(client)

    create_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={
            "execute_now": True,
            "input_data": {"topic": "new docs", "api_key": "secret"},
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    run = body["run"]

    assert body["success"] is True
    assert run["status"] == "succeeded"
    assert run["input_data"]["value"]["api_key"] == "[redacted]"
    assert run["output_data"]["value"]["outputs"]["summarize"]["message"] == (
        "processed Summarize new docs"
    )
    assert run["actual_cost_cents"] == 2
    assert run["steps"][0]["artifacts"][0]["artifact_type"] == "summary"
    assert {event["event_type"] for event in run["events"]}.issuperset(
        {"run_queued", "run_claimed", "step_succeeded", "agent_run_completed"}
    )

    detail_response = await client.get(f"/api-internal/v1/workflows/runs/{run['id']}")
    list_response = await client.get(f"/api-internal/v1/workflows/{workflow_id}/runs")
    assert detail_response.status_code == 200
    assert detail_response.json()["run"]["id"] == run["id"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    audit_result = await test_db.execute(
        select(AuditLog).where(AuditLog.resource_id == run["id"])
    )
    assert "workflow_run_create" in {
        entry.action for entry in audit_result.scalars().all()
    }


@pytest.mark.asyncio
async def test_run_api_serializes_branch_outputs_and_skipped_steps(
    workflow_run_client,
) -> None:
    client, _, _ = workflow_run_client
    workflow_id = await _create_published_workflow(client, _branch_workflow_payload())

    create_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={
            "execute_now": True,
            "input_data": {"topic": "new docs"},
        },
    )

    assert create_response.status_code == 201
    run = create_response.json()["run"]
    assert run["status"] == "succeeded"
    assert run["output_data"]["value"]["outputs"]["branch"]["matched"] is True
    assert run["output_data"]["value"]["outputs"]["branch"]["skipped_step_keys"] == [
        "notify"
    ]
    assert [(step["step_key"], step["status"]) for step in run["steps"]] == [
        ("seed", "succeeded"),
        ("branch", "succeeded"),
        ("notify", "skipped"),
    ]
    event_types = {event["event_type"] for event in run["events"]}
    assert {"branch_evaluated", "step_skipped"}.issubset(event_types)


@pytest.mark.asyncio
async def test_run_api_cancel_and_retry(workflow_run_client, test_db) -> None:
    client, _, _ = workflow_run_client
    workflow_id = await _create_published_workflow(client)
    create_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"input_data": {"topic": "new docs"}},
    )
    run_id = create_response.json()["run"]["id"]

    cancel_response = await client.post(
        f"/api-internal/v1/workflows/runs/{run_id}/cancel",
        json={"reason": "operator stopped"},
    )
    retry_response = await client.post(
        f"/api-internal/v1/workflows/runs/{run_id}/retry",
        json={"reason": "try again"},
    )
    invalid_retry_response = await client.post(
        f"/api-internal/v1/workflows/runs/{retry_response.json()['run']['id']}/retry",
        json={},
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["run"]["status"] == "cancelled"
    assert retry_response.status_code == 201
    retry = retry_response.json()["run"]
    assert retry["status"] == "queued"
    assert retry["retry_of_run_id"] == run_id
    assert invalid_retry_response.status_code == 409

    audit_result = await test_db.execute(
        select(AuditLog).where(AuditLog.resource_type == "workflow_run")
    )
    actions = {entry.action for entry in audit_result.scalars().all()}
    assert {"workflow_run_cancel", "workflow_run_retry"}.issubset(actions)


@pytest.mark.asyncio
async def test_run_api_denies_non_owner_access(workflow_run_client) -> None:
    client, state, _ = workflow_run_client
    workflow_id = await _create_published_workflow(client)
    create_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"input_data": {"topic": "new docs"}},
    )
    run_id = create_response.json()["run"]["id"]

    state["actor"] = _actor(99999, "other@example.com", "other")

    detail_response = await client.get(f"/api-internal/v1/workflows/runs/{run_id}")
    run_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"input_data": {"topic": "other docs"}},
    )

    assert detail_response.status_code == 404
    assert run_response.status_code == 404
