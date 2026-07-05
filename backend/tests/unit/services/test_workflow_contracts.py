"""Tests for workflow contract scaffolding."""

import pytest
from pydantic import ValidationError

from app.modules.workflow.main import WorkflowModule
from app.schemas.workflow import (
    WorkflowDefinitionDocument,
    WorkflowTriggerDefinition,
    WorkflowTriggerFireRequest,
    WorkflowTriggerType,
)
from app.services.workflows import WorkflowService, list_workflow_templates


def test_nightly_rag_summary_shape_validates() -> None:
    definition = WorkflowDefinitionDocument(
        trigger=WorkflowTriggerDefinition(
            type=WorkflowTriggerType.SCHEDULE,
            cron="0 2 * * *",
            timezone="UTC",
        ),
        steps=[
            {
                "key": "find_new_docs",
                "type": "rag.query",
                "name": "Find new documents",
                "config": {"collection_id": "collection-id"},
            },
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize documents",
                "depends_on": ["find_new_docs"],
                "config": {
                    "agent_id": "agent-id",
                    "prompt_template": "Summarize the new documents.",
                },
            },
        ],
    )

    assert definition.schema_version == 1
    assert definition.trigger.type == WorkflowTriggerType.SCHEDULE
    assert [step.key for step in definition.steps] == ["find_new_docs", "summarize"]


def test_duplicate_step_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate step key"):
        WorkflowDefinitionDocument(
            steps=[
                {"key": "same", "type": "rag.query", "name": "First"},
                {"key": "same", "type": "agent.run", "name": "Second"},
            ],
        )


def test_dependencies_must_reference_earlier_steps() -> None:
    with pytest.raises(ValidationError, match="unknown or later step"):
        WorkflowDefinitionDocument(
            steps=[
                {
                    "key": "summarize",
                    "type": "agent.run",
                    "name": "Summarize",
                    "depends_on": ["find_new_docs"],
                },
                {
                    "key": "find_new_docs",
                    "type": "rag.query",
                    "name": "Find new documents",
                },
            ],
        )


def test_schedule_trigger_requires_cron_and_timezone() -> None:
    with pytest.raises(ValidationError, match="schedule triggers require cron"):
        WorkflowTriggerDefinition(type=WorkflowTriggerType.SCHEDULE, timezone="UTC")

    with pytest.raises(ValidationError, match="schedule triggers require timezone"):
        WorkflowTriggerDefinition(type=WorkflowTriggerType.SCHEDULE, cron="0 2 * * *")


def test_api_and_event_triggers_require_fire_fields() -> None:
    with pytest.raises(ValidationError, match="api triggers require api_slug"):
        WorkflowTriggerDefinition(type=WorkflowTriggerType.API)

    with pytest.raises(ValidationError, match="event triggers require event_name"):
        WorkflowTriggerDefinition(type=WorkflowTriggerType.EVENT)

    request = WorkflowTriggerFireRequest(idempotency_key="  deploy-1  ")
    assert request.idempotency_key == "deploy-1"

    with pytest.raises(ValidationError, match="idempotency_key"):
        WorkflowTriggerFireRequest(idempotency_key=" ")


def test_workflow_service_exposes_default_catalog() -> None:
    service = WorkflowService()
    step_types = {entry.type for entry in service.list_step_catalog()}

    assert {
        "rag.query",
        "agent.run",
        "notify.in_app",
        "condition.no_results_skip",
    }.issubset(step_types)
    assert service.get_step_catalog("rag.query").supports_test is True


def test_workflow_templates_validate_and_are_copied() -> None:
    templates = list_workflow_templates()
    template_ids = {template.id for template in templates}

    assert {
        "nightly-rag-summary",
        "connector-intake-triage",
        "weekly-extraction-report",
    }.issubset(template_ids)

    first = list_workflow_templates()[0]
    first.name = "mutated"

    assert list_workflow_templates()[0].name != "mutated"


@pytest.mark.asyncio
async def test_workflow_module_keeps_status_and_execute_behavior() -> None:
    module = WorkflowModule()
    await module.initialize()

    status_result = await module.process_request({"action": "status"}, {})
    execute_result = await module.process_request(
        {"action": "execute", "workflow": {"id": "sample"}}, {"user": "test"}
    )
    catalog_result = await module.process_request({"action": "catalog"}, {})
    invalid_result = await module.process_request(
        {"action": "validate", "definition": {"steps": []}}, {}
    )

    assert status_result["success"] is True
    assert "registered_step_types" in status_result["stats"]
    assert execute_result["success"] is True
    assert execute_result["workflow"] == {"id": "sample"}
    assert execute_result["status"] == "completed"
    assert catalog_result["success"] is True
    assert len(catalog_result["steps"]) >= 4
    assert invalid_result["success"] is False
    assert "details" in invalid_result

    await module.cleanup()
