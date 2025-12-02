"""
Permissions Module
Role-based access control decorators and utilities
"""
from datetime import datetime
from functools import wraps
from typing import List, Optional, Union, Callable
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer

from app.models.user import User


security = HTTPBearer()


def require_permission(
    user: User, permission: str, resource_id: Optional[Union[str, int]] = None
):
    """
    Check if user has the required permission

    Args:
        user: User object from dependency injection
        permission: Required permission string
        resource_id: Optional resource ID for resource-specific permissions

    Raises:
        HTTPException: If user doesn't have the required permission
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active"
        )

    # Check if account is locked
    if user.account_locked:
        if user.account_locked_until and user.account_locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is temporarily locked",
            )
        else:
            # Unlock account if lock period has expired
            user.unlock_account()

    # Check permission
    if not user.has_permission(permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission}' required",
        )


def require_permissions(permissions: List[str], require_all: bool = True):
    """
    Decorator to require multiple permissions

    Args:
        permissions: List of required permissions
        require_all: If True, user must have all permissions. If False, any one permission is sufficient
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (assuming it's passed as a dependency)
            user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                    break

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check permissions
            if require_all:
                # User must have all permissions
                for permission in permissions:
                    if not user.has_permission(permission):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"All of the following permissions required: {', '.join(permissions)}",
                        )
            else:
                # User needs at least one permission
                if not any(
                    user.has_permission(permission) for permission in permissions
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"At least one of the following permissions required: {', '.join(permissions)}",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role_names: Union[str, List[str]], require_all: bool = True):
    """
    Decorator to require specific roles

    Args:
        role_names: Required role name(s)
        require_all: If True, user must have all roles. If False, any one role is sufficient
    """
    if isinstance(role_names, str):
        role_names = [role_names]

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                    break

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check roles
            user_role_names = []
            if user.role:
                user_role_names.append(user.role.name)

            if require_all:
                # User must have all roles
                for role_name in role_names:
                    if role_name not in user_role_names:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"All of the following roles required: {', '.join(role_names)}",
                        )
            else:
                # User needs at least one role
                if not any(role_name in user_role_names for role_name in role_names):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"At least one of the following roles required: {', '.join(role_names)}",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_minimum_role(minimum_role_level: str):
    """
    Decorator to require minimum role level based on hierarchy

    Args:
        minimum_role_level: Minimum required role level
    """
    role_hierarchy = {"read_only": 1, "user": 2, "admin": 3, "super_admin": 4}

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs
            user = None
            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                    break

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Superusers bypass role checks
            if user.is_superuser:
                return await func(*args, **kwargs)

            # Check role level
            if not user.role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Minimum role level '{minimum_role_level}' required",
                )

            user_level = role_hierarchy.get(user.role.level, 0)
            required_level = role_hierarchy.get(minimum_role_level, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Minimum role level '{minimum_role_level}' required",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_resource_permission(
    user: User, resource_type: str, resource_id: Union[str, int], action: str
) -> bool:
    """
    Check if user has permission to perform action on specific resource

    Args:
        user: User object
        resource_type: Type of resource (e.g., 'user', 'budget', 'api_key')
        resource_id: ID of the resource
        action: Action to perform (e.g., 'read', 'update', 'delete')

    Returns:
        bool: True if user has permission, False otherwise
    """
    # Superusers can do anything
    if user.is_superuser:
        return True

    # Check basic permissions
    permission = f"{action}_{resource_type}"
    if user.has_permission(permission):
        return True

    # Check own resource permissions
    if resource_type == "user" and str(resource_id) == str(user.id):
        if user.has_permission(f"{action}_own"):
            return True

    # Check role-based resource access
    if user.role:
        # Admins can manage all users
        if resource_type == "user" and user.role.level in ["admin", "super_admin"]:
            return True

        # Users with budget permissions can manage budgets
        if resource_type == "budget" and user.role.can_manage_budgets:
            return True

    return False


def require_resource_permission(
    resource_type: str, resource_id_param: str = "resource_id", action: str = "read"
):
    """
    Decorator to require permission for specific resource

    Args:
        resource_type: Type of resource
        resource_id_param: Name of parameter containing resource ID
        action: Action to perform
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user and resource ID from kwargs
            user = None
            resource_id = None

            for key, value in kwargs.items():
                if isinstance(value, User):
                    user = value
                elif key == resource_id_param:
                    resource_id = value

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if resource_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resource ID not provided",
                )

            # Check resource permission
            if not check_resource_permission(user, resource_type, resource_id, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{action}_{resource_type}' required",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_budget_permission(user: User, budget_id: int, action: str) -> bool:
    """
    Check if user has permission to perform action on specific budget

    Args:
        user: User object
        budget_id: ID of the budget
        action: Action to perform

    Returns:
        bool: True if user has permission, False otherwise
    """
    # Superusers can do anything
    if user.is_superuser:
        return True

    # Check if user owns the budget
    for budget in user.budgets:
        if budget.id == budget_id and budget.is_active:
            return user.has_permission(f"{action}_own")

    # Check if user can manage all budgets
    if user.has_permission(f"{action}_all") or (
        user.role and user.role.can_manage_budgets
    ):
        return True

    return False


def check_api_key_permission(user: User, api_key_id: int, action: str) -> bool:
    """
    Check if user has permission to perform action on specific API key

    Args:
        user: User object
        api_key_id: ID of the API key
        action: Action to perform

    Returns:
        bool: True if user has permission, False otherwise
    """
    # Superusers can do anything
    if user.is_superuser:
        return True

    # Check if user owns the API key
    for api_key in user.api_keys:
        if api_key.id == api_key_id:
            return user.has_permission(f"{action}_own")

    # Check if user can manage all API keys
    if user.has_permission(f"{action}_all"):
        return True

    return False
