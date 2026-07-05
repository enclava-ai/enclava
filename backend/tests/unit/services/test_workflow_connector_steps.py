"""Tests for connector workflow step execution."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.connector_source import ConnectorSource, ConnectorStatus, ConnectorType
from app.models.rag_collection import RagCollection
from app.models.rag_document import RagDocument
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowRunStatus,
    WorkflowStepDefinition,
    WorkflowStepRunStatus,
)
from app.services.connector_sync_service import ConnectorSyncService
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowService,
)
from app.services.workflows.steps import (
    ConnectorSyncHandler,
    WorkflowStepContext,
    WorkflowStepExecutionError,
)


class StubConnectorSyncService(ConnectorSyncService):
    """Connector sync service with external fetching replaced by a DB insert."""

    async def _do_sync(
        self,
        connector: ConnectorSource,
        job: Any,
        *,
        created_documents: list[RagDocument] | None = None,
    ) -> tuple[int, int]:
        document = RagDocument(
            collection_id=connector.collection_id,
            filename="doc-1.md",
            original_filename="Doc 1",
            file_path="",
            file_type="md",
            file_size=12,
            mime_type="text/markdown",
            source_url="https://example.com/doc-1",
            status="indexed",
            converted_content="Connector document content",
            word_count=3,
            character_count=26,
            vector_count=1,
            document_metadata={"title": "Doc 1"},
            connector_source_id=connector.id,
            external_id="doc-1",
            external_updated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
            indexed_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
            processed_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        )
        self.db.add(document)
        await self.db.flush()
        if created_documents is not None:
            created_documents.append(document)
        return 1, 0


class FakeConnectorService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def run_sync_for_workflow(
        self, *, connector_id: int, max_records: int
    ) -> dict[str, Any]:
        self.calls.append({"connector_id": connector_id, "max_records": max_records})
        return self.response


def _actor(user_id: int) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": [],
    }


def _definition(step: dict[str, Any]) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        steps=[
            {
                "key": "sync",
                "type": "connector.sync",
                "name": "Sync connector",
                "config": step,
                "retry": {"max_attempts": 1},
            }
        ]
    )


async def _published_workflow(
    test_db, actor: dict[str, Any], definition: WorkflowDefinitionDocument
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Connector workflow",
            definition=definition,
        ),
        actor,
    )
    await lifecycle.publish_definition(test_db, created.id, actor)
    await test_db.commit()
    return created


async def _queued_run(
    test_db,
    actor: dict[str, Any],
    definition: WorkflowDefinitionDocument,
    runtime: WorkflowRuntimeService,
):
    workflow = await _published_workflow(test_db, actor, definition)
    run = await runtime.create_manual_run(
        test_db,
        workflow.id,
        WorkflowManualRunRequest(input_data={}),
        actor,
    )
    await test_db.commit()
    return run


@pytest.mark.asyncio
async def test_connector_workflow_sync_adapter_returns_safe_document_output(
    test_db, test_user
) -> None:
    collection = RagCollection(
        name="Connector Collection",
        qdrant_collection_name="connector_collection",
        owner_user_id=int(test_user["id"]),
    )
    test_db.add(collection)
    await test_db.flush()
    connector = ConnectorSource(
        name="Engineering Notion",
        connector_type=ConnectorType.NOTION.value,
        collection_id=collection.id,
        config={},
        encrypted_credentials="secret-token",
        sync_frequency="PT1H",
        status=ConnectorStatus.ACTIVE.value,
        created_by_user_id=int(test_user["id"]),
    )
    test_db.add(connector)
    await test_db.flush()

    result = await StubConnectorSyncService(test_db).run_sync_for_workflow(
        connector.id,
        max_records=10,
    )
    output = result.to_workflow_output()

    assert output["connector_id"] == connector.id
    assert output["connector_name"] == "Engineering Notion"
    assert output["docs_indexed"] == 1
    assert output["docs_failed"] == 0
    assert output["documents"][0]["title"] == "Doc 1"
    assert output["documents"][0]["content_preview"] == "Connector document content"
    assert "secret-token" not in str(output)
    assert "encrypted_credentials" not in str(output)


@pytest.mark.asyncio
async def test_connector_step_success_persists_output_artifact_and_event(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    connector = FakeConnectorService(
        {
            "job_id": 42,
            "connector_id": 7,
            "connector_name": "GitHub Issues",
            "connector_type": "github",
            "collection_id": 3,
            "status": "success",
            "docs_indexed": 2,
            "docs_failed": 0,
            "documents": [
                {"document_id": 101, "title": "Issue 101"},
                {"document_id": 102, "title": "Issue 102"},
            ],
        }
    )
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(connector_service=connector)
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            {
                "connector_id": "7",
                "since": "connector_checkpoint",
                "max_records": 2,
            }
        ),
        runtime,
    )

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert connector.calls == [{"connector_id": 7, "max_records": 2}]
    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert reloaded.steps[0].status == WorkflowStepRunStatus.SUCCEEDED
    output = reloaded.output_data.value["outputs"]["sync"]
    assert output["count"] == 2
    assert output["items"][0]["title"] == "Issue 101"
    assert reloaded.steps[0].artifacts[0].artifact_type == "json"
    assert {event.event_type for event in reloaded.events}.issuperset(
        {"connector_sync_completed"}
    )


@pytest.mark.asyncio
async def test_connector_step_failed_sync_marks_step_and_run_failed(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    connector = FakeConnectorService(
        {
            "job_id": 43,
            "connector_id": 7,
            "status": "failed",
            "docs_indexed": 0,
            "docs_failed": 0,
            "error_message": "token expired",
            "documents": [],
        }
    )
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(connector_service=connector)
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition({"connector_id": "7"}),
        runtime,
    )

    with pytest.raises(WorkflowStepExecutionError, match="token expired"):
        await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, queued.id, actor)

    assert reloaded.status == WorkflowRunStatus.FAILED
    assert reloaded.steps[0].status == WorkflowStepRunStatus.FAILED
    assert "connector sync failed for connector 7" in reloaded.steps[0].error


@pytest.mark.asyncio
async def test_connector_step_requires_connector_id(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    connector = FakeConnectorService({"status": "success", "documents": []})
    definition = _definition({"connector_id": ""})
    step = WorkflowStepDefinition(
        key="sync",
        type="connector.sync",
        name="Sync connector",
        config={"connector_id": ""},
    )
    context = WorkflowStepContext(
        db=test_db,
        run=SimpleNamespace(id="run-1", workflow=None),
        definition=definition,
        step=step,
        previous_outputs={},
        dependencies=WorkflowRuntimeDependencies(connector_service=connector),
        actor=actor,
    )

    with pytest.raises(WorkflowStepExecutionError, match="connector_id is required"):
        await ConnectorSyncHandler().execute(context)
    assert connector.calls == []
