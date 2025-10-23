"""
Enhanced Health Check Endpoints

Provides comprehensive health monitoring including:
- Basic HTTP health
- Resource usage checks
- Session leak detection
- Database connectivity
- Service dependencies
"""

import asyncio
import logging
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import async_session_factory
from app.services.embedding_service import embedding_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class HealthChecker:
    """Comprehensive health checking service"""

    def __init__(self):
        self.last_checks: Dict[str, Dict] = {}
        self.check_history: Dict[str, list] = {}

    async def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        start_time = time.time()

        try:
            async with async_session_factory() as session:
                # Simple query to check connectivity
                await session.execute(select(1))

                # Check table availability
                await session.execute(text("SELECT COUNT(*) FROM information_schema.tables"))

                duration = time.time() - start_time

                return {
                    "status": "healthy",
                    "response_time_ms": round(duration * 1000, 2),
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {
                        "connection": "successful",
                        "query_execution": "successful"
                    }
                }

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "connection": "failed",
                    "error_type": type(e).__name__
                }
            }

    async def check_memory_health(self) -> Dict[str, Any]:
        """Check memory usage and detect potential leaks"""
        try:
            memory = psutil.virtual_memory()
            process = psutil.Process()

            # Get process-specific memory
            process_memory = process.memory_info()
            process_memory_mb = process_memory.rss / (1024 * 1024)

            # Check for memory issues
            memory_status = "healthy"
            issues = []

            if process_memory_mb > 4000:  # 4GB threshold
                memory_status = "warning"
                issues.append(f"High memory usage: {process_memory_mb:.1f}MB")

            if process_memory_mb > 8000:  # 8GB critical threshold
                memory_status = "critical"
                issues.append(f"Critical memory usage: {process_memory_mb:.1f}MB")

            # Check system memory pressure
            if memory.percent > 90:
                memory_status = "critical"
                issues.append(f"System memory pressure: {memory.percent:.1f}%")
            elif memory.percent > 80:
                if memory_status == "healthy":
                    memory_status = "warning"
                issues.append(f"High system memory usage: {memory.percent:.1f}%")

            return {
                "status": memory_status,
                "timestamp": datetime.utcnow().isoformat(),
                "process_memory_mb": round(process_memory_mb, 2),
                "system_memory_percent": memory.percent,
                "system_available_gb": round(memory.available / (1024**3), 2),
                "issues": issues
            }

        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def check_connection_health(self) -> Dict[str, Any]:
        """Check for connection leaks and network health"""
        try:
            process = psutil.Process()

            # Get network connections
            connections = process.connections()

            # Analyze connections
            total_connections = len(connections)
            established_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
            http_connections = len([c for c in connections if any(port in str(c.laddr) for port in [80, 8000, 3000])])

            # Check for connection issues
            connection_status = "healthy"
            issues = []

            if total_connections > 500:
                connection_status = "warning"
                issues.append(f"High connection count: {total_connections}")

            if total_connections > 1000:
                connection_status = "critical"
                issues.append(f"Critical connection count: {total_connections}")

            # Check for potential session leaks (high number of connections to HTTP ports)
            if http_connections > 100:
                connection_status = "warning"
                issues.append(f"High HTTP connection count: {http_connections}")

            return {
                "status": connection_status,
                "timestamp": datetime.utcnow().isoformat(),
                "total_connections": total_connections,
                "established_connections": established_connections,
                "http_connections": http_connections,
                "issues": issues
            }

        except Exception as e:
            logger.error(f"Connection health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def check_embedding_service_health(self) -> Dict[str, Any]:
        """Check embedding service health and session management"""
        try:
            start_time = time.time()

            # Get embedding service stats
            stats = await embedding_service.get_stats()

            duration = time.time() - start_time

            # Check service status
            service_status = "healthy" if stats.get("initialized", False) else "warning"
            issues = []

            if not stats.get("initialized", False):
                issues.append("Embedding service not initialized")

            # Check backend type
            backend = stats.get("backend", "unknown")
            if backend == "fallback_random":
                service_status = "warning"
                issues.append("Using fallback random embeddings")

            return {
                "status": service_status,
                "response_time_ms": round(duration * 1000, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "stats": stats,
                "issues": issues
            }

        except Exception as e:
            logger.error(f"Embedding service health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        if not settings.REDIS_URL:
            return {
                "status": "not_configured",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            import redis.asyncio as redis

            start_time = time.time()

            client = redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )

            # Test Redis connection
            await asyncio.wait_for(client.ping(), timeout=3.0)

            duration = time.time() - start_time

            await client.close()

            return {
                "status": "healthy",
                "response_time_ms": round(duration * 1000, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        checks = {
            "database": await self.check_database_health(),
            "memory": await self.check_memory_health(),
            "connections": await self.check_connection_health(),
            "embedding_service": await self.check_embedding_service_health(),
            "redis": await self.check_redis_health()
        }

        # Determine overall status
        statuses = [check.get("status", "error") for check in checks.values()]

        if "critical" in statuses or "error" in statuses:
            overall_status = "unhealthy"
        elif "warning" in statuses or "unhealthy" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Count issues
        total_issues = sum(len(check.get("issues", [])) for check in checks.values())

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "summary": {
                "total_checks": len(checks),
                "healthy_checks": len([s for s in statuses if s == "healthy"]),
                "degraded_checks": len([s for s in statuses if s in ["warning", "degraded", "unhealthy"]]),
                "failed_checks": len([s for s in statuses if s in ["critical", "error"]]),
                "total_issues": total_issues
            },
            "version": "1.0.0",
            "uptime_seconds": int(time.time() - psutil.boot_time())
        }


# Global health checker instance
health_checker = HealthChecker()


@router.get("/health")
async def basic_health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with all services"""
    try:
        return await health_checker.get_comprehensive_health()
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/memory")
async def memory_health_check():
    """Memory-specific health check"""
    try:
        return await health_checker.check_memory_health()
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Memory health check failed: {str(e)}"
        )


@router.get("/health/connections")
async def connection_health_check():
    """Connection-specific health check"""
    try:
        return await health_checker.check_connection_health()
    except Exception as e:
        logger.error(f"Connection health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Connection health check failed: {str(e)}"
        )


@router.get("/health/embedding")
async def embedding_service_health_check():
    """Embedding service-specific health check"""
    try:
        return await health_checker.check_embedding_service_health()
    except Exception as e:
        logger.error(f"Embedding service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service health check failed: {str(e)}"
        )