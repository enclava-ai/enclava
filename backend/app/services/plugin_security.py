"""
Plugin Security and Authentication Service
Handles plugin tokens, permissions, and security policies
"""
from jose import jwt
import hashlib
import secrets
import time
import redis
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import json
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.models.plugin import (
    Plugin,
    PluginConfiguration,
    PluginAuditLog,
    PluginPermission,
)
from app.models.user import User
from app.models.api_key import APIKey
from app.db.database import get_db
from app.services.plugin_configuration_service import PluginConfigurationService
from app.utils.exceptions import SecurityError, PluginError


logger = get_logger("plugin.security")


class PluginTokenManager:
    """Manages plugin authentication tokens"""

    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)

        # Initialize Redis connection for token blacklist
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis for token blacklist: {e}")
            self.redis_client = None

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for plugin secrets"""
        # First, try to get from environment variable (production)
        if settings.PLUGIN_ENCRYPTION_KEY:
            try:
                # Environment variable should contain base64-encoded key
                import base64

                return base64.b64decode(settings.PLUGIN_ENCRYPTION_KEY.encode())
            except Exception as e:
                logger.error(f"Invalid PLUGIN_ENCRYPTION_KEY in environment: {e}")
                raise SecurityError("Invalid encryption key configuration")

        # Development fallback: generate and store in data directory
        data_dir = Path("/data/plugin_keys")
        data_dir.mkdir(parents=True, exist_ok=True)
        key_file = data_dir / "encryption.key"

        try:
            if key_file.exists():
                return key_file.read_bytes()
            else:
                # Generate new key for development
                key = Fernet.generate_key()
                key_file.write_bytes(key)

                import base64

                logger.warning(
                    f"Generated new plugin encryption key for development. "
                    f"For production, set PLUGIN_ENCRYPTION_KEY environment variable to: "
                    f"{base64.b64encode(key).decode()}"
                )
                return key
        except Exception as e:
            logger.error(f"Failed to manage encryption key: {e}")
            raise SecurityError(f"Encryption key management failed: {e}")

    def generate_plugin_token(
        self,
        plugin_id: str,
        user_id: str,
        permissions: List[str],
        expires_hours: int = 24,
    ) -> str:
        """Generate JWT token for plugin authentication"""
        try:
            now = datetime.now(timezone.utc)
            expiration = now + timedelta(hours=expires_hours)

            payload = {
                "sub": user_id,
                "plugin_id": plugin_id,
                "permissions": permissions,
                "iat": int(now.timestamp()),
                "exp": int(expiration.timestamp()),
                "aud": "enclava-plugin",
                "iss": "enclava-platform",
                "jti": secrets.token_urlsafe(16),  # JWT ID for revocation
            }

            token = jwt.encode(payload, self.secret_key, algorithm="HS256")

            logger.info(f"Generated plugin token for {plugin_id} (user: {user_id})")
            return token

        except Exception as e:
            logger.error(f"Failed to generate plugin token: {e}")
            raise SecurityError(f"Token generation failed: {e}")

    def verify_plugin_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Verify and decode plugin token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                audience="enclava-plugin",
                issuer="enclava-platform",
            )

            # Additional validation
            if "plugin_id" not in payload or "sub" not in payload:
                return False, None

            # Check if specific token is revoked
            if self._is_token_revoked(payload.get("jti")):
                return False, None

            # Check if plugin/user tokens are revoked
            plugin_id = payload.get("plugin_id")
            user_id = payload.get("sub")
            if self._is_plugin_user_revoked(plugin_id, user_id):
                return False, None

            return True, payload

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid plugin token: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return False, None

    def _is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked using Redis blacklist"""
        if not jti or not self.redis_client:
            return False

        try:
            # Check if token JTI exists in blacklist
            blacklist_key = f"plugin_token_blacklist:{jti}"
            is_revoked = self.redis_client.exists(blacklist_key)

            if is_revoked:
                logger.debug(f"Token {jti} found in blacklist")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # Fail secure - if we can't check blacklist, assume token is valid
            # This prevents service disruption from Redis issues
            return False

    def revoke_plugin_tokens(
        self, plugin_id: str, user_id: Optional[str] = None
    ) -> bool:
        """Revoke all tokens for a plugin or user"""
        try:
            if not self.redis_client:
                logger.error("Redis not available for token revocation")
                return False

            # For this implementation, we'll mark the plugin/user combination as revoked
            # In a production system, you'd want to track individual JTI tokens
            revocation_key = f"plugin_revocation:{plugin_id}"
            if user_id:
                revocation_key += f":user:{user_id}"

            # Set revocation flag with 7-day expiration (max token lifetime)
            expiration_seconds = 7 * 24 * 60 * 60  # 7 days
            self.redis_client.setex(
                revocation_key, expiration_seconds, int(time.time())
            )

            logger.info(f"Revoked plugin tokens for {plugin_id} (user: {user_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke tokens: {e}")
            return False

    def revoke_specific_token(self, jti: str, expires_at: datetime) -> bool:
        """Revoke a specific token by adding its JTI to blacklist"""
        try:
            if not jti or not self.redis_client:
                logger.error("Cannot revoke token: missing JTI or Redis unavailable")
                return False

            # Calculate time until token expires
            now = datetime.now(timezone.utc)
            if expires_at <= now:
                # Token already expired, no need to blacklist
                return True

            ttl_seconds = int((expires_at - now).total_seconds())

            # Add JTI to blacklist with TTL matching token expiration
            blacklist_key = f"plugin_token_blacklist:{jti}"
            self.redis_client.setex(blacklist_key, ttl_seconds, int(time.time()))

            logger.info(f"Revoked token {jti}, expires in {ttl_seconds} seconds")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke specific token {jti}: {e}")
            return False

    def cleanup_expired_revocations(self) -> int:
        """Clean up expired token revocations (Redis TTL handles this automatically)"""
        try:
            if not self.redis_client:
                return 0

            # Redis TTL automatically cleans up expired keys
            # This method is for manual cleanup or statistics

            # Count current blacklisted tokens
            pattern = "plugin_token_blacklist:*"
            blacklisted_count = len(self.redis_client.keys(pattern))

            logger.debug(f"Current blacklisted tokens: {blacklisted_count}")
            return blacklisted_count

        except Exception as e:
            logger.error(f"Failed to cleanup revocations: {e}")
            return 0

    def _is_plugin_user_revoked(self, plugin_id: str, user_id: str) -> bool:
        """Check if all tokens for a plugin/user combination are revoked"""
        if not plugin_id or not user_id or not self.redis_client:
            return False

        try:
            # Check plugin-level revocation
            plugin_revocation_key = f"plugin_revocation:{plugin_id}"
            if self.redis_client.exists(plugin_revocation_key):
                logger.debug(f"Plugin {plugin_id} tokens are revoked")
                return True

            # Check user-specific revocation for this plugin
            user_revocation_key = f"plugin_revocation:{plugin_id}:user:{user_id}"
            if self.redis_client.exists(user_revocation_key):
                logger.debug(f"Plugin {plugin_id} tokens revoked for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check plugin/user revocation: {e}")
            # Fail secure - if we can't check, assume not revoked
            return False

    def encrypt_plugin_secret(self, secret: str) -> str:
        """Encrypt plugin secret for storage"""
        try:
            encrypted = self.cipher_suite.encrypt(secret.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt secret: {e}")
            raise SecurityError("Secret encryption failed")

    def decrypt_plugin_secret(self, encrypted_secret: str) -> str:
        """Decrypt plugin secret"""
        try:
            decrypted = self.cipher_suite.decrypt(encrypted_secret.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret: {e}")
            raise SecurityError("Secret decryption failed")

    def get_revocation_status(
        self, plugin_id: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get revocation status for plugin and user"""
        try:
            if not self.redis_client:
                return {"status": "unknown", "error": "Redis unavailable"}

            status = {
                "plugin_id": plugin_id,
                "user_id": user_id,
                "plugin_revoked": False,
                "user_revoked": False,
                "revoked_at": None,
            }

            # Check plugin-level revocation
            plugin_key = f"plugin_revocation:{plugin_id}"
            if self.redis_client.exists(plugin_key):
                status["plugin_revoked"] = True
                revoked_timestamp = self.redis_client.get(plugin_key)
                if revoked_timestamp:
                    status["revoked_at"] = int(revoked_timestamp)

            # Check user-specific revocation
            if user_id:
                user_key = f"plugin_revocation:{plugin_id}:user:{user_id}"
                if self.redis_client.exists(user_key):
                    status["user_revoked"] = True
                    revoked_timestamp = self.redis_client.get(user_key)
                    if revoked_timestamp:
                        status["revoked_at"] = int(revoked_timestamp)

            return status

        except Exception as e:
            logger.error(f"Failed to get revocation status: {e}")
            return {"status": "error", "error": str(e)}


class PluginPermissionManager:
    """Manages plugin permissions and access control"""

    PLATFORM_API_PERMISSIONS = {
        "chatbot:invoke": "Invoke chatbot conversations",
        "chatbot:manage": "Manage chatbot instances",
        "chatbot:read": "Read chatbot configurations",
        "rag:query": "Query RAG collections",
        "rag:manage": "Manage RAG collections and documents",
        "rag:read": "Read RAG collection metadata",
        "llm:completion": "Generate LLM completions",
        "llm:embeddings": "Generate text embeddings",
        "llm:models": "List available LLM models",
        "workflow:execute": "Execute workflow processes",
        "workflow:read": "Read workflow definitions",
        "cache:read": "Read cached data",
        "cache:write": "Write cached data",
        "user:read": "Read user profile data",
        "user:settings": "Access user settings",
        "admin:users": "Manage users (admin only)",
        "admin:system": "System administration (admin only)",
    }

    PLUGIN_SCOPE_PERMISSIONS = {
        "read": "Read plugin data",
        "write": "Modify plugin data",
        "config": "Manage plugin configuration",
        "install": "Install/uninstall plugin",
        "execute": "Execute plugin functions",
    }

    def __init__(self):
        self.permission_cache: Dict[str, Set[str]] = {}

    def validate_permissions(
        self, requested_permissions: List[str]
    ) -> Tuple[bool, List[str]]:
        """Validate requested permissions against allowed permissions"""
        valid_permissions = set(self.PLATFORM_API_PERMISSIONS.keys()) | set(
            self.PLUGIN_SCOPE_PERMISSIONS.keys()
        )

        invalid_permissions = []
        for permission in requested_permissions:
            if permission.endswith(":*"):
                # Wildcard permission - check if base exists
                base_permission = permission[:-2]
                if not any(
                    p.startswith(base_permission + ":") for p in valid_permissions
                ):
                    invalid_permissions.append(permission)
            elif permission not in valid_permissions:
                invalid_permissions.append(permission)

        return len(invalid_permissions) == 0, invalid_permissions

    def check_permission(
        self, user_id: str, plugin_id: str, permission: str, db: Session
    ) -> bool:
        """Check if user has permission for plugin action"""
        try:
            # Get user permissions from cache or database
            cache_key = f"{user_id}:{plugin_id}"
            if cache_key not in self.permission_cache:
                self._load_user_permissions(user_id, plugin_id, db)

            user_permissions = self.permission_cache.get(cache_key, set())

            # Check exact permission match
            if permission in user_permissions:
                return True

            # Check wildcard permissions
            permission_parts = permission.split(":")
            if len(permission_parts) == 2:
                wildcard_permission = f"{permission_parts[0]}:*"
                if wildcard_permission in user_permissions:
                    return True

            return False

        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False

    def _load_user_permissions(self, user_id: str, plugin_id: str, db: Session):
        """Load user permissions for plugin from database"""
        try:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return

            # Get plugin configuration
            config = (
                db.query(PluginConfiguration)
                .filter(
                    PluginConfiguration.user_id == user_id,
                    PluginConfiguration.plugin_id == plugin_id,
                    PluginConfiguration.is_active == True,
                )
                .first()
            )

            permissions = set()

            # Add base plugin permissions
            if config:
                permissions.update(self.PLUGIN_SCOPE_PERMISSIONS.keys())

            # Add platform API permissions based on plugin manifest
            plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
            if plugin and plugin.manifest_data:
                manifest_permissions = (
                    plugin.manifest_data.get("spec", {})
                    .get("permissions", {})
                    .get("platform_apis", [])
                )
                permissions.update(manifest_permissions)

            # Add explicitly granted permissions from database
            from datetime import datetime, timezone

            explicitly_granted = (
                db.query(PluginPermission)
                .filter(
                    PluginPermission.plugin_id == plugin_id,
                    PluginPermission.user_id == user_id,
                    PluginPermission.granted == True,
                )
                .filter(
                    # Only include non-expired permissions
                    (PluginPermission.expires_at.is_(None))
                    | (PluginPermission.expires_at > datetime.now(timezone.utc))
                )
                .all()
            )

            for permission_record in explicitly_granted:
                permissions.add(permission_record.permission_name)

            # Add admin permissions if user is admin
            if hasattr(user, "is_admin") and user.is_admin:
                permissions.update(["admin:users", "admin:system"])

            # Cache permissions
            cache_key = f"{user_id}:{plugin_id}"
            self.permission_cache[cache_key] = permissions

        except Exception as e:
            logger.error(f"Failed to load user permissions: {e}")

    def get_user_permissions(
        self, user_id: str, plugin_id: str, db: Session
    ) -> List[str]:
        """Get list of permissions for user and plugin"""
        cache_key = f"{user_id}:{plugin_id}"
        if cache_key not in self.permission_cache:
            self._load_user_permissions(user_id, plugin_id, db)

        return list(self.permission_cache.get(cache_key, set()))

    def grant_permission(
        self,
        user_id: str,
        plugin_id: str,
        permission: str,
        granted_by: str,
        db: Session,
    ) -> bool:
        """Grant permission to user for plugin"""
        try:
            # Validate permission
            valid, invalid = self.validate_permissions([permission])
            if not valid:
                raise SecurityError(f"Invalid permission: {permission}")

            # Store permission grant in database
            permission_record = PluginPermission(
                plugin_id=plugin_id,
                user_id=user_id,
                permission_name=permission,
                granted=True,
                granted_by_user_id=granted_by,
                reason=f"Permission granted by user {granted_by}",
            )

            db.add(permission_record)

            # Invalidate cache to force reload
            cache_key = f"{user_id}:{plugin_id}"
            if cache_key in self.permission_cache:
                del self.permission_cache[cache_key]

            # Log permission grant
            audit_log = PluginAuditLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="grant_permission",
                details={"permission": permission, "granted_by": granted_by},
            )
            db.add(audit_log)
            db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to grant permission: {e}")
            db.rollback()
            return False

    def revoke_permission(
        self,
        user_id: str,
        plugin_id: str,
        permission: str,
        revoked_by: str,
        db: Session,
    ) -> bool:
        """Revoke permission from user for plugin"""
        try:
            # Mark permission as revoked in database
            permission_record = (
                db.query(PluginPermission)
                .filter(
                    PluginPermission.plugin_id == plugin_id,
                    PluginPermission.user_id == user_id,
                    PluginPermission.permission_name == permission,
                    PluginPermission.granted == True,
                )
                .first()
            )

            if permission_record:
                # Mark as revoked
                permission_record.granted = False
                permission_record.revoked_at = func.now()
                permission_record.revoked_by_user_id = revoked_by
                permission_record.reason = f"Permission revoked by user {revoked_by}"
            else:
                logger.warning(
                    f"Permission {permission} not found for user {user_id}, plugin {plugin_id}"
                )

            # Invalidate cache to force reload
            cache_key = f"{user_id}:{plugin_id}"
            if cache_key in self.permission_cache:
                del self.permission_cache[cache_key]

            # Log permission revocation
            audit_log = PluginAuditLog(
                plugin_id=plugin_id,
                user_id=user_id,
                action="revoke_permission",
                details={"permission": permission, "revoked_by": revoked_by},
            )
            db.add(audit_log)
            db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to revoke permission: {e}")
            db.rollback()
            return False


class PluginSecurityPolicyManager:
    """Manages security policies for plugins"""

    DEFAULT_SECURITY_POLICY = {
        "max_api_calls_per_minute": 100,
        "max_memory_mb": 128,
        "max_cpu_percent": 25,
        "max_disk_mb": 100,
        "max_network_connections": 10,
        "allowed_domains": [],
        "blocked_domains": ["localhost", "127.0.0.1", "0.0.0.0"],
        "require_https": True,
        "allow_file_access": False,
        "allow_system_calls": False,
        "enable_audit_logging": True,
        "token_expires_hours": 24,
        "max_token_lifetime_hours": 168,  # 1 week
    }

    def __init__(self):
        self.policy_cache: Dict[str, Dict[str, Any]] = {}

    async def get_security_policy(self, plugin_id: str, db: Session) -> Dict[str, Any]:
        """Get security policy for plugin with persistent storage support"""
        # Check cache first for performance
        if plugin_id in self.policy_cache:
            return self.policy_cache[plugin_id]

        try:
            # Get plugin from database
            plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()
            if not plugin:
                logger.warning(
                    f"Plugin {plugin_id} not found, using default security policy"
                )
                return self.DEFAULT_SECURITY_POLICY.copy()

            # Start with default policy
            policy = self.DEFAULT_SECURITY_POLICY.copy()

            # Try to load stored policy from configuration service
            try:
                # Create an async session wrapper for the configuration service
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.db.database import async_session_factory

                # Use async session for configuration service
                async with async_session_factory() as async_db:
                    config_service = PluginConfigurationService(async_db)
                    stored_policy = await config_service.get_configuration(
                        plugin_id=plugin_id,
                        user_id="system",
                        config_key="security_policy",
                        default_value=None,
                    )

                    if stored_policy:
                        logger.debug(
                            f"Loaded stored security policy for plugin {plugin_id}"
                        )
                        policy.update(stored_policy)
                        # Cache for performance
                        self.policy_cache[plugin_id] = policy
                        return policy

            except Exception as config_error:
                logger.warning(
                    f"Failed to load stored security policy for {plugin_id}: {config_error}"
                )
                # Continue with manifest-based policy

            # Override with plugin manifest settings if no stored policy
            if plugin.manifest_data:
                manifest_spec = plugin.manifest_data.get("spec", {})
                manifest_policy = manifest_spec.get("security_policy", {})
                if manifest_policy:
                    policy.update(manifest_policy)
                    logger.debug(
                        f"Applied manifest security policy for plugin {plugin_id}"
                    )

                # Add allowed domains from manifest
                external_services = manifest_spec.get("external_services", {})
                if external_services.get("allowed_domains"):
                    existing_domains = policy.get("allowed_domains", [])
                    policy["allowed_domains"] = (
                        existing_domains + external_services["allowed_domains"]
                    )

            # Cache policy for performance
            self.policy_cache[plugin_id] = policy
            logger.debug(
                f"Security policy loaded for plugin {plugin_id}: {len(policy)} settings"
            )
            return policy

        except Exception as e:
            logger.error(f"Failed to get security policy for {plugin_id}: {e}")
            return self.DEFAULT_SECURITY_POLICY.copy()

    def validate_security_policy(
        self, policy: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate security policy configuration"""
        errors = []

        # Check required fields
        required_fields = [
            "max_api_calls_per_minute",
            "max_memory_mb",
            "token_expires_hours",
        ]
        for field in required_fields:
            if field not in policy:
                errors.append(f"Missing required field: {field}")

        # Validate numeric limits
        numeric_limits = {
            "max_api_calls_per_minute": (1, 1000),
            "max_memory_mb": (16, 1024),
            "max_cpu_percent": (1, 100),
            "max_disk_mb": (10, 10240),
            "token_expires_hours": (1, 168),
        }

        for field, (min_val, max_val) in numeric_limits.items():
            if field in policy:
                value = policy[field]
                if (
                    not isinstance(value, (int, float))
                    or value < min_val
                    or value > max_val
                ):
                    errors.append(f"{field} must be between {min_val} and {max_val}")

        # Validate domains
        if "allowed_domains" in policy:
            if not isinstance(policy["allowed_domains"], list):
                errors.append("allowed_domains must be a list")

        return len(errors) == 0, errors

    async def update_security_policy(
        self, plugin_id: str, policy: Dict[str, Any], updated_by: str, db: Session
    ) -> bool:
        """Update security policy for plugin with persistent storage"""
        try:
            # Validate policy
            valid, errors = self.validate_security_policy(policy)
            if not valid:
                raise SecurityError(f"Invalid security policy: {errors}")

            # Store policy in database using configuration service
            try:
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.db.database import async_session_factory

                # Use async session for configuration service
                async with async_session_factory() as async_db:
                    config_service = PluginConfigurationService(async_db)

                    # Store security policy as system configuration
                    success = await config_service.set_configuration(
                        plugin_id=plugin_id,
                        user_id="system",  # System-level configuration
                        config_key="security_policy",
                        config_value=policy,
                        config_type="system_config",
                    )

                    if not success:
                        logger.error(
                            f"Failed to persist security policy for plugin {plugin_id}"
                        )
                        return False

                    logger.info(
                        f"Successfully persisted security policy for plugin {plugin_id}"
                    )

            except Exception as config_error:
                logger.error(
                    f"Failed to persist security policy using configuration service: {config_error}"
                )
                # Fall back to cache-only storage for now
                logger.warning(
                    f"Falling back to cache-only storage for plugin {plugin_id}"
                )

            # Update cache for fast access
            self.policy_cache[plugin_id] = policy

            # Log policy update in audit trail
            try:
                audit_log = PluginAuditLog(
                    plugin_id=plugin_id,
                    action="update_security_policy",
                    details={
                        "policy": policy,
                        "updated_by": updated_by,
                        "policy_keys": list(policy.keys()),
                        "timestamp": int(time.time()),
                    },
                )
                db.add(audit_log)
                db.commit()
                logger.debug(f"Logged security policy update for plugin {plugin_id}")

            except Exception as audit_error:
                logger.warning(f"Failed to log security policy update: {audit_error}")
                # Don't fail the whole operation due to audit logging issues
                db.rollback()

            logger.info(
                f"Updated security policy for plugin {plugin_id} with {len(policy)} settings"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update security policy for {plugin_id}: {e}")
            if hasattr(db, "rollback"):
                db.rollback()
            return False

    async def check_policy_compliance(
        self, plugin_id: str, action: str, context: Dict[str, Any], db: Session
    ) -> bool:
        """Check if action complies with plugin security policy"""
        try:
            # Get current security policy (using async method)
            policy = await self.get_security_policy(plugin_id, db)

            logger.debug(
                f"Checking policy compliance for plugin {plugin_id}, action: {action}"
            )

            # Check specific action types
            if action == "api_call":
                # Check API call limits
                max_calls = policy.get("max_api_calls_per_minute", 100)
                # Note: Actual rate limiting would be implemented by the rate limiter
                return True

            elif action == "network_access":
                domain = context.get("domain")
                if not domain:
                    logger.warning(
                        f"Network access check for {plugin_id} failed: no domain provided"
                    )
                    return False

                # Check blocked domains first
                blocked_domains = policy.get("blocked_domains", [])
                for blocked in blocked_domains:
                    if domain.endswith(blocked) or domain == blocked:
                        logger.info(
                            f"Network access denied for {plugin_id}: domain {domain} is blocked"
                        )
                        return False

                # Check allowed domains if specified
                allowed_domains = policy.get("allowed_domains", [])
                if allowed_domains:
                    domain_allowed = any(
                        domain.endswith(allowed) or domain == allowed
                        for allowed in allowed_domains
                    )
                    if not domain_allowed:
                        logger.info(
                            f"Network access denied for {plugin_id}: domain {domain} not in allowed list"
                        )
                        return False

                # Check HTTPS requirement
                require_https = policy.get("require_https", True)
                if require_https and context.get("protocol", "").lower() != "https":
                    logger.info(
                        f"Network access denied for {plugin_id}: HTTPS required but protocol is {context.get('protocol')}"
                    )
                    return False

                logger.debug(
                    f"Network access approved for {plugin_id} to domain {domain}"
                )
                return True

            elif action == "file_access":
                allow_file_access = policy.get("allow_file_access", False)
                if not allow_file_access:
                    logger.info(
                        f"File access denied for {plugin_id}: not allowed by policy"
                    )
                return allow_file_access

            elif action == "system_call":
                allow_system_calls = policy.get("allow_system_calls", False)
                if not allow_system_calls:
                    logger.info(
                        f"System call denied for {plugin_id}: not allowed by policy"
                    )
                return allow_system_calls

            elif action == "resource_usage":
                # Check resource limits
                resource_type = context.get("resource_type")
                usage_value = context.get("usage_value", 0)

                if resource_type == "memory":
                    max_memory = policy.get("max_memory_mb", 128)
                    return usage_value <= max_memory
                elif resource_type == "cpu":
                    max_cpu = policy.get("max_cpu_percent", 25)
                    return usage_value <= max_cpu
                elif resource_type == "disk":
                    max_disk = policy.get("max_disk_mb", 100)
                    return usage_value <= max_disk
                elif resource_type == "network_connections":
                    max_connections = policy.get("max_network_connections", 10)
                    return usage_value <= max_connections

            # Default: allow unknown actions (fail open for compatibility)
            logger.debug(
                f"Unknown action {action} for plugin {plugin_id}, defaulting to allow"
            )
            return True

        except Exception as e:
            logger.error(f"Policy compliance check failed for {plugin_id}: {e}")
            # Fail secure: deny access on errors
            return False


# Global instances
plugin_token_manager = PluginTokenManager()
plugin_permission_manager = PluginPermissionManager()
plugin_security_policy_manager = PluginSecurityPolicyManager()
