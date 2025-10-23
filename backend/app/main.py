"""Main FastAPI application entry point"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import get_current_user
from app.db.database import init_db, async_session_factory
from app.api.internal_v1 import internal_api_router
from app.api.public_v1 import public_api_router
from app.utils.exceptions import CustomHTTPException
from app.services.module_manager import module_manager
from app.services.metrics import setup_metrics
from app.services.analytics import init_analytics_service
from app.middleware.analytics import setup_analytics_middleware
from app.services.config_manager import init_config_manager

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def _check_redis_startup():
    """Validate Redis connectivity during startup."""
    if not settings.REDIS_URL:
        logger.info("Startup Redis check skipped: REDIS_URL not configured")
        return

    try:
        import redis.asyncio as redis
    except ModuleNotFoundError:
        logger.warning("Startup Redis check skipped: redis library not installed")
        return

    client = redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )

    start = time.perf_counter()
    try:
        await asyncio.wait_for(client.ping(), timeout=3.0)
        duration = time.perf_counter() - start
        logger.info(
            "Startup Redis check succeeded",
            extra={"redis_url": settings.REDIS_URL, "duration_seconds": round(duration, 3)},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Startup Redis check failed",
            extra={"error": str(exc), "redis_url": settings.REDIS_URL},
        )
    finally:
        await client.close()


async def _check_database_startup():
    """Validate database connectivity during startup."""
    start = time.perf_counter()
    try:
        async with async_session_factory() as session:
            await asyncio.wait_for(session.execute(select(1)), timeout=3.0)
        duration = time.perf_counter() - start
        logger.info(
            "Startup database check succeeded",
            extra={"duration_seconds": round(duration, 3)},
        )
    except (asyncio.TimeoutError, SQLAlchemyError) as exc:
        logger.error(
            "Startup database check failed",
            extra={"error": str(exc)},
        )
        raise


async def run_startup_dependency_checks():
    """Run dependency checks once during application startup."""
    logger.info("Running startup dependency checks...")
    await _check_redis_startup()
    await _check_database_startup()
    logger.info("Startup dependency checks complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    """
    logger.info("Starting Enclava platform...")
    
    # Initialize core cache service (before database to provide caching for auth)
    from app.core.cache import core_cache
    try:
        await core_cache.initialize()
        logger.info("Core cache service initialized successfully")
    except Exception as e:
        logger.warning(f"Core cache service initialization failed: {e}")

    # Run one-time dependency checks (non-blocking for auth requests)
    try:
        await run_startup_dependency_checks()
    except Exception:
        logger.error("Critical dependency check failed during startup")
        raise

    # Initialize database
    await init_db()
    
    # Initialize config manager
    await init_config_manager()

    # Initialize LLM service (needed by RAG module)
    from app.services.llm.service import llm_service
    try:
        await llm_service.initialize()
        logger.info("LLM service initialized successfully")
    except Exception as e:
        logger.warning(f"LLM service initialization failed: {e}")

    # Initialize analytics service
    init_analytics_service()

    # Initialize module manager with FastAPI app for router registration
    logger.info("Initializing module manager...")
    await module_manager.initialize(app)
    app.state.module_manager = module_manager
    logger.info("Module manager initialized successfully")
    
    # Initialize permission registry
    logger.info("Initializing permission registry...")
    from app.services.permission_manager import permission_registry
    permission_registry.register_platform_permissions()
    logger.info("Permission registry initialized successfully")
    
    # Initialize document processor
    from app.services.document_processor import document_processor
    await document_processor.start()
    app.state.document_processor = document_processor
    
    # Setup metrics
    setup_metrics(app)
    
    # Start background audit worker
    from app.services.audit_service import start_audit_worker
    start_audit_worker()
    
    # Initialize plugin auto-discovery service
    from app.services.plugin_autodiscovery import initialize_plugin_autodiscovery
    try:
        discovery_results = await initialize_plugin_autodiscovery()
        app.state.plugin_discovery_results = discovery_results
        logger.info(f"Plugin auto-discovery completed: {discovery_results['summary']}")
    except Exception as e:
        logger.warning(f"Plugin auto-discovery failed: {e}")
    
    logger.info("Platform started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down platform...")

    # Cleanup embedding service HTTP sessions
    from app.services.embedding_service import embedding_service
    try:
        await embedding_service.cleanup()
        logger.info("Embedding service cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up embedding service: {e}")

    # Close core cache service
    from app.core.cache import core_cache
    await core_cache.cleanup()

    # Close Redis connection for cached API key service
    from app.services.cached_api_key import cached_api_key_service
    await cached_api_key_service.close()

    # Stop document processor
    if hasattr(app.state, 'document_processor'):
        await app.state.document_processor.stop()

    await module_manager.cleanup()
    logger.info("Platform shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Enclava - Modular AI Platform with confidential processing",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,
    max_age=settings.SESSION_EXPIRE_MINUTES * 60,
)

# Add analytics middleware
setup_analytics_middleware(app)

# Security middleware disabled - handled externally

# Rate limiting middleware disabled - handled externally


# Exception handlers
@app.exception_handler(CustomHTTPException)
async def custom_http_exception_handler(request, exc: CustomHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.detail,
            "details": exc.details,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    # Convert validation errors to JSON-serializable format
    errors = []
    for error in exc.errors():
        error_dict = {
            "type": error.get("type", ""),
            "location": error.get("loc", []),
            "message": error.get("msg", ""),
            "input": str(error.get("input", "")) if error.get("input") is not None else None
        }
        errors.append(error_dict)
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "details": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# Include Internal API routes (for frontend)
app.include_router(internal_api_router, prefix="/api-internal/v1")

# Include Public API routes (for external clients)  
app.include_router(public_api_router, prefix="/api/v1")

# OpenAI-compatible routes are now included in public API router at /api/v1/


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Enclava - Modular AI Platform",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "internal_docs": "/api-internal/v1/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level=settings.APP_LOG_LEVEL.lower(),
    )
