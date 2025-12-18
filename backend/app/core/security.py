"""
Security utilities for authentication and authorization
"""

import asyncio
import concurrent.futures
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.utils.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

# Password hashing
# Use a lower work factor for better performance in production
pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)

# JWT token handling
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    import time

    start_time = time.time()
    logger.debug(
        f"=== PASSWORD VERIFICATION START === BCRYPT_ROUNDS: {settings.BCRYPT_ROUNDS}"
    )

    try:
        # Run password verification in a thread with timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                pwd_context.verify, plain_password, hashed_password
            )
            result = future.result(timeout=5.0)  # 5 second timeout

        end_time = time.time()
        duration = end_time - start_time
        logger.debug(
            f"=== PASSWORD VERIFICATION END === Duration: {duration:.3f}s, Result: {result}"
        )

        if duration > 1:
            logger.warning(f"PASSWORD VERIFICATION TOOK TOO LONG: {duration:.3f}s")

        return result
    except concurrent.futures.TimeoutError:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"=== PASSWORD VERIFICATION TIMEOUT === Duration: {duration:.3f}s")
        return False  # Treat timeout as verification failure
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(
            f"=== PASSWORD VERIFICATION FAILED === Duration: {duration:.3f}s, Error: {e}"
        )
        raise


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verify an API key against its hash"""
    return pwd_context.verify(plain_api_key, hashed_api_key)


def get_api_key_hash(api_key: str) -> str:
    """Generate API key hash"""
    return pwd_context.hash(api_key)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    import time

    start_time = time.time()
    logger.debug(f"=== CREATE ACCESS TOKEN START ===")

    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({"exp": expire})
        logger.debug(f"JWT encode start...")
        encode_start = time.time()
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
        )
        encode_end = time.time()
        encode_duration = encode_end - encode_start

        end_time = time.time()
        total_duration = end_time - start_time

        # Log token creation details
        logger.debug(f"Created access token for user {data.get('sub')}")
        logger.debug(f"Token expires at: {expire.isoformat()} (UTC)")
        logger.debug(f"Current UTC time: {datetime.utcnow().isoformat()}")
        logger.debug(
            f"ACCESS_TOKEN_EXPIRE_MINUTES setting: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}"
        )
        logger.debug(f"JWT encode duration: {encode_duration:.3f}s")
        logger.debug(f"Total token creation duration: {total_duration:.3f}s")
        logger.debug(f"=== CREATE ACCESS TOKEN END ===")

        return encoded_jwt
    except Exception as e:
        end_time = time.time()
        total_duration = end_time - start_time
        logger.error(
            f"=== CREATE ACCESS TOKEN FAILED === Duration: {total_duration:.3f}s, Error: {e}"
        )
        raise


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token and return payload"""
    try:
        # Log current time before verification
        current_time = datetime.utcnow()
        logger.debug(f"Verifying token at: {current_time.isoformat()} (UTC)")

        # Decode without verification first to check expiration
        try:
            unverified_payload = jwt.get_unverified_claims(token)
            exp_timestamp = unverified_payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=None)
                logger.debug(f"Token expiration time: {exp_datetime.isoformat()} (UTC)")
                logger.debug(
                    f"Time until expiration: {(exp_datetime - current_time).total_seconds()} seconds"
                )
        except Exception as decode_error:
            logger.debug(
                f"Could not decode token for expiration check: {decode_error}"
            )

        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        logger.debug(f"Token verified successfully for user {payload.get('sub')}")
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        logger.warning(f"Current UTC time: {datetime.utcnow().isoformat()}")
        raise AuthenticationError("Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get current user from JWT token"""
    try:
        # Log server time for debugging clock sync issues
        server_time = datetime.utcnow()
        logger.debug(f"get_current_user called at: {server_time.isoformat()} (UTC)")

        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        # Load user from database
        from app.models.user import User
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        # Query user from database
        stmt = select(User).options(selectinload(User.role)).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # If user doesn't exist in DB but token is valid, create basic user info from token
            return {
                "id": int(user_id),
                "email": payload.get("email"),
                "is_superuser": payload.get("is_superuser", False),
                "role": payload.get("role", "user"),
                "is_active": True,
                "permissions": [],  # Default to empty list for permissions
            }

        # Update last login
        user.update_last_login()
        await db.commit()

        # Calculate effective permissions using permission manager
        from app.services.permission_manager import permission_registry

        # Convert role to name for permission calculation
        user_roles = [user.role.name] if user.role else []

        # For super admin users, use only role-based permissions, ignore custom permissions
        # Custom permissions might contain legacy formats like ['*'] or dict formats
        custom_permissions = []
        if not user.is_superuser:
            # Support both list-based and dict-based custom permission formats
            raw_custom_perms = getattr(user, "custom_permissions", None)
            if raw_custom_perms:
                if isinstance(raw_custom_perms, list):
                    custom_permissions = raw_custom_perms
                elif isinstance(raw_custom_perms, dict):
                    granted = raw_custom_perms.get("granted")
                    if isinstance(granted, list):
                        custom_permissions = granted

        # Calculate effective permissions based on role and custom permissions
        effective_permissions = permission_registry.get_user_permissions(
            roles=user_roles, custom_permissions=custom_permissions
        )

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
            "role": user.role.name if user.role else None,
            "permissions": effective_permissions,  # Use calculated permissions
            "user_obj": user,  # Include full user object for other operations
        }
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError("Could not validate credentials")


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current active user"""
    # Check if user is active in database
    if not current_user.get("is_active", False):
        raise AuthenticationError("User account is inactive")
    return current_user


async def get_current_superuser(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current superuser"""
    if not current_user.get("is_superuser"):
        raise AuthorizationError("Insufficient privileges")
    return current_user


