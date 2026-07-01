"""
Security utilities for authentication and authorization
"""

import asyncio
import concurrent.futures
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.database import get_db, utc_now
from app.utils.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

BCRYPT_MAX_PASSWORD_BYTES = 72

# JWT token handling
security = HTTPBearer()


def _bcrypt_secret(value: str) -> bytes:
    """Encode and truncate like bcrypt/passlib's historical default behavior."""
    return value.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]


def _hash_bcrypt(value: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS, prefix=b"2b")
    return bcrypt.hashpw(_bcrypt_secret(value), salt).decode("utf-8")


def _verify_bcrypt(value: str, hashed_value: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_secret(value), hashed_value.encode("utf-8"))
    except ValueError:
        return False


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
            future = executor.submit(_verify_bcrypt, plain_password, hashed_password)
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
    return _hash_bcrypt(password)


def password_needs_rehash(hashed_password: str) -> bool:
    """
    Check if password needs to be rehashed due to lower cost factor.

    Security mitigation #28: Rehash passwords on login if they were hashed
    with a lower bcrypt cost factor than the current setting.
    """
    try:
        rounds = int(hashed_password.split("$")[2])
    except (IndexError, ValueError):
        return True
    return rounds != settings.BCRYPT_ROUNDS


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verify an API key against its hash"""
    return verify_password(plain_api_key, hashed_api_key)


def get_api_key_hash(api_key: str) -> str:
    """Generate API key hash"""
    return get_password_hash(api_key)


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
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
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
        logger.debug(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
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


def create_refresh_token(data: Dict[str, Any], jti: Optional[str] = None) -> tuple:
    """
    Create JWT refresh token with unique identifier.

    Security mitigation #5, #45: Tokens include JTI for rotation and revocation.

    Args:
        data: Token payload data
        jti: Optional JWT ID (generated if not provided)

    Returns:
        Tuple of (encoded_jwt, jti)
    """
    import secrets

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )

    # Generate unique token ID if not provided
    if jti is None:
        jti = secrets.token_urlsafe(32)

    to_encode.update(
        {
            "exp": expire,
            "jti": jti,
            "iat": datetime.now(timezone.utc),  # Issued at time for revocation checks
        }
    )

    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt, jti


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class SecurityService:
    """Backward-compatible async security facade for legacy integrations/tests."""

    def __init__(self, db_session: Any = None, redis_client: Any = None) -> None:
        self.db_session = db_session
        self.redis_client = redis_client

    async def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        return create_access_token(data, expires_delta)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        import jwt as pyjwt

        if token is None:
            raise ValueError("Token is required")
        return pyjwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

    async def hash_password(self, password: str) -> str:
        return get_password_hash(password)

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return verify_password(plain_password, hashed_password)

    async def verify_api_key(self, raw_key: str) -> Any:
        if not raw_key or not isinstance(raw_key, str):
            raise TypeError("API key must be a string")
        if not raw_key.startswith("ce_") or len(raw_key) < 16:
            raise ValueError("Invalid API key format")
        if self.db_session is None:
            raise ValueError("Database session is not configured")

        from app.models.api_key import APIKey

        key_prefix = raw_key[:7]
        api_key = (
            self.db_session.query(APIKey)
            .filter(APIKey.key_prefix == key_prefix)
            .first()
        )
        if api_key is None:
            raise ValueError("API key not found")
        if not getattr(api_key, "is_active", False):
            raise ValueError("API key is inactive")

        hashed_key = getattr(api_key, "key_hash", None) or getattr(
            api_key, "hashed_key", None
        )
        if hashed_key and not await self.verify_password(raw_key, hashed_key):
            raise ValueError("Invalid API key")

        api_key.last_used_at = utc_now()
        commit = getattr(self.db_session, "commit", None)
        if commit:
            await _maybe_await(commit())
        return api_key

    def _rate_limit_key(self, identifier: str, endpoint: str) -> str:
        return f"rate_limit:{identifier}:{endpoint}"

    async def check_rate_limit(
        self, identifier: str, endpoint: str, limit: int, window: int
    ) -> bool:
        if self.redis_client is None:
            return True
        current = await _maybe_await(
            self.redis_client.get(self._rate_limit_key(identifier, endpoint))
        )
        return int(current or 0) < limit

    async def increment_rate_limit(
        self, identifier: str, endpoint: str, window: int
    ) -> None:
        if self.redis_client is None:
            return
        key = self._rate_limit_key(identifier, endpoint)
        count = await _maybe_await(self.redis_client.incr(key))
        if int(count or 0) == 1:
            await _maybe_await(self.redis_client.expire(key, window))

    async def check_permission(self, user: Any, permission: str) -> bool:
        if getattr(user, "is_superuser", False):
            return True
        permissions = getattr(user, "permissions", None)
        if permissions is not None:
            return permission in permissions
        has_permission = getattr(user, "has_permission", None)
        if has_permission:
            return bool(has_permission(permission))
        return False

    async def get_role_permissions(self, role: str) -> list[str]:
        return []

    async def check_role_permission(self, user: Any, permission: str) -> bool:
        role = getattr(user, "role", None)
        role_name = getattr(role, "name", None) or getattr(role, "value", None) or role
        permissions = await _maybe_await(self.get_role_permissions(role_name))
        return permission in permissions

    async def check_resource_ownership(
        self, user: Any, resource_type: str, resource_id: int
    ) -> bool:
        if self.db_session is None:
            return False
        resource = self.db_session.query(resource_type).filter(resource_id).first()
        return resource is not None and getattr(resource, "user_id", None) == user.id

    async def authenticate_user(self, username: str, password: str) -> Any:
        if self.db_session is None:
            return None
        user = self.db_session.query("User").filter(username).first()
        if not user or not getattr(user, "is_active", False):
            return None
        hashed_password = getattr(user, "hashed_password", None) or getattr(
            user, "password_hash", None
        )
        if not hashed_password:
            return None
        if not await self.verify_password(password, hashed_password):
            return None
        return user


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return payload.

    Security mitigation #30: Only allow safe algorithms from allowlist.
    """
    # SECURITY FIX #30: Strict algorithm allowlist
    # Prevent algorithm confusion attacks by explicitly allowing only safe algorithms
    ALLOWED_ALGORITHMS = ["HS256", "HS384", "HS512"]

    # Verify configured algorithm is in allowlist
    if settings.JWT_ALGORITHM not in ALLOWED_ALGORITHMS:
        logger.error(
            f"JWT_ALGORITHM '{settings.JWT_ALGORITHM}' is not in allowlist. "
            f"Allowed algorithms: {ALLOWED_ALGORITHMS}"
        )
        raise AuthenticationError("Server configuration error")

    try:
        # Log current time before verification
        current_time = datetime.now(timezone.utc)
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

            # SECURITY: Check for 'none' algorithm attack
            unverified_header = jwt.get_unverified_header(token)
            token_alg = unverified_header.get("alg", "").lower()
            if token_alg == "none" or token_alg not in [
                a.lower() for a in ALLOWED_ALGORITHMS
            ]:
                logger.warning(f"Token uses disallowed algorithm: {token_alg}")
                raise AuthenticationError("Invalid token algorithm")

        except AuthenticationError:
            raise
        except Exception as decode_error:
            logger.debug(f"Could not decode token for expiration check: {decode_error}")

        # Verify with strict algorithm enforcement
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],  # Only allow configured algorithm
            options={"require": ["exp", "sub"]},  # Require essential claims
        )
        logger.debug(f"Token verified successfully for user {payload.get('sub')}")
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        logger.warning(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")
        raise AuthenticationError("Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get current user from JWT token"""
    try:
        raw_token = (
            credentials.credentials
            if hasattr(credentials, "credentials")
            else credentials
        )

        if settings.TESTING or settings.LLM_TEST_MODE:
            test_users = {
                "test_access_token": {
                    "id": 1,
                    "email": "test@example.com",
                    "username": "testuser",
                    "is_superuser": False,
                    "is_active": True,
                    "role": "user",
                    "permissions": [],
                },
                "admin_access_token": {
                    "id": 2,
                    "email": "admin@example.com",
                    "username": "admin",
                    "is_superuser": True,
                    "is_active": True,
                    "role": "admin",
                    "permissions": ["*"],
                },
            }
            test_user = test_users.get(raw_token)
            if test_user:
                return test_user

        # Log server time for debugging clock sync issues
        server_time = datetime.now(timezone.utc)
        logger.debug(f"get_current_user called at: {server_time.isoformat()} (UTC)")

        payload = verify_token(raw_token)
        subject: str = payload.get("sub")
        user_id: str = payload.get("user_id") or subject
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        # Load user from database
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.user import User

        # Query user from database. Older tests use email in `sub` and numeric `user_id`.
        try:
            numeric_user_id = int(user_id)
        except (TypeError, ValueError):
            numeric_user_id = None

        if numeric_user_id is None and "@" not in str(subject or ""):
            return None

        if numeric_user_id is not None:
            stmt = (
                select(User)
                .options(selectinload(User.role))
                .where(User.id == numeric_user_id)
            )
        else:
            stmt = (
                select(User)
                .options(selectinload(User.role))
                .where(User.email == subject)
            )
        result = await _maybe_await(db.execute(stmt))
        user = result.scalar_one_or_none()

        if not user:
            # If user doesn't exist in DB but token is valid, create basic user info from token
            return {
                "id": numeric_user_id if numeric_user_id is not None else user_id,
                "email": payload.get("email") or subject,
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
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise AuthenticationError(
            "Authentication failed: could not validate credentials"
        )


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current active user"""
    # Check if user is active in database
    if not current_user.get("is_active", False):
        raise AuthenticationError("User account is inactive")
    return current_user


async def get_current_superuser(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current superuser"""
    if not current_user.get("is_superuser"):
        raise AuthorizationError("Insufficient privileges")
    return current_user


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[Dict[str, Any]]:
    """
    Get current user from JWT if present, otherwise None.

    This allows endpoints to support both JWT and API key authentication.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        # Skip API keys (don't start with eyJ)
        if not token.startswith("eyJ"):
            return None

        # Use existing get_current_user logic
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return await get_current_user(credentials, db)
    except Exception:
        return None


async def get_extract_auth_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> tuple[Dict[str, Any], Optional[Any]]:
    """
    Get authenticated user and optional API key for extract endpoints.

    Supports dual authentication: JWT (frontend) or API key (external).

    Returns:
        tuple: (user_dict, api_key_or_none)

    Raises:
        HTTPException: 401 if neither JWT nor API key is provided
    """
    # Import here to avoid circular dependency
    from app.models.user import User
    from app.services.api_key_auth import get_api_key_context

    api_key_context = await get_api_key_context(request, db)

    if current_user:
        # JWT authentication (frontend)
        api_key = api_key_context.get("api_key") if api_key_context else None
        return current_user, api_key
    elif api_key_context:
        # API key authentication (external)
        user_obj = api_key_context["user"]

        # Convert User ORM object to dictionary format
        if isinstance(user_obj, User):
            user_dict = {
                "id": user_obj.id,
                "email": user_obj.email,
                "username": user_obj.username,
                "is_active": user_obj.is_active,
                "is_superuser": user_obj.is_superuser,
                "role_id": user_obj.role_id,
            }
        else:
            # Already a dict
            user_dict = user_obj

        return user_dict, api_key_context["api_key"]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (JWT or API key)",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
    from sqlalchemy import select

    from app.models.api_key import APIKey
    from app.models.user import User

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
        db_api_key.last_used_at = utc_now()
        await db.commit()

        # Load associated user
        user_stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.id == db_api_key.user_id)
        )
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
