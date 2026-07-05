"""Tests for workflow schedule board and operations tabs APIs."""

from __future__ import annotations

from datetime import datetime, timedelta
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
from app.models.workflow import WorkflowRun, WorkflowTrigger, WorkflowVersion
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
)


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"schedule board {kwargs['prompt']}",
            "usage": {"total_tokens": 7},
            "actual_cost_cents": 3,
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
    name: str = "Scheduled workflow",
    cron: str = "0 2 * * *",
) -> dict[str, Any]:
    return {
        "name": name,
        "description": "Visible on the schedule board",
        "tags": ["schedule"],
        "definition": {
            "trigger": {
                "type": "schedule",
                "cron": cron,
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
                        "prompt_template": "Summarize scheduled data",
                    },
                }
            ],
        },
    }


@pytest_asyncio.fixture
async def schedule_board_client(test_db, test_user, monkeypatch):
    actor = _actor(
        int(test_user["id"]),
        test_user["email"],
        test_user["username"],
    )

    async def override_get_db():
        yield test_db

    async def override_get_current_user():
        return actor

    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(agent_service=FakeAgentService())
    )
    monkeypatch.setattr(workflows_api, "runtime_service", runtime)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, actor
    finally:
        app.dependency_overrides.clear()


async def _create_publish_enable(
    client: AsyncClient,
    *,
    payload: dict[str, Any] | None = None,
) -> str:
    create_response = await client.post(
        "/api-internal/v1/workflows/",
        json=payload or _workflow_payload(),
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
async def test_schedule_board_groups_schedules_and_disabled_health(
    schedule_board_client,
) -> None:
    client, _ = schedule_board_client
    workflow_id = await _create_publish_enable(client)

    enabled_response = await client.get(
        "/api-internal/v1/workflows/operations/schedules"
    )
    disable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/disable",
        json={"reason": "pause schedule"},
    )
    disabled_response = await client.get(
        "/api-internal/v1/workflows/operations/schedules"
    )

    enabled_board = enabled_response.json()["schedule_board"]
    disabled_item = disabled_response.json()["schedule_board"]["schedules"][0]

    assert enabled_response.status_code == 200
    assert {group["key"] for group in enabled_board["groups"]} == {
        "today",
        "tomorrow",
        "this_week",
        "later",
    }
    assert enabled_board["schedules"][0]["health"] == "healthy"
    assert len(enabled_board["schedules"][0]["preview"]) == 5
    assert disable_response.status_code == 200
    assert disabled_item["health"] == "disabled"
    assert disabled_item["trigger_enabled"] is False


@pytest.mark.asyncio
async def test_existing_schedule_preview_and_lifecycle_audit(
    schedule_board_client, test_db
) -> None:
    client, _ = schedule_board_client
    workflow_id = await _create_publish_enable(client)

    disable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/disable",
        json={"reason": "maintenance"},
    )
    enable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable",
        json={"reason": "resume"},
    )
    preview_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/schedule/preview",
        params={"count": 5},
    )

    trigger_result = await test_db.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    trigger = trigger_result.scalar_one()
    audit_result = await test_db.execute(
        select(AuditLog).where(AuditLog.resource_id == workflow_id)
    )
    actions = [entry.action for entry in audit_result.scalars().all()]

    assert disable_response.status_code == 200
    assert enable_response.status_code == 200
    assert trigger.enabled is True
    assert trigger.next_run_at is not None
    assert preview_response.status_code == 200
    assert len(preview_response.json()["preview"]["next_runs"]) == 5
    assert "workflow_disable" in actions
    assert actions.count("workflow_enable") >= 2


@pytest.mark.asyncio
async def test_recent_runs_filter_by_status_and_workflow(
    schedule_board_client, test_db
) -> None:
    client, actor = schedule_board_client
    failed_workflow_id = await _create_publish_enable(
        client, payload=_workflow_payload(name="Failed scheduled workflow")
    )
    ok_workflow_id = await _create_publish_enable(
        client, payload=_workflow_payload(name="Succeeded scheduled workflow")
    )
    version_result = await test_db.execute(
        select(WorkflowVersion).where(WorkflowVersion.workflow_id == failed_workflow_id)
    )
    version = version_result.scalar_one()
    test_db.add(
        WorkflowRun(
            workflow_id=failed_workflow_id,
            version_id=version.id,
            trigger_type="schedule",
            status="failed",
            error="boom",
            requested_by_user_id=int(actor["id"]),
            created_at=datetime.utcnow() - timedelta(minutes=5),
            updated_at=datetime.utcnow() - timedelta(minutes=4),
            queued_at=datetime.utcnow() - timedelta(minutes=5),
            started_at=datetime.utcnow() - timedelta(minutes=5),
            completed_at=datetime.utcnow() - timedelta(minutes=4),
        )
    )
    await test_db.commit()
    run_response = await client.post(
        f"/api-internal/v1/workflows/{ok_workflow_id}/runs",
        json={"input_data": {}, "execute_now": True},
    )
    failed_response = await client.get(
        "/api-internal/v1/workflows/operations/runs",
        params={"status": "failed"},
    )
    scoped_response = await client.get(
        "/api-internal/v1/workflows/operations/runs",
        params={"workflow_id": ok_workflow_id},
    )

    assert run_response.status_code == 201
    assert {run["status"] for run in failed_response.json()["runs"]} == {"failed"}
    assert {run["workflow_id"] for run in scoped_response.json()["runs"]} == {
        ok_workflow_id
    }


@pytest.mark.asyncio
async def test_operations_template_summaries(schedule_board_client) -> None:
    client, _ = schedule_board_client

    response = await client.get("/api-internal/v1/workflows/operations/templates")

    templates = response.json()["templates"]
    assert response.status_code == 200
    assert len(templates) >= 3
    assert {"id", "name", "trigger_type", "step_count", "tags"}.issubset(templates[0])
