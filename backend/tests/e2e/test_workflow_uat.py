"""Executable UAT coverage for workflow release readiness."""

from __future__ import annotations

from copy import deepcopy
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
from app.models.workflow import WorkflowRun, WorkflowTrigger
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowSchedulerService,
)


class FakeRagService:
    def __init__(self, *, failures_remaining: int = 0) -> None:
        self.failures_remaining = failures_remaining
        self.calls = 0

    async def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls += 1
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise RuntimeError("forced RAG failure")
        return [
            {
                "document_id": "doc-1",
                "title": "Release readiness note",
                "content": "Workflow release coverage should summarize new RAG data.",
                "score": 0.91,
            }
        ]


class FakeAgentService:
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "message": f"Nightly summary generated from {kwargs['prompt']}",
            "usage": {"total_tokens": 12},
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
        "permissions": ["workflow.manage"],
    }


@pytest_asyncio.fixture
async def workflow_uat_client(test_db, test_user, monkeypatch):
    actor = _actor(
        int(test_user["id"]),
        test_user["email"],
        test_user["username"],
    )
    state: dict[str, Any] = {"actor": actor, "rag_service": FakeRagService()}

    async def override_get_db():
        yield test_db

    async def override_get_current_user():
        return state["actor"]

    def install_runtime() -> None:
        runtime = WorkflowRuntimeService(
            dependencies=WorkflowRuntimeDependencies(
                agent_service=FakeAgentService(),
                rag_service=state["rag_service"],
            )
        )
        monkeypatch.setattr(workflows_api, "runtime_service", runtime)
        monkeypatch.setattr(
            workflows_api,
            "scheduler_service",
            WorkflowSchedulerService(runtime),
        )

    install_runtime()
    state["install_runtime"] = install_runtime
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, state, actor
    finally:
        app.dependency_overrides.clear()


def _nightly_definition(
    template_definition: dict[str, Any], owner_user_id: int
) -> dict[str, Any]:
    definition = deepcopy(template_definition)
    steps = {step["key"]: step for step in definition["steps"]}
    steps["find_new_docs"]["config"]["collection_id"] = "1"
    steps["find_new_docs"]["config"]["query"] = "recent release documents"
    steps["summarize"]["config"]["agent_id"] = "agent-1"
    steps["summarize"]["config"]["estimated_cost_cents"] = 1
    steps["notify_owner"]["config"]["recipients"] = [str(owner_user_id)]
    definition["runtime"] = {
        "concurrency_policy": "allow_parallel",
        "timeout_seconds": 1800,
        "budget_limit_cents": 100,
        "redaction_policy": "default",
    }
    return definition


async def _create_nightly_workflow(
    client: AsyncClient,
    owner_user_id: int,
    *,
    name: str = "Nightly RAG Summary UAT",
) -> tuple[str, dict[str, Any]]:
    template_response = await client.get(
        "/api-internal/v1/workflows/templates/nightly-rag-summary"
    )
    assert template_response.status_code == 200
    template = template_response.json()["template"]
    definition = _nightly_definition(template["definition"], owner_user_id)

    validate_response = await client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=definition,
    )
    create_response = await client.post(
        "/api-internal/v1/workflows/",
        json={
            "name": name,
            "description": "Executable release UAT",
            "tags": ["uat", "rag", "schedule"],
            "metadata": {"template_id": "nightly-rag-summary"},
            "definition": definition,
        },
    )
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={"reason": "uat publish v1"},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["success"] is True
    assert create_response.status_code == 201
    assert publish_response.status_code == 200
    assert publish_response.json()["workflow"]["latest_version_number"] == 1
    return workflow_id, definition


