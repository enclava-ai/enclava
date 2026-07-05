"""Workflow operations console read models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import utc_now
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowTrigger,
    WorkflowVersion,
)
from app.schemas.workflow import (
    WorkflowDefinitionStatus,
    WorkflowHealthState,
    WorkflowOperationsResponse,
    WorkflowOperationsRow,
    WorkflowOperationsTotals,
    WorkflowRunStatus,
    WorkflowRunSummary,
    WorkflowScheduleBoardGroup,
    WorkflowScheduleBoardItem,
    WorkflowScheduleBoardResponse,
    WorkflowScheduleBoardRun,
    WorkflowSchedulePreviewItem,
    WorkflowSchedulePreviewRequest,
    WorkflowTemplateSummary,
    WorkflowTriggerType,
)

from .scheduler import WorkflowSchedulerService, WorkflowScheduleValidationError
from .service import _actor_id, _can_read_all
from .templates import list_workflow_templates


class WorkflowOperationsService:
    """Builds compact workflow operations console payloads."""

    MISSED_GRACE_SECONDS = 300
    ACTIVE_RUN_STATUSES = {
        WorkflowRunStatus.QUEUED.value,
        WorkflowRunStatus.RUNNING.value,
        WorkflowRunStatus.PAUSED.value,
    }

    async def list_operations(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
    ) -> WorkflowOperationsResponse:
        """Return workflow rows visible to the actor with run and health metadata."""
        workflows = await self._list_visible_workflows(db, actor)
        workflow_ids = [workflow.id for workflow in workflows]
        if not workflow_ids:
            return WorkflowOperationsResponse()

        latest_runs = await self._ranked_runs(db, workflow_ids)
        active_runs = await self._ranked_runs(
            db, workflow_ids, statuses=self.ACTIVE_RUN_STATUSES
        )
        failed_runs = await self._ranked_runs(
            db, workflow_ids, statuses={WorkflowRunStatus.FAILED.value}
        )
        successful_runs = await self._ranked_runs(
            db, workflow_ids, statuses={WorkflowRunStatus.SUCCEEDED.value}
        )
        run_stats = await self._run_stats(db, workflow_ids)

        now = utc_now()
        rows = [
            self._to_row(
                workflow,
                now=now,
                latest_run=latest_runs.get(workflow.id),
                active_run=active_runs.get(workflow.id),
                latest_failed_run=failed_runs.get(workflow.id),
                last_successful_run=successful_runs.get(workflow.id),
                stats=run_stats.get(workflow.id, {}),
            )
            for workflow in workflows
        ]
        return WorkflowOperationsResponse(
            workflows=rows,
            totals=self._totals(rows),
        )

    async def list_recent_runs(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
        *,
        failed_only: bool = False,
        status: Optional[WorkflowRunStatus] = None,
        workflow_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[WorkflowRunSummary]:
        """Return recent visible workflow runs for operations panels."""
        workflows = await self._list_visible_workflows(db, actor)
        workflow_ids = [workflow.id for workflow in workflows]
        if not workflow_ids:
            return []

        names_by_id = {workflow.id: workflow.name for workflow in workflows}
        if workflow_id is not None:
            if workflow_id not in names_by_id:
                return []
            workflow_ids = [workflow_id]

        stmt: Select[tuple[WorkflowRun]] = (
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.version))
            .where(WorkflowRun.workflow_id.in_(workflow_ids))
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .limit(limit)
        )
        if failed_only:
            stmt = stmt.where(WorkflowRun.status == WorkflowRunStatus.FAILED.value)
        if status is not None:
            stmt = stmt.where(WorkflowRun.status == status.value)

        result = await db.execute(stmt)
        return [
            summary
            for run in result.scalars().all()
            if (summary := _run_summary(run, names_by_id.get(run.workflow_id, "")))
            is not None
        ]

    async def list_schedule_board(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
    ) -> WorkflowScheduleBoardResponse:
        """Return visible schedule triggers with upcoming fire-time groups."""
        workflows = await self._list_visible_workflows(db, actor)
        workflow_ids = [workflow.id for workflow in workflows]
        if not workflow_ids:
            return WorkflowScheduleBoardResponse(groups=_empty_schedule_groups())

        latest_runs = await self._ranked_runs(db, workflow_ids)
        active_runs = await self._ranked_runs(
            db, workflow_ids, statuses=self.ACTIVE_RUN_STATUSES
        )
        failed_runs = await self._ranked_runs(
            db, workflow_ids, statuses={WorkflowRunStatus.FAILED.value}
        )
        now = utc_now()
        schedules: list[WorkflowScheduleBoardItem] = []
        upcoming: list[WorkflowScheduleBoardRun] = []

        for workflow in workflows:
            trigger = _current_trigger(workflow)
            if (
                not trigger
                or trigger.trigger_type != WorkflowTriggerType.SCHEDULE.value
            ):
                continue

            latest_run = latest_runs.get(workflow.id)
            active_run = active_runs.get(workflow.id)
            failed_run = failed_runs.get(workflow.id)
            health = self._schedule_health_state(
                workflow, trigger, latest_run, active_run, now
            )
            preview = _preview_trigger(trigger, now=now)
            item = WorkflowScheduleBoardItem(
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                description=workflow.description,
                status=WorkflowDefinitionStatus(workflow.status),
                health=health,
                owner_label=_owner_label(workflow),
                tags=workflow.tags or [],
                trigger_id=trigger.id,
                trigger_enabled=bool(trigger.enabled),
                cron_expression=trigger.cron_expression,
                timezone=trigger.timezone,
                misfire_policy=trigger.misfire_policy,
                next_run_at=trigger.next_run_at,
                last_fire_at=trigger.last_fire_at,
                latest_run=_run_summary(latest_run, workflow.name),
                active_run=_run_summary(active_run, workflow.name),
                latest_failed_run=_run_summary(failed_run, workflow.name),
                preview=preview,
            )
            schedules.append(item)
            upcoming.extend(
                WorkflowScheduleBoardRun(
                    workflow_id=workflow.id,
                    workflow_name=workflow.name,
                    trigger_id=trigger.id,
                    run_at=preview_item.run_at,
                    local_time=preview_item.local_time,
                    timezone=preview_item.timezone,
                    health=health,
                    workflow_status=WorkflowDefinitionStatus(workflow.status),
                    trigger_enabled=bool(trigger.enabled),
                )
                for preview_item in preview
            )

        return WorkflowScheduleBoardResponse(
            schedules=schedules,
            groups=_group_upcoming_runs(upcoming, now),
        )

    def list_template_summaries(self) -> list[WorkflowTemplateSummary]:
        """Return compact workflow template summaries."""
        return [
            WorkflowTemplateSummary(
                id=template.id,
                name=template.name,
                description=template.description,
                trigger_type=template.definition.trigger.type,
                step_count=len(template.definition.steps),
                tags=template.tags,
                builder_category=template.builder_category,
                available_for_authoring=template.available_for_authoring,
                unavailable_reason=template.unavailable_reason,
            )
            for template in list_workflow_templates()
        ]

    async def _list_visible_workflows(
        self,
        db: AsyncSession,
        actor: Mapping[str, Any],
    ) -> list[WorkflowDefinition]:
        stmt: Select[tuple[WorkflowDefinition]] = (
            select(WorkflowDefinition)
            .options(
                selectinload(WorkflowDefinition.owner),
                selectinload(WorkflowDefinition.triggers),
                selectinload(WorkflowDefinition.versions),
            )
            .where(WorkflowDefinition.status != WorkflowDefinitionStatus.ARCHIVED.value)
            .order_by(WorkflowDefinition.updated_at.desc())
        )
        if not _can_read_all(actor):
            stmt = stmt.where(WorkflowDefinition.owner_user_id == _actor_id(actor))

        result = await db.execute(stmt)
        return list(result.scalars().unique().all())

    async def _ranked_runs(
        self,
        db: AsyncSession,
        workflow_ids: list[str],
        *,
        statuses: Optional[set[str]] = None,
    ) -> dict[str, WorkflowRun]:
        row_number = (
            func.row_number()
            .over(
                partition_by=WorkflowRun.workflow_id,
                order_by=[WorkflowRun.created_at.desc(), WorkflowRun.id.desc()],
            )
            .label("row_number")
        )
        ranked_stmt = select(WorkflowRun.id.label("run_id"), row_number).where(
            WorkflowRun.workflow_id.in_(workflow_ids)
        )
        if statuses:
            ranked_stmt = ranked_stmt.where(WorkflowRun.status.in_(statuses))

        ranked = ranked_stmt.subquery()
        result = await db.execute(
            select(WorkflowRun)
            .join(ranked, WorkflowRun.id == ranked.c.run_id)
            .options(selectinload(WorkflowRun.version))
            .where(ranked.c.row_number == 1)
        )
        return {run.workflow_id: run for run in result.scalars().all()}

    async def _run_stats(
        self,
        db: AsyncSession,
        workflow_ids: list[str],
    ) -> dict[str, dict[str, int]]:
        result = await db.execute(
            select(
                WorkflowRun.workflow_id,
                func.count(WorkflowRun.id).label("run_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (WorkflowRun.status == WorkflowRunStatus.FAILED.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("failure_count"),
                func.coalesce(func.sum(WorkflowRun.estimated_cost_cents), 0).label(
                    "estimated_cost_cents"
                ),
                func.coalesce(func.sum(WorkflowRun.actual_cost_cents), 0).label(
                    "actual_cost_cents"
                ),
            )
            .where(WorkflowRun.workflow_id.in_(workflow_ids))
            .group_by(WorkflowRun.workflow_id)
        )
        return {
            row.workflow_id: {
                "run_count": int(row.run_count or 0),
                "failure_count": int(row.failure_count or 0),
                "estimated_cost_cents": int(row.estimated_cost_cents or 0),
                "actual_cost_cents": int(row.actual_cost_cents or 0),
            }
            for row in result.all()
        }

    def _to_row(
        self,
        workflow: WorkflowDefinition,
        *,
        now: datetime,
        latest_run: Optional[WorkflowRun],
        active_run: Optional[WorkflowRun],
        latest_failed_run: Optional[WorkflowRun],
        last_successful_run: Optional[WorkflowRun],
        stats: dict[str, int],
    ) -> WorkflowOperationsRow:
        trigger = _current_trigger(workflow)
        latest_summary = _run_summary(latest_run, workflow.name)
        active_summary = _run_summary(active_run, workflow.name)
        failed_summary = _run_summary(latest_failed_run, workflow.name)
        success_summary = _run_summary(last_successful_run, workflow.name)
        return WorkflowOperationsRow(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            status=WorkflowDefinitionStatus(workflow.status),
            health=self._health_state(workflow, trigger, latest_run, active_run, now),
            owner_user_id=workflow.owner_user_id,
            owner_label=_owner_label(workflow),
            latest_version_number=workflow.latest_version_number,
            is_active=bool(workflow.is_active),
            tags=workflow.tags or [],
            trigger_type=(
                WorkflowTriggerType(trigger.trigger_type)
                if trigger
                else WorkflowTriggerType.MANUAL
            ),
            trigger_enabled=bool(trigger.enabled) if trigger else False,
            cron_expression=trigger.cron_expression if trigger else None,
            timezone=trigger.timezone if trigger else None,
            next_run_at=trigger.next_run_at if trigger else None,
            last_fire_at=trigger.last_fire_at if trigger else None,
            latest_run=latest_summary,
            active_run=active_summary,
            latest_failed_run=failed_summary,
            last_successful_run=success_summary,
            run_count=stats.get("run_count", 0),
            failure_count=stats.get("failure_count", 0),
            budget_limit_cents=_budget_limit(workflow, latest_run),
            estimated_cost_cents=stats.get("estimated_cost_cents", 0),
            actual_cost_cents=stats.get("actual_cost_cents", 0),
            updated_at=workflow.updated_at,
        )

    def _health_state(
        self,
        workflow: WorkflowDefinition,
        trigger: Optional[WorkflowTrigger],
        latest_run: Optional[WorkflowRun],
        active_run: Optional[WorkflowRun],
        now: datetime,
    ) -> WorkflowHealthState:
        if (
            workflow.status != WorkflowDefinitionStatus.ACTIVE.value
            or not workflow.is_active
        ):
            return WorkflowHealthState.DISABLED
        if active_run is not None:
            return WorkflowHealthState.RUNNING
        if latest_run and latest_run.status == WorkflowRunStatus.FAILED.value:
            return WorkflowHealthState.FAILED
        if (
            trigger
            and trigger.trigger_type == WorkflowTriggerType.SCHEDULE.value
            and trigger.enabled
            and trigger.next_run_at
        ):
            if trigger.next_run_at < now - timedelta(seconds=self.MISSED_GRACE_SECONDS):
                return WorkflowHealthState.MISSED
            return WorkflowHealthState.HEALTHY
        return WorkflowHealthState.NO_SCHEDULE

    def _schedule_health_state(
        self,
        workflow: WorkflowDefinition,
        trigger: WorkflowTrigger,
        latest_run: Optional[WorkflowRun],
        active_run: Optional[WorkflowRun],
        now: datetime,
    ) -> WorkflowHealthState:
        if (
            workflow.status != WorkflowDefinitionStatus.ACTIVE.value
            or not workflow.is_active
            or not trigger.enabled
        ):
            return WorkflowHealthState.DISABLED
        if active_run is not None:
            return WorkflowHealthState.RUNNING
        if latest_run and latest_run.status == WorkflowRunStatus.FAILED.value:
            return WorkflowHealthState.FAILED
        if trigger.next_run_at and trigger.next_run_at < now - timedelta(
            seconds=self.MISSED_GRACE_SECONDS
        ):
            return WorkflowHealthState.MISSED
        return WorkflowHealthState.HEALTHY

    def _totals(self, rows: list[WorkflowOperationsRow]) -> WorkflowOperationsTotals:
        return WorkflowOperationsTotals(
            total=len(rows),
            active=sum(
                1
                for row in rows
                if row.status == WorkflowDefinitionStatus.ACTIVE and row.is_active
            ),
            disabled=sum(
                1 for row in rows if row.health == WorkflowHealthState.DISABLED
            ),
            running=sum(1 for row in rows if row.health == WorkflowHealthState.RUNNING),
            failed=sum(1 for row in rows if row.health == WorkflowHealthState.FAILED),
            missed=sum(1 for row in rows if row.health == WorkflowHealthState.MISSED),
        )


def _current_trigger(workflow: WorkflowDefinition) -> Optional[WorkflowTrigger]:
    triggers = list(workflow.triggers or [])
    if not triggers:
        return None
    if workflow.current_version_id:
        for trigger in triggers:
            if trigger.version_id == workflow.current_version_id:
                return trigger
    return triggers[0]


def _current_version(workflow: WorkflowDefinition) -> Optional[WorkflowVersion]:
    if not workflow.current_version_id:
        return None
    for version in workflow.versions or []:
        if version.id == workflow.current_version_id:
            return version
    return None


def _budget_limit(
    workflow: WorkflowDefinition,
    latest_run: Optional[WorkflowRun],
) -> Optional[int]:
    version = _current_version(workflow)
    runtime = (version.definition or {}).get("runtime") if version else None
    if isinstance(runtime, dict) and runtime.get("budget_limit_cents") is not None:
        return int(runtime["budget_limit_cents"])
    return latest_run.budget_limit_cents if latest_run else None


def _owner_label(workflow: WorkflowDefinition) -> Optional[str]:
    owner = workflow.owner
    if owner is None:
        return None
    return owner.email or owner.username


def _run_summary(
    run: Optional[WorkflowRun],
    workflow_name: str,
) -> Optional[WorkflowRunSummary]:
    if run is None:
        return None
    return WorkflowRunSummary(
        id=run.id,
        workflow_id=run.workflow_id,
        workflow_name=workflow_name,
        version_id=run.version_id,
        version_number=run.version.version_number if run.version else None,
        status=WorkflowRunStatus(run.status),
        trigger_type=WorkflowTriggerType(run.trigger_type),
        requested_by_user_id=run.requested_by_user_id,
        retry_of_run_id=run.retry_of_run_id,
        queued_at=run.queued_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        duration_ms=_duration_ms(run),
        budget_limit_cents=run.budget_limit_cents,
        estimated_cost_cents=run.estimated_cost_cents,
        actual_cost_cents=run.actual_cost_cents,
    )


def _duration_ms(run: WorkflowRun) -> Optional[int]:
    if not run.started_at or not run.completed_at:
        return None
    return int((run.completed_at - run.started_at).total_seconds() * 1000)


def _preview_trigger(
    trigger: WorkflowTrigger,
    *,
    now: datetime,
    count: int = 5,
) -> list[WorkflowSchedulePreviewItem]:
    if not trigger.cron_expression or not trigger.timezone:
        return []
    try:
        return (
            WorkflowSchedulerService()
            .preview_schedule(
                WorkflowSchedulePreviewRequest(
                    cron=trigger.cron_expression,
                    timezone=trigger.timezone,
                    count=count,
                    start_at=now,
                )
            )
            .next_runs
        )
    except WorkflowScheduleValidationError:
        return []


def _group_upcoming_runs(
    runs: list[WorkflowScheduleBoardRun],
    now: datetime,
) -> list[WorkflowScheduleBoardGroup]:
    grouped = {key: [] for key, _ in _schedule_group_specs()}
    for run in sorted(runs, key=lambda item: item.run_at):
        grouped[_schedule_group_key(run.run_at, now)].append(run)

    return [
        WorkflowScheduleBoardGroup(key=key, label=label, runs=grouped[key])
        for key, label in _schedule_group_specs()
    ]


def _empty_schedule_groups() -> list[WorkflowScheduleBoardGroup]:
    return [
        WorkflowScheduleBoardGroup(key=key, label=label)
        for key, label in _schedule_group_specs()
    ]


def _schedule_group_specs() -> list[tuple[str, str]]:
    return [
        ("today", "Today"),
        ("tomorrow", "Tomorrow"),
        ("this_week", "This Week"),
        ("later", "Later"),
    ]


def _schedule_group_key(run_at: datetime, now: datetime) -> str:
    run_date = _aware_utc(run_at).date()
    today = _aware_utc(now).date()
    if run_date == today:
        return "today"
    if run_date == today + timedelta(days=1):
        return "tomorrow"
    if run_date <= today + timedelta(days=7):
        return "this_week"
    return "later"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
