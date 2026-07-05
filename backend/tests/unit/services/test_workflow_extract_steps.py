"""Tests for Extract workflow step execution."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from app.db.database import utc_now
from app.models.extract_result import ExtractResult
from app.models.extract_template import ExtractTemplate
from app.models.rag_collection import RagCollection
from app.models.rag_document import RagDocument
from app.models.workflow import WorkflowRun
from app.modules.extract.services.extract_service import ExtractService
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionDocument,
    WorkflowManualRunRequest,
    WorkflowRunStatus,
    WorkflowStepRunStatus,
)
from app.services.workflows import (
    WorkflowRuntimeDependencies,
    WorkflowRuntimeService,
    WorkflowService,
)
from app.services.workflows.steps import WorkflowStepExecutionError


class FakeConnectorService:
    async def run_sync_for_workflow(
        self, *, connector_id: int, max_records: int
    ) -> dict[str, Any]:
        return {
            "job_id": 11,
            "connector_id": connector_id,
            "connector_name": "Docs",
            "status": "success",
            "docs_indexed": 1,
            "docs_failed": 0,
            "documents": [
                {
                    "document_id": 101,
                    "title": "Launch notes",
                    "source_url": "https://example.com/launch",
                    "content_preview": "Launch notes content",
                }
            ],
        }


class FakeExtractService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def run_template_for_workflow(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def _actor(user_id: int) -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"user-{user_id}@example.com",
        "role": "user",
        "permissions": [],
    }


def _definition(steps: list[dict[str, Any]]) -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(steps=steps)


async def _published_workflow(
    test_db, actor: dict[str, Any], definition: WorkflowDefinitionDocument
):
    lifecycle = WorkflowService()
    created = await lifecycle.create_definition(
        test_db,
        WorkflowDefinitionCreate(
            name="Extract workflow",
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


def _extract_success_response() -> dict[str, Any]:
    return {
        "success": True,
        "job_id": "job-1",
        "template_id": "weekly",
        "status": "completed",
        "summary": "Report ready",
        "document_count": 1,
        "result": {"summary": "Report ready"},
        "validation_errors": [],
        "validation_warnings": [],
        "cost_cents": 3,
        "model_used": "gpt-4o",
    }


@pytest.mark.asyncio
async def test_extract_adapter_persists_job_and_result(
    test_db, test_user, monkeypatch
) -> None:
    template = ExtractTemplate(
        id="weekly",
        description="Weekly report",
        system_prompt="Extract a report.",
        user_prompt="Return JSON with a summary.",
        output_schema=None,
        context_schema=None,
        is_default=False,
        is_active=True,
    )
    test_db.add(template)
    await test_db.flush()

    service = ExtractService()

    async def fake_model(*args: Any, **kwargs: Any) -> str:
        return "gpt-4o"

    async def fake_completion(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"summary":"Adapter ready"}')
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )

    monkeypatch.setattr(service, "_get_model_for_processing", fake_model)
    monkeypatch.setattr(
        "app.modules.extract.services.extract_service.llm_service.create_chat_completion",
        fake_completion,
    )

    result = await service.run_template_for_workflow(
        test_db,
        template_id="weekly",
        documents=[{"title": "Doc", "content": "Important content"}],
        context={"team": "ops"},
        current_user={"id": int(test_user["id"])},
        workflow_run_id="run-1",
        step_key="extract",
    )

    rows = await test_db.execute(select(ExtractResult))
    saved_result = rows.scalar_one()
    assert result["job_id"]
    assert result["status"] == "completed_with_errors"
    assert result["summary"] == "Adapter ready"
    assert saved_result.parsed_data == {"summary": "Adapter ready"}


@pytest.mark.asyncio
async def test_extract_step_uses_previous_step_documents(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    extract = FakeExtractService(_extract_success_response())
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            connector_service=FakeConnectorService(),
            extract_service=extract,
        )
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            [
                {
                    "key": "sync",
                    "type": "connector.sync",
                    "name": "Sync",
                    "config": {"connector_id": "7"},
                },
                {
                    "key": "extract",
                    "type": "extract.run_template",
                    "name": "Extract",
                    "depends_on": ["sync"],
                    "config": {
                        "template_id": "weekly",
                        "document_source": "previous_step",
                        "input_step_key": "sync",
                        "path": "items",
                    },
                },
            ]
        ),
        runtime,
    )

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert extract.calls[0]["documents"][0]["title"] == "Launch notes"
    assert reloaded.status == WorkflowRunStatus.SUCCEEDED
    assert reloaded.steps[-1].status == WorkflowStepRunStatus.SUCCEEDED
    output = reloaded.output_data.value["outputs"]["extract"]
    assert output["summary"] == "Report ready"
    assert output["cost_cents"] == 3
    assert reloaded.steps[-1].artifacts[0].artifact_type == "extract_result"


@pytest.mark.asyncio
async def test_extract_step_uses_rag_filter_documents(test_db, test_user) -> None:
    actor = _actor(int(test_user["id"]))
    now = utc_now()
    cutoff = now - timedelta(days=1)
    collection = RagCollection(
        name="Weekly docs",
        qdrant_collection_name="weekly_docs",
        owner_user_id=int(test_user["id"]),
    )
    test_db.add(collection)
    await test_db.flush()
    test_db.add(
        RagDocument(
            collection_id=collection.id,
            filename="weekly.md",
            original_filename="Weekly",
            converted_content="Weekly document content",
            status="indexed",
            document_metadata={"title": "Weekly"},
            indexed_at=now,
        )
    )
    test_db.add(
        RagDocument(
            collection_id=collection.id,
            filename="old-weekly.md",
            original_filename="Old weekly",
            converted_content="Old weekly document content",
            status="indexed",
            document_metadata={"title": "Old weekly"},
            indexed_at=now - timedelta(days=2),
        )
    )
    await test_db.flush()
    extract = FakeExtractService(_extract_success_response())
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(extract_service=extract)
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            [
                {
                    "key": "extract",
                    "type": "extract.run_template",
                    "name": "Extract",
                    "config": {
                        "template_id": "weekly",
                        "document_source": "rag_filter",
                        "collection_id": str(collection.id),
                        "max_documents": 5,
                    },
                }
            ]
        ),
        runtime,
    )
    test_db.add(
        WorkflowRun(
            workflow_id=queued.workflow_id,
            version_id=queued.version_id,
            trigger_type="manual",
            status="succeeded",
            queued_at=cutoff,
            started_at=cutoff,
            completed_at=cutoff,
            created_at=cutoff,
            updated_at=cutoff,
        )
    )
    await test_db.flush()

    executed = await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, executed.id, actor)

    assert len(extract.calls[0]["documents"]) == 1
    assert extract.calls[0]["documents"][0]["title"] == "Weekly"
    assert extract.calls[0]["documents"][0]["content"] == "Weekly document content"
    assert reloaded.status == WorkflowRunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_extract_step_failed_execution_marks_step_and_run_failed(
    test_db, test_user
) -> None:
    actor = _actor(int(test_user["id"]))
    extract = FakeExtractService(
        {
            "success": False,
            "job_id": "job-2",
            "template_id": "weekly",
            "status": "failed",
            "error_message": "model unavailable",
            "document_count": 1,
            "result": {},
        }
    )
    runtime = WorkflowRuntimeService(
        dependencies=WorkflowRuntimeDependencies(
            connector_service=FakeConnectorService(),
            extract_service=extract,
        )
    )
    queued = await _queued_run(
        test_db,
        actor,
        _definition(
            [
                {
                    "key": "sync",
                    "type": "connector.sync",
                    "name": "Sync",
                    "config": {"connector_id": "7"},
                },
                {
                    "key": "extract",
                    "type": "extract.run_template",
                    "name": "Extract",
                    "config": {
                        "template_id": "weekly",
                        "document_source": "previous_step",
                        "input_step_key": "sync",
                    },
                },
            ]
        ),
        runtime,
    )

    with pytest.raises(WorkflowStepExecutionError, match="model unavailable"):
        await runtime.execute_run(test_db, queued.id, worker_id="worker-1")
    await test_db.commit()
    reloaded = await runtime.get_run_detail(test_db, queued.id, actor)

    assert reloaded.status == WorkflowRunStatus.FAILED
    assert reloaded.steps[-1].status == WorkflowStepRunStatus.FAILED
    assert "extract template weekly failed" in reloaded.steps[-1].error
