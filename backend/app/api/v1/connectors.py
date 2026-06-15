"""
Connector management API endpoints.

All endpoints require authentication.  Mutating endpoints (create, update,
delete, trigger sync) additionally require admin-level access.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.connector_source import (
    ConnectorSource,
    ConnectorSyncJob,
    ConnectorStatus,
    ConnectorType,
)
from app.models.rag_collection import RagCollection
from app.models.user import User
from app.utils.collection_access import can_user_access_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Connectors"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    collection_id: int
    config: dict[str, Any] = {}
    credentials: dict[str, Any] = {}   # plaintext — encrypted before DB write
    sync_frequency: str = "PT1H"

    @field_validator("connector_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid = {t.value for t in ConnectorType}
        if v not in valid:
            raise ValueError(f"Unknown connector_type '{v}'. Valid: {sorted(valid)}")
        return v

    @field_validator("sync_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        from app.tasks.connector_sync import _parse_duration
        try:
            _parse_duration(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return v


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    credentials: Optional[dict[str, Any]] = None  # plaintext — re-encrypted if provided
    sync_frequency: Optional[str] = None
    status: Optional[str] = None  # 'active' or 'paused'

    @field_validator("sync_frequency")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.tasks.connector_sync import _parse_duration
        try:
            _parse_duration(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_admin(user: User) -> None:
    if user.is_superuser:
        return
    if user.role and user.role.level in ("admin", "super_admin"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required to manage connectors",
    )


async def _get_connector_or_404(
    connector_id: int, db: AsyncSession
) -> ConnectorSource:
    connector = await db.get(ConnectorSource, connector_id)
    if connector is None or not connector.is_active:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/connectors")
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all active connectors.  Admins see all; regular users see connectors
    whose target collection they can access."""
    stmt = select(ConnectorSource).where(ConnectorSource.is_active.is_(True))
    result = await db.execute(stmt)
    connectors = result.scalars().all()

    is_admin = current_user.is_superuser or (
        current_user.role and current_user.role.level in ("admin", "super_admin")
    )

    visible = []
    for c in connectors:
        if is_admin:
            visible.append(c)
        else:
            collection = await db.get(RagCollection, c.collection_id)
            if collection and can_user_access_collection(collection, current_user):
                visible.append(c)

    return {"success": True, "connectors": [c.to_dict() for c in visible]}


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
async def create_connector(
    data: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a new connector.  Requires admin."""
    _require_admin(current_user)

    # Verify target collection exists
    collection = await db.get(RagCollection, data.collection_id)
    if collection is None or not collection.is_active:
        raise HTTPException(status_code=404, detail="Target collection not found")

    # Encrypt credentials
    encrypted: Optional[str] = None
    if data.credentials:
        from app.services.connector_sync_service import encrypt_credentials
        encrypted = encrypt_credentials(data.credentials)

    connector = ConnectorSource(
        name=data.name,
        connector_type=data.connector_type,
        collection_id=data.collection_id,
        config=data.config,
        encrypted_credentials=encrypted,
        sync_frequency=data.sync_frequency,
        status=ConnectorStatus.PENDING,
        created_by_user_id=current_user.id,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    return {
        "success": True,
        "connector": connector.to_dict(),
        "message": "Connector created successfully",
    }


@router.get("/connectors/{connector_id}")
async def get_connector(
    connector_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get a single connector.  Users may only see connectors for accessible collections."""
    connector = await _get_connector_or_404(connector_id, db)

    is_admin = current_user.is_superuser or (
        current_user.role and current_user.role.level in ("admin", "super_admin")
    )
    if not is_admin:
        collection = await db.get(RagCollection, connector.collection_id)
        if not collection or not can_user_access_collection(collection, current_user):
            raise HTTPException(status_code=404, detail="Connector not found")

    return {"success": True, "connector": connector.to_dict()}


@router.patch("/connectors/{connector_id}")
async def update_connector(
    connector_id: int,
    data: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update connector settings.  Requires admin."""
    _require_admin(current_user)
    connector = await _get_connector_or_404(connector_id, db)

    if data.name is not None:
        connector.name = data.name
    if data.config is not None:
        connector.config = data.config
    if data.credentials is not None:
        from app.services.connector_sync_service import encrypt_credentials
        connector.encrypted_credentials = encrypt_credentials(data.credentials)
    if data.sync_frequency is not None:
        connector.sync_frequency = data.sync_frequency
    if data.status is not None:
        allowed = {ConnectorStatus.ACTIVE, ConnectorStatus.PAUSED}
        if data.status not in {s.value for s in allowed}:
            raise HTTPException(
                status_code=400,
                detail=f"status must be one of: {[s.value for s in allowed]}",
            )
        connector.status = data.status

    await db.commit()
    await db.refresh(connector)
    return {"success": True, "connector": connector.to_dict()}


@router.delete("/connectors/{connector_id}")
async def delete_connector(
    connector_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete a connector (sets is_active=False).  Requires admin."""
    _require_admin(current_user)
    connector = await _get_connector_or_404(connector_id, db)

    connector.is_active = False
    connector.status = ConnectorStatus.PAUSED
    await db.commit()

    return {"success": True, "message": "Connector deleted"}


@router.post("/connectors/{connector_id}/sync")
async def trigger_sync(
    connector_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Manually trigger an immediate sync.  Requires admin."""
    _require_admin(current_user)
    connector = await _get_connector_or_404(connector_id, db)

    # Fire the sync in a background task so the HTTP response returns immediately
    import asyncio
    from app.tasks.connector_sync import sync_connector_now

    asyncio.create_task(sync_connector_now(connector.id))

    return {
        "success": True,
        "message": f"Sync triggered for connector '{connector.name}'",
    }


@router.post("/connectors/{connector_id}/validate")
async def validate_connector(
    connector_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Test that the connector's credentials and config are valid.  Requires admin."""
    _require_admin(current_user)
    connector = await _get_connector_or_404(connector_id, db)

    credentials: dict[str, Any] = {}
    if connector.encrypted_credentials:
        from app.services.connector_sync_service import decrypt_credentials
        credentials = decrypt_credentials(connector.encrypted_credentials)

    from app.connectors.registry import build_connector
    try:
        impl = build_connector(
            ConnectorType(connector.connector_type),
            config=connector.config or {},
            credentials=credentials,
        )
        impl.validate()
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {"success": True, "message": "Connector credentials are valid"}


@router.get("/connectors/{connector_id}/jobs")
async def list_sync_jobs(
    connector_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return recent sync job history for a connector.  Requires admin."""
    _require_admin(current_user)
    await _get_connector_or_404(connector_id, db)

    stmt = (
        select(ConnectorSyncJob)
        .where(ConnectorSyncJob.connector_id == connector_id)
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return {"success": True, "jobs": [j.to_dict() for j in jobs]}


@router.get("/connectors/types/available")
async def available_connector_types(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the list of connector types that are registered."""
    from app.connectors.registry import available_connector_types as _avail
    return {
        "success": True,
        "connector_types": [t.value for t in _avail()],
    }
