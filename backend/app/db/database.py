"""
Database connection and session management
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine with optimized connection pooling
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.APP_DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=50,          # Increased from 20 for better concurrency
    max_overflow=100,      # Increased from 30 for burst capacity  
    pool_recycle=3600,     # Recycle connections every hour
    pool_timeout=30,       # Max time to get connection from pool
    connect_args={
        "command_timeout": 5,
        "server_settings": {
            "application_name": "enclava_backend",
        },
    },
)

# Create async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create synchronous engine and session for budget enforcement (optimized)
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=25,          # Increased from 10 for better performance
    max_overflow=50,       # Increased from 20 for burst capacity
    pool_recycle=3600,     # Recycle connections every hour
    pool_timeout=30,       # Max time to get connection from pool
    connect_args={
        "application_name": "enclava_backend_sync",
    },
)

# Create sync session factory
SessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)

# Create base class for models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            # Only log if there's an actual error, not normal operation
            if str(e).strip():  # Only log if error message exists
                logger.error(f"Database session error: {str(e)}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models.user import User
            from app.models.api_key import APIKey
            from app.models.usage_tracking import UsageTracking
            # Import additional models - these are available
            try:
                from app.models.budget import Budget
            except ImportError:
                logger.warning("Budget model not available yet")
            
            try:
                from app.models.audit_log import AuditLog
            except ImportError:
                logger.warning("AuditLog model not available yet")
            
            try:
                from app.models.module import Module
            except ImportError:
                logger.warning("Module model not available yet")
            
            # Tables are now created via migration container - no need to create here
            # await conn.run_sync(Base.metadata.create_all)  # DISABLED - migrations handle this
            
        # Create default admin user if no admin exists
        await create_default_admin()
            
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def create_default_admin():
    """Create default admin user if user with ADMIN_EMAIL doesn't exist"""
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.config import settings
    from sqlalchemy import select
    
    try:
        async with async_session_factory() as session:
            # Check if user with ADMIN_EMAIL exists
            stmt = select(User).where(User.email == settings.ADMIN_EMAIL)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                logger.info(f"User with email {settings.ADMIN_EMAIL} already exists - skipping admin creation")
                return
            
            # Create admin user from environment variables
            admin_email = settings.ADMIN_EMAIL
            admin_password = settings.ADMIN_PASSWORD
            # Generate username from email (part before @)
            admin_username = admin_email.split('@')[0]
            
            admin_user = User.create_default_admin(
                email=admin_email,
                username=admin_username,
                password_hash=get_password_hash(admin_password)
            )
            
            session.add(admin_user)
            await session.commit()
            
            logger.warning("=" * 60)
            logger.warning("ADMIN USER CREATED FROM ENVIRONMENT")
            logger.warning(f"Email: {admin_email}")
            logger.warning(f"Username: {admin_username}")
            logger.warning("Password: [Set via ADMIN_PASSWORD - only used on first creation]")
            logger.warning("PLEASE CHANGE THE PASSWORD AFTER FIRST LOGIN")
            logger.warning("=" * 60)
            
    except Exception as e:
        logger.error(f"Failed to create default admin user: {e}")
        # Don't raise here as this shouldn't block the application startup