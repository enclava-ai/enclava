"""
Enhanced Permission Manager for Module-Specific Permissions

Provides hierarchical permission management with wildcard support,
dynamic module permission registration, and fine-grained access control.
"""

import re
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class PermissionAction(str, Enum):
    """Standard permission actions"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"
    VIEW = "view"
    ADMIN = "admin"


@dataclass
class Permission:
    """Permission definition"""
    resource: str
    action: str
    description: str = ""
    conditions: Optional[Dict[str, Any]] = None


@dataclass
class PermissionScope:
    """Permission scope for context-aware permissions"""
    namespace: str
    resource: str
    action: str
    context: Dict[str, Any] = None


class PermissionTree:
    """Hierarchical permission tree for efficient wildcard matching"""
    
    def __init__(self):
        self.root = {}
        self.permissions: Dict[str, Permission] = {}
    
    def add_permission(self, permission_string: str, permission: Permission):
        """Add a permission to the tree"""
        parts = permission_string.split(":")
        current = self.root
        
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current["_permission"] = permission
        self.permissions[permission_string] = permission
    
    def has_permission(self, user_permissions: List[str], required: str) -> bool:
        """Check if user has required permission with wildcard support"""
        # Handle None or empty permissions
        if not user_permissions:
            return False
            
        # Direct match
        if required in user_permissions:
            return True
        
        # Check wildcard patterns
        for user_perm in user_permissions:
            if self._matches_wildcard(user_perm, required):
                return True
        
        return False
    
    def _matches_wildcard(self, pattern: str, permission: str) -> bool:
        """Check if a wildcard pattern matches a permission"""
        if "*" not in pattern:
            return pattern == permission
        
        pattern_parts = pattern.split(":")
        perm_parts = permission.split(":")
        
        # Handle patterns ending with * (e.g., "platform:*" should match "platform:audit:read")
        if pattern_parts[-1] == "*" and len(pattern_parts) == 2:
            # Pattern like "platform:*" should match any permission starting with "platform:"
            if len(perm_parts) >= 2 and pattern_parts[0] == perm_parts[0]:
                return True
        
        # Original logic for exact-length matching (e.g., "platform:audit:*" matches "platform:audit:read")
        if len(pattern_parts) != len(perm_parts):
            return False
        
        for pattern_part, perm_part in zip(pattern_parts, perm_parts):
            if pattern_part == "*":
                continue
            elif pattern_part != perm_part:
                return False
        
        return True
    
    def get_matching_permissions(self, user_permissions: List[str]) -> Set[str]:
        """Get all permissions that match user's granted permissions"""
        matching = set()
        
        for granted in user_permissions:
            if "*" in granted:
                # Find all permissions matching this wildcard
                for perm in self.permissions.keys():
                    if self._matches_wildcard(granted, perm):
                        matching.add(perm)
            else:
                matching.add(granted)
        
        return matching


