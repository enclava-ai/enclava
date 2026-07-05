"""Workflow step handler implementations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol

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
        AgentRunHandler(),
        NotifyInAppHandler(),
        NoResultsSkipHandler(),
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
