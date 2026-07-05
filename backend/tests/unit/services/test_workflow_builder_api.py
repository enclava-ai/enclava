"""Tests for workflow builder catalog and validation APIs."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import get_current_user
from app.db.database import get_db
from app.main import app


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


@pytest_asyncio.fixture
async def builder_client(test_db, test_user):
    actor = _actor(
        int(test_user["id"]),
        test_user["email"],
        test_user["username"],
    )

    async def override_get_db():
        yield test_db

    async def override_get_current_user():
        return actor

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _definition_with_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger": {"type": "manual"},
        "steps": [step],
    }


@pytest.mark.asyncio
async def test_builder_catalog_exposes_enabled_and_disabled_steps(
    builder_client: AsyncClient,
) -> None:
    response = await builder_client.get("/api-internal/v1/workflows/steps/catalog")

    assert response.status_code == 200
    steps = {entry["type"]: entry for entry in response.json()["steps"]}
    assert len(steps) >= 6
    assert steps["rag.query"]["enabled"] is True
    assert steps["agent.run"]["required_permissions"] == ["agent:execute"]
    assert steps["connector.sync"]["enabled"] is False
    assert "Phase 6" in steps["connector.sync"]["disabled_reason"]
    assert steps["extract.run_template"]["enabled"] is False


@pytest.mark.asyncio
async def test_builder_step_detail_and_template_detail(
    builder_client: AsyncClient,
) -> None:
    step_response = await builder_client.get(
        "/api-internal/v1/workflows/steps/catalog/agent.run"
    )
    template_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/nightly-rag-summary"
    )
    missing_response = await builder_client.get(
        "/api-internal/v1/workflows/steps/catalog/not.real"
    )

    assert step_response.status_code == 200
    assert step_response.json()["step"]["supports_retry"] is True
    assert template_response.status_code == 200
    template = template_response.json()["template"]
    assert template["id"] == "nightly-rag-summary"
    assert len(template["definition"]["steps"]) == 4
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_builder_validation_reports_registry_errors(
    builder_client: AsyncClient,
) -> None:
    missing_config_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=_definition_with_step(
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize",
                "config": {"prompt_template": "Summarize it."},
            }
        ),
    )
    unknown_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=_definition_with_step(
            {
                "key": "unknown",
                "type": "unknown.step",
                "name": "Unknown",
                "config": {},
            }
        ),
    )
    disabled_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=_definition_with_step(
            {
                "key": "sync",
                "type": "connector.sync",
                "name": "Sync",
                "config": {"connector_id": "connector-1"},
            }
        ),
    )

    missing_error = missing_config_response.json()["errors"][0]
    assert missing_config_response.status_code == 200
    assert missing_config_response.json()["success"] is False
    assert missing_error["path"] == "steps[0].config.agent_id"
    assert missing_error["code"] == "missing_step_config"

    unknown_error = unknown_response.json()["errors"][0]
    assert unknown_response.json()["success"] is False
    assert unknown_error["path"] == "steps[0].type"
    assert unknown_error["code"] == "unknown_step_type"

    disabled_error = disabled_response.json()["errors"][0]
    assert disabled_response.json()["success"] is False
    assert disabled_error["code"] == "disabled_step_type"
    assert "Phase 6" in disabled_error["message"]


@pytest.mark.asyncio
async def test_nightly_template_validates_and_disabled_template_publish_blocks(
    builder_client: AsyncClient,
) -> None:
    nightly_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/nightly-rag-summary"
    )
    connector_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/connector-intake-triage"
    )
    nightly_definition = nightly_response.json()["template"]["definition"]
    connector_definition = connector_response.json()["template"]["definition"]

    validate_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=nightly_definition,
    )
    create_response = await builder_client.post(
        "/api-internal/v1/workflows/",
        json={
            "name": "Connector draft",
            "definition": connector_definition,
        },
    )
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["success"] is True
    assert create_response.status_code == 201
    assert publish_response.status_code == 422
    publish_errors = publish_response.json()["detail"]["errors"]
    assert any(error["code"] == "disabled_step_type" for error in publish_errors)