async def _current_trigger(test_db, workflow_id: str) -> WorkflowTrigger:
    result = await test_db.execute(
        select(WorkflowTrigger).where(WorkflowTrigger.workflow_id == workflow_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_wf_test_03_nightly_rag_summary_schedule_disable_and_version_uat(
    workflow_uat_client,
    test_db,
    test_user,
) -> None:
    client, _, actor = workflow_uat_client
    workflow_id, definition = await _create_nightly_workflow(
        client,
        int(test_user["id"]),
    )

    manual_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={
            "execute_now": True,
            "input_data": {"request_id": "uat-manual", "api_key": "secret"},
        },
    )
    preview_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/schedule/preview?count=3",
        json={},
    )
    enable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable",
        json={"reason": "uat enable schedule"},
    )
    trigger = await _current_trigger(test_db, workflow_id)
    due_at = datetime.utcnow() - timedelta(minutes=1)
    trigger.next_run_at = due_at
    await test_db.commit()
    tick_response = await client.post(
        "/api-internal/v1/workflows/scheduler/tick?create_limit=5&execute_limit=0"
    )
    runs_after_tick = await test_db.execute(
        select(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id)
    )
    run_rows = runs_after_tick.scalars().all()

    disable_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/disable",
        json={"reason": "uat disable schedule"},
    )
    trigger = await _current_trigger(test_db, workflow_id)
    trigger.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    await test_db.commit()
    disabled_tick_response = await client.post(
        "/api-internal/v1/workflows/scheduler/tick?create_limit=5&execute_limit=0"
    )

    updated_definition = deepcopy(definition)
    updated_definition["steps"][0]["config"]["query"] = "version two documents"
    update_response = await client.put(
        f"/api-internal/v1/workflows/{workflow_id}",
        json={"definition": updated_definition},
    )
    publish_v2_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={"reason": "uat publish v2"},
    )
    manual_run = manual_response.json()["run"]
    detail_response = await client.get(
        f"/api-internal/v1/workflows/runs/{manual_run['id']}"
    )

    assert actor["permissions"] == ["workflow.manage"]
    assert manual_response.status_code == 201
    assert manual_response.json()["success"] is True
    assert manual_run["status"] == "succeeded"
    assert manual_run["version_number"] == 1
    assert manual_run["input_data"]["value"]["api_key"] == "[redacted]"
    assert any(
        artifact["artifact_type"] == "summary" for artifact in manual_run["artifacts"]
    )
    assert preview_response.status_code == 200
    assert [
        item["local_time"] for item in preview_response.json()["preview"]["next_runs"]
    ]
    assert enable_response.status_code == 200
    assert tick_response.status_code == 200
    assert tick_response.json()["scheduler"]["created_runs"] == 1
    assert any(run.trigger_type == "schedule" for run in run_rows)
    assert disable_response.status_code == 200
    assert disabled_tick_response.status_code == 200
    assert disabled_tick_response.json()["scheduler"]["created_runs"] == 0
    assert update_response.status_code == 200
    assert publish_v2_response.status_code == 200
    assert publish_v2_response.json()["workflow"]["latest_version_number"] == 2
    assert detail_response.status_code == 200
    assert detail_response.json()["run"]["version_number"] == 1


@pytest.mark.asyncio
async def test_wf_test_03_forced_rag_failure_and_retry_uat(
    workflow_uat_client,
    test_user,
) -> None:
    client, state, _ = workflow_uat_client
    state["rag_service"] = FakeRagService(failures_remaining=2)
    state["install_runtime"]()
    workflow_id, _ = await _create_nightly_workflow(
        client,
        int(test_user["id"]),
        name="Nightly RAG Summary Failure UAT",
    )

    failed_response = await client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"execute_now": True, "input_data": {"request_id": "uat-failure"}},
    )
    failed_run = failed_response.json()["run"]
    retry_response = await client.post(
        f"/api-internal/v1/workflows/runs/{failed_run['id']}/retry",
        json={"reason": "uat retry after forced RAG failure"},
    )
    assert retry_response.status_code == 201, retry_response.text
    retry_run = retry_response.json()["run"]
    execute_retry_response = await client.post(
        f"/api-internal/v1/workflows/runs/{retry_run['id']}/execute"
    )

    assert failed_response.status_code == 201
    assert failed_response.json()["success"] is False
    assert failed_run["status"] == "failed"
    assert "forced RAG failure" in failed_run["error"]
    assert retry_response.status_code == 201
    assert retry_run["status"] == "queued"
    assert retry_run["retry_of_run_id"] == failed_run["id"]
    assert execute_retry_response.status_code == 200
    assert execute_retry_response.json()["success"] is True
    assert execute_retry_response.json()["run"]["status"] == "succeeded"
