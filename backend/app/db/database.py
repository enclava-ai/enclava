"""
Database connection and session management

This module manages database connections with optimized pool settings:
- Primary async pool (asyncpg): 30 + 50 overflow = 80 max connections
- Legacy sync pool (psycopg2): 5 + 10 overflow = 15 max connections
- Total: 95 max connections (under PostgreSQL default of 100)

Pool monitoring is available via get_pool_status() function.
"""

import logging
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# Pool metrics tracking
_pool_metrics = {
    "async_checkouts": 0,
    "async_checkins": 0,
    "async_overflow": 0,
    "sync_checkouts": 0,
    "sync_checkins": 0,
    "sync_overflow": 0,
}

# Create async engine with optimized connection pooling
# This is the PRIMARY engine - most operations should use async sessions
# Pool sizing: 30 base + 50 overflow = 80 max connections
# Note: PostgreSQL default max_connections=100, leave headroom for admin/monitoring
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.APP_DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=30,  # Base pool size for steady-state operations
    max_overflow=50,  # Burst capacity for high load
    pool_recycle=3600,  # Recycle connections every hour
    pool_timeout=30,  # Max time to get connection from pool
    connect_args={
        "timeout": 5,
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

# Create synchronous engine for legacy code paths and startup operations
# IMPORTANT: This pool should be MINIMAL - prefer async operations for all new code
# Most budget enforcement, chatbot, and API operations now use async sessions
# Pool sizing: 5 base + 10 overflow = 15 max connections
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=5,  # Minimal - only for startup/migrations/legacy paths
    max_overflow=10,  # Small burst for edge cases
    pool_recycle=3600,  # Recycle connections every hour
    pool_timeout=30,  # Max time to get connection from pool
    connect_args={
        "connect_timeout": 5,
        "application_name": "enclava_backend_sync",
    },
)

# Create sync session factory
# NOTE: Prefer async_session_factory for all new code
SessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)

# Create base class for models
Base = declarative_base()


# ============================================================================
# Pool Monitoring
# ============================================================================

def _setup_pool_monitoring():
    """Set up event listeners for pool monitoring"""

    # Sync engine pool events
    @event.listens_for(sync_engine, "checkout")
    def sync_checkout(dbapi_conn, connection_record, connection_proxy):
        _pool_metrics["sync_checkouts"] += 1
        pool = sync_engine.pool
        if pool.overflow() > 0:
            _pool_metrics["sync_overflow"] = pool.overflow()
            logger.debug(f"Sync pool checkout (overflow: {pool.overflow()})")

    @event.listens_for(sync_engine, "checkin")
    def sync_checkin(dbapi_conn, connection_record):
        _pool_metrics["sync_checkins"] += 1

    # Note: Async engine pool events work on the underlying sync engine
    # We access it via engine.sync_engine for event registration
    try:
        sync_async_engine = engine.sync_engine

        @event.listens_for(sync_async_engine, "checkout")
        def async_checkout(dbapi_conn, connection_record, connection_proxy):
            _pool_metrics["async_checkouts"] += 1
            pool = sync_async_engine.pool
            if pool.overflow() > 0:
                _pool_metrics["async_overflow"] = pool.overflow()
                logger.debug(f"Async pool checkout (overflow: {pool.overflow()})")

        @event.listens_for(sync_async_engine, "checkin")
        def async_checkin(dbapi_conn, connection_record):
            _pool_metrics["async_checkins"] += 1

    except Exception as e:
        logger.warning(f"Could not set up async pool monitoring: {e}")


def get_pool_status() -> Dict[str, Any]:
    """
    Get current status of database connection pools.

    Returns:
        Dict containing pool statistics for both async and sync engines
    """
    try:
        # Get async pool status
        async_pool = engine.sync_engine.pool
        async_status = {
            "size": async_pool.size(),
            "checked_in": async_pool.checkedin(),
            "checked_out": async_pool.checkedout(),
            "overflow": async_pool.overflow(),
            "invalid": async_pool.invalidatedcount() if hasattr(async_pool, 'invalidatedcount') else 0,
        }
    except Exception as e:
        async_status = {"error": str(e)}

    try:
        # Get sync pool status
        sync_pool = sync_engine.pool
        sync_status = {
            "size": sync_pool.size(),
            "checked_in": sync_pool.checkedin(),
            "checked_out": sync_pool.checkedout(),
            "overflow": sync_pool.overflow(),
            "invalid": sync_pool.invalidatedcount() if hasattr(sync_pool, 'invalidatedcount') else 0,
        }
    except Exception as e:
        sync_status = {"error": str(e)}

    return {
        "async_pool": async_status,
        "sync_pool": sync_status,
        "metrics": _pool_metrics.copy(),
        "config": {
            "async_pool_size": 30,
            "async_max_overflow": 50,
            "async_max_connections": 80,
            "sync_pool_size": 5,
            "sync_max_overflow": 10,
            "sync_max_connections": 15,
            "total_max_connections": 95,
        }
    }


