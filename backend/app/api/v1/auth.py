"""
Authentication API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    get_current_active_user,
)
from app.db.database import get_db
from app.models.user import User
from app.utils.exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# Request/Response Models
class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if not v.isalnum():
            raise ValueError('Username must contain only alphanumeric characters')
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    
    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
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
        role="user"
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.from_orm(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login user and return access tokens"""
    
    logger.info(f"=== LOGIN DEBUG ===")
    logger.info(f"Login attempt for email: {user_data.email}")
    logger.info(f"Current UTC time: {datetime.utcnow().isoformat()}")
    logger.info(f"Settings check - DATABASE_URL: {'SET' if settings.DATABASE_URL else 'NOT SET'}")
    logger.info(f"Settings check - JWT_SECRET: {'SET' if settings.JWT_SECRET else 'NOT SET'}")
    logger.info(f"Settings check - ADMIN_EMAIL: {settings.ADMIN_EMAIL}")
    logger.info(f"Settings check - BCRYPT_ROUNDS: {settings.BCRYPT_ROUNDS}")
    
    # DEBUG: Check database connection with timeout
    try:
        logger.info("Testing database connection...")
        test_start = datetime.utcnow()
        await db.execute(select(1))
        test_end = datetime.utcnow()
        logger.info(f"Database connection test successful. Time: {(test_end - test_start).total_seconds()} seconds")
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error"
        )
    
    start_time = datetime.utcnow()
    
    # Get user by email
    logger.info("Querying user by email...")
    query_start = datetime.utcnow()
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    query_end = datetime.utcnow()
    logger.info(f"User query completed. Time: {(query_end - query_start).total_seconds()} seconds")
    
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"User not found: {user_data.email}")
        # List available users for debugging
        try:
            all_users_stmt = select(User).limit(5)
            all_users_result = await db.execute(all_users_stmt)
            all_users = all_users_result.scalars().all()
            logger.info(f"Available users (first 5): {[u.email for u in all_users]}")
        except Exception as e:
            logger.error(f"Could not list users: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    logger.info(f"User found: {user.email}, is_active: {user.is_active}")
    logger.info(f"User found, starting password verification...")
    verify_start = datetime.utcnow()
    
    if not verify_password(user_data.password, user.hashed_password):
        verify_end = datetime.utcnow()
        logger.warning(f"Password verification failed. Time taken: {(verify_end - verify_start).total_seconds()} seconds")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    verify_end = datetime.utcnow()
    logger.info(f"Password verification successful. Time taken: {(verify_end - verify_start).total_seconds()} seconds")
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    # Update last login
    logger.info("Updating last login...")
    update_start = datetime.utcnow()
    user.update_last_login()
    await db.commit()
    update_end = datetime.utcnow()
    logger.info(f"Last login updated. Time: {(update_end - update_start).total_seconds()} seconds")
    
    # Create tokens
    logger.info("Creating tokens...")
    token_start = datetime.utcnow()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info(f"Creating access token with expiration: {access_token_expires}")
    logger.info(f"ACCESS_TOKEN_EXPIRE_MINUTES from settings: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "is_superuser": user.is_superuser,
            "role": user.role
        },
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "type": "refresh"}
    )
    token_end = datetime.utcnow()
    logger.info(f"Tokens created. Time: {(token_end - token_start).total_seconds()} seconds")
    
    total_time = datetime.utcnow() - start_time
    logger.info(f"=== LOGIN COMPLETED === Total time: {total_time.total_seconds()} seconds")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    
    try:
        payload = verify_token(token_data.refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        
        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Get user from database
        stmt = select(User).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.info(f"REFRESH: Creating new access token with expiration: {access_token_expires}")
        logger.info(f"REFRESH: ACCESS_TOKEN_EXPIRE_MINUTES from settings: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")
        logger.info(f"REFRESH: Current UTC time: {datetime.utcnow().isoformat()}")
        
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "is_superuser": user.is_superuser,
                "role": user.role
            },
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=token_data.refresh_token,  # Keep same refresh token
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    
    # Get full user details from database
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)


@router.post("/logout")
async def logout():
    """Logout user (client should discard tokens)"""
    return {"message": "Successfully logged out"}


@router.post("/verify-token")
async def verify_user_token(
    current_user: dict = Depends(get_current_user)
):
    """Verify if the current token is valid"""
    return {
        "valid": True,
        "user_id": current_user["id"],
        "email": current_user["email"]
    }


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    
    # Get user from database
    stmt = select(User).where(User.id == int(current_user["id"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    user.hashed_password = get_password_hash(password_data.new_password)
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Password changed successfully"}