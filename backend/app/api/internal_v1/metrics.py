"""
Prometheus Metrics Endpoint

Exposes metrics in Prometheus format for scraping.
This endpoint typically does not require authentication as it's
scraped by Prometheus from internal network.
"""

from fastapi import APIRouter, Response

from app.core.logging import get_logger
from app.services.metrics import get_metrics_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def get_metrics():
    """
    Get Prometheus metrics in text format.

    Returns metrics for:
    - Usage tracking (requests, tokens, costs, latency)
    - Budget monitoring
    - Pricing sync operations
    - API key status

    This endpoint is designed to be scraped by Prometheus and
    typically does not require authentication.
    """
    try:
        metrics_service = get_metrics_service()
        metrics_data = metrics_service.get_metrics()
        content_type = metrics_service.get_content_type()

        return Response(
            content=metrics_data,
            media_type=content_type,
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(
            content=b"# Error generating metrics\n",
            media_type="text/plain",
            status_code=500,
        )
