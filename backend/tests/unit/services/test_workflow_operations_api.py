"""Tests for internal workflow operations APIs."""

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
from app.models.workflow import WorkflowRun, WorkflowTrigger, WorkflowVersion
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
)


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"operations {kwargs['prompt']}",
            "usage": {"total_tokens": 8},
            "actual_cost_cents": 2,
        }


def _actor(
    user_id: int,
    email: str,
    username: str,
    *,
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": email,
        "username": username,
        "is_superuser": False,
        "is_active": True,
        "role": "user",
        "permissions": permissions or [],
    }


def _workflow_payload(
    *,
    name: str = "Operations workflow",
    trigger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": "Visible in operations",
        "tags": ["ops"],
        "definition": {
            "trigger": trigger or {"type": "manual"},
            "runtime": {"budget_limit_cents": 1200},
            "steps": [
                {
                    "key": "summarize",
                    "type": "agent.run",
                    "name": "Summarize",
                    "config": {
                        "agent_id": "agent-1",
                        "prompt_template": "Summarize operations",
                    },
                }
            ],
        },
    }


@pytest_asyncio.fixture
async def operations_client(test_db, test_user, monkeypatch):
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
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, state, owner
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
async def test_operations_empty_state(operations_client) -> None:
    client, _, _ = operations_client

    response = await client.get("/api-internal/v1/workflows/operations")

    assert response.status_code == 200
    assert response.json()["operations"]["totals"]["total"] == 0
    assert response.json()["operations"]["workflows"] == []


@pytest.mark.asyncio
async def test_operations_visibility_matches_workflow_read(
    operations_client,
) -> None:
    client, state, owner = operations_client
    await _create_publish_enable(client)

    owner_response = await client.get("/api-internal/v1/workflows/operations")
    state["actor"] = _actor(999, "other@example.com", "other")
    other_response = await client.get("/api-internal/v1/workflows/operations")
    state["actor"] = _actor(
        999,
        "reader@example.com",
        "reader",
        permissions=["workflow.read"],
    )
    reader_response = await client.get("/api-internal/v1/workflows/operations")
    state["actor"] = owner

    assert owner_response.json()["operations"]["totals"]["total"] == 1
    assert other_response.json()["operations"]["totals"]["total"] == 0
    assert reader_response.json()["operations"]["totals"]["total"] == 1


@pytest.mark.asyncio
async def test_operations_run_now_updates_latest_run(operations_client) -> None:
    client, _, _ = operations_client
    workflow_id = await _create_publish_enable(client)

    run_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"input_data": {}, "execute_now": True},
    )
    operations_response = await client.get("/api-internal/v1/workflows/operations")
    recent_response = await client.get(
        "/api-internal/v1/workflows/operations/recent-runs"
    )

    row = operations_response.json()["operations"]["workflows"][0]

    assert run_response.status_code == 201
    assert row["health"] == "no_schedule"
    assert row["latest_run"]["status"] == "succeeded"
    assert row["run_count"] == 1
    assert row["budget_limit_cents"] == 1200
    assert recent_response.json()["runs"][0]["id"] == row["latest_run"]["id"]


