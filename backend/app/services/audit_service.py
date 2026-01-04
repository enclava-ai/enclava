"""
Audit logging service with async/non-blocking capabilities
"""

import asyncio
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.audit_log import AuditLog
from app.core.logging import get_logger

logger = get_logger(__name__)

# Background audit logging queue
_audit_queue = asyncio.Queue(maxsize=1000)
_audit_worker_started = False


async def _audit_worker():
    """Background worker to process audit events"""
    from app.db.database import async_session_factory

    logger.info("Audit worker started")

    while True:
        try:
            # Get audit event from queue
            audit_data = await _audit_queue.get()

            if audit_data is None:  # Shutdown signal
                break

            # Process the audit event in a separate database session
            async with async_session_factory() as db:
                try:
                    audit_log = AuditLog(**audit_data)
                    db.add(audit_log)
                    await db.commit()
                    logger.debug(f"Background audit logged: {audit_data.get('action')}")
                except Exception as e:
                    logger.error(f"Failed to write audit log in background: {e}")
                    await db.rollback()

            _audit_queue.task_done()

        except Exception as e:
            logger.error(f"Audit worker error: {e}")
            await asyncio.sleep(1)  # Brief pause before retrying


def start_audit_worker():
    """Start the background audit worker"""
    global _audit_worker_started
    if not _audit_worker_started:
        asyncio.create_task(_audit_worker())
        _audit_worker_started = True
        logger.info("Audit worker task created")


def _parse_user_id(user_id: Optional[str]) -> Optional[int]:
    """Convert user_id string to integer, handling None and invalid values."""
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (ValueError, TypeError):
        return None


async def log_audit_event_async(
    user_id: Optional[str] = None,
    api_key_id: Optional[str] = None,
    action: str = "",
    resource_type: str = "",
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    severity: str = "info",
):
    """
    Log an audit event asynchronously (non-blocking)

    This function queues the audit event for background processing,
    so it doesn't block the main request flow.
    """
    try:
        # Ensure audit worker is started
        if not _audit_worker_started:
            start_audit_worker()

        audit_details = details or {}
        if api_key_id:
            audit_details["api_key_id"] = api_key_id

        # Convert user_id to integer (database expects Integer, not String)
        parsed_user_id = _parse_user_id(user_id)

        audit_data = {
            "user_id": parsed_user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "description": f"{action} on {resource_type}",
            "details": audit_details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "severity": severity,
            "created_at": datetime.utcnow(),
        }

        # Queue the audit event (non-blocking)
        try:
            _audit_queue.put_nowait(audit_data)
            logger.debug(f"Audit event queued: {action} on {resource_type}")
        except asyncio.QueueFull:
            logger.warning("Audit queue full, dropping audit event")

    except Exception as e:
        logger.error(f"Failed to queue audit event: {e}")
        # Don't raise - audit failures shouldn't break main operations


async def log_audit_event(
    db: AsyncSession,
    user_id: Optional[str] = None,
    api_key_id: Optional[str] = None,
    action: str = "",
    resource_type: str = "",
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    severity: str = "info",
):
    """
    Log an audit event to the database

    Args:
        db: Database session
        user_id: ID of the user performing the action
        api_key_id: ID of the API key used (if applicable)
        action: Action being performed (e.g., "create_user", "login", "delete_resource")
        resource_type: Type of resource being acted upon (e.g., "user", "api_key", "budget")
        resource_id: ID of the specific resource
        details: Additional details about the action
        ip_address: IP address of the request
        user_agent: User agent string
        success: Whether the action was successful
        severity: Severity level (info, warning, error, critical)
    """

    try:
        audit_details = details or {}
        if api_key_id:
            audit_details["api_key_id"] = api_key_id

        # Convert user_id to integer (database expects Integer, not String)
        parsed_user_id = _parse_user_id(user_id)

        audit_log = AuditLog(
            user_id=parsed_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=f"{action} on {resource_type}",
            details=audit_details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            severity=severity,
            created_at=datetime.utcnow(),
        )

        db.add(audit_log)
        await db.flush()  # Don't commit here, let the caller control the transaction

        logger.debug(
            f"Audit event logged: {action} on {resource_type} by user {user_id}"
        )

    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        # Don't raise here as audit logging shouldn't break the main operation


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Query audit logs with filtering

    Args:
        db: Database session
        user_id: Filter by user ID
        action: Filter by action
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List of audit log entries
    """

    from sqlalchemy import select, and_

    query = select(AuditLog)
    conditions = []

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

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def get_audit_stats(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """
    Get audit statistics

    Args:
        db: Database session
        start_date: Start date for statistics
        end_date: End date for statistics

    Returns:
        Dictionary with audit statistics
    """

    from sqlalchemy import select, func, and_

    conditions = []
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)

    # Total events
    total_query = select(func.count(AuditLog.id))
    if conditions:
        total_query = total_query.where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_events = total_result.scalar()

    # Events by action
    action_query = select(AuditLog.action, func.count(AuditLog.id)).group_by(
        AuditLog.action
    )
    if conditions:
        action_query = action_query.where(and_(*conditions))
    action_result = await db.execute(action_query)
    events_by_action = dict(action_result.fetchall())

    # Events by resource type
    resource_query = select(AuditLog.resource_type, func.count(AuditLog.id)).group_by(
        AuditLog.resource_type
    )
    if conditions:
        resource_query = resource_query.where(and_(*conditions))
    resource_result = await db.execute(resource_query)
    events_by_resource = dict(resource_result.fetchall())

    # Events by severity
    severity_query = select(AuditLog.severity, func.count(AuditLog.id)).group_by(
        AuditLog.severity
    )
    if conditions:
        severity_query = severity_query.where(and_(*conditions))
    severity_result = await db.execute(severity_query)
    events_by_severity = dict(severity_result.fetchall())

    # Success rate
    success_query = select(AuditLog.success, func.count(AuditLog.id)).group_by(
        AuditLog.success
    )
    if conditions:
        success_query = success_query.where(and_(*conditions))
    success_result = await db.execute(success_query)
    success_stats = dict(success_result.fetchall())

    return {
        "total_events": total_events,
        "events_by_action": events_by_action,
        "events_by_resource_type": events_by_resource,
        "events_by_severity": events_by_severity,
        "success_rate": success_stats.get(True, 0) / total_events
        if total_events > 0
        else 0,
        "failure_rate": success_stats.get(False, 0) / total_events
        if total_events > 0
        else 0,
    }
