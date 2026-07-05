"""Tests for internal workflow scheduler API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.internal_v1 import workflows as workflows_api
from app.core.security import get_current_user
from app.db.database import get_db
from app.main import app
from app.models.workflow import WorkflowRun, WorkflowTrigger
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowSchedulerService,
)


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"scheduled {kwargs['prompt']}",
            "usage": {"total_tokens": 5},
            "actual_cost_cents": 1,
        }


def _actor(
    user_id: int,
    email: str,
    username: str,
    *,
    manage: bool = True,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": email,
        "username": username,
        "is_superuser": False,
        "is_active": True,
        "role": "user",
        "permissions": ["workflow.manage"] if manage else [],
    }


def _workflow_payload() -> dict[str, Any]:
    return {
        "name": "Scheduled workflow",
        "definition": {
            "trigger": {
                "type": "schedule",
                "cron": "0 2 * * *",
                "timezone": "UTC",
                "misfire_policy": "run_once",
            },
            "runtime": {"concurrency_policy": "allow_parallel"},
            "steps": [
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
        },
    }


@pytest_asyncio.fixture
async def scheduler_client(test_db, test_user, monkeypatch):
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
        "scheduler_service",
        WorkflowSchedulerService(runtime),
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


async def _create_enabled_workflow(client: AsyncClient) -> str:
    create_response = await client.post(
        "/api-internal/v1/workflows/", json=_workflow_payload()
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
async def test_schedule_preview_api_validates_cron_and_timezone(
    scheduler_client,
) -> None:
    client, _, _ = scheduler_client

    valid_response = await client.post(
        "/api-internal/v1/workflows/schedule/preview",
        json={
            "cron": "0 2 * * *",
            "timezone": "UTC",
            "count": 2,
            "start_at": "2026-01-01T00:00:00Z",
        },
    )
    invalid_response = await client.post(
        "/api-internal/v1/workflows/schedule/preview",
        json={"cron": "not cron", "timezone": "UTC"},
    )
    invalid_timezone_response = await client.post(
        "/api-internal/v1/workflows/schedule/preview",
        json={"cron": "0 2 * * *", "timezone": "Mars/Olympus"},
    )

    assert valid_response.status_code == 200
    assert len(valid_response.json()["preview"]["next_runs"]) == 2
    assert invalid_response.status_code == 422
    assert invalid_timezone_response.status_code == 422


@pytest.mark.asyncio
async def test_scheduler_tick_requires_manage_permission(scheduler_client) -> None:
    client, state, owner = scheduler_client
    state["actor"] = {**owner, "permissions": []}

    response = await client.post("/api-internal/v1/workflows/scheduler/tick")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_scheduler_tick_api_creates_and_executes_due_run(
    scheduler_client, test_db
) -> None:
    client, _, _ = scheduler_client
    workflow_id = await _create_enabled_workflow(client)
    due_at = datetime(2026, 1, 1, 2, 0)
    trigger_result = await test_db.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    trigger = trigger_result.scalar_one()
    trigger.next_run_at = due_at
    await test_db.commit()

    response = await client.post(
        "/api-internal/v1/workflows/scheduler/tick",
        params={"create_limit": 10, "execute_limit": 5},
    )

    run_result = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id)
    )
    run = run_result.scalar_one()

    assert response.status_code == 200
    assert response.json()["scheduler"]["created_runs"] == 1
    assert response.json()["scheduler"]["executed_runs"] == 1
    assert run.status == "succeeded"
    assert run.trigger_id == trigger.id
