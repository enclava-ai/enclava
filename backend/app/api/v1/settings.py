"""
Settings management endpoints
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_user
from app.services.permission_manager import require_permission
from app.services.audit_service import log_audit_event
from app.core.logging import get_logger
from app.core.config import settings as app_settings

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class SettingValue(BaseModel):
    value: Any
    value_type: str = Field(..., pattern="^(string|integer|float|boolean|json|list)$")
    description: Optional[str] = None
    is_secret: bool = False


class SettingResponse(BaseModel):
    key: str
    value: Any
    value_type: str
    description: Optional[str] = None
    is_secret: bool = False
    category: str
    is_system: bool = False
    created_at: str
    updated_at: Optional[str] = None


class SettingUpdate(BaseModel):
    value: Any
    description: Optional[str] = None


class SystemInfoResponse(BaseModel):
    version: str
    environment: str
    database_status: str
    redis_status: str
    litellm_status: str
    modules_loaded: int
    active_users: int
    total_api_keys: int
    uptime_seconds: int


class PlatformConfigResponse(BaseModel):
    app_name: str
    debug_mode: bool
    log_level: str
    cors_origins: List[str]
    rate_limiting_enabled: bool
    max_upload_size: int
    session_timeout_minutes: int
    api_key_prefix: str
    features: Dict[str, bool]
    maintenance_mode: bool = False
    maintenance_message: Optional[str] = None


class SecurityConfigResponse(BaseModel):
    password_min_length: int
    password_require_special: bool
    password_require_numbers: bool
    password_require_uppercase: bool
    session_timeout_minutes: int
    max_login_attempts: int
    lockout_duration_minutes: int
    require_2fa: bool = False
    allowed_domains: List[str] = Field(default_factory=list)
    ip_whitelist_enabled: bool = False


# Global settings storage (in a real app, this would be in database)
SETTINGS_STORE: Dict[str, Dict[str, Any]] = {
    "platform": {
        "app_name": {"value": "Confidential Empire", "type": "string", "description": "Application name"},
        "maintenance_mode": {"value": False, "type": "boolean", "description": "Enable maintenance mode"},
        "maintenance_message": {"value": None, "type": "string", "description": "Maintenance mode message"},
        "debug_mode": {"value": False, "type": "boolean", "description": "Enable debug mode"},
        "max_upload_size": {"value": 10485760, "type": "integer", "description": "Maximum upload size in bytes"},
    },
    "api": {
        # Security Settings
        "security_enabled": {"value": True, "type": "boolean", "description": "Enable API security system"},
        "threat_detection_enabled": {"value": True, "type": "boolean", "description": "Enable threat detection analysis"},
        "rate_limiting_enabled": {"value": True, "type": "boolean", "description": "Enable rate limiting"},
        "ip_reputation_enabled": {"value": True, "type": "boolean", "description": "Enable IP reputation checking"},
        "anomaly_detection_enabled": {"value": True, "type": "boolean", "description": "Enable anomaly detection"},
        "security_headers_enabled": {"value": True, "type": "boolean", "description": "Enable security headers"},
        
        # Rate Limiting by Authentication Level  
        "rate_limit_authenticated_per_minute": {"value": 200, "type": "integer", "description": "Rate limit for authenticated users per minute"},
        "rate_limit_authenticated_per_hour": {"value": 5000, "type": "integer", "description": "Rate limit for authenticated users per hour"},
        "rate_limit_api_key_per_minute": {"value": 1000, "type": "integer", "description": "Rate limit for API key users per minute"},
        "rate_limit_api_key_per_hour": {"value": 20000, "type": "integer", "description": "Rate limit for API key users per hour"},
        "rate_limit_premium_per_minute": {"value": 5000, "type": "integer", "description": "Rate limit for premium users per minute"},
        "rate_limit_premium_per_hour": {"value": 100000, "type": "integer", "description": "Rate limit for premium users per hour"},
        
        # Security Thresholds
        "security_risk_threshold": {"value": 0.8, "type": "float", "description": "Risk score threshold for blocking requests (0.0-1.0)"},
        "security_warning_threshold": {"value": 0.6, "type": "float", "description": "Risk score threshold for warnings (0.0-1.0)"},
        "anomaly_threshold": {"value": 0.7, "type": "float", "description": "Anomaly severity threshold (0.0-1.0)"},
        
        # Request Settings
        "max_request_size_mb": {"value": 10, "type": "integer", "description": "Maximum request size in MB for standard users"},
        "max_request_size_premium_mb": {"value": 50, "type": "integer", "description": "Maximum request size in MB for premium users"},
        "enable_cors": {"value": True, "type": "boolean", "description": "Enable CORS headers"},
        "cors_origins": {"value": ["http://localhost:3000", "http://localhost:53000"], "type": "list", "description": "Allowed CORS origins"},
        "api_key_expiry_days": {"value": 90, "type": "integer", "description": "Default API key expiry in days"},
        
        # IP Security
        "blocked_ips": {"value": [], "type": "list", "description": "List of blocked IP addresses"},
        "allowed_ips": {"value": [], "type": "list", "description": "List of allowed IP addresses (empty = allow all)"},
        "csp_header": {"value": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';", "type": "string", "description": "Content Security Policy header"},
    },
    "security": {
        "password_min_length": {"value": 8, "type": "integer", "description": "Minimum password length"},
        "password_require_special": {"value": True, "type": "boolean", "description": "Require special characters in passwords"},
        "password_require_numbers": {"value": True, "type": "boolean", "description": "Require numbers in passwords"},
        "password_require_uppercase": {"value": True, "type": "boolean", "description": "Require uppercase letters in passwords"},
        "max_login_attempts": {"value": 5, "type": "integer", "description": "Maximum login attempts before lockout"},
        "lockout_duration_minutes": {"value": 15, "type": "integer", "description": "Account lockout duration in minutes"},
        "require_2fa": {"value": False, "type": "boolean", "description": "Require two-factor authentication"},
        "ip_whitelist_enabled": {"value": False, "type": "boolean", "description": "Enable IP whitelist"},
        "allowed_domains": {"value": [], "type": "list", "description": "Allowed email domains for registration"},
    },
    "features": {
        "user_registration": {"value": True, "type": "boolean", "description": "Allow user registration"},
        "api_key_creation": {"value": True, "type": "boolean", "description": "Allow API key creation"},
        "budget_enforcement": {"value": True, "type": "boolean", "description": "Enable budget enforcement"},
        "audit_logging": {"value": True, "type": "boolean", "description": "Enable audit logging"},
        "module_hot_reload": {"value": True, "type": "boolean", "description": "Enable module hot reload"},
        "tee_support": {"value": True, "type": "boolean", "description": "Enable TEE (Trusted Execution Environment) support"},
        "advanced_analytics": {"value": True, "type": "boolean", "description": "Enable advanced analytics"},
    },
    "notifications": {
        "email_enabled": {"value": False, "type": "boolean", "description": "Enable email notifications"},
        "slack_enabled": {"value": False, "type": "boolean", "description": "Enable Slack notifications"},
        "webhook_enabled": {"value": False, "type": "boolean", "description": "Enable webhook notifications"},
        "budget_alerts": {"value": True, "type": "boolean", "description": "Enable budget alert notifications"},
        "security_alerts": {"value": True, "type": "boolean", "description": "Enable security alert notifications"},
    }
}


# Settings management endpoints
@router.get("/")
async def list_settings(
    category: Optional[str] = None,
    include_secrets: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all settings or settings in a specific category"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:read")
    
    result = {}
    
    for cat, settings in SETTINGS_STORE.items():
        if category and cat != category:
            continue
            
        result[cat] = {}
        for key, setting in settings.items():
            # Hide secret values unless specifically requested and user has permission
            if setting.get("is_secret", False) and not include_secrets:
                if not any(perm in current_user.get("permissions", []) for perm in ["platform:settings:admin", "platform:*"]):
                    continue
            
            result[cat][key] = {
                "value": setting["value"],
                "type": setting["type"],
                "description": setting.get("description", ""),
                "is_secret": setting.get("is_secret", False)
            }
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="list_settings",
        resource_type="setting",
        details={"category": category, "include_secrets": include_secrets}
    )
    
    return result


@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get system information and status"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:read")
    
    import psutil
    import time
    from app.models.api_key import APIKey
    
    # Get database status
    try:
        await db.execute(select(1))
        database_status = "healthy"
    except Exception:
        database_status = "error"
    
    # Get Redis status (simplified check)
    redis_status = "healthy"  # Would implement actual Redis check
    
    # Get LiteLLM status (simplified check)
    litellm_status = "healthy"  # Would implement actual LiteLLM check
    
    # Get modules loaded (from module manager)
    modules_loaded = 8  # Would get from actual module manager
    
    # Get active users count (last 24 hours)
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    active_users_query = select(User.id).where(User.last_login >= yesterday)
    active_users_result = await db.execute(active_users_query)
    active_users = len(active_users_result.fetchall())
    
    # Get total API keys
    total_api_keys_query = select(APIKey.id)
    total_api_keys_result = await db.execute(total_api_keys_query)
    total_api_keys = len(total_api_keys_result.fetchall())
    
    # Get uptime (simplified - would track actual start time)
    uptime_seconds = int(time.time()) % 86400  # Placeholder
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_system_info",
        resource_type="system"
    )
    
    return SystemInfoResponse(
        version="1.0.0",
        environment="production",
        database_status=database_status,
        redis_status=redis_status,
        litellm_status=litellm_status,
        modules_loaded=modules_loaded,
        active_users=active_users,
        total_api_keys=total_api_keys,
        uptime_seconds=uptime_seconds
    )


@router.get("/platform-config", response_model=PlatformConfigResponse)
async def get_platform_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get platform configuration"""
    
    # Basic users can see non-sensitive platform config
    platform_settings = SETTINGS_STORE.get("platform", {})
    feature_settings = SETTINGS_STORE.get("features", {})
    
    features = {key: setting["value"] for key, setting in feature_settings.items()}
    
    # Get API settings for rate limiting
    api_settings = SETTINGS_STORE.get("api", {})
    
    return PlatformConfigResponse(
        app_name=platform_settings.get("app_name", {}).get("value", "Confidential Empire"),
        debug_mode=platform_settings.get("debug_mode", {}).get("value", False),
        log_level=app_settings.LOG_LEVEL,
        cors_origins=app_settings.CORS_ORIGINS,
        rate_limiting_enabled=api_settings.get("rate_limiting_enabled", {}).get("value", True),
        max_upload_size=platform_settings.get("max_upload_size", {}).get("value", 10485760),
        session_timeout_minutes=app_settings.SESSION_EXPIRE_MINUTES,
        api_key_prefix=app_settings.API_KEY_PREFIX,
        features=features,
        maintenance_mode=platform_settings.get("maintenance_mode", {}).get("value", False),
        maintenance_message=platform_settings.get("maintenance_message", {}).get("value")
    )


