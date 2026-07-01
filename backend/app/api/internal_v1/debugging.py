"""
Debugging API endpoints for troubleshooting platform issues

SECURITY: These endpoints expose internal system state and should only be
accessible to superusers/admins. (#50)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db

router = APIRouter()


def _require_debug_access(current_user: dict) -> dict:
    """
    Require superuser or admin role for debug endpoint access.

    Security mitigation #50: Debug endpoints should only be accessible to admins.
    """
    if current_user.get("is_superuser"):
        return current_user

    role = current_user.get("role")
    if role and hasattr(role, "name"):
        role_name = role.name
    else:
        role_name = role

    if role_name in ("super_admin", "admin"):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Debug endpoints require administrator privileges",
    )


@router.get("/system/status")
async def get_system_status(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """Get system status for debugging"""
    # SECURITY FIX #50: Require admin privileges for debug endpoints
    _require_debug_access(current_user)

    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check module status
    module_status = {}
    try:
        from app.services.module_manager import module_manager

        modules = module_manager.list_modules()
        for module_name, module_info in modules.items():
            module_status[module_name] = {
                "status": module_info.get("status", "unknown"),
                "enabled": module_info.get("enabled", False),
            }
    except Exception as e:
        module_status = {"error": str(e)}

    # Check Redis (if configured)
    redis_status = "not configured"
    try:
        from app.core.cache import core_cache

        await core_cache.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    # Check Qdrant (if configured)
    qdrant_status = "not configured"
    try:
        from app.services.qdrant_service import qdrant_service

        collections = await qdrant_service.list_collections()
        qdrant_status = f"healthy ({len(collections)} collections)"
    except Exception as e:
        qdrant_status = f"error: {str(e)}"

    return {
        "database": db_status,
        "modules": module_status,
        "redis": redis_status,
        "qdrant": qdrant_status,
        "timestamp": "UTC",
    }
