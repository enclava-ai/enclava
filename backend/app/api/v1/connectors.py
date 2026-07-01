"""
Connector management API endpoints.

All endpoints require authentication.  Mutating endpoints (create, update,
delete, trigger sync) additionally require admin-level access.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import core_cache
from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.connector_source import (
    ConnectorSource,
    ConnectorStatus,
    ConnectorSyncJob,
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
    credentials: dict[str, Any] = {}  # plaintext — encrypted before DB write
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


class OAuthAuthorizeRequest(BaseModel):
    connector_type: str  # "notion" or "github"
    collection_id: int
    connector_name: Optional[str] = None  # optional name override


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_user(auth_context: Any) -> Optional[User]:
    if isinstance(auth_context, User):
        return auth_context
    if isinstance(auth_context, dict):
        user_obj = auth_context.get("user_obj")
        if isinstance(user_obj, User):
            return user_obj
    return None


def _auth_user_id(auth_context: Any) -> int:
    user = _auth_user(auth_context)
    if user:
        return int(user.id)
    if isinstance(auth_context, dict):
        return int(auth_context["id"])
    return int(auth_context.id)


def _role_level(auth_context: Any) -> Optional[str]:
    user = _auth_user(auth_context)
    if user and user.role:
        return user.role.level
    if isinstance(auth_context, dict):
        role = auth_context.get("role")
        return role if isinstance(role, str) else None
    role = getattr(auth_context, "role", None)
    if isinstance(role, str) or role is None:
        return role
    return getattr(role, "level", None)


def _is_admin(auth_context: Any) -> bool:
    user = _auth_user(auth_context)
    if user and user.is_superuser:
        return True
    if isinstance(auth_context, dict) and auth_context.get("is_superuser"):
        return True
    return _role_level(auth_context) in ("admin", "super_admin")


def _require_admin(user: Any) -> None:
    if _is_admin(user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required to manage connectors",
    )


async def _get_connector_or_404(connector_id: int, db: AsyncSession) -> ConnectorSource:
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

    is_admin = _is_admin(current_user)
    user_obj = _auth_user(current_user)

    visible = []
    for c in connectors:
        if is_admin:
            visible.append(c)
        else:
            collection = await db.get(RagCollection, c.collection_id)
            if collection and can_user_access_collection(collection, user_obj):
                visible.append(c)

    return {"success": True, "connectors": [c.to_dict() for c in visible]}


@router.get("/connectors/collections")
async def list_connector_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """List database-backed RAG collections that can be connector targets."""
    stmt = select(RagCollection).where(RagCollection.is_active.is_(True))
    result = await db.execute(stmt)
    collections = result.scalars().all()

    user_obj = _auth_user(current_user)
    visible = [
        collection
        for collection in collections
        if _is_admin(current_user) or can_user_access_collection(collection, user_obj)
    ]

    return {
        "success": True,
        "collections": [
            {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
            }
            for collection in visible
        ],
    }


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
        created_by_user_id=_auth_user_id(current_user),
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

    is_admin = _is_admin(current_user)
    if not is_admin:
        collection = await db.get(RagCollection, connector.collection_id)
        if not collection or not can_user_access_collection(
            collection, _auth_user(current_user)
        ):
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


@router.post("/connectors/oauth/authorize")
async def oauth_authorize(
    data: OAuthAuthorizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Initiate an OAuth authorization flow for a connector.  Requires admin."""
    _require_admin(current_user)

    supported = {"notion", "github"}
    if data.connector_type not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"connector_type must be one of: {sorted(supported)}",
        )

    # Verify target collection exists
    collection = await db.get(RagCollection, data.collection_id)
    if collection is None or not collection.is_active:
        raise HTTPException(status_code=404, detail="Target collection not found")

    # Validate provider credentials are configured
    if data.connector_type == "notion":
        if not settings.NOTION_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Notion OAuth is not configured. "
                    "Set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET environment variables."
                ),
            )
    elif data.connector_type == "github":
        if not settings.GITHUB_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "GitHub OAuth is not configured. "
                    "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
                ),
            )

    # Generate a CSRF-safe state token and store it in Redis
    state = secrets.token_urlsafe(32)
    state_data = {
        "connector_type": data.connector_type,
        "collection_id": data.collection_id,
        "user_id": _auth_user_id(current_user),
        "connector_name": data.connector_name,
    }
    await core_cache.set(f"oauth_state:{state}", state_data, ttl=600)

    # Build provider-specific authorization URL
    redirect_uri = f"{settings.BASE_URL}/api-internal/v1/connectors/oauth/callback"
    if data.connector_type == "notion":
        params = {
            "client_id": settings.NOTION_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "owner": "user",
            "state": state,
        }
        oauth_url = f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"
    else:  # github
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "repo,read:user",
            "state": state,
        }
        oauth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    return {"success": True, "oauth_url": oauth_url, "state": state}


