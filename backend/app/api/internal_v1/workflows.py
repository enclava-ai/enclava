"""Internal workflow lifecycle API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.schemas.workflow import (
    WorkflowApprovalAction,
    WorkflowDefinitionCreate,
    WorkflowDefinitionStatus,
    WorkflowDefinitionUpdate,
    WorkflowLifecycleAction,
    WorkflowManualRunRequest,
    WorkflowRunAction,
    WorkflowRunStatus,
    WorkflowSchedulePreviewRequest,
)
from app.services.workflows import (
    WorkflowNotFoundError,
    WorkflowOperationsService,
    WorkflowPermissionError,
    WorkflowRunConflictError,
    WorkflowRunNotFoundError,
    WorkflowRunPermissionError,
    WorkflowRuntimeService,
    WorkflowRunValidationError,
    WorkflowSchedulerService,
    WorkflowScheduleValidationError,
    WorkflowService,
    WorkflowValidationError,
)
from app.services.workflows.steps import WorkflowStepExecutionError

router = APIRouter(tags=["Workflows"])
workflow_service = WorkflowService()
runtime_service = WorkflowRuntimeService()
scheduler_service = WorkflowSchedulerService(runtime_service)
operations_service = WorkflowOperationsService()


def _map_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (WorkflowNotFoundError, WorkflowRunNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (WorkflowPermissionError, WorkflowRunPermissionError)):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(
        exc,
        (
            WorkflowValidationError,
            WorkflowRunValidationError,
            WorkflowScheduleValidationError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(exc),
                "errors": getattr(exc, "details", []),
            },
        )
    if isinstance(exc, WorkflowRunConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="workflow operation failed",
    )


def _has_workflow_manage_access(actor: dict) -> bool:
    if actor.get("is_superuser") or actor.get("role") in {"admin", "super_admin"}:
        return True
    permissions = actor.get("permissions") or []
    if permissions == "*":
        return True
    if isinstance(permissions, dict):
        permissions = permissions.get("granted", [])
    aliases = {"workflow.manage", "workflow:manage", "*"}
    return any(permission in aliases for permission in permissions)


@router.get("/catalog")
async def list_workflow_step_catalog(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List workflow step catalog entries."""
    return {
        "success": True,
        "steps": [
            entry.model_dump(mode="json")
            for entry in workflow_service.list_step_catalog()
        ],
    }


