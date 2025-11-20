"""Authentication API endpoints"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    get_current_active_user,
)
from app.db.database import get_db, create_default_admin
from app.models.user import User
from app.utils.exceptions import AuthenticationError, ValidationError

logger = get_logger(__name__)

router = APIRouter()
security = HTTPBearer()


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


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    force_password_change: Optional[bool] = None
    message: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    role: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

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

    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if username already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
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

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        role=user.role.name if user.role else None,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login user and return access tokens"""

    # Determine identifier for logging and user lookup
    identifier = user_data.email if user_data.email else user_data.username
    logger.info(
        "LOGIN_DEBUG_START",
        request_time=datetime.utcnow().isoformat(),
        identifier=identifier,
        database_url="SET" if settings.DATABASE_URL else "NOT SET",
        jwt_secret="SET" if settings.JWT_SECRET else "NOT SET",
        admin_email=settings.ADMIN_EMAIL,
        bcrypt_rounds=settings.BCRYPT_ROUNDS,
    )

    start_time = datetime.utcnow()

    # Get user by email or username
    logger.info("LOGIN_USER_QUERY_START")
    query_start = datetime.utcnow()

    if user_data.email:
        stmt = select(User).options(selectinload(User.role)).where(User.email == user_data.email)
    else:
        stmt = select(User).options(selectinload(User.role)).where(User.username == user_data.username)

    result = await db.execute(stmt)
    query_end = datetime.utcnow()
    logger.info(
        "LOGIN_USER_QUERY_END",
        duration_seconds=(query_end - query_start).total_seconds(),
    )

    user = result.scalar_one_or_none()

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
            logger.info("LOGIN_ADMIN_BOOTSTRAP_START", email=user_data.email)
            try:
                await create_default_admin()
                # Re-run lookup after bootstrap attempt
                stmt = select(User).options(selectinload(User.role)).where(User.email == user_data.email)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    logger.info("LOGIN_ADMIN_BOOTSTRAP_SUCCESS", email=user.email)
            except Exception as bootstrap_exc:
                logger.error("LOGIN_ADMIN_BOOTSTRAP_FAILED", error=str(bootstrap_exc))

        if not user:
            logger.warning("LOGIN_USER_NOT_FOUND", identifier=identifier)
            # List available users for debugging
            try:
                all_users_stmt = select(User).limit(5)
                all_users_result = await db.execute(all_users_stmt)
                all_users = all_users_result.scalars().all()
                logger.info(
                    "LOGIN_USER_LIST",
                    users=[u.email for u in all_users],
                )
            except Exception as e:
                logger.error("LOGIN_USER_LIST_FAILURE", error=str(e))

            if bootstrap_attempted:
                logger.warning(
                    "LOGIN_ADMIN_BOOTSTRAP_UNSUCCESSFUL", email=user_data.email
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

    logger.info("LOGIN_USER_FOUND", email=user.email, is_active=user.is_active)
    logger.info("LOGIN_PASSWORD_VERIFY_START")
    verify_start = datetime.utcnow()

    if not verify_password(user_data.password, user.hashed_password):
        verify_end = datetime.utcnow()
        logger.warning(
            "LOGIN_PASSWORD_VERIFY_FAILURE",
            duration_seconds=(verify_end - verify_start).total_seconds(),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    verify_end = datetime.utcnow()
    logger.info(
        "LOGIN_PASSWORD_VERIFY_SUCCESS",
        duration_seconds=(verify_end - verify_start).total_seconds(),
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is disabled"
        )

    # Update last login
    logger.info("LOGIN_LAST_LOGIN_UPDATE_START")
    update_start = datetime.utcnow()
    user.update_last_login()
    await db.commit()
    update_end = datetime.utcnow()
    logger.info(
        "LOGIN_LAST_LOGIN_UPDATE_SUCCESS",
        duration_seconds=(update_end - update_start).total_seconds(),
    )

    # Create tokens
    logger.info("LOGIN_TOKEN_CREATE_START")
    token_start = datetime.utcnow()
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

    refresh_token = create_refresh_token(data={"sub": str(user.id), "type": "refresh"})
    token_end = datetime.utcnow()
    logger.info(
        "LOGIN_TOKEN_CREATE_SUCCESS",
        duration_seconds=(token_end - token_start).total_seconds(),
    )

    total_time = datetime.utcnow() - start_time
    logger.info(
        "LOGIN_DEBUG_COMPLETE",
        total_duration_seconds=total_time.total_seconds(),
    )

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

    return response_data


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""

    try:
        payload = verify_token(token_data.refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Get user from database
        stmt = select(User).options(selectinload(User.role)).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.info(
            f"REFRESH: Creating new access token with expiration: {access_token_expires}"
        )
        logger.info(
            f"REFRESH: ACCESS_TOKEN_EXPIRE_MINUTES from settings: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}"
        )
        logger.info(f"REFRESH: Current UTC time: {datetime.utcnow().isoformat()}")

        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "is_superuser": user.is_superuser,
                "role": user.role.name if user.role else None,
            },
            expires_delta=access_token_expires,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=token_data.refresh_token,  # Keep same refresh token
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

    # Get full user details from database
    stmt = select(User).options(selectinload(User.role)).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        role=user.role.name if user.role else None,
        created_at=user.created_at,
    )


@router.post("/logout")
async def logout():
    """Logout user (client should discard tokens)"""
    return {"message": "Successfully logged out"}


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

    # Get user from database
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

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
    user.updated_at = datetime.utcnow()

    await db.commit()

    return {"message": "Password changed successfully"}
