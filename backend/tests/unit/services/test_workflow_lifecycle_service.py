"""Tests for workflow lifecycle service."""

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.workflow import WorkflowDefinition, WorkflowVersion
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowDefinitionStatus,
    WorkflowDefinitionUpdate,
)
from app.services.workflows import WorkflowService, WorkflowValidationError


def _actor(user_id: int, *, admin: bool = False) -> dict:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "is_superuser": admin,
        "role": "admin" if admin else "user",
        "permissions": ["*"] if admin else [],
    }


def _definition(collection_id: str = "collection-1") -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        steps=[
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query collection",
                "config": {"collection_id": collection_id},
            }
        ]
    )


def _create_payload(name: str = "Nightly summary") -> WorkflowDefinitionCreate:
    return WorkflowDefinitionCreate(name=name, definition=_definition())


@pytest.mark.asyncio
async def test_publish_creates_immutable_versions(test_db, test_user) -> None:
    service = WorkflowService()
    actor = _actor(int(test_user["id"]))

    created = await service.create_definition(test_db, _create_payload(), actor)
    await test_db.commit()

    published_v1 = await service.publish_definition(test_db, created.id, actor)
    await test_db.commit()

    await service.update_definition(
        test_db,
        created.id,
        WorkflowDefinitionUpdate(definition=_definition("collection-2")),
        actor,
    )
    await test_db.commit()
    published_v2 = await service.publish_definition(test_db, created.id, actor)
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == created.id)
        .order_by(WorkflowVersion.version_number)
    )
    versions = result.scalars().all()

    assert published_v1.latest_version_number == 1
    assert published_v2.latest_version_number == 2
    assert (
        versions[0].definition["steps"][0]["config"]["collection_id"] == "collection-1"
    )
    assert (
        versions[1].definition["steps"][0]["config"]["collection_id"] == "collection-2"
    )


@pytest.mark.asyncio
async def test_admin_publish_records_actor_on_version(test_db, test_user) -> None:
    service = WorkflowService()
    owner = _actor(int(test_user["id"]))
    admin_user = User(
        email="admin@example.com",
        username="admin",
        hashed_password="test",
        is_active=True,
        is_superuser=True,
    )
    test_db.add(admin_user)
    await test_db.flush()
    admin = _actor(int(admin_user.id), admin=True)

    created = await service.create_definition(test_db, _create_payload(), owner)
    await test_db.commit()
    await service.publish_definition(test_db, created.id, admin)
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowVersion).where(WorkflowVersion.workflow_id == created.id)
    )
    version = result.scalar_one()

    assert version.created_by_user_id == admin_user.id
    assert version.published_by_user_id == admin_user.id


@pytest.mark.asyncio
async def test_enable_requires_publish(test_db, test_user) -> None:
    service = WorkflowService()
    actor = _actor(int(test_user["id"]))
    created = await service.create_definition(test_db, _create_payload(), actor)

    with pytest.raises(WorkflowValidationError, match="published before enabling"):
        await service.enable_definition(test_db, created.id, actor)


@pytest.mark.asyncio
async def test_list_filters_by_owner_unless_admin(test_db, test_user) -> None:
    service = WorkflowService()
    owner = _actor(int(test_user["id"]))
    other_user = User(
        email="other@example.com",
        username="other",
        hashed_password="test",
        is_active=True,
    )
    test_db.add(other_user)
    await test_db.flush()
    other = _actor(int(other_user.id))

    await service.create_definition(test_db, _create_payload("Owner workflow"), owner)
    await service.create_definition(test_db, _create_payload("Other workflow"), other)
    await test_db.commit()

    owner_visible = await service.list_definitions(test_db, owner)
    admin_visible = await service.list_definitions(
        test_db, _actor(int(test_user["id"]), admin=True)
    )

    assert [workflow.name for workflow in owner_visible] == ["Owner workflow"]
    assert {workflow.name for workflow in admin_visible} == {
        "Owner workflow",
        "Other workflow",
    }


@pytest.mark.asyncio
async def test_workflow_manage_permission_allows_cross_owner_access(
    test_db, test_user
) -> None:
    service = WorkflowService()
    owner = _actor(int(test_user["id"]))
    manager = {**owner, "permissions": ["workflow.manage"]}
    other_user = User(
        email="other-manager-case@example.com",
        username="other-manager-case",
        hashed_password="test",
        is_active=True,
    )
    test_db.add(other_user)
    await test_db.flush()
    other = _actor(int(other_user.id))

    owner_workflow = await service.create_definition(
        test_db, _create_payload("Owner workflow"), owner
    )
    other_workflow = await service.create_definition(
        test_db, _create_payload("Other workflow"), other
    )
    await test_db.commit()

    manager_visible = await service.list_definitions(test_db, manager)
    updated = await service.update_definition(
        test_db,
        other_workflow.id,
        WorkflowDefinitionUpdate(name="Managed workflow"),
        manager,
    )
    await test_db.commit()

    assert {workflow.id for workflow in manager_visible} == {
        owner_workflow.id,
        other_workflow.id,
    }
    assert updated.name == "Managed workflow"


@pytest.mark.asyncio
async def test_archive_hides_workflow_and_writes_audit(test_db, test_user) -> None:
    service = WorkflowService()
    actor = _actor(int(test_user["id"]))
    created = await service.create_definition(test_db, _create_payload(), actor)
    await test_db.commit()

    archived = await service.archive_definition(test_db, created.id, actor)
    await test_db.commit()
    visible = await service.list_definitions(test_db, actor)

    audit_result = await test_db.execute(
        select(AuditLog).where(AuditLog.resource_id == created.id)
    )
    actions = {entry.action for entry in audit_result.scalars().all()}

    assert archived.status == WorkflowDefinitionStatus.ARCHIVED
    assert visible == []
    assert {"workflow_create", "workflow_archive"}.issubset(actions)


@pytest.mark.asyncio
async def test_enable_and_disable_toggle_current_trigger(test_db, test_user) -> None:
    service = WorkflowService()
    actor = _actor(int(test_user["id"]))
    created = await service.create_definition(test_db, _create_payload(), actor)
    await service.publish_definition(test_db, created.id, actor)
    enabled = await service.enable_definition(test_db, created.id, actor)
    disabled = await service.disable_definition(test_db, created.id, actor)
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == created.id)
    )
    workflow = result.scalar_one()

    assert enabled.status == WorkflowDefinitionStatus.ACTIVE
    assert disabled.status == WorkflowDefinitionStatus.DISABLED
    assert workflow.is_active is False
