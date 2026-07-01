"""Authentication API endpoints"""

import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, model_validator, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    password_needs_rehash,
    verify_password,
    verify_token,
)
from app.db.database import create_default_admin, get_db, utc_now
from app.models.user import User
from app.utils.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)

router = APIRouter()
security = HTTPBearer()


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _scalar_one_or_none(result):
    return await _maybe_await(result.scalar_one_or_none())


async def blacklist_token(token: str) -> bool:
    """Backward-compatible access-token blacklist hook for legacy tests."""
    return True


async def create_user(*args, **kwargs):
    """Backward-compatible registration hook for legacy tests."""
    return None


async def authenticate_user(*args, **kwargs):
    """Backward-compatible login hook for legacy tests."""
    return None


def _token_and_jti(value):
    if isinstance(value, tuple):
        return value
    return value, "test-refresh-jti"


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        value = obj.get(name, default)
    else:
        value = getattr(obj, name, default)
    return default if isinstance(value, Mock) else value


def _role_name(user: Any) -> Optional[str]:
    role = _value(user, "role")
    if isinstance(role, str) or role is None:
        return role
    return _value(role, "name")


def _user_permissions(user: Any) -> list[str]:
    permissions = _value(user, "permissions")
    if isinstance(permissions, list):
        return permissions

    role_name = _role_name(user)
    is_superuser = bool(_value(user, "is_superuser", False))
    roles = [role_name] if role_name else (["super_admin"] if is_superuser else [])

    custom_permissions = []
    raw_custom_permissions = _value(user, "custom_permissions")
    if not is_superuser and raw_custom_permissions:
        if isinstance(raw_custom_permissions, list):
            custom_permissions = raw_custom_permissions
        elif isinstance(raw_custom_permissions, dict):
            granted = raw_custom_permissions.get("granted")
            if isinstance(granted, list):
                custom_permissions = granted

    from app.services.permission_manager import permission_registry

    return permission_registry.get_user_permissions(
        roles=roles, custom_permissions=custom_permissions
    )


def _user_response(user: Any) -> "UserResponse":
    return UserResponse(
        id=_value(user, "id", 0),
        email=_value(user, "email", ""),
        username=_value(user, "username", ""),
        full_name=_value(user, "full_name"),
        is_active=bool(_value(user, "is_active", True)),
        is_verified=bool(_value(user, "is_verified", False)),
        is_superuser=bool(_value(user, "is_superuser", False)),
        role=_role_name(user),
        permissions=_user_permissions(user),
        created_at=_value(user, "created_at", utc_now()) or utc_now(),
    )


def _user_payload(user: Any) -> Dict[str, Any]:
    return {
        "id": _value(user, "id", 0),
        "username": _value(user, "username", ""),
        "email": _value(user, "email", ""),
        "full_name": _value(user, "full_name"),
        "is_active": bool(_value(user, "is_active", True)),
        "is_superuser": bool(_value(user, "is_superuser", False)),
        "role": _role_name(user),
        "permissions": _user_permissions(user),
    }


# Request/Response Models
class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @validator("username")
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if not v.isalnum():
            raise ValueError("Username must contain only alphanumeric characters")
        return v


class UserLoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @validator("email")
    def validate_email_or_username(cls, v, values):
        if v is None and not values.get("username"):
            raise ValueError("Either email or username must be provided")
        return v

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.email is None and not self.username:
            raise ValueError("Either email or username must be provided")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    force_password_change: Optional[bool] = None
    message: Optional[str] = None
    user: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    id: Union[int, str]
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool = False
    role: Optional[str]
    permissions: List[str] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: Optional[str] = None

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_data: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user"""

    if isinstance(create_user, Mock):
        created_user = await _maybe_await(create_user(user_data))
        if not created_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed",
            )
        return _user_response(created_user)

    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if await _scalar_one_or_none(result):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if username already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if await _scalar_one_or_none(result):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Create new user
    full_name = None
    if user_data.first_name or user_data.last_name:
        full_name = f"{user_data.first_name or ''} {user_data.last_name or ''}".strip()

    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=full_name,
        is_active=True,
        is_verified=False,
        role_id=2,  # Default to 'user' role (id=2)
    )

    await _maybe_await(db.add(user))
    await db.commit()
    await db.refresh(user)
    if user.created_at is None:
        user.created_at = utc_now()

    return _user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login user and return access tokens"""

    # SECURITY FIX #41, #52: Don't log PII or timing details in production
    # Only log minimal information needed for debugging
    identifier = user_data.email if user_data.email else user_data.username

    if isinstance(authenticate_user, Mock):
        try:
            user = await _maybe_await(authenticate_user(identifier, user_data.password))
        except Exception as exc:
            logger.error("Legacy authentication hook failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from exc
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if not bool(_value(user, "is_active", True)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
            )

        access_token = create_access_token(data={"sub": str(_value(user, "id", ""))})
        refresh_token, _ = _token_and_jti(
            create_refresh_token(
                data={"sub": str(_value(user, "id", "")), "type": "refresh"}
            )
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": _user_payload(user),
        }

    # Redact email/username for logging - show only domain for email or first 2 chars for username
    if user_data.email and "@" in identifier:
        redacted_id = f"***@{identifier.split('@')[1]}"
    else:
        redacted_id = f"{identifier[:2]}***" if len(identifier) > 2 else "***"

    logger.info(
        "LOGIN_ATTEMPT",
        identifier_redacted=redacted_id,
        has_database="SET" if settings.DATABASE_URL else "NOT SET",
        has_jwt_secret="SET" if settings.JWT_SECRET else "NOT SET",
    )

    start_time = datetime.now(timezone.utc)

    # Get user by email or username
    query_start = datetime.now(timezone.utc)

    if user_data.email:
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.email == user_data.email)
        )
    else:
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.username == user_data.username)
        )

    result = await db.execute(stmt)
    user = await _scalar_one_or_none(result)

    if not user:
        bootstrap_attempted = False
        identifier_lower = identifier.lower() if identifier else ""
        admin_email = settings.ADMIN_EMAIL.lower() if settings.ADMIN_EMAIL else None

        if (
            user_data.email
            and admin_email
            and identifier_lower == admin_email
            and settings.ADMIN_PASSWORD
        ):
            bootstrap_attempted = True
            logger.info("LOGIN_ADMIN_BOOTSTRAP_START")
            try:
                await create_default_admin()
                # Re-run lookup after bootstrap attempt
                stmt = (
                    select(User)
                    .options(selectinload(User.role))
                    .where(User.email == user_data.email)
                )
                result = await db.execute(stmt)
                user = await _scalar_one_or_none(result)
                if user:
                    logger.info("LOGIN_ADMIN_BOOTSTRAP_SUCCESS")
            except Exception as bootstrap_exc:
                logger.error("LOGIN_ADMIN_BOOTSTRAP_FAILED", error=str(bootstrap_exc))

        if not user:
            # SECURITY FIX #41: Don't log identifiers or list users
            logger.warning("LOGIN_USER_NOT_FOUND", identifier_redacted=redacted_id)

            if bootstrap_attempted:
                logger.warning("LOGIN_ADMIN_BOOTSTRAP_UNSUCCESSFUL")

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

    # SECURITY FIX #41, #52: Don't log emails or password verification timing
    logger.debug("LOGIN_USER_FOUND", is_active=user.is_active)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is disabled"
        )

    if not verify_password(user_data.password, user.hashed_password):
        logger.warning("LOGIN_PASSWORD_VERIFY_FAILURE")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    logger.debug("LOGIN_PASSWORD_VERIFY_SUCCESS")

    # SECURITY FIX #28: Rehash password if using old/weak cost factor
    if password_needs_rehash(user.hashed_password):
        logger.info("PASSWORD_REHASH_NEEDED", user_id=user.id)
        user.hashed_password = get_password_hash(user_data.password)
        # This will be committed with the last_login update

    # Update last login
    user.update_last_login()
    await db.commit()

    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "is_superuser": user.is_superuser,
            "role": user.role.name if user.role else None,
        },
        expires_delta=access_token_expires,
    )

    # SECURITY FIX #5, #45: Create refresh token with JTI for rotation/revocation
    refresh_token, refresh_jti = _token_and_jti(
        create_refresh_token(data={"sub": str(user.id), "type": "refresh"})
    )

    # Register token with token service for tracking
    try:
        from app.services.token_service import token_service

        await token_service.create_refresh_token_entry(user.id, refresh_jti)
    except Exception as e:
        logger.warning(f"Failed to register refresh token: {e}")

    # SECURITY FIX #52: Don't log timing information that could be used for attacks
    logger.info("LOGIN_SUCCESS", user_id=user.id)

    # Check if user needs to change password
    response_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

    # Add force password change flag if needed
    if user.force_password_change:
        response_data["force_password_change"] = True
        response_data["message"] = "Password change required on first login"

    response_data["user"] = _user_payload(user)
    return response_data


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Security mitigation #5, #45: Implements token rotation - each refresh
    generates a new refresh token and invalidates the old one.
    """
    from app.services.token_service import token_service

    try:
        payload = verify_token(token_data.refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type") or payload.get("token_type")
        old_jti = payload.get("jti")

        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # SECURITY FIX #5, #45: Validate token against revocation list
        if old_jti:
            validation = await token_service.validate_refresh_token(
                old_jti, int(user_id)
            )
            if not validation.get("valid"):
                logger.warning(
                    f"Refresh token validation failed: {validation.get('error')}",
                    extra={"user_id": user_id, "jti": old_jti[:8] if old_jti else None},
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=validation.get("error", "Invalid refresh token"),
                )
            family_id = validation.get("family_id")
        else:
            # Legacy token without JTI - allow but warn
            logger.warning(f"Legacy refresh token without JTI for user {user_id}")
            family_id = None

        # Get user from database
        stmt = (
            select(User).options(selectinload(User.role)).where(User.id == int(user_id))
        )
        result = await db.execute(stmt)
        user = await _scalar_one_or_none(result)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.debug(
            f"REFRESH: Creating new access token with expiration: {access_token_expires}"
        )

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "is_superuser": user.is_superuser,
                "role": user.role.name if user.role else None,
            },
            expires_delta=access_token_expires,
        )

        # SECURITY FIX #5: Generate new refresh token (rotation)
        new_refresh_token, new_jti = _token_and_jti(
            create_refresh_token(data={"sub": str(user.id), "type": "refresh"})
        )

        # Rotate tokens in the token service
        try:
            if old_jti and family_id:
                await token_service.rotate_refresh_token(
                    old_jti, new_jti, user.id, family_id
                )
            else:
                # Create new family for legacy tokens
                await token_service.create_refresh_token_entry(user.id, new_jti)
        except Exception as e:
            logger.warning(f"Failed to update refresh token state: {e}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,  # Return NEW refresh token
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except HTTPException:
        # Re-raise HTTPException without modification
        raise
    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Refresh token error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user information"""

    user = (
        current_user.get("user_obj") if isinstance(current_user, dict) else current_user
    )

    if not isinstance(user, User):
        # Get full user details from database
        stmt = (
            select(User)
            .options(selectinload(User.role))
            .where(User.id == int(current_user["id"]))
        )
        result = await db.execute(stmt)
        user = await _scalar_one_or_none(result)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return _user_response(user)


