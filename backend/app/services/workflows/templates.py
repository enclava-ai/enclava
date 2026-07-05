"""Workflow template seed definitions."""

from __future__ import annotations

from app.schemas.workflow import (
    WorkflowDefinitionDocument,
    WorkflowTemplate,
    WorkflowTriggerDefinition,
    WorkflowTriggerType,
)

NIGHTLY_RAG_SUMMARY_TEMPLATE = WorkflowTemplate(
    id="nightly-rag-summary",
    name="Nightly RAG Summary",
    description="Summarize new RAG documents on a nightly schedule.",
    tags=["rag", "agent", "schedule"],
    required_placeholders=["collection_id", "agent_id", "owner_user_id"],
    builder_category="RAG",
    available_for_authoring=True,
    definition=WorkflowDefinitionDocument(
        trigger=WorkflowTriggerDefinition(
            type=WorkflowTriggerType.SCHEDULE,
            cron="0 2 * * *",
            timezone="UTC",
        ),
        metadata={"template": "nightly-rag-summary"},
        steps=[
            {
                "key": "find_new_docs",
                "type": "rag.query",
                "name": "Find new documents",
                "config": {
                    "collection_id": "{{collection_id}}",
                    "query": "{{query}}",
                    "since": {"type": "last_successful_run"},
                    "limit": 25,
                },
                "retry": {"max_attempts": 2, "backoff_seconds": 60},
            },
            {
                "key": "skip_if_empty",
                "type": "condition.no_results_skip",
                "name": "Skip when nothing changed",
                "depends_on": ["find_new_docs"],
                "config": {"input_step_key": "find_new_docs", "path": "documents"},
                "retry": {"max_attempts": 1},
            },
            {
                "key": "summarize",
                "type": "agent.run",
                "name": "Summarize changes",
                "depends_on": ["skip_if_empty"],
                "config": {
                    "agent_id": "{{agent_id}}",
                    "prompt_template": (
                        "Summarize the new documents for an operations digest."
                    ),
                    "input_mapping": {"documents": "find_new_docs.documents"},
                },
                "retry": {"max_attempts": 1},
            },
            {
                "key": "notify_owner",
                "type": "notify.in_app",
                "name": "Notify owner",
                "depends_on": ["summarize"],
                "config": {
                    "recipients": ["{{owner_user_id}}"],
                    "title_template": "Nightly RAG summary ready",
                    "body_template": "{{summarize.message}}",
                    "severity": "info",
                },
                "retry": {"max_attempts": 2, "backoff_seconds": 30},
            },
        ],
    ),
)

CONNECTOR_INTAKE_TRIAGE_TEMPLATE = WorkflowTemplate(
    id="connector-intake-triage",
    name="Connector Intake Triage",
    description="Sync a connector and triage newly ingested records.",
    tags=["connector", "rag", "agent"],
    required_placeholders=["connector_id", "agent_id", "owner_user_id"],
    builder_category="Connector",
    available_for_authoring=True,
    definition=WorkflowDefinitionDocument(
        trigger=WorkflowTriggerDefinition(type=WorkflowTriggerType.MANUAL),
        metadata={"template": "connector-intake-triage"},
        steps=[
            {
                "key": "sync_connector",
                "type": "connector.sync",
                "name": "Sync connector",
                "config": {
                    "connector_id": "{{connector_id}}",
                    "since": "connector_checkpoint",
                    "max_records": 50,
                },
                "retry": {"max_attempts": 2, "backoff_seconds": 120},
            },
            {
                "key": "triage_items",
                "type": "agent.run",
                "name": "Triage new items",
                "depends_on": ["sync_connector"],
                "config": {
                    "agent_id": "{{agent_id}}",
                    "prompt_template": "Classify and prioritize newly synced items.",
                    "input_mapping": {"items": "sync_connector.items"},
                },
            },
            {
                "key": "notify_owner",
                "type": "notify.in_app",
                "name": "Notify owner",
                "depends_on": ["triage_items"],
                "config": {
                    "recipients": ["{{owner_user_id}}"],
                    "title_template": "Connector triage complete",
                    "body_template": "{{triage_items.message}}",
                    "severity": "info",
                },
            },
        ],
    ),
)

WEEKLY_EXTRACTION_REPORT_TEMPLATE = WorkflowTemplate(
    id="weekly-extraction-report",
    name="Weekly Extraction Report",
    description="Run an Extract template over weekly documents and notify the owner.",
    tags=["extract", "schedule"],
    required_placeholders=["template_id", "collection_id", "owner_user_id"],
    builder_category="Extract",
    available_for_authoring=True,
    definition=WorkflowDefinitionDocument(
        trigger=WorkflowTriggerDefinition(
            type=WorkflowTriggerType.SCHEDULE,
            cron="0 8 * * 1",
            timezone="UTC",
        ),
        metadata={"template": "weekly-extraction-report"},
        steps=[
            {
                "key": "run_extract",
                "type": "extract.run_template",
                "name": "Run extraction template",
                "config": {
                    "template_id": "{{template_id}}",
                    "document_source": "rag_filter",
                    "collection_id": "{{collection_id}}",
                    "since": "last_successful_run",
                    "max_documents": 25,
                },
                "retry": {"max_attempts": 1},
            },
            {
                "key": "notify_owner",
                "type": "notify.in_app",
                "name": "Notify owner",
                "depends_on": ["run_extract"],
                "config": {
                    "recipients": ["{{owner_user_id}}"],
                    "title_template": "Weekly extraction report ready",
                    "body_template": "{{run_extract.summary}}",
                    "severity": "info",
                },
            },
        ],
    ),
)

_TEMPLATES: dict[str, WorkflowTemplate] = {
    NIGHTLY_RAG_SUMMARY_TEMPLATE.id: NIGHTLY_RAG_SUMMARY_TEMPLATE,
    CONNECTOR_INTAKE_TRIAGE_TEMPLATE.id: CONNECTOR_INTAKE_TRIAGE_TEMPLATE,
    WEEKLY_EXTRACTION_REPORT_TEMPLATE.id: WEEKLY_EXTRACTION_REPORT_TEMPLATE,
}


def list_workflow_templates() -> list[WorkflowTemplate]:
    """Return workflow template seeds as deep copies."""
    return [
        template.model_copy(deep=True)
        for _, template in sorted(_TEMPLATES.items(), key=lambda item: item[0])
    ]


def get_workflow_template(template_id: str) -> WorkflowTemplate:
    """Return a workflow template seed by id."""
    try:
        return _TEMPLATES[template_id].model_copy(deep=True)
    except KeyError as exc:
        raise KeyError(f"Unknown workflow template: {template_id}") from exc
