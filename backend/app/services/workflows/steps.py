"""Workflow step handler implementations."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import WorkflowRun
from app.schemas.workflow import WorkflowDefinitionDocument, WorkflowStepDefinition

from .service import WorkflowRuntimeDependencies


class WorkflowStepExecutionError(Exception):
    """Step handler failed with an actionable workflow error."""


@dataclass
class WorkflowStepArtifactSpec:
    """Artifact requested by a step handler."""

    artifact_type: str
    name: str
    data: Optional[dict[str, Any]] = None
    storage_uri: Optional[str] = None
    redaction_policy: Optional[str] = None


@dataclass
class WorkflowStepEventSpec:
    """Event requested by a step handler."""

    event_type: str
    message: str
    severity: str = "info"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStepResult:
    """Structured result returned by a step handler."""

    output_data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[WorkflowStepArtifactSpec] = field(default_factory=list)
    events: list[WorkflowStepEventSpec] = field(default_factory=list)
    estimated_cost_cents: int = 0
    actual_cost_cents: int = 0
    skip_remaining: bool = False
    skip_step_keys: list[str] = field(default_factory=list)
    skip_reason: Optional[str] = None


@dataclass
class WorkflowStepContext:
    """Context passed to a workflow step handler."""

    db: AsyncSession
    run: WorkflowRun
    definition: WorkflowDefinitionDocument
    step: WorkflowStepDefinition
    previous_outputs: dict[str, dict[str, Any]]
    dependencies: WorkflowRuntimeDependencies
    actor: Optional[Mapping[str, Any]] = None


class WorkflowStepHandler(Protocol):
    """Protocol implemented by workflow step handlers."""

    step_type: str

    def estimate_cost_cents(self, context: WorkflowStepContext) -> int:
        """Return a pre-execution cost estimate."""
        ...

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        """Execute the step."""
        ...


class BaseWorkflowStepHandler:
    """Base class for simple step handlers."""

    step_type: str

    def estimate_cost_cents(self, context: WorkflowStepContext) -> int:
        return 0


class NoResultsSkipHandler(BaseWorkflowStepHandler):
    """Skip remaining steps when a previous output path is empty."""

    step_type = "condition.no_results_skip"

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        input_step_key = context.step.config.get("input_step_key")
        if not input_step_key:
            raise WorkflowStepExecutionError("input_step_key is required")

        path = context.step.config.get("path")
        source = context.previous_outputs.get(input_step_key, {})
        value = _resolve_path(source, path) if path else source
        matched = _is_empty(value)
        return WorkflowStepResult(
            output_data={
                "matched": matched,
                "action": "skip_remaining" if matched else "continue",
                "input_step_key": input_step_key,
                "path": path,
            },
            events=[
                WorkflowStepEventSpec(
                    event_type="condition_evaluated",
                    message=(
                        "No results condition matched"
                        if matched
                        else "No results condition did not match"
                    ),
                    data={"matched": matched, "input_step_key": input_step_key},
                )
            ],
            skip_remaining=matched,
        )


class BranchConditionHandler(BaseWorkflowStepHandler):
    """Choose a forward-only branch by skipping configured later steps."""

    step_type = "condition.branch"

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        input_step_key = context.step.config.get("input_step_key")
        if not input_step_key:
            raise WorkflowStepExecutionError("input_step_key is required")

        operator = str(context.step.config.get("operator") or "").strip()
        if not operator:
            raise WorkflowStepExecutionError("operator is required")

        path = context.step.config.get("path")
        source = context.previous_outputs.get(str(input_step_key), {})
        value = _resolve_path(source, path) if path else source
        expected = context.step.config.get("value")
        matched = _evaluate_branch_condition(value, operator, expected)
        selected_label = str(
            context.step.config.get("matched_label" if matched else "not_matched_label")
            or ("Matched" if matched else "Not matched")
        )
        target_field = (
            "matched_skip_step_keys" if matched else "not_matched_skip_step_keys"
        )
        skipped_step_keys = _branch_target_keys(context.step.config.get(target_field))
        skip_reason = f"Branch {context.step.key} selected {selected_label}"

        output = {
            "matched": matched,
            "input_step_key": str(input_step_key),
            "path": path,
            "operator": operator,
            "selected_label": selected_label,
            "skipped_step_keys": skipped_step_keys,
        }
        return WorkflowStepResult(
            output_data=output,
            events=[
                WorkflowStepEventSpec(
                    event_type="branch_evaluated",
                    message=(
                        f"Branch matched: {selected_label}"
                        if matched
                        else f"Branch not matched: {selected_label}"
                    ),
                    data=output,
                )
            ],
            skip_step_keys=skipped_step_keys,
            skip_reason=skip_reason,
        )


class ConnectorSyncHandler(BaseWorkflowStepHandler):
    """Run a connector sync and expose newly indexed records."""

    step_type = "connector.sync"

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        connector_id = _render_value(context.step.config.get("connector_id"), context)
        if connector_id in (None, ""):
            raise WorkflowStepExecutionError("connector_id is required")

        resolved_connector_id = _coerce_int(connector_id, "connector_id")
        max_records = _bounded_int(
            context.step.config.get("max_records"),
            default=50,
            minimum=1,
            maximum=100,
        )
        since = context.step.config.get("since") or "connector_checkpoint"

        service = context.dependencies.connector_service
        if service is None:
            from app.services.connector_sync_service import ConnectorSyncService

            service = ConnectorSyncService(context.db)

        runner = getattr(service, "run_sync_for_workflow", None)
        if runner is None:
            runner = getattr(service, "sync_for_workflow", None)
        if runner is None:
            fallback = getattr(service, "run_sync", None)
            if fallback is None:
                raise WorkflowStepExecutionError(
                    "connector service does not support workflow sync"
                )
            result = await _maybe_await(fallback(resolved_connector_id))
        else:
            result = await _maybe_await(
                runner(connector_id=resolved_connector_id, max_records=max_records)
            )

        data = _connector_result_mapping(result)
        status = _status_key(data.get("status"))
        if status in {"failed", "error"}:
            root_cause = data.get("error_message") or "sync job failed"
            raise WorkflowStepExecutionError(
                f"connector sync failed for connector {resolved_connector_id}: {root_cause}"
            )

        items = data.get("documents") or data.get("items") or []
        if not isinstance(items, list):
            items = []
        output = {
            "connector_id": str(data.get("connector_id") or resolved_connector_id),
            "connector_name": data.get("connector_name"),
            "connector_type": data.get("connector_type"),
            "collection_id": data.get("collection_id"),
            "job_id": data.get("job_id") or data.get("id"),
            "status": status or "success",
            "docs_indexed": int(data.get("docs_indexed") or len(items) or 0),
            "docs_failed": int(data.get("docs_failed") or 0),
            "count": len(items),
            "items": items[:max_records],
            "since": since,
        }
        return WorkflowStepResult(
            output_data=output,
            artifacts=[
                WorkflowStepArtifactSpec(
                    artifact_type="json",
                    name=f"{context.step.key}-connector-sync",
                    data=output,
                )
            ],
            events=[
                WorkflowStepEventSpec(
                    event_type="connector_sync_completed",
                    message=f"Connector sync returned {len(items[:max_records])} records",
                    data={
                        "connector_id": output["connector_id"],
                        "job_id": output["job_id"],
                        "docs_indexed": output["docs_indexed"],
                        "docs_failed": output["docs_failed"],
                    },
                )
            ],
        )


class ExtractRunTemplateHandler(BaseWorkflowStepHandler):
    """Run an Extract template over workflow-selected documents."""

    step_type = "extract.run_template"

    def estimate_cost_cents(self, context: WorkflowStepContext) -> int:
        return int(context.step.config.get("estimated_cost_cents") or 1)

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        template_id = _render_value(context.step.config.get("template_id"), context)
        if template_id in (None, ""):
            raise WorkflowStepExecutionError("template_id is required")

        max_documents = _bounded_int(
            context.step.config.get("max_documents"),
            default=25,
            minimum=1,
            maximum=100,
        )
        documents = await _resolve_extract_documents(context, max_documents)
        if not documents:
            raise WorkflowStepExecutionError(
                "no documents matched the Extract step input"
            )

        service = context.dependencies.extract_service
        if service is None:
            from app.modules.extract.services.extract_service import ExtractService

            service = ExtractService()

        runner = getattr(service, "run_template_for_workflow", None)
        if runner is None:
            raise WorkflowStepExecutionError(
                "extract service does not support workflow template execution"
            )

        result = await _maybe_await(
            runner(
                db=context.db,
                template_id=str(template_id),
                documents=documents,
                context=_extract_context_config(context.step.config.get("context")),
                current_user=_workflow_actor_for_extract(context),
                workflow_run_id=context.run.id,
                step_key=context.step.key,
            )
        )
        data = _response_mapping(result)
        status = _status_key(data.get("status"))
        if status in {"failed", "error"}:
            root_cause = (
                data.get("error_message") or "Extract template execution failed"
            )
            raise WorkflowStepExecutionError(
                f"extract template {template_id} failed: {root_cause}"
            )

        output = {
            "template_id": str(data.get("template_id") or template_id),
            "job_id": data.get("job_id"),
            "status": status or data.get("status") or "completed",
            "summary": data.get("summary") or "Extract template completed",
            "document_count": int(data.get("document_count") or len(documents)),
            "result": data.get("result") or data.get("data") or {},
            "validation_errors": data.get("validation_errors") or [],
            "validation_warnings": data.get("validation_warnings") or [],
            "cost_cents": int(data.get("cost_cents") or 0),
            "model_used": data.get("model_used"),
        }
        return WorkflowStepResult(
            output_data=output,
            artifacts=[
                WorkflowStepArtifactSpec(
                    artifact_type="extract_result",
                    name=f"{context.step.key}-extract-result",
                    data=output,
                )
            ],
            events=[
                WorkflowStepEventSpec(
                    event_type="extract_template_completed",
                    message=f"Extract template processed {output['document_count']} documents",
                    data={
                        "template_id": output["template_id"],
                        "job_id": output["job_id"],
                        "document_count": output["document_count"],
                    },
                )
            ],
            estimated_cost_cents=self.estimate_cost_cents(context),
            actual_cost_cents=output["cost_cents"],
        )


class RAGQueryHandler(BaseWorkflowStepHandler):
    """Run a RAG collection search."""

    step_type = "rag.query"

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        collection_id = _render_value(context.step.config.get("collection_id"), context)
        query = _render_value(context.step.config.get("query") or "", context)
        limit = int(
            context.step.config.get("limit") or context.step.config.get("top_k") or 5
        )
        min_score = context.step.config.get("min_score")
        filters = context.step.config.get("filters")
        if not collection_id:
            raise WorkflowStepExecutionError("collection_id is required")
        if not query:
            query = "workflow query"

        service = context.dependencies.rag_service
        if service is None:
            from app.services.rag_service import RAGService

            service = RAGService(context.db)

        search = getattr(service, "search", None)
        if not search:
            raise WorkflowStepExecutionError("rag service does not support search")

        resolved_collection = (
            int(collection_id)
            if isinstance(collection_id, str) and collection_id.isdigit()
            else collection_id
        )
        documents = await _maybe_await(
            search(
                collection_id=resolved_collection,
                query=str(query),
                top_k=limit,
                filters=filters,
                min_score=min_score,
            )
        )
        documents = list(documents or [])
        output = {"documents": documents, "count": len(documents), "query": query}
        return WorkflowStepResult(
            output_data=output,
            artifacts=[
                WorkflowStepArtifactSpec(
                    artifact_type="json",
                    name=f"{context.step.key}-results",
                    data={"count": len(documents), "documents": documents},
                )
            ],
            events=[
                WorkflowStepEventSpec(
                    event_type="rag_query_completed",
                    message=f"RAG query returned {len(documents)} documents",
                    data={"count": len(documents)},
                )
            ],
        )


class AgentRunHandler(BaseWorkflowStepHandler):
    """Run an agent with a rendered prompt."""

    step_type = "agent.run"

    def estimate_cost_cents(self, context: WorkflowStepContext) -> int:
        return int(context.step.config.get("estimated_cost_cents") or 1)

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        agent_id = _render_value(context.step.config.get("agent_id"), context)
        prompt_template = context.step.config.get("prompt_template")
        if not agent_id:
            raise WorkflowStepExecutionError("agent_id is required")
        if not prompt_template:
            raise WorkflowStepExecutionError("prompt_template is required")

        mapped_inputs = {
            key: _resolve_context_path(path, context)
            for key, path in (context.step.config.get("input_mapping") or {}).items()
        }
        prompt = _render_template(str(prompt_template), context, mapped_inputs)
        service = context.dependencies.agent_service
        if service is None:
            raise WorkflowStepExecutionError("agent service dependency unavailable")

        response = await _invoke_agent(
            service, agent_id, prompt, mapped_inputs, context
        )
        message = _response_text(response)
        usage = _response_mapping(response).get("usage") or {}
        actual_cost_cents = int(
            _response_mapping(response).get("actual_cost_cents")
            or usage.get("cost_cents")
            or 0
        )
        output = {"message": message, "usage": usage, "agent_id": str(agent_id)}
        return WorkflowStepResult(
            output_data=output,
            artifacts=[
                WorkflowStepArtifactSpec(
                    artifact_type="summary",
                    name=f"{context.step.key}-summary",
                    data={"message": message, "usage": usage},
                )
            ],
            events=[
                WorkflowStepEventSpec(
                    event_type="agent_run_completed",
                    message="Agent run completed",
                    data={"agent_id": str(agent_id)},
                )
            ],
            estimated_cost_cents=self.estimate_cost_cents(context),
            actual_cost_cents=actual_cost_cents,
        )


class NotifyInAppHandler(BaseWorkflowStepHandler):
    """Create an in-app notification."""

    step_type = "notify.in_app"

    async def execute(self, context: WorkflowStepContext) -> WorkflowStepResult:
        raw_recipients = context.step.config.get("recipients") or []
        recipients = [_render_value(recipient, context) for recipient in raw_recipients]
        recipients = [
            str(recipient) for recipient in recipients if recipient is not None
        ]
        title = _render_template(
            str(context.step.config.get("title_template") or "Workflow notification"),
            context,
        )
        body = _render_template(
            str(context.step.config.get("body_template") or ""), context
        )
        severity = context.step.config.get("severity") or "info"
        if not recipients:
            raise WorkflowStepExecutionError("notification recipients are required")

        service = context.dependencies.notification_service
        notification_ids: list[str]
        if service is not None:
            sender = getattr(service, "send_notification", None) or getattr(
                service, "send_in_app", None
            )
            if not sender:
                raise WorkflowStepExecutionError(
                    "notification service does not support sending"
                )
            response = await _maybe_await(
                sender(
                    recipients=recipients,
                    subject=title,
                    body=body,
                    metadata={
                        "workflow_run_id": context.run.id,
                        "step_key": context.step.key,
                        "severity": severity,
                    },
                )
            )
            notification_ids = [str(getattr(response, "id", response))]
        else:
            notification_ids = [f"workflow-{context.run.id}-{context.step.key}"]

        output = {
            "notification_ids": notification_ids,
            "recipients": recipients,
            "title": title,
            "severity": severity,
        }
        return WorkflowStepResult(
            output_data=output,
            artifacts=[
                WorkflowStepArtifactSpec(
                    artifact_type="notification",
                    name=f"{context.step.key}-notification",
                    data=output,
                )
            ],
            events=[
                WorkflowStepEventSpec(
                    event_type="notification_created",
                    message="Notification created",
                    data={"notification_ids": notification_ids},
                )
            ],
        )


def create_default_step_handlers(
    dependencies: WorkflowRuntimeDependencies,
) -> dict[str, WorkflowStepHandler]:
    """Create default MVP workflow step handlers."""
    handlers: list[WorkflowStepHandler] = [
        RAGQueryHandler(),
        ConnectorSyncHandler(),
        ExtractRunTemplateHandler(),
        AgentRunHandler(),
        NotifyInAppHandler(),
        NoResultsSkipHandler(),
        BranchConditionHandler(),
    ]
    return {handler.step_type: handler for handler in handlers}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, list, tuple, set, dict)):
        return len(value) == 0
    return False


def _resolve_path(source: Any, path: Optional[str]) -> Any:
    if not path:
        return source
    current = source
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


def _branch_target_keys(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _evaluate_branch_condition(value: Any, operator: str, expected: Any) -> bool:
    if operator == "exists":
        return value is not None
    if operator == "empty":
        return _is_empty(value)
    if operator == "non_empty":
        return not _is_empty(value)
    if operator == "truthy":
        return bool(value)
    if operator == "falsy":
        return not bool(value)
    if operator == "equals":
        return _branch_values_equal(value, expected)
    if operator == "not_equals":
        return not _branch_values_equal(value, expected)
    if operator == "contains":
        return _branch_contains(value, expected)
    if operator in {
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
    }:
        return _compare_branch_values(value, expected, operator)
    raise WorkflowStepExecutionError(f"unsupported branch operator: {operator}")


def _branch_values_equal(left: Any, right: Any) -> bool:
    left_number = _branch_number(left)
    right_number = _branch_number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left) == str(right)


def _branch_contains(value: Any, expected: Any) -> bool:
    if isinstance(value, Mapping):
        return str(expected) in {str(key) for key in value.keys()}
    if isinstance(value, (list, tuple, set)):
        return any(_branch_values_equal(item, expected) for item in value)
    if value is None:
        return False
    return str(expected) in str(value)


def _compare_branch_values(value: Any, expected: Any, operator: str) -> bool:
    left = _branch_number(value)
    right = _branch_number(expected)
    if left is None or right is None:
        return False
    if operator == "greater_than":
        return left > right
    if operator == "greater_than_or_equal":
        return left >= right
    if operator == "less_than":
        return left < right
    if operator == "less_than_or_equal":
        return left <= right
    return False


def _branch_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_context_path(path: str, context: WorkflowStepContext) -> Any:
    if not path:
        return None
    if "." not in path:
        return context.previous_outputs.get(path)
    step_key, output_path = path.split(".", 1)
    return _resolve_path(context.previous_outputs.get(step_key, {}), output_path)


def _render_template(
    template: str,
    context: WorkflowStepContext,
    extra_values: Optional[dict[str, Any]] = None,
) -> str:
    def replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        value = _resolve_template_value(path, context, extra_values or {})
        if value is None:
            raise WorkflowStepExecutionError(f"template value not found: {path}")
        return str(value)

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)


def _render_value(value: Any, context: WorkflowStepContext) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        full_match = re.fullmatch(r"\{\{\s*([^}]+?)\s*\}\}", stripped)
        if full_match:
            return _resolve_template_value(full_match.group(1).strip(), context, {})
        if "{{" in value:
            return _render_template(value, context)
    return value


def _coerce_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WorkflowStepExecutionError(f"{field_name} must be an integer") from exc


def _bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def _status_key(value: Any) -> str:
    raw = str(getattr(value, "value", value) or "")
    return raw.rsplit(".", 1)[-1].lower()


async def _resolve_extract_documents(
    context: WorkflowStepContext, max_documents: int
) -> list[dict[str, Any]]:
    source = context.step.config.get("document_source") or (
        "previous_step" if context.step.config.get("input_step_key") else "rag_filter"
    )
    if source == "previous_step":
        input_step_key = context.step.config.get("input_step_key")
        if not input_step_key:
            raise WorkflowStepExecutionError("input_step_key is required")
        path = context.step.config.get("path") or "items"
        value = _resolve_path(context.previous_outputs.get(input_step_key, {}), path)
        if value is None and path == "items":
            value = _resolve_path(
                context.previous_outputs.get(input_step_key, {}), "documents"
            )
        return _normalize_document_items(value, max_documents)

    if source != "rag_filter":
        raise WorkflowStepExecutionError(f"unknown document_source: {source}")

    collection_id = _render_value(context.step.config.get("collection_id"), context)
    if collection_id in (None, ""):
        raise WorkflowStepExecutionError("collection_id is required")
    connector_id = _render_value(context.step.config.get("connector_id"), context)

    from app.models.rag_document import RagDocument

    stmt = (
        select(RagDocument)
        .where(
            RagDocument.collection_id == _coerce_int(collection_id, "collection_id"),
            RagDocument.is_deleted.is_(False),
        )
        .order_by(RagDocument.indexed_at.desc().nulls_last(), RagDocument.id.desc())
        .limit(max_documents)
    )
    if connector_id not in (None, ""):
        stmt = stmt.where(
            RagDocument.connector_source_id == _coerce_int(connector_id, "connector_id")
        )
    since = context.step.config.get("since") or "last_successful_run"
    if since == "last_successful_run":
        cutoff = await _last_successful_run_completed_at(context)
        if cutoff is not None:
            stmt = stmt.where(
                RagDocument.indexed_at.is_not(None),
                RagDocument.indexed_at > cutoff,
            )
    elif since != "all_matching":
        raise WorkflowStepExecutionError(f"unknown since filter: {since}")

    result = await context.db.execute(stmt)
    return [_rag_document_summary(document) for document in result.scalars().all()]


async def _last_successful_run_completed_at(context: WorkflowStepContext) -> Any:
    stmt = (
        select(WorkflowRun.completed_at)
        .where(
            WorkflowRun.workflow_id == context.run.workflow_id,
            WorkflowRun.status == "succeeded",
            WorkflowRun.id != context.run.id,
            WorkflowRun.completed_at.is_not(None),
        )
        .order_by(WorkflowRun.completed_at.desc(), WorkflowRun.created_at.desc())
        .limit(1)
    )
    result = await context.db.execute(stmt)
    return result.scalar_one_or_none()


def _normalize_document_items(value: Any, max_documents: int) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    documents: list[dict[str, Any]] = []
    for item in items[:max_documents]:
        if isinstance(item, Mapping):
            document = dict(item)
        else:
            document = {"content": str(item)}
        if "content" not in document and "content_preview" not in document:
            document["content_preview"] = str(
                document.get("summary")
                or document.get("title")
                or document.get("filename")
                or ""
            )
        documents.append(document)
    return documents


def _rag_document_summary(document: Any) -> dict[str, Any]:
    metadata = document.document_metadata or {}
    content = document.converted_content or ""
    return {
        "document_id": document.id,
        "collection_id": document.collection_id,
        "title": metadata.get("title")
        or document.original_filename
        or document.filename,
        "filename": document.filename,
        "original_filename": document.original_filename,
        "source_url": document.source_url,
        "external_id": document.external_id,
        "external_updated_at": (
            document.external_updated_at.isoformat()
            if document.external_updated_at
            else None
        ),
        "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
        "word_count": document.word_count,
        "character_count": document.character_count,
        "content": content[:12000],
        "content_preview": content[:4000],
        "metadata": metadata,
    }


def _extract_context_config(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WorkflowStepExecutionError("context must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise WorkflowStepExecutionError("context must be a JSON object")
        return parsed
    raise WorkflowStepExecutionError("context must be a JSON object")


def _workflow_actor_for_extract(context: WorkflowStepContext) -> dict[str, Any]:
    actor = dict(context.actor or {})
    user_id = actor.get("id") or context.run.requested_by_user_id
    if user_id is None and context.run.workflow is not None:
        user_id = context.run.workflow.owner_user_id
    if user_id is None:
        raise WorkflowStepExecutionError("extract step requires a workflow owner")
    actor["id"] = int(user_id)
    actor.setdefault("email", "workflow-system@local")
    return actor


def _resolve_template_value(
    path: str, context: WorkflowStepContext, extra_values: dict[str, Any]
) -> Any:
    if path in extra_values:
        return extra_values[path]
    if path == "owner_user_id":
        return context.run.workflow.owner_user_id if context.run.workflow else None
    if path == "workflow_id":
        return context.run.workflow_id
    if path == "run_id":
        return context.run.id
    if path.startswith("input."):
        return _resolve_path(context.run.input_data or {}, path.removeprefix("input."))
    if "." in path:
        return _resolve_context_path(path, context)
    return context.previous_outputs.get(path)


async def _invoke_agent(
    service: Any,
    agent_id: Any,
    prompt: str,
    mapped_inputs: dict[str, Any],
    context: WorkflowStepContext,
) -> Any:
    for method_name in ("run", "invoke", "chat"):
        method = getattr(service, method_name, None)
        if method:
            return await _maybe_await(
                method(
                    agent_id=agent_id,
                    prompt=prompt,
                    inputs=mapped_inputs,
                    workflow_run_id=context.run.id,
                )
            )
    raise WorkflowStepExecutionError("agent service does not support run/invoke/chat")


def _response_mapping(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    return {}


def _connector_result_mapping(response: Any) -> dict[str, Any]:
    if hasattr(response, "to_workflow_output"):
        return dict(response.to_workflow_output())
    if isinstance(response, Mapping):
        return dict(response)
    if is_dataclass(response):
        return asdict(response)
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    if hasattr(response, "to_dict"):
        data = response.to_dict()
        if "id" in data and "job_id" not in data:
            data["job_id"] = data["id"]
        return data
    return {}


def _response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    data = _response_mapping(response)
    if "message" in data:
        return str(data["message"])
    if "content" in data:
        return str(data["content"])
    choices = data.get("choices")
    if choices:
        message = (
            choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
        )
        content = message.get("content") or choices[0].get("text")
        if content is not None:
            return str(content)
    return str(response)


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