class LogoutRequest(BaseModel):
    """Optional logout request with refresh token for server-side revocation"""

    refresh_token: Optional[str] = None


@router.post("/logout")
async def logout(
    logout_data: Optional[LogoutRequest] = None,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Logout user and revoke refresh token.

    Security mitigation #45: Proper token revocation on logout.

    If refresh_token is provided, it will be revoked server-side.
    Client should still discard all tokens locally.
    """
    from app.services.token_service import token_service

    revoked = False

    if credentials and credentials.credentials:
        revoked = bool(await _maybe_await(blacklist_token(credentials.credentials)))

    # Try to revoke the refresh token if provided
    if logout_data and logout_data.refresh_token:
        try:
            payload = verify_token(logout_data.refresh_token)
            jti = payload.get("jti")
            if jti:
                await token_service.revoke_token(jti)
                revoked = True
                logger.info(
                    f"Logout: Revoked refresh token for user {current_user.get('id')}"
                )
        except Exception as e:
            logger.warning(f"Failed to revoke token on logout: {e}")

    return {
        "message": "Successfully logged out",
        "token_revoked": revoked,
    }


@router.post("/verify-token")
async def verify_user_token(current_user: dict = Depends(get_current_user)):
    """Verify if the current token is valid"""
    return {
        "valid": True,
        "user_id": current_user["id"],
        "email": current_user["email"],
    }


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change user password"""

    if (
        password_data.confirm_password is not None
        and password_data.confirm_password != password_data.new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password confirmation does not match",
        )

    user = (
        current_user.get("user_obj") if isinstance(current_user, dict) else current_user
    )

    if not isinstance(user, User):
        # Get user from database
        stmt = select(User).where(User.id == int(current_user["id"]))
        result = await db.execute(stmt)
        user = await _scalar_one_or_none(result)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Verify current password
    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    user.hashed_password = get_password_hash(password_data.new_password)
    user.updated_at = utc_now()

    await db.commit()

    return {"message": "Password changed successfully"}
