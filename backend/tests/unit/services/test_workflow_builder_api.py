"""Tests for workflow builder catalog and validation APIs."""

from __future__ import annotations

from copy import deepcopy
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


def _nightly_authoring_definition(
    definition: dict[str, Any], owner_user_id: int
) -> dict[str, Any]:
    authored = deepcopy(definition)
    steps = {step["key"]: step for step in authored["steps"]}
    steps["find_new_docs"]["config"]["collection_id"] = "1"
    steps["find_new_docs"]["config"]["query"] = "recent documents"
    steps["summarize"]["config"]["agent_id"] = "agent-1"
    steps["notify_owner"]["config"]["recipients"] = [str(owner_user_id)]
    authored["runtime"] = {
        "concurrency_policy": "skip_if_running",
        "timeout_seconds": 1800,
        "budget_limit_cents": 100,
        "redaction_policy": "default",
    }
    return authored


def _connector_authoring_definition(
    definition: dict[str, Any], owner_user_id: int
) -> dict[str, Any]:
    authored = deepcopy(definition)
    steps = {step["key"]: step for step in authored["steps"]}
    steps["sync_connector"]["config"]["connector_id"] = "1"
    steps["triage_items"]["config"]["agent_id"] = "agent-1"
    steps["notify_owner"]["config"]["recipients"] = [str(owner_user_id)]
    authored["runtime"] = {
        "concurrency_policy": "skip_if_running",
        "timeout_seconds": 1800,
        "budget_limit_cents": 100,
        "redaction_policy": "default",
    }
    return authored


def _weekly_authoring_definition(
    definition: dict[str, Any], owner_user_id: int
) -> dict[str, Any]:
    authored = deepcopy(definition)
    steps = {step["key"]: step for step in authored["steps"]}
    steps["run_extract"]["config"]["template_id"] = "weekly"
    steps["run_extract"]["config"]["collection_id"] = "1"
    steps["notify_owner"]["config"]["recipients"] = [str(owner_user_id)]
    authored["runtime"] = {
        "concurrency_policy": "skip_if_running",
        "timeout_seconds": 1800,
        "budget_limit_cents": 100,
        "redaction_policy": "default",
    }
    return authored


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
    assert steps["connector.sync"]["enabled"] is True
    assert steps["connector.sync"]["required_permissions"] == ["connectors:sync"]
    assert steps["extract.run_template"]["enabled"] is True


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
    assert template["required_placeholders"] == [
        "collection_id",
        "agent_id",
        "owner_user_id",
    ]
    assert template["builder_category"] == "RAG"
    assert template["available_for_authoring"] is True
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
    missing_extract_target_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=_definition_with_step(
            {
                "key": "extract",
                "type": "extract.run_template",
                "name": "Extract",
                "config": {
                    "template_id": "template-1",
                    "document_source": "rag_filter",
                },
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

    missing_extract_target_error = missing_extract_target_response.json()["errors"][0]
    assert missing_extract_target_response.json()["success"] is False
    assert missing_extract_target_error["code"] == "missing_step_config"
    assert missing_extract_target_error["path"] == "steps[0].config.collection_id"


@pytest.mark.asyncio
async def test_templates_expose_availability_and_raw_placeholder_publish_blocks(
    builder_client: AsyncClient,
) -> None:
    nightly_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/nightly-rag-summary"
    )
    connector_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/connector-intake-triage"
    )
    weekly_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/weekly-extraction-report"
    )
    nightly_definition = nightly_response.json()["template"]["definition"]
    connector = connector_response.json()["template"]
    weekly = weekly_response.json()["template"]
    connector_definition = connector["definition"]

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
    assert validate_response.json()["success"] is False
    assert any(
        error["code"] == "unresolved_placeholder"
        for error in validate_response.json()["errors"]
    )
    assert connector["available_for_authoring"] is True
    assert weekly["available_for_authoring"] is True
    assert weekly["required_placeholders"] == [
        "template_id",
        "collection_id",
        "owner_user_id",
    ]
    assert create_response.status_code == 201
    assert publish_response.status_code == 422
    publish_errors = publish_response.json()["detail"]["errors"]
    assert any(error["code"] == "unresolved_placeholder" for error in publish_errors)


