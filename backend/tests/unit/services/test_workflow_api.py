"""Tests for internal workflow lifecycle API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import get_current_user
from app.db.database import get_db
from app.main import app
from app.models.audit_log import AuditLog


def _workflow_payload(name: str = "Nightly summary") -> dict:
    return {
        "name": name,
        "definition": {
            "steps": [
                {
                    "key": "query",
                    "type": "rag.query",
                    "name": "Query collection",
                    "config": {"collection_id": "collection-1"},
                }
            ]
        },
    }


@pytest_asyncio.fixture
async def workflow_client(test_db, test_user):
    actor = {
        "id": int(test_user["id"]),
        "email": test_user["email"],
        "username": test_user["username"],
        "is_superuser": False,
        "is_active": True,
        "role": "user",
        "permissions": [],
    }

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


@pytest.mark.asyncio
async def test_workflow_lifecycle_api_creates_publishes_and_toggles(
    workflow_client, test_db
) -> None:
    create_response = await workflow_client.post(
        "/api-internal/v1/workflows/", json=_workflow_payload()
    )
    assert create_response.status_code == 201
    workflow_id = create_response.json()["workflow"]["id"]

    publish_response = await workflow_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/publish", json={}
    )
    enable_response = await workflow_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/enable", json={}
    )
    disable_response = await workflow_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/disable", json={}
    )
    list_response = await workflow_client.get("/api-internal/v1/workflows/")

    assert publish_response.status_code == 200
    assert publish_response.json()["workflow"]["latest_version_number"] == 1
    assert enable_response.json()["workflow"]["status"] == "active"
    assert disable_response.json()["workflow"]["status"] == "disabled"
    assert list_response.json()["total"] == 1

    audit_result = await test_db.execute(
        select(AuditLog).where(AuditLog.resource_id == workflow_id)
    )
    actions = {entry.action for entry in audit_result.scalars().all()}
    assert {
        "workflow_create",
        "workflow_publish",
        "workflow_enable",
        "workflow_disable",
    }.issubset(actions)


@pytest.mark.asyncio
async def test_workflow_api_validation_and_catalog(workflow_client) -> None:
    invalid_response = await workflow_client.post(
        "/api-internal/v1/workflows/validate", json={"steps": []}
    )
    catalog_response = await workflow_client.get("/api-internal/v1/workflows/catalog")
    templates_response = await workflow_client.get(
        "/api-internal/v1/workflows/templates"
    )

    assert invalid_response.status_code == 200
    assert invalid_response.json()["success"] is False
    assert catalog_response.status_code == 200
    assert len(catalog_response.json()["steps"]) >= 4
    assert templates_response.status_code == 200
    assert len(templates_response.json()["templates"]) >= 3


@pytest.mark.asyncio
async def test_workflow_api_archive_hides_default_list(workflow_client) -> None:
    create_response = await workflow_client.post(
        "/api-internal/v1/workflows/", json=_workflow_payload()
    )
    workflow_id = create_response.json()["workflow"]["id"]

    archive_response = await workflow_client.post(
        f"/api-internal/v1/workflows/{workflow_id}/archive", json={}
    )
    list_response = await workflow_client.get("/api-internal/v1/workflows/")
    archived_list_response = await workflow_client.get(
        "/api-internal/v1/workflows/?include_archived=true"
    )

    assert archive_response.status_code == 200
    assert archive_response.json()["workflow"]["status"] == "archived"
    assert list_response.json()["total"] == 0
    assert archived_list_response.json()["total"] == 1