@router.get("/security-config", response_model=SecurityConfigResponse)
async def get_security_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get security configuration"""
    
    # Check permissions for sensitive security settings
    require_permission(current_user.get("permissions", []), "platform:settings:read")
    
    security_settings = SETTINGS_STORE.get("security", {})
    
    return SecurityConfigResponse(
        password_min_length=security_settings.get("password_min_length", {}).get("value", 8),
        password_require_special=security_settings.get("password_require_special", {}).get("value", True),
        password_require_numbers=security_settings.get("password_require_numbers", {}).get("value", True),
        password_require_uppercase=security_settings.get("password_require_uppercase", {}).get("value", True),
        session_timeout_minutes=app_settings.SESSION_EXPIRE_MINUTES,
        max_login_attempts=security_settings.get("max_login_attempts", {}).get("value", 5),
        lockout_duration_minutes=security_settings.get("lockout_duration_minutes", {}).get("value", 15),
        require_2fa=security_settings.get("require_2fa", {}).get("value", False),
        allowed_domains=security_settings.get("allowed_domains", {}).get("value", []),
        ip_whitelist_enabled=security_settings.get("ip_whitelist_enabled", {}).get("value", False)
    )


@router.get("/{category}/{key}")
async def get_setting(
    category: str,
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific setting value"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:read")
    
    if category not in SETTINGS_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings category '{category}' not found"
        )
    
    if key not in SETTINGS_STORE[category]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found in category '{category}'"
        )
    
    setting = SETTINGS_STORE[category][key]
    
    # Check if it's a secret setting
    if setting.get("is_secret", False):
        require_permission(current_user.get("permissions", []), "platform:settings:admin")
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="get_setting",
        resource_type="setting",
        resource_id=f"{category}.{key}"
    )
    
    return {
        "category": category,
        "key": key,
        "value": setting["value"],
        "type": setting["type"],
        "description": setting.get("description", ""),
        "is_secret": setting.get("is_secret", False)
    }


@router.put("/{category}/{key}")
async def update_setting(
    category: str,
    key: str,
    setting_update: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a specific setting"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:update")
    
    if category not in SETTINGS_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings category '{category}' not found"
        )
    
    if key not in SETTINGS_STORE[category]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found in category '{category}'"
        )
    
    setting = SETTINGS_STORE[category][key]
    
    # Check if it's a secret setting
    if setting.get("is_secret", False):
        require_permission(current_user.get("permissions", []), "platform:settings:admin")
    
    # Store original value for audit
    original_value = setting["value"]
    
    # Validate value type
    expected_type = setting["type"]
    new_value = setting_update.value
    
    if expected_type == "integer" and not isinstance(new_value, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{key}' expects an integer value"
        )
    elif expected_type == "boolean" and not isinstance(new_value, bool):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{key}' expects a boolean value"
        )
    elif expected_type == "float" and not isinstance(new_value, (int, float)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{key}' expects a numeric value"
        )
    elif expected_type == "list" and not isinstance(new_value, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{key}' expects a list value"
        )
    
    # Update setting
    SETTINGS_STORE[category][key]["value"] = new_value
    if setting_update.description is not None:
        SETTINGS_STORE[category][key]["description"] = setting_update.description
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="update_setting",
        resource_type="setting",
        resource_id=f"{category}.{key}",
        details={
            "original_value": original_value,
            "new_value": new_value,
            "description_updated": setting_update.description is not None
        }
    )
    
    logger.info(f"Setting updated: {category}.{key} by {current_user['username']}")
    
    return {
        "category": category,
        "key": key,
        "value": new_value,
        "type": expected_type,
        "description": SETTINGS_STORE[category][key].get("description", ""),
        "message": "Setting updated successfully"
    }


@router.post("/reset-defaults")
async def reset_to_defaults(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset settings to default values"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:admin")
    
    # Define default values
    defaults = {
        "platform": {
            "app_name": {"value": "Confidential Empire", "type": "string"},
            "maintenance_mode": {"value": False, "type": "boolean"},
            "debug_mode": {"value": False, "type": "boolean"},
            "max_upload_size": {"value": 10485760, "type": "integer"},
        },
        "api": {
            # Security Settings
            "security_enabled": {"value": True, "type": "boolean"},
            "threat_detection_enabled": {"value": True, "type": "boolean"},
            "rate_limiting_enabled": {"value": True, "type": "boolean"},
            "ip_reputation_enabled": {"value": True, "type": "boolean"},
            "anomaly_detection_enabled": {"value": True, "type": "boolean"},
            "security_headers_enabled": {"value": True, "type": "boolean"},
            
            # Rate Limiting by Authentication Level
            "rate_limit_authenticated_per_minute": {"value": 200, "type": "integer"},
            "rate_limit_authenticated_per_hour": {"value": 5000, "type": "integer"},
            "rate_limit_api_key_per_minute": {"value": 1000, "type": "integer"},
            "rate_limit_api_key_per_hour": {"value": 20000, "type": "integer"},
            "rate_limit_premium_per_minute": {"value": 5000, "type": "integer"},
            "rate_limit_premium_per_hour": {"value": 100000, "type": "integer"},
            
            # Security Thresholds
            "security_risk_threshold": {"value": 0.8, "type": "float"},
            "security_warning_threshold": {"value": 0.6, "type": "float"},
            "anomaly_threshold": {"value": 0.7, "type": "float"},
            
            # Request Settings
            "max_request_size_mb": {"value": 10, "type": "integer"},
            "max_request_size_premium_mb": {"value": 50, "type": "integer"},
            "enable_cors": {"value": True, "type": "boolean"},
            "cors_origins": {"value": ["http://localhost:3000", "http://localhost:53000"], "type": "list"},
            "api_key_expiry_days": {"value": 90, "type": "integer"},
            
            # IP Security
            "blocked_ips": {"value": [], "type": "list"},
            "allowed_ips": {"value": [], "type": "list"},
            "csp_header": {"value": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';", "type": "string"},
        },
        "security": {
            "password_min_length": {"value": 8, "type": "integer"},
            "password_require_special": {"value": True, "type": "boolean"},
            "password_require_numbers": {"value": True, "type": "boolean"},
            "password_require_uppercase": {"value": True, "type": "boolean"},
            "max_login_attempts": {"value": 5, "type": "integer"},
            "lockout_duration_minutes": {"value": 15, "type": "integer"},
            "require_2fa": {"value": False, "type": "boolean"},
            "ip_whitelist_enabled": {"value": False, "type": "boolean"},
            "allowed_domains": {"value": [], "type": "list"},
        },
        "features": {
            "user_registration": {"value": True, "type": "boolean"},
            "api_key_creation": {"value": True, "type": "boolean"},
            "budget_enforcement": {"value": True, "type": "boolean"},
            "audit_logging": {"value": True, "type": "boolean"},
            "module_hot_reload": {"value": True, "type": "boolean"},
            "tee_support": {"value": True, "type": "boolean"},
            "advanced_analytics": {"value": True, "type": "boolean"},
        }
    }
    
    reset_categories = [category] if category else list(defaults.keys())
    
    for cat in reset_categories:
        if cat in defaults and cat in SETTINGS_STORE:
            for key, default_setting in defaults[cat].items():
                if key in SETTINGS_STORE[cat]:
                    SETTINGS_STORE[cat][key]["value"] = default_setting["value"]
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="reset_settings_to_defaults",
        resource_type="setting",
        details={"categories_reset": reset_categories}
    )
    
    logger.info(f"Settings reset to defaults: {reset_categories} by {current_user['username']}")
    
    return {
        "message": f"Settings reset to defaults for categories: {reset_categories}",
        "categories_reset": reset_categories
    }


@router.post("/export")
async def export_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export all settings to JSON"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:export")
    
    # Export all settings (excluding secrets for non-admin users)
    export_data = {}
    
    for category, settings in SETTINGS_STORE.items():
        export_data[category] = {}
        for key, setting in settings.items():
            # Skip secret settings for non-admin users
            if setting.get("is_secret", False):
                if not any(perm in current_user.get("permissions", []) for perm in ["platform:settings:admin", "platform:*"]):
                    continue
            
            export_data[category][key] = {
                "value": setting["value"],
                "type": setting["type"],
                "description": setting.get("description", ""),
                "is_secret": setting.get("is_secret", False)
            }
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="export_settings",
        resource_type="setting",
        details={"categories_exported": list(export_data.keys())}
    )
    
    return {
        "settings": export_data,
        "exported_at": datetime.utcnow().isoformat(),
        "exported_by": current_user['username']
    }


@router.post("/import")
async def import_settings(
    settings_data: Dict[str, Dict[str, Dict[str, Any]]],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import settings from JSON"""
    
    # Check permissions
    require_permission(current_user.get("permissions", []), "platform:settings:admin")
    
    imported_count = 0
    errors = []
    
    for category, settings in settings_data.items():
        if category not in SETTINGS_STORE:
            errors.append(f"Unknown category: {category}")
            continue
            
        for key, setting_data in settings.items():
            if key not in SETTINGS_STORE[category]:
                errors.append(f"Unknown setting: {category}.{key}")
                continue
            
            try:
                # Validate and import
                expected_type = SETTINGS_STORE[category][key]["type"]
                new_value = setting_data.get("value")
                
                # Basic type validation
                if expected_type == "integer" and not isinstance(new_value, int):
                    errors.append(f"Invalid type for {category}.{key}: expected integer")
                    continue
                elif expected_type == "boolean" and not isinstance(new_value, bool):
                    errors.append(f"Invalid type for {category}.{key}: expected boolean")
                    continue
                
                SETTINGS_STORE[category][key]["value"] = new_value
                if "description" in setting_data:
                    SETTINGS_STORE[category][key]["description"] = setting_data["description"]
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Error importing {category}.{key}: {str(e)}")
    
    # Log audit event
    await log_audit_event(
        db=db,
        user_id=current_user['id'],
        action="import_settings",
        resource_type="setting",
        details={
            "imported_count": imported_count,
            "errors_count": len(errors),
            "errors": errors
        }
    )
    
    logger.info(f"Settings imported: {imported_count} settings by {current_user['username']}")
    
    return {
        "message": f"Import completed. {imported_count} settings imported.",
        "imported_count": imported_count,
        "errors": errors
    }