@router.get("/steps/catalog")
async def list_workflow_builder_step_catalog(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List builder-ready workflow step catalog entries."""
    return {
        "success": True,
        "steps": [
            entry.model_dump(mode="json")
            for entry in workflow_service.list_step_catalog()
        ],
    }


@router.get("/steps/catalog/{step_type}")
async def get_workflow_builder_step_catalog_entry(
    step_type: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get one builder-ready step catalog entry."""
    try:
        entry = workflow_service.get_step_catalog(step_type)
        return {"success": True, "step": entry.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/templates")
async def list_workflow_templates(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List workflow template seeds."""
    return {
        "success": True,
        "templates": [
            template.model_dump(mode="json")
            for template in workflow_service.list_templates()
        ],
    }


@router.get("/templates/{template_id}")
async def get_workflow_template(
    template_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get one workflow template seed."""
    try:
        template = workflow_service.get_template(template_id)
        return {"success": True, "template": template.model_dump(mode="json")}
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/validate")
async def validate_workflow_definition(
    definition: dict[str, Any],
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Validate a workflow definition document."""
    result = await workflow_service.validate_workflow_payload(definition)
    return {"success": result.valid, **result.model_dump(mode="json")}


@router.post("/steps/validate")
async def validate_workflow_builder_definition(
    definition: dict[str, Any],
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Validate a workflow definition document for builder use."""
    result = await workflow_service.validate_workflow_payload(definition)
    return {"success": result.valid, **result.model_dump(mode="json")}


@router.get("/")
async def list_workflows(
    include_archived: bool = Query(default=False),
    status_filter: Optional[WorkflowDefinitionStatus] = Query(
        default=None, alias="status"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List workflows visible to the authenticated user."""
    workflows = await workflow_service.list_definitions(
        db,
        current_user,
        include_archived=include_archived,
        status=status_filter,
    )
    return {
        "success": True,
        "workflows": [workflow.model_dump(mode="json") for workflow in workflows],
        "total": len(workflows),
    }


@router.post("/schedule/preview")
async def preview_workflow_schedule(
    payload: WorkflowSchedulePreviewRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Preview a workflow cron schedule."""
    try:
        preview = scheduler_service.preview_schedule(payload)
        return {"success": True, "preview": preview.model_dump(mode="json")}
    except WorkflowScheduleValidationError as exc:
        raise _map_service_error(exc) from exc


@router.get("/scheduler/status")
async def get_workflow_scheduler_status(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get in-process workflow scheduler status."""
    from app.tasks.workflow_scheduler import workflow_scheduler

    return {
        "success": True,
        "scheduler": workflow_scheduler.status().model_dump(mode="json"),
    }


@router.post("/scheduler/tick")
async def run_workflow_scheduler_tick(
    create_limit: int = Query(default=50, ge=1, le=200),
    execute_limit: int = Query(default=5, ge=0, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Run one scheduler tick for operators and tests."""
    if not _has_workflow_manage_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workflow manage permission required",
        )
    try:
        result = await scheduler_service.run_tick(
            db,
            create_limit=create_limit,
            execute_limit=execute_limit,
            worker_id=f"scheduler-api-{current_user.get('id')}",
        )
        await db.commit()
        return {"success": True, "scheduler": result.model_dump(mode="json")}
    except WorkflowScheduleValidationError as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.get("/operations")
async def list_workflow_operations(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List compact workflow operations rows."""
    operations = await operations_service.list_operations(db, current_user)
    return {"success": True, "operations": operations.model_dump(mode="json")}


@router.get("/operations/recent-runs")
async def list_workflow_operations_recent_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List recent runs visible to the workflow operations console."""
    runs = await operations_service.list_recent_runs(
        db,
        current_user,
        limit=limit,
    )
    return {"success": True, "runs": [run.model_dump(mode="json") for run in runs]}


@router.get("/operations/failures")
async def list_workflow_operations_failures(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List recent failed runs visible to the workflow operations console."""
    runs = await operations_service.list_recent_runs(
        db,
        current_user,
        failed_only=True,
        limit=limit,
    )
    return {"success": True, "runs": [run.model_dump(mode="json") for run in runs]}


@router.get("/operations/runs")
async def list_workflow_operations_runs(
    limit: int = Query(default=20, ge=1, le=100),
    workflow_id: Optional[str] = Query(default=None),
    status_filter: Optional[WorkflowRunStatus] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List recent runs visible to the workflow operations tabs."""
    runs = await operations_service.list_recent_runs(
        db,
        current_user,
        workflow_id=workflow_id,
        status=status_filter,
        limit=limit,
    )
    return {"success": True, "runs": [run.model_dump(mode="json") for run in runs]}


@router.get("/operations/schedules")
async def list_workflow_schedule_board(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List schedule board data visible to the actor."""
    board = await operations_service.list_schedule_board(db, current_user)
    return {"success": True, "schedule_board": board.model_dump(mode="json")}


@router.get("/operations/templates")
async def list_workflow_operation_templates(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List compact template summaries for workflow operations tabs."""
    return {
        "success": True,
        "templates": [
            template.model_dump(mode="json")
            for template in operations_service.list_template_summaries()
        ],
    }


@router.post("/{workflow_id}/schedule/preview")
async def preview_existing_workflow_schedule(
    workflow_id: str,
    count: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Preview the current schedule trigger for an existing workflow."""
    try:
        workflow = await workflow_service.get_definition(db, workflow_id, current_user)
        trigger = next(
            (
                item
                for item in reversed(workflow.triggers)
                if item.trigger_type.value == "schedule"
            ),
            None,
        )
        if trigger is None or not trigger.cron_expression or not trigger.timezone:
            raise WorkflowScheduleValidationError("workflow has no schedule trigger")
        preview = scheduler_service.preview_schedule(
            WorkflowSchedulePreviewRequest(
                cron=trigger.cron_expression,
                timezone=trigger.timezone,
                count=count,
            )
        )
        return {"success": True, "preview": preview.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
        WorkflowScheduleValidationError,
    ) as exc:
        raise _map_service_error(exc) from exc


@router.get("/runs/{run_id}")
async def get_workflow_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get workflow run detail."""
    try:
        run = await runtime_service.get_run_detail(db, run_id, current_user)
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        raise _map_service_error(exc) from exc


@router.post("/runs/{run_id}/execute")
async def execute_workflow_run(
    run_id: str,
    worker_id: str = Query(default="manual-api", min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Execute a queued workflow run synchronously."""
    try:
        try:
            run = await runtime_service.execute_run(
                db, run_id, worker_id=worker_id, actor=current_user
            )
        except WorkflowStepExecutionError as exc:
            await db.commit()
            failed = await runtime_service.get_run_detail(db, run_id, current_user)
            return {
                "success": False,
                "error": str(exc),
                "run": failed.model_dump(mode="json"),
            }
        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/runs/{run_id}/retry", status_code=status.HTTP_201_CREATED)
async def retry_workflow_run(
    run_id: str,
    action: Optional[WorkflowRunAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Queue a retry for a terminal workflow run."""
    try:
        run = await runtime_service.retry_run(
            db,
            run_id,
            current_user,
            reason=(action.reason if action else None),
        )
        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/runs/{run_id}/cancel")
async def cancel_workflow_run(
    run_id: str,
    action: Optional[WorkflowRunAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Cancel or request cancellation for a workflow run."""
    try:
        run = await runtime_service.request_cancel_run(
            db,
            run_id,
            current_user,
            reason=(action.reason if action else None),
        )
        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/runs/{run_id}/approve")
async def approve_workflow_run(
    run_id: str,
    action: Optional[WorkflowApprovalAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Approve a paused workflow run and resume execution."""
    try:
        try:
            run = await runtime_service.resolve_approval(
                db,
                run_id,
                current_user,
                approved=True,
                comment=(action.comment if action else None),
                worker_id=f"approval-user-{current_user.get('id')}",
            )
        except WorkflowStepExecutionError as exc:
            await db.commit()
            failed = await runtime_service.get_run_detail(db, run_id, current_user)
            return {
                "success": False,
                "error": str(exc),
                "run": failed.model_dump(mode="json"),
            }
        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/runs/{run_id}/reject")
async def reject_workflow_run(
    run_id: str,
    action: Optional[WorkflowApprovalAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Reject a paused workflow run and skip remaining steps."""
    try:
        run = await runtime_service.resolve_approval(
            db,
            run_id,
            current_user,
            approved=False,
            comment=(action.comment if action else None),
            worker_id=f"approval-user-{current_user.get('id')}",
        )
        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List recent runs for a workflow."""
    try:
        runs = await runtime_service.list_workflow_runs(
            db, workflow_id, current_user, limit=limit
        )
        return {
            "success": True,
            "runs": [run.model_dump(mode="json") for run in runs],
            "total": len(runs),
        }
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        raise _map_service_error(exc) from exc


@router.post("/{workflow_id}/runs", status_code=status.HTTP_201_CREATED)
async def create_workflow_run(
    workflow_id: str,
    payload: WorkflowManualRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create a manual workflow run and optionally execute it immediately."""
    try:
        run = await runtime_service.create_manual_run(
            db, workflow_id, payload, current_user
        )
        if payload.execute_now:
            try:
                run = await runtime_service.execute_run(
                    db,
                    run.id,
                    worker_id=f"manual-user-{current_user.get('id')}",
                    actor=current_user,
                )
            except WorkflowStepExecutionError as exc:
                await db.commit()
                failed = await runtime_service.get_run_detail(db, run.id, current_user)
                return {
                    "success": False,
                    "error": str(exc),
                    "run": failed.model_dump(mode="json"),
                }

        await db.commit()
        return {"success": True, "run": run.model_dump(mode="json")}
    except (
        WorkflowRunNotFoundError,
        WorkflowRunPermissionError,
        WorkflowRunValidationError,
        WorkflowRunConflictError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create a workflow draft."""
    try:
        workflow = await workflow_service.create_definition(db, payload, current_user)
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc
    except ValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get workflow detail."""
    try:
        workflow = await workflow_service.get_definition(db, workflow_id, current_user)
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        raise _map_service_error(exc) from exc


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    payload: WorkflowDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Update workflow draft fields."""
    try:
        workflow = await workflow_service.update_definition(
            db, workflow_id, payload, current_user
        )
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc
    except ValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


@router.post("/{workflow_id}/publish")
async def publish_workflow(
    workflow_id: str,
    action: Optional[WorkflowLifecycleAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Publish the workflow draft as an immutable version."""
    try:
        workflow = await workflow_service.publish_definition(
            db, workflow_id, current_user, action or WorkflowLifecycleAction()
        )
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/{workflow_id}/enable")
async def enable_workflow(
    workflow_id: str,
    action: Optional[WorkflowLifecycleAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Enable a published workflow."""
    try:
        workflow = await workflow_service.enable_definition(
            db, workflow_id, current_user, action or WorkflowLifecycleAction()
        )
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/{workflow_id}/disable")
async def disable_workflow(
    workflow_id: str,
    action: Optional[WorkflowLifecycleAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Disable a workflow."""
    try:
        workflow = await workflow_service.disable_definition(
            db, workflow_id, current_user, action or WorkflowLifecycleAction()
        )
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc


@router.post("/{workflow_id}/archive")
async def archive_workflow(
    workflow_id: str,
    action: Optional[WorkflowLifecycleAction] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Archive a workflow."""
    try:
        workflow = await workflow_service.archive_definition(
            db, workflow_id, current_user, action or WorkflowLifecycleAction()
        )
        await db.commit()
        return {"success": True, "workflow": workflow.model_dump(mode="json")}
    except (
        WorkflowNotFoundError,
        WorkflowPermissionError,
        WorkflowValidationError,
    ) as exc:
        await db.rollback()
        raise _map_service_error(exc) from exc
