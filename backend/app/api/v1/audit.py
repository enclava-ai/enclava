"""
Audit log query endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.core.security import get_current_user
from app.services.permission_manager import require_permission
from app.services.audit_service import log_audit_event, get_audit_logs, get_audit_stats
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool
    severity: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    size: int


class AuditStatsResponse(BaseModel):
    total_events: int
    events_by_action: dict
    events_by_resource_type: dict
    events_by_severity: dict
    success_rate: float
    failure_rate: float
    events_by_user: dict
    events_by_hour: dict
    top_actions: List[dict]
    top_resources: List[dict]


class AuditSearchRequest(BaseModel):
    user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    success: Optional[bool] = None
    severity: Optional[str] = None
    ip_address: Optional[str] = None
    search_text: Optional[str] = None


class SecurityEventsResponse(BaseModel):
    suspicious_activities: List[dict]
    failed_logins: List[dict]
    unusual_access_patterns: List[dict]
    high_severity_events: List[dict]


# Audit log query endpoints
@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    success: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with filtering and pagination"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:audit:read")

    # Build query
    query = select(AuditLog)
    conditions = []

    # Apply filters
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    if success is not None:
        conditions.append(AuditLog.success == success)
    if severity:
        conditions.append(AuditLog.severity == severity)
    if search:
        search_conditions = [
            AuditLog.action.ilike(f"%{search}%"),
            AuditLog.resource_type.ilike(f"%{search}%"),
            AuditLog.details.astext.ilike(f"%{search}%"),
        ]
        conditions.append(or_(*search_conditions))

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(AuditLog.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    offset = (page - 1) * size
    query = query.offset(offset).limit(size).order_by(AuditLog.created_at.desc())

    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()

    # Log audit event for this query
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="query_audit_logs",
        resource_type="audit_log",
        details={
            "filters": {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "success": success,
                "severity": severity,
                "search": search,
            },
            "page": page,
            "size": size,
            "total_results": total,
        },
    )

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        size=size,
    )


@router.post("/search", response_model=AuditLogListResponse)
async def search_audit_logs(
    search_request: AuditSearchRequest,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advanced search for audit logs"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:audit:read")

    # Use the audit service function
    logs = await get_audit_logs(
        db=db,
        user_id=search_request.user_id,
        action=search_request.action,
        resource_type=search_request.resource_type,
        resource_id=search_request.resource_id,
        start_date=search_request.start_date,
        end_date=search_request.end_date,
        limit=size,
        offset=(page - 1) * size,
    )

    # Get total count for the search
    total_query = select(func.count(AuditLog.id))
    conditions = []

    if search_request.user_id:
        conditions.append(AuditLog.user_id == search_request.user_id)
    if search_request.action:
        conditions.append(AuditLog.action == search_request.action)
    if search_request.resource_type:
        conditions.append(AuditLog.resource_type == search_request.resource_type)
    if search_request.resource_id:
        conditions.append(AuditLog.resource_id == search_request.resource_id)
    if search_request.start_date:
        conditions.append(AuditLog.created_at >= search_request.start_date)
    if search_request.end_date:
        conditions.append(AuditLog.created_at <= search_request.end_date)
    if search_request.success is not None:
        conditions.append(AuditLog.success == search_request.success)
    if search_request.severity:
        conditions.append(AuditLog.severity == search_request.severity)
    if search_request.ip_address:
        conditions.append(AuditLog.ip_address == search_request.ip_address)
    if search_request.search_text:
        search_conditions = [
            AuditLog.action.ilike(f"%{search_request.search_text}%"),
            AuditLog.resource_type.ilike(f"%{search_request.search_text}%"),
            AuditLog.details.astext.ilike(f"%{search_request.search_text}%"),
        ]
        conditions.append(or_(*search_conditions))

    if conditions:
        total_query = total_query.where(and_(*conditions))

    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="advanced_search_audit_logs",
        resource_type="audit_log",
        details={
            "search_criteria": search_request.model_dump(exclude_unset=True),
            "results_count": len(logs),
            "total_matches": total,
        },
    )

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        size=size,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_statistics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit log statistics"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:audit:read")

    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Get basic stats using audit service
    basic_stats = await get_audit_stats(db, start_date, end_date)

    # Get additional statistics
    conditions = [AuditLog.created_at >= start_date, AuditLog.created_at <= end_date]

    # Events by user
    user_query = (
        select(AuditLog.user_id, func.count(AuditLog.id).label("count"))
        .where(and_(*conditions))
        .group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    user_result = await db.execute(user_query)
    events_by_user = dict(user_result.fetchall())

    # Events by hour of day
    hour_query = (
        select(
            func.extract("hour", AuditLog.created_at).label("hour"),
            func.count(AuditLog.id).label("count"),
        )
        .where(and_(*conditions))
        .group_by(func.extract("hour", AuditLog.created_at))
        .order_by("hour")
    )

    hour_result = await db.execute(hour_query)
    events_by_hour = dict(hour_result.fetchall())

    # Top actions
    top_actions_query = (
        select(AuditLog.action, func.count(AuditLog.id).label("count"))
        .where(and_(*conditions))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    top_actions_result = await db.execute(top_actions_query)
    top_actions = [
        {"action": row[0], "count": row[1]} for row in top_actions_result.fetchall()
    ]

    # Top resources
    top_resources_query = (
        select(AuditLog.resource_type, func.count(AuditLog.id).label("count"))
        .where(and_(*conditions))
        .group_by(AuditLog.resource_type)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )

    top_resources_result = await db.execute(top_resources_query)
    top_resources = [
        {"resource_type": row[0], "count": row[1]}
        for row in top_resources_result.fetchall()
    ]

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_audit_statistics",
        resource_type="audit_log",
        details={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_events": basic_stats["total_events"],
        },
    )

    return AuditStatsResponse(
        **basic_stats,
        events_by_user=events_by_user,
        events_by_hour=events_by_hour,
        top_actions=top_actions,
        top_resources=top_resources,
    )


@router.get("/security-events", response_model=SecurityEventsResponse)
async def get_security_events(
    hours: int = Query(24, ge=1, le=168),  # Last 24 hours by default, max 1 week
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get security-related events and anomalies"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:audit:read")

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    # Failed logins
    failed_logins_query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.created_at >= start_time,
                AuditLog.action == "login",
                AuditLog.success == False,
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )

    failed_logins_result = await db.execute(failed_logins_query)
    failed_logins = [
        {
            "timestamp": log.created_at.isoformat(),
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "details": log.details,
        }
        for log in failed_logins_result.scalars().all()
    ]

    # High severity events
    high_severity_query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.created_at >= start_time,
                AuditLog.severity.in_(["error", "critical"]),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )

    high_severity_result = await db.execute(high_severity_query)
    high_severity_events = [
        {
            "timestamp": log.created_at.isoformat(),
            "action": log.action,
            "resource_type": log.resource_type,
            "severity": log.severity,
            "user_id": log.user_id,
            "ip_address": log.ip_address,
            "success": log.success,
            "details": log.details,
        }
        for log in high_severity_result.scalars().all()
    ]

    # Suspicious activities (multiple failed attempts from same IP)
    suspicious_ips_query = (
        select(AuditLog.ip_address, func.count(AuditLog.id).label("failed_count"))
        .where(
            and_(
                AuditLog.created_at >= start_time,
                AuditLog.success == False,
                AuditLog.ip_address.isnot(None),
            )
        )
        .group_by(AuditLog.ip_address)
        .having(func.count(AuditLog.id) >= 5)
        .order_by(func.count(AuditLog.id).desc())
    )

    suspicious_ips_result = await db.execute(suspicious_ips_query)
    suspicious_activities = [
        {
            "ip_address": row[0],
            "failed_attempts": row[1],
            "risk_level": "high" if row[1] >= 10 else "medium",
        }
        for row in suspicious_ips_result.fetchall()
    ]

    # Unusual access patterns (users accessing from multiple IPs)
    unusual_access_query = (
        select(
            AuditLog.user_id,
            func.count(func.distinct(AuditLog.ip_address)).label("ip_count"),
            func.array_agg(func.distinct(AuditLog.ip_address)).label("ip_addresses"),
        )
        .where(
            and_(
                AuditLog.created_at >= start_time,
                AuditLog.user_id.isnot(None),
                AuditLog.ip_address.isnot(None),
            )
        )
        .group_by(AuditLog.user_id)
        .having(func.count(func.distinct(AuditLog.ip_address)) >= 3)
        .order_by(func.count(func.distinct(AuditLog.ip_address)).desc())
    )

    unusual_access_result = await db.execute(unusual_access_query)
    unusual_access_patterns = [
        {
            "user_id": row[0],
            "unique_ips": row[1],
            "ip_addresses": row[2] if row[2] else [],
        }
        for row in unusual_access_result.fetchall()
    ]

    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="get_security_events",
        resource_type="audit_log",
        details={
            "time_range_hours": hours,
            "failed_logins_count": len(failed_logins),
            "high_severity_count": len(high_severity_events),
            "suspicious_ips_count": len(suspicious_activities),
            "unusual_access_patterns_count": len(unusual_access_patterns),
        },
    )

    return SecurityEventsResponse(
        suspicious_activities=suspicious_activities,
        failed_logins=failed_logins,
        unusual_access_patterns=unusual_access_patterns,
        high_severity_events=high_severity_events,
    )


@router.get("/export")
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs in CSV or JSON format"""

    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:audit:export")

    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Limit export size
    max_records = 10000

    # Build query
    query = select(AuditLog)
    conditions = [AuditLog.created_at >= start_date, AuditLog.created_at <= end_date]

    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)

    query = (
        query.where(and_(*conditions))
        .order_by(AuditLog.created_at.desc())
        .limit(max_records)
    )

    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()

    # Log export event
    await log_audit_event(
        db=db,
        user_id=current_user["id"],
        action="export_audit_logs",
        resource_type="audit_log",
        details={
            "format": format,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "records_exported": len(logs),
            "filters": {
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
            },
        },
    )

    if format == "json":
        from fastapi.responses import JSONResponse

        export_data = [
            {
                "id": str(log.id),
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "success": log.success,
                "severity": log.severity,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
        return JSONResponse(content=export_data)

    else:  # CSV format
        import csv
        import io
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "ID",
                "User ID",
                "Action",
                "Resource Type",
                "Resource ID",
                "IP Address",
                "Success",
                "Severity",
                "Created At",
                "Details",
            ]
        )

        # Write data
        for log in logs:
            writer.writerow(
                [
                    str(log.id),
                    log.user_id or "",
                    log.action,
                    log.resource_type,
                    log.resource_id or "",
                    log.ip_address or "",
                    log.success,
                    log.severity,
                    log.created_at.isoformat(),
                    str(log.details),
                ]
            )

        output.seek(0)

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
            },
        )