def log_pool_status():
    """Log current pool status (useful for debugging)"""
    status = get_pool_status()
    logger.info(f"Database pool status: {status}")


# Initialize pool monitoring
_setup_pool_monitoring()

# Metadata for migrations
metadata = MetaData()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    from fastapi import HTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    async with async_session_factory() as session:
        try:
            yield session
        except (HTTPException, StarletteHTTPException):
            # Don't log HTTP exceptions - these are normal API responses (401, 403, 404, etc.)
            # Just rollback any pending transaction and re-raise
            await session.rollback()
            raise
        except SQLAlchemyError as e:
            # Log actual database errors
            logger.error(f"Database error during request: {e}")
            await session.rollback()
            raise
        except Exception as e:
            # Log unexpected errors but don't treat them as database failures
            logger.warning(f"Request error (non-database): {type(e).__name__}")
            await session.rollback()
            raise


async def init_db():
    """Initialize database"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models.user import User
            from app.models.role import Role
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

        # Create default roles if they don't exist
        await create_default_roles()

        # Create default admin user if no admin exists
        await create_default_admin()

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def create_default_roles():
    """Create default roles if they don't exist"""
    from app.models.role import Role, RoleLevel
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    try:
        async with async_session_factory() as session:
            # Check if any roles exist
            stmt = select(Role).limit(1)
            result = await session.execute(stmt)
            existing_role = result.scalar_one_or_none()

            if existing_role:
                logger.info("Roles already exist - skipping default role creation")
                return

            # Create default roles using the Role.create_default_roles class method
            default_roles = Role.create_default_roles()

            for role in default_roles:
                session.add(role)

            await session.commit()

            logger.info("Created default roles: read_only, user, admin, super_admin")

    except SQLAlchemyError as e:
        logger.error(f"Failed to create default roles due to database error: {e}")
        raise


async def create_default_admin():
    """Create default admin user if user with ADMIN_EMAIL doesn't exist"""
    from app.models.user import User
    from app.models.role import Role
    from app.core.security import get_password_hash
    from app.core.config import settings
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    try:
        admin_email = settings.ADMIN_EMAIL
        admin_password = settings.ADMIN_PASSWORD

        if not admin_email or not admin_password:
            logger.info("Admin bootstrap skipped: ADMIN_EMAIL or ADMIN_PASSWORD unset")
            return

        async with async_session_factory() as session:
            # Check if user with ADMIN_EMAIL exists
            stmt = select(User).where(User.email == admin_email)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                logger.info(
                    f"User with email {admin_email} already exists - skipping admin creation"
                )
                return

            # Get the super_admin role
            stmt = select(Role).where(Role.name == "super_admin")
            result = await session.execute(stmt)
            super_admin_role = result.scalar_one_or_none()

            if not super_admin_role:
                logger.error("Super admin role not found - cannot create admin user")
                return

            # Create admin user from environment variables
            # Generate username from email (part before @)
            admin_username = admin_email.split("@")[0]

            admin_user = User.create_default_admin(
                email=admin_email,
                username=admin_username,
                password_hash=get_password_hash(admin_password),
            )

            # Assign the super_admin role
            admin_user.role_id = super_admin_role.id

            session.add(admin_user)
            await session.commit()

            logger.warning("=" * 60)
            logger.warning("ADMIN USER CREATED FROM ENVIRONMENT")
            logger.warning(f"Email: {admin_email}")
            logger.warning(f"Username: {admin_username}")
            logger.warning("Role: Super Administrator")
            logger.warning(
                "Password: [Set via ADMIN_PASSWORD - only used on first creation]"
            )
            logger.warning("PLEASE CHANGE THE PASSWORD AFTER FIRST LOGIN")
            logger.warning("=" * 60)

    except SQLAlchemyError as e:
        logger.error(f"Failed to create default admin user due to database error: {e}")
    except AttributeError as e:
        logger.error(
            f"Failed to create default admin user: invalid ADMIN_EMAIL '{settings.ADMIN_EMAIL}'"
        )
    except Exception as e:
        logger.error(f"Failed to create default admin user: {e}")
        # Don't raise here as this shouldn't block the application startup
