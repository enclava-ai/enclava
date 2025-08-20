"""
Main FastAPI application entry point
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security import get_current_user
from app.db.database import init_db
from app.api.v1 import api_router
from app.utils.exceptions import CustomHTTPException
from app.services.module_manager import module_manager
from app.services.metrics import setup_metrics
from app.services.analytics import init_analytics_service
from app.middleware.analytics import setup_analytics_middleware
from app.services.config_manager import init_config_manager

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


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
    
    # Initialize database
    await init_db()
    
    # Initialize config manager
    await init_config_manager()
    
    # Initialize analytics service
    init_analytics_service()
    
    # Initialize module manager with FastAPI app for router registration
    await module_manager.initialize(app)
    app.state.module_manager = module_manager
    
    # Initialize document processor
    from app.services.document_processor import document_processor
    await document_processor.start()
    app.state.document_processor = document_processor
    
    # Setup metrics
    setup_metrics(app)
    
    # Start background audit worker
    from app.services.audit_service import start_audit_worker
    start_audit_worker()
    
    logger.info("Platform started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down platform...")
    
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

# Add security middleware
from app.middleware.security import setup_security_middleware
setup_security_middleware(app, enabled=settings.API_SECURITY_ENABLED)


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


# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Include OpenAI-compatible routes
from app.api.v1.openai_compat import router as openai_router
app.include_router(openai_router, prefix="/v1", tags=["openai-compat"])


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