class ModulePermissionRegistry:
    """Registry for module-specific permissions"""
    
    def __init__(self):
        self.tree = PermissionTree()
        self.module_permissions: Dict[str, List[Permission]] = {}
        self.role_permissions: Dict[str, List[str]] = {}
        self.default_roles = self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> Dict[str, List[str]]:
        """Initialize default permission roles"""
        return {
            "super_admin": [
                "platform:*",
                "modules:*",
                "llm:*"
            ],
            "admin": [
                "platform:*",
                "modules:*",
                "llm:*"
            ],
            "developer": [
                "platform:api-keys:*",
                "platform:budgets:read",
                "llm:completions:execute",
                "llm:embeddings:execute",
                "modules:*:read",
                "modules:*:execute"
            ],
            "user": [
                "llm:completions:execute",
                "llm:embeddings:execute",
                "modules:*:read"
            ],
            "readonly": [
                "platform:*:read",
                "modules:*:read"
            ]
        }
    
    def register_module(self, module_id: str, permissions: List[Permission]):
        """Register permissions for a module"""
        self.module_permissions[module_id] = permissions
        
        for perm in permissions:
            perm_string = f"modules:{module_id}:{perm.resource}:{perm.action}"
            self.tree.add_permission(perm_string, perm)
        
        logger.info(f"Registered {len(permissions)} permissions for module {module_id}")
    
    def register_platform_permissions(self):
        """Register core platform permissions"""
        platform_permissions = [
            Permission("users", "create", "Create users"),
            Permission("users", "read", "View users"),
            Permission("users", "update", "Update users"),
            Permission("users", "delete", "Delete users"),
            Permission("users", "manage", "Full user management"),
            
            Permission("api-keys", "create", "Create API keys"),
            Permission("api-keys", "read", "View API keys"),
            Permission("api-keys", "update", "Update API keys"),
            Permission("api-keys", "delete", "Delete API keys"),
            Permission("api-keys", "manage", "Full API key management"),
            
            Permission("budgets", "create", "Create budgets"),
            Permission("budgets", "read", "View budgets"),
            Permission("budgets", "update", "Update budgets"),
            Permission("budgets", "delete", "Delete budgets"),
            Permission("budgets", "manage", "Full budget management"),
            
            Permission("audit", "read", "View audit logs"),
            Permission("audit", "export", "Export audit logs"),
            
            Permission("settings", "read", "View settings"),
            Permission("settings", "update", "Update settings"),
            Permission("settings", "manage", "Full settings management"),
            
            Permission("health", "read", "View health status"),
            Permission("metrics", "read", "View metrics"),
            
            Permission("permissions", "read", "View permissions"),
            Permission("permissions", "manage", "Manage permissions"),
            
            Permission("roles", "create", "Create roles"),
            Permission("roles", "read", "View roles"),
            Permission("roles", "update", "Update roles"),
            Permission("roles", "delete", "Delete roles"),
        ]
        
        for perm in platform_permissions:
            perm_string = f"platform:{perm.resource}:{perm.action}"
            self.tree.add_permission(perm_string, perm)
        
        # Register LLM permissions
        llm_permissions = [
            Permission("completions", "execute", "Execute chat completions"),
            Permission("embeddings", "execute", "Execute embeddings"),
            Permission("models", "list", "List available models"),
            Permission("usage", "view", "View usage statistics"),
        ]
        
        for perm in llm_permissions:
            perm_string = f"llm:{perm.resource}:{perm.action}"
            self.tree.add_permission(perm_string, perm)
        
        logger.info("Registered platform and LLM permissions")
    
    def check_permission(self, user_permissions: List[str], required: str, 
                        context: Dict[str, Any] = None) -> bool:
        """Check if user has required permission"""
        # Basic permission check
        has_perm = self.tree.has_permission(user_permissions, required)
        
        if not has_perm:
            return False
        
        # Context-based permission checks
        if context:
            return self._check_context_permissions(user_permissions, required, context)
        
        return True
    
    def _check_context_permissions(self, user_permissions: List[str], 
                                  required: str, context: Dict[str, Any]) -> bool:
        """Check context-aware permissions"""
        # Extract resource owner information
        resource_owner = context.get("owner_id")
        current_user = context.get("user_id")
        
        # Users can always access their own resources
        if resource_owner and current_user and resource_owner == current_user:
            return True
        
        # Check for elevated permissions for cross-user access
        if resource_owner and resource_owner != current_user:
            elevated_required = required.replace(":read", ":manage").replace(":update", ":manage")
            return self.tree.has_permission(user_permissions, elevated_required)
        
        return True
    
    def get_user_permissions(self, roles: List[str],
                           custom_permissions: List[str] = None) -> List[str]:
        """Get effective permissions for a user based on roles and custom permissions"""
        import time
        start_time = time.time()
        logger.info(f"=== GET USER PERMISSIONS START === Roles: {roles}, Custom perms: {custom_permissions}")
        
        try:
            permissions = set()
            
            # Add role-based permissions
            for role in roles:
                role_perms = self.role_permissions.get(role, self.default_roles.get(role, []))
                logger.info(f"Role '{role}' has {len(role_perms)} permissions")
                permissions.update(role_perms)
            
            # Add custom permissions
            if custom_permissions:
                permissions.update(custom_permissions)
                logger.info(f"Added {len(custom_permissions)} custom permissions")
            
            result = list(permissions)
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"=== GET USER PERMISSIONS END === Total permissions: {len(result)}, Duration: {duration:.3f}s")
            
            return result
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"=== GET USER PERMISSIONS FAILED === Duration: {duration:.3f}s, Error: {e}")
            raise
    
    def get_module_permissions(self, module_id: str) -> List[Permission]:
        """Get all permissions for a specific module"""
        return self.module_permissions.get(module_id, [])
    
    def get_available_permissions(self, namespace: str = None) -> Dict[str, List[Permission]]:
        """Get all available permissions, optionally filtered by namespace"""
        if namespace:
            filtered = {}
            for perm_string, permission in self.tree.permissions.items():
                if perm_string.startswith(f"{namespace}:"):
                    if namespace not in filtered:
                        filtered[namespace] = []
                    filtered[namespace].append(permission)
            return filtered
        
        # Group by namespace
        grouped = {}
        for perm_string, permission in self.tree.permissions.items():
            namespace = perm_string.split(":")[0]
            if namespace not in grouped:
                grouped[namespace] = []
            grouped[namespace].append(permission)
        
        return grouped
    
    def create_role(self, role_name: str, permissions: List[str]):
        """Create a custom role with specific permissions"""
        self.role_permissions[role_name] = permissions
        logger.info(f"Created role '{role_name}' with {len(permissions)} permissions")
    
    def validate_permissions(self, permissions: List[str]) -> Dict[str, Any]:
        """Validate a list of permissions"""
        valid = []
        invalid = []
        
        for perm in permissions:
            if perm in self.tree.permissions or self._is_valid_wildcard(perm):
                valid.append(perm)
            else:
                invalid.append(perm)
        
        return {
            "valid": valid,
            "invalid": invalid,
            "is_valid": len(invalid) == 0
        }
    
    def _is_valid_wildcard(self, permission: str) -> bool:
        """Check if a wildcard permission is valid"""
        if "*" not in permission:
            return False
        
        parts = permission.split(":")
        
        # Check if the structure is valid
        if len(parts) < 2:
            return False
        
        # Check if there are any valid permissions matching this pattern
        for existing_perm in self.tree.permissions.keys():
            if self.tree._matches_wildcard(permission, existing_perm):
                return True
        
        return False
    
    def get_permission_hierarchy(self) -> Dict[str, Any]:
        """Get the permission hierarchy tree structure"""
        def build_tree(node, path=""):
            tree = {}
            for key, value in node.items():
                if key == "_permission":
                    tree["_permission"] = {
                        "resource": value.resource,
                        "action": value.action,
                        "description": value.description
                    }
                else:
                    current_path = f"{path}:{key}" if path else key
                    tree[key] = build_tree(value, current_path)
            return tree
        
        return build_tree(self.tree.root)


def require_permission(user_permissions: List[str], required_permission: str, context: Optional[Dict[str, Any]] = None):
    """
    Decorator function to require a specific permission
    Raises HTTPException if user doesn't have the required permission
    
    Args:
        user_permissions: List of user's permissions
        required_permission: The permission string required
        context: Optional context for conditional permissions
        
    Raises:
        HTTPException: If user doesn't have the required permission
    """
    from fastapi import HTTPException, status
    
    if not permission_registry.check_permission(user_permissions, required_permission, context):
        logger.warning(f"Permission denied: required '{required_permission}', user has {user_permissions}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {required_permission}"
        )


# Global permission registry instance
permission_registry = ModulePermissionRegistry()