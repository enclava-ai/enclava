"""Tests for internal workflow trigger fire API endpoints."""

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
from app.models.workflow import WorkflowRun
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowTriggerFireService,
)


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"triggered {kwargs['prompt']}",
            "usage": {"total_tokens": 5},
            "actual_cost_cents": 1,
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


def _workflow_payload(
    *,
    name: str,
    trigger: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "definition": {
            "trigger": trigger,
            "runtime": {
                "concurrency_policy": "allow_parallel",
                "budget_limit_cents": 20,
            },
            "steps": [
                {
                    "key": "summarize",
                    "type": "agent.run",
                    "name": "Summarize",
                    "config": {
                        "agent_id": "agent-1",
                        "prompt_template": "Summarize trigger payload",
                        "estimated_cost_cents": 1,
                    },
                }
            ],
        },
    }


@pytest_asyncio.fixture
async def trigger_client(test_db, test_user, monkeypatch):
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

    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    monkeypatch.setattr(workflows_api, "runtime_service", runtime)
    monkeypatch.setattr(
        workflows_api,
        "trigger_fire_service",
        WorkflowTriggerFireService(runtime),
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


async def _create_enabled_workflow(
    client: AsyncClient,
    *,
    name: str,
    trigger: dict[str, Any],
) -> str:
    create_response = await client.post(
        "/api-internal/v1/workflows/",
        json=_workflow_payload(name=name, trigger=trigger),
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish", json={}
    )
    enable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable", json={}
    )
    assert publish_response.status_code == 200
    assert enable_response.status_code == 200
    return workflow_id


@pytest.mark.asyncio
async def test_api_trigger_fire_endpoint_creates_and_deduplicates_run(
    trigger_client, test_db
) -> None:
    client, _, _ = trigger_client
    workflow_id = await _create_enabled_workflow(
        client,
        name="API fire workflow",
        trigger={"type": "api", "api_slug": "api-smoke"},
    )

    first = await client.post(
        "/api-internal/v1/workflows/triggers/api/api-smoke/fire",
        json={"idempotency_key": "deploy-1", "input_data": {"topic": "docs"}},
    )
    duplicate = await client.post(
        "/api-internal/v1/workflows/triggers/api/api-smoke/fire",
        json={"idempotency_key": "deploy-1", "input_data": {"topic": "docs"}},
    )
    missing_key = await client.post(
        "/api-internal/v1/workflows/triggers/api/api-smoke/fire",
        json={"input_data": {"topic": "docs"}},
    )
    run_result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id)
    )
    runs = run_result.scalars().all()

    assert first.status_code == 200
    assert first.json()["trigger_fire"]["created_runs"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["trigger_fire"]["duplicate_runs"] == 1
    assert duplicate.json()["trigger_fire"]["runs"][0]["run_id"] == (
        first.json()["trigger_fire"]["runs"][0]["run_id"]
    )
    assert missing_key.status_code == 422
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_event_trigger_fire_endpoint_returns_matching_run_results(
    trigger_client,
) -> None:
    client, _, _ = trigger_client
    await _create_enabled_workflow(
        client,
        name="First event fire workflow",
        trigger={"type": "event", "event_name": "rag.documents.indexed"},
    )
    await _create_enabled_workflow(
        client,
        name="Second event fire workflow",
        trigger={"type": "event", "event_name": "rag.documents.indexed"},
    )

    response = await client.post(
        "/api-internal/v1/workflows/triggers/events/rag.documents.indexed/fire",
        json={"idempotency_key": "batch-1", "input_data": {"collection_id": "1"}},
    )

    assert response.status_code == 200
    body = response.json()["trigger_fire"]
    assert body["trigger_type"] == "event"
    assert body["created_runs"] == 2
    assert len(body["runs"]) == 2


@pytest.mark.asyncio
async def test_trigger_fire_endpoint_rejects_unauthorized_actor(
    trigger_client,
) -> None:
    client, state, owner = trigger_client
    await _create_enabled_workflow(
        client,
        name="Private trigger workflow",
        trigger={"type": "api", "api_slug": "private-api"},
    )
    state["actor"] = {
        **owner,
        "id": int(owner["id"]) + 100,
        "email": "other@example.com",
        "permissions": [],
    }

    response = await client.post(
        "/api-internal/v1/workflows/triggers/api/private-api/fire",
        json={"idempotency_key": "denied"},
    )

    assert response.status_code == 403