def generate_api_key() -> str:
    """Generate a new API key"""
    import secrets
    import string

    # Generate random string
    alphabet = string.ascii_letters + string.digits
    api_key = "".join(secrets.choice(alphabet) for _ in range(32))

    return f"{settings.API_KEY_PREFIX}{api_key}"


def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return get_password_hash(api_key)


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify API key against hash"""
    return verify_password(api_key, hashed_key)


async def get_api_key_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """Get user from API key"""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return None

    # Implement API key lookup in database
    from app.models.api_key import APIKey
    from app.models.user import User
    from sqlalchemy import select

    try:
        # Extract key prefix for lookup
        if len(api_key) < 8:
            return None

        key_prefix = api_key[:8]

        # Query API key from database
        stmt = (
            select(APIKey)
            .join(User)
            .where(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == True,
                User.is_active == True,
            )
        )
        result = await db.execute(stmt)
        db_api_key = result.scalar_one_or_none()

        if not db_api_key:
            return None

        # Verify the API key hash
        if not verify_api_key(api_key, db_api_key.key_hash):
            return None

        # Check if key is valid (not expired)
        if not db_api_key.is_valid():
            return None

        # Update last used timestamp
        db_api_key.last_used_at = datetime.utcnow()
        await db.commit()

        # Load associated user
        user_stmt = select(User).options(selectinload(User.role)).where(User.id == db_api_key.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        # Calculate effective permissions using permission manager
        from app.services.permission_manager import permission_registry

        # Convert role to name for permission calculation
        user_roles = [user.role.name] if user.role else []

        # Use API key specific permissions if available
        api_key_permissions = db_api_key.permissions if db_api_key.permissions else []

        # Normalize permissions into a flat list of granted permission strings
        custom_permissions: list[str] = []

        # Handle API key permissions that may be stored as list or dict
        if isinstance(api_key_permissions, list):
            custom_permissions.extend(api_key_permissions)
        elif isinstance(api_key_permissions, dict):
            api_granted = api_key_permissions.get("granted")
            if isinstance(api_granted, list):
                custom_permissions.extend(api_granted)

        # Merge in user-level custom permissions for non-superusers
        raw_user_custom = getattr(user, "custom_permissions", None)
        if raw_user_custom and not user.is_superuser:
            if isinstance(raw_user_custom, list):
                custom_permissions.extend(raw_user_custom)
            elif isinstance(raw_user_custom, dict):
                user_granted = raw_user_custom.get("granted")
                if isinstance(user_granted, list):
                    custom_permissions.extend(user_granted)

        # Calculate effective permissions based on role and custom permissions
        effective_permissions = permission_registry.get_user_permissions(
            roles=user_roles, custom_permissions=custom_permissions
        )

        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
            "role": user.role,
            "permissions": effective_permissions,
            "api_key": db_api_key,
            "user_obj": user,
            "auth_type": "api_key",
        }
    except Exception as e:
        logger.error(f"API key lookup error: {e}")
        return None


class RequiresPermission:
    """Dependency class for permission checking"""

    def __init__(self, permission: str):
        self.permission = permission

    def __call__(self, current_user: Dict[str, Any] = Depends(get_current_user)):
        # Implement permission checking
        # Check if user is superuser (has all permissions)
        if current_user.get("is_superuser", False):
            return current_user

        # Check role-based permissions
        role = current_user.get("role", "user")
        role_permissions = {
            "user": ["read_own", "create_own", "update_own"],
            "admin": ["read_all", "create_all", "update_all", "delete_own"],
            "super_admin": [
                "read_all",
                "create_all",
                "update_all",
                "delete_all",
                "manage_users",
                "manage_modules",
            ],
        }

        if role in role_permissions and self.permission in role_permissions[role]:
            return current_user

        # Check custom permissions
        user_permissions = current_user.get("permissions", {})
        if self.permission in user_permissions:
            return current_user

        # If user has access to full user object, use the model's has_permission method
        user_obj = current_user.get("user_obj")
        if user_obj and hasattr(user_obj, "has_permission"):
            if user_obj.has_permission(self.permission):
                return current_user

        raise AuthorizationError(f"Permission '{self.permission}' required")


class RequiresRole:
    """Dependency class for role checking"""

    def __init__(self, role: str):
        self.role = role

    def __call__(self, current_user: Dict[str, Any] = Depends(get_current_user)):
        # Implement role checking
        # Superusers have access to everything
        if current_user.get("is_superuser", False):
            return current_user

        user_role = current_user.get("role", "user")

        # Define role hierarchy
        role_hierarchy = {"user": 1, "admin": 2, "super_admin": 3}

        required_level = role_hierarchy.get(self.role, 0)
        user_level = role_hierarchy.get(user_role, 0)

        if user_level >= required_level:
            return current_user

        raise AuthorizationError(
            f"Role '{self.role}' required, but user has role '{user_role}'"
        )