@pytest.mark.asyncio
async def test_nightly_template_authoring_payload_publishes_enables_and_runs(
    builder_client: AsyncClient,
    test_user,
) -> None:
    template_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/nightly-rag-summary"
    )
    definition = _nightly_authoring_definition(
        template_response.json()["template"]["definition"],
        int(test_user["id"]),
    )

    validate_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=definition,
    )
    create_response = await builder_client.post(
        "/api-internal/v1/workflows/",
        json={
            "name": "Nightly RAG Summary",
            "description": "Authoring test",
            "tags": ["rag", "schedule"],
            "metadata": {"template_id": "nightly-rag-summary"},
            "definition": definition,
        },
    )
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={"reason": "authoring test"},
    )
    enable_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable",
        json={"reason": "authoring test"},
    )
    run_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={"input_data": {"query": "recent documents"}},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["success"] is True
    assert create_response.status_code == 201
    assert publish_response.status_code == 200
    assert publish_response.json()["workflow"]["latest_version_number"] == 1
    assert enable_response.status_code == 200
    assert enable_response.json()["workflow"]["status"] == "active"
    assert run_response.status_code == 201
    assert run_response.json()["run"]["id"]


@pytest.mark.asyncio
async def test_connector_template_authoring_payload_publishes_enables_and_runs(
    builder_client: AsyncClient,
    test_user,
) -> None:
    template_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/connector-intake-triage"
    )
    definition = _connector_authoring_definition(
        template_response.json()["template"]["definition"],
        int(test_user["id"]),
    )

    validate_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=definition,
    )
    create_response = await builder_client.post(
        "/api-internal/v1/workflows/",
        json={
            "name": "Connector Intake Triage",
            "description": "Authoring test",
            "tags": ["connector", "agent"],
            "metadata": {"template_id": "connector-intake-triage"},
            "definition": definition,
        },
    )
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={"reason": "authoring test"},
    )
    enable_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable",
        json={"reason": "authoring test"},
    )
    run_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["success"] is True
    assert create_response.status_code == 201
    assert publish_response.status_code == 200
    assert publish_response.json()["workflow"]["latest_version_number"] == 1
    assert enable_response.status_code == 200
    assert enable_response.json()["workflow"]["status"] == "active"
    assert run_response.status_code == 201
    assert run_response.json()["run"]["id"]


@pytest.mark.asyncio
async def test_weekly_extract_template_authoring_payload_publishes_enables_and_runs(
    builder_client: AsyncClient,
    test_user,
) -> None:
    template_response = await builder_client.get(
        "/api-internal/v1/workflows/templates/weekly-extraction-report"
    )
    definition = _weekly_authoring_definition(
        template_response.json()["template"]["definition"],
        int(test_user["id"]),
    )

    validate_response = await builder_client.post(
        "/api-internal/v1/workflows/steps/validate",
        json=definition,
    )
    create_response = await builder_client.post(
        "/api-internal/v1/workflows/",
        json={
            "name": "Weekly Extraction Report",
            "description": "Authoring test",
            "tags": ["extract", "schedule"],
            "metadata": {"template_id": "weekly-extraction-report"},
            "definition": definition,
        },
    )
    workflow_id = create_response.json()["workflow"]["id"]
    publish_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish",
        json={"reason": "authoring test"},
    )
    enable_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable",
        json={"reason": "authoring test"},
    )
    run_response = await builder_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/runs",
        json={},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["success"] is True
    assert create_response.status_code == 201
    assert publish_response.status_code == 200
    assert publish_response.json()["workflow"]["latest_version_number"] == 1
    assert enable_response.status_code == 200
    assert enable_response.json()["workflow"]["status"] == "active"
    assert run_response.status_code == 201
    assert run_response.json()["run"]["id"]
