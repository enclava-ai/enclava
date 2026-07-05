"""Tests for workflow persistence models."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.workflow import (
    WorkflowArtifact,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowTrigger,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowDefinitionDocument,
    WorkflowTriggerDefinition,
    WorkflowTriggerType,
)


def _definition(collection_id: str = "collection-1") -> WorkflowDefinitionDocument:
    return WorkflowDefinitionDocument(
        trigger=WorkflowTriggerDefinition(
            type=WorkflowTriggerType.SCHEDULE,
            cron="0 2 * * *",
            timezone="UTC",
        ),
        steps=[
            {
                "key": "query",
                "type": "rag.query",
                "name": "Query collection",
                "config": {"collection_id": collection_id},
            }
        ],
    )


@pytest.mark.asyncio
async def test_workflow_definition_version_and_trigger_relationships(test_db) -> None:
    definition = _definition()
    workflow = WorkflowDefinition(
        name="Nightly summary",
        created_by="1",
        owner_user_id=None,
        draft_definition=definition.model_dump(mode="json"),
        steps=[step.model_dump(mode="json") for step in definition.steps],
        tags=["rag"],
        status="draft",
    )
    version = WorkflowVersion(
        workflow=workflow,
        version_number=1,
        status="published",
        definition=definition.model_dump(mode="json"),
        definition_checksum="a" * 64,
    )
    trigger = WorkflowTrigger(
        workflow=workflow,
        version=version,
        trigger_type="schedule",
        cron_expression="0 2 * * *",
        timezone="UTC",
        misfire_policy="run_once",
        config=definition.trigger.model_dump(mode="json"),
    )

    test_db.add(workflow)
    test_db.add(version)
    test_db.add(trigger)
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowDefinition).options(
            selectinload(WorkflowDefinition.versions),
            selectinload(WorkflowDefinition.triggers),
        )
    )
    persisted = result.scalar_one()

    assert persisted.id
    assert persisted.versions[0].definition["steps"][0]["type"] == "rag.query"
    assert persisted.triggers[0].trigger_type == "schedule"
    assert persisted.tags == ["rag"]


@pytest.mark.asyncio
async def test_run_step_artifact_and_event_contracts_can_be_persisted(test_db) -> None:
    definition = _definition()
    workflow = WorkflowDefinition(
        name="Nightly summary",
        created_by="1",
        draft_definition=definition.model_dump(mode="json"),
        steps=[step.model_dump(mode="json") for step in definition.steps],
        status="active",
        is_active=True,
    )
    version = WorkflowVersion(
        workflow=workflow,
        version_number=1,
        status="published",
        definition=definition.model_dump(mode="json"),
        definition_checksum="b" * 64,
    )
    trigger = WorkflowTrigger(
        workflow=workflow,
        version=version,
        trigger_type="manual",
        config={"type": "manual"},
        enabled=True,
    )
    run = WorkflowRun(
        workflow=workflow,
        version=version,
        trigger=trigger,
        status="queued",
        trigger_type="manual",
    )
    step_run = WorkflowStepRun(
        run=run,
        step_key="query",
        step_type="rag.query",
        status="pending",
    )
    artifact = WorkflowArtifact(
        run=run,
        step_run=step_run,
        artifact_type="summary",
        name="Summary",
        data={"summary": "ok"},
    )
    event = WorkflowEvent(
        workflow=workflow,
        version=version,
        run=run,
        step_run=step_run,
        event_type="run_queued",
        message="Run queued",
    )

    test_db.add_all([workflow, version, trigger, run, step_run, artifact, event])
    await test_db.commit()

    result = await test_db.execute(
        select(WorkflowRun).options(
            selectinload(WorkflowRun.step_runs),
            selectinload(WorkflowRun.artifacts),
            selectinload(WorkflowRun.events),
        )
    )
    persisted = result.scalar_one()

    assert persisted.step_runs[0].step_key == "query"
    assert persisted.artifacts[0].data == {"summary": "ok"}
    assert persisted.events[0].event_type == "run_queued"