@router.get("/connectors/oauth/callback")
async def oauth_callback(
    db: AsyncSession = Depends(get_db),
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> RedirectResponse:
    """Handle OAuth provider callback.  The state token provides the auth context."""
    base_admin_url = f"{settings.BASE_URL}/admin/rag"

    # Provider signalled an error
    if error:
        return RedirectResponse(
            url=f"{base_admin_url}?oauth_error={error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not state or not code:
        return RedirectResponse(
            url=f"{base_admin_url}?oauth_error=missing_state_or_code",
            status_code=status.HTTP_302_FOUND,
        )

    # Retrieve and validate the state from Redis
    state_data = await core_cache.get(f"oauth_state:{state}")
    if not state_data:
        return RedirectResponse(
            url=f"{base_admin_url}?oauth_error=invalid_or_expired_state",
            status_code=status.HTTP_302_FOUND,
        )

    # state_data may already be a dict (cache deserializes JSON automatically)
    if isinstance(state_data, str):
        try:
            state_data = json.loads(state_data)
        except json.JSONDecodeError:
            return RedirectResponse(
                url=f"{base_admin_url}?oauth_error=malformed_state",
                status_code=status.HTTP_302_FOUND,
            )

    connector_type = state_data.get("connector_type")
    collection_id = state_data.get("collection_id")
    user_id = state_data.get("user_id")
    connector_name = state_data.get("connector_name")

    redirect_uri = f"{settings.BASE_URL}/api-internal/v1/connectors/oauth/callback"

    # Exchange the authorization code for an access token
    credentials: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if connector_type == "notion":
                import base64 as _b64

                creds_str = (
                    f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}"
                )
                basic_token = _b64.b64encode(creds_str.encode()).decode()
                resp = await client.post(
                    "https://api.notion.com/v1/oauth/token",
                    headers={
                        "Authorization": f"Basic {basic_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                )
                resp.raise_for_status()
                token_data = resp.json()
                credentials = {
                    "access_token": token_data.get("access_token"),
                    "bot_id": token_data.get("bot_id"),
                    "workspace_id": token_data.get("workspace_id"),
                    "workspace_name": token_data.get("workspace_name"),
                }
            elif connector_type == "github":
                resp = await client.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    json={
                        "client_id": settings.GITHUB_CLIENT_ID,
                        "client_secret": settings.GITHUB_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                )
                resp.raise_for_status()
                token_data = resp.json()
                if "error" in token_data:
                    raise ValueError(
                        token_data.get("error_description", token_data["error"])
                    )
                credentials = {
                    "access_token": token_data.get("access_token"),
                    "token_type": token_data.get("token_type"),
                    "scope": token_data.get("scope"),
                }
            else:
                return RedirectResponse(
                    url=f"{base_admin_url}?oauth_error=unsupported_connector_type",
                    status_code=status.HTTP_302_FOUND,
                )
    except Exception as exc:
        logger.error("OAuth token exchange failed for %s: %s", connector_type, exc)
        return RedirectResponse(
            url=f"{base_admin_url}?oauth_error=token_exchange_failed",
            status_code=status.HTTP_302_FOUND,
        )

    # Encrypt credentials and persist the connector
    from app.services.connector_sync_service import encrypt_credentials

    encrypted = encrypt_credentials(credentials)
    name = connector_name or f"{connector_type.capitalize()} (OAuth)"
    connector = ConnectorSource(
        name=name,
        connector_type=connector_type,
        collection_id=collection_id,
        config={},
        encrypted_credentials=encrypted,
        sync_frequency="PT1H",
        status=ConnectorStatus.PENDING,
        created_by_user_id=user_id,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    # Clean up the one-time state token from Redis
    await core_cache.delete(f"oauth_state:{state}")

    return RedirectResponse(
        url=(
            f"{base_admin_url}"
            f"?oauth_success=true"
            f"&connector_id={connector.id}"
            f"&tab=connectors"
        ),
        status_code=status.HTTP_302_FOUND,
    )


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
