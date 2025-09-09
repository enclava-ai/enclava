"""
Platform API routes for core platform operations
Includes permissions, users, API keys, budgets, audit, etc.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.services.permission_manager import permission_registry, Permission, PermissionScope
from app.core.logging import get_logger
from app.core.security import get_current_user

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models for API
class PermissionResponse(BaseModel):
    resource: str
    action: str
    description: str
    conditions: Optional[Dict[str, Any]] = None


class PermissionHierarchyResponse(BaseModel):
    hierarchy: Dict[str, Any]


class PermissionValidationRequest(BaseModel):
    permissions: List[str]


class PermissionValidationResponse(BaseModel):
    valid: List[str]
    invalid: List[str]
    is_valid: bool


class PermissionCheckRequest(BaseModel):
    user_permissions: List[str]
    required_permission: str
    context: Optional[Dict[str, Any]] = None


class PermissionCheckResponse(BaseModel):
    has_permission: bool
    matching_permissions: List[str]


class RoleRequest(BaseModel):
    role_name: str
    permissions: List[str]


class RoleResponse(BaseModel):
    role_name: str
    permissions: List[str]
    created: bool = True


class UserPermissionsRequest(BaseModel):
    roles: List[str]
    custom_permissions: Optional[List[str]] = None


class UserPermissionsResponse(BaseModel):
    effective_permissions: List[str]
    roles: List[str]
    custom_permissions: List[str]


# Permission management endpoints
@router.get("/permissions", response_model=Dict[str, List[PermissionResponse]])
async def get_available_permissions(namespace: Optional[str] = None):
    """Get all available permissions, optionally filtered by namespace"""
    try:
        permissions = permission_registry.get_available_permissions(namespace)
        
        # Convert to response format
        result = {}
        for ns, perms in permissions.items():
            result[ns] = [
                PermissionResponse(
                    resource=perm.resource,
                    action=perm.action,
                    description=perm.description,
                    conditions=getattr(perm, 'conditions', None)
                )
                for perm in perms
            ]
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get permissions: {str(e)}"
        )


@router.get("/permissions/hierarchy", response_model=PermissionHierarchyResponse)
async def get_permission_hierarchy():
    """Get the permission hierarchy tree structure"""
    try:
        hierarchy = permission_registry.get_permission_hierarchy()
        return PermissionHierarchyResponse(hierarchy=hierarchy)
    
    except Exception as e:
        logger.error(f"Error getting permission hierarchy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get permission hierarchy: {str(e)}"
        )


@router.post("/permissions/validate", response_model=PermissionValidationResponse)
async def validate_permissions(request: PermissionValidationRequest):
    """Validate a list of permissions"""
    try:
        validation_result = permission_registry.validate_permissions(request.permissions)
        return PermissionValidationResponse(**validation_result)
    
    except Exception as e:
        logger.error(f"Error validating permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate permissions: {str(e)}"
        )


@router.post("/permissions/check", response_model=PermissionCheckResponse)
async def check_permission(
    request: PermissionCheckRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check if user has a specific permission"""
    try:
        has_permission = permission_registry.check_permission(
            request.user_permissions,
            request.required_permission,
            request.context
        )
        
        matching_permissions = list(permission_registry.tree.get_matching_permissions(
            request.user_permissions
        ))
        
        return PermissionCheckResponse(
            has_permission=has_permission,
            matching_permissions=matching_permissions
        )
    
    except Exception as e:
        logger.error(f"Error checking permission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check permission: {str(e)}"
        )


@router.get("/permissions/modules/{module_id}", response_model=List[PermissionResponse])
async def get_module_permissions(module_id: str):
    """Get permissions for a specific module"""
    try:
        permissions = permission_registry.get_module_permissions(module_id)
        
        return [
            PermissionResponse(
                resource=perm.resource,
                action=perm.action,
                description=perm.description,
                conditions=getattr(perm, 'conditions', None)
            )
            for perm in permissions
        ]
    
    except Exception as e:
        logger.error(f"Error getting module permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get module permissions: {str(e)}"
        )


# Role management endpoints
@router.post("/roles", response_model=RoleResponse)
async def create_role(request: RoleRequest):
    """Create a custom role with specific permissions"""
    try:
        # Validate permissions first
        validation_result = permission_registry.validate_permissions(request.permissions)
        if not validation_result["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permissions: {validation_result['invalid']}"
            )
        
        permission_registry.create_role(request.role_name, request.permissions)
        
        return RoleResponse(
            role_name=request.role_name,
            permissions=request.permissions
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create role: {str(e)}"
        )


@router.get("/roles", response_model=Dict[str, List[str]])
async def get_roles():
    """Get all available roles and their permissions"""
    try:
        # Combine default roles and custom roles
        all_roles = {**permission_registry.default_roles, **permission_registry.role_permissions}
        return all_roles
    
    except Exception as e:
        logger.error(f"Error getting roles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get roles: {str(e)}"
        )


@router.get("/roles/{role_name}", response_model=RoleResponse)
async def get_role(role_name: str):
    """Get a specific role and its permissions"""
    try:
        # Check default roles first, then custom roles
        permissions = (permission_registry.role_permissions.get(role_name) or 
                      permission_registry.default_roles.get(role_name))
        
        if permissions is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found"
            )
        
        return RoleResponse(
            role_name=role_name,
            permissions=permissions,
            created=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get role: {str(e)}"
        )


# User permission calculation endpoints
@router.post("/users/permissions", response_model=UserPermissionsResponse)
async def calculate_user_permissions(request: UserPermissionsRequest):
    """Calculate effective permissions for a user based on roles and custom permissions"""
    try:
        effective_permissions = permission_registry.get_user_permissions(
            request.roles,
            request.custom_permissions
        )
        
        return UserPermissionsResponse(
            effective_permissions=effective_permissions,
            roles=request.roles,
            custom_permissions=request.custom_permissions or []
        )
    
    except Exception as e:
        logger.error(f"Error calculating user permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate user permissions: {str(e)}"
        )


# Health and status endpoints
@router.get("/health")
async def platform_health():
    """Platform health check endpoint"""
    try:
        # Get permission system status
        total_permissions = len(permission_registry.tree.permissions)
        total_modules = len(permission_registry.module_permissions)
        total_roles = len(permission_registry.default_roles) + len(permission_registry.role_permissions)
        
        return {
            "status": "healthy",
            "service": "Confidential Empire Platform API",
            "version": "1.0.0",
            "permission_system": {
                "total_permissions": total_permissions,
                "registered_modules": total_modules,
                "available_roles": total_roles
            }
        }
    
    except Exception as e:
        logger.error(f"Error checking platform health: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.get("/metrics")
async def platform_metrics():
    """Get platform metrics"""
    try:
        # Get permission system metrics
        namespaces = permission_registry.get_available_permissions()
        
        metrics = {
            "permissions": {
                "total": len(permission_registry.tree.permissions),
                "by_namespace": {ns: len(perms) for ns, perms in namespaces.items()}
            },
            "modules": {
                "registered": len(permission_registry.module_permissions),
                "names": list(permission_registry.module_permissions.keys())
            },
            "roles": {
                "default": len(permission_registry.default_roles),
                "custom": len(permission_registry.role_permissions),
                "total": len(permission_registry.default_roles) + len(permission_registry.role_permissions)
            }
        }
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error getting platform metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get platform metrics: {str(e)}"
        )