@pytest.mark.asyncio
async def test_operations_reports_failed_and_missed_health(
    operations_client, test_db
) -> None:
    client, _, owner = operations_client
    failed_workflow_id = await _create_publish_enable(
        client,
        payload=_workflow_payload(name="Failed workflow"),
    )
    scheduled_workflow_id = await _create_publish_enable(
        client,
        payload=_workflow_payload(
            name="Missed workflow",
            trigger={
                "type": "schedule",
                "cron": "0 2 * * *",
                "timezone": "UTC",
            },
        ),
    )
    version_result = await test_db.execute(
        select(WorkflowVersion).where(WorkflowVersion.workflow_id == failed_workflow_id)
    )
    version = version_result.scalar_one()
    test_db.add(
        WorkflowRun(
            workflow_id=failed_workflow_id,
            version_id=version.id,
            trigger_type="manual",
            status="failed",
            error="boom",
            requested_by_user_id=int(owner["id"]),
            created_at=datetime(2026, 1, 1, 2, 0),
            updated_at=datetime(2026, 1, 1, 2, 1),
            queued_at=datetime(2026, 1, 1, 2, 0),
            started_at=datetime(2026, 1, 1, 2, 0),
            completed_at=datetime(2026, 1, 1, 2, 1),
            actual_cost_cents=4,
        )
    )
    trigger_result = await test_db.execute(
        select(WorkflowTrigger).where(
            WorkflowTrigger.workflow_id == scheduled_workflow_id
        )
    )
    trigger = trigger_result.scalar_one()
    trigger.next_run_at = datetime.utcnow() - timedelta(hours=1)
    await test_db.commit()

    operations_response = await client.get("/api-internal/v1/workflows/operations")
    failures_response = await client.get(
        "/api-internal/v1/workflows/operations/failures"
    )
    rows = {
        row["name"]: row
        for row in operations_response.json()["operations"]["workflows"]
    }

    assert rows["Failed workflow"]["health"] == "failed"
    assert rows["Failed workflow"]["failure_count"] == 1
    assert rows["Missed workflow"]["health"] == "missed"
    assert operations_response.json()["operations"]["totals"]["failed"] == 1
    assert operations_response.json()["operations"]["totals"]["missed"] == 1
    assert failures_response.json()["runs"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_admin_metrics_and_maintenance_endpoints_are_manage_only(
    operations_client, test_db
) -> None:
    client, state, owner = operations_client
    scheduled_workflow_id = await _create_publish_enable(
        client,
        payload=_workflow_payload(
            name="Admin metrics schedule",
            trigger={
                "type": "schedule",
                "cron": "0 2 * * *",
                "timezone": "UTC",
            },
        ),
    )
    version_result = await test_db.execute(
        select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == scheduled_workflow_id
        )
    )
    version = version_result.scalar_one()
    now = datetime.utcnow()
    test_db.add_all(
        [
            WorkflowRun(
                workflow_id=scheduled_workflow_id,
                version_id=version.id,
                trigger_type="manual",
                status="failed",
                error="admin metrics failure",
                requested_by_user_id=int(owner["id"]),
                created_at=now - timedelta(hours=1),
                updated_at=now - timedelta(minutes=55),
                queued_at=now - timedelta(hours=1),
                started_at=now - timedelta(hours=1),
                completed_at=now - timedelta(minutes=55),
                actual_cost_cents=17,
            ),
            WorkflowRun(
                workflow_id=scheduled_workflow_id,
                version_id=version.id,
                trigger_type="manual",
                status="running",
                requested_by_user_id=int(owner["id"]),
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
                queued_at=now - timedelta(hours=2),
                started_at=now - timedelta(hours=2),
                locked_by="stale-worker",
                lock_expires_at=now - timedelta(minutes=5),
                actual_cost_cents=3,
            ),
        ]
    )
    trigger_result = await test_db.execute(
        select(WorkflowTrigger).where(
            WorkflowTrigger.workflow_id == scheduled_workflow_id
        )
    )
    trigger = trigger_result.scalar_one()
    trigger.next_run_at = now - timedelta(minutes=10)
    await test_db.commit()

    metrics_forbidden = await client.get(
        "/api-internal/v1/workflows/operations/admin-metrics"
    )
    recovery_forbidden = await client.post(
        "/api-internal/v1/workflows/operations/recover-stale-locks"
    )
    retention_forbidden = await client.post(
        "/api-internal/v1/workflows/operations/retention",
        json={"dry_run": True},
    )
    state["actor"] = {**owner, "permissions": ["workflow.manage"]}

    metrics_response = await client.get(
        "/api-internal/v1/workflows/operations/admin-metrics"
    )
    recovery_response = await client.post(
        "/api-internal/v1/workflows/operations/recover-stale-locks",
        json={"reason": "api test"},
    )
    retention_response = await client.post(
        "/api-internal/v1/workflows/operations/retention",
        json={"dry_run": True},
    )

    metrics = metrics_response.json()["metrics"]

    assert metrics_forbidden.status_code == 403
    assert recovery_forbidden.status_code == 403
    assert retention_forbidden.status_code == 403
    assert metrics_response.status_code == 200
    assert metrics["scheduler_lag_seconds"] >= 600
    assert metrics["stale_lock_count"] == 1
    assert metrics["long_running_count"] == 1
    assert metrics["failed_runs_24h"] == 1
    assert metrics["top_workflows_by_cost"][0]["actual_cost_cents"] == 20
    assert recovery_response.status_code == 200
    assert recovery_response.json()["recovery"]["recovered_count"] == 1
    assert retention_response.status_code == 200
    assert retention_response.json()["retention"]["dry_run"] is True
