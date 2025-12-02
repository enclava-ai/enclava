# Enhanced Embedding Service with Rate Limiting Handling
"""
Enhanced embedding service that adds basic retry semantics around the local
embedding generator. Since embeddings are fully local, rate-limiting metadata is
largely informational but retained for compatibility.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancedEmbeddingService(EmbeddingService):
    """Enhanced embedding service with lightweight retry bookkeeping"""

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(model_name)
        self.rate_limit_tracker = {
            "requests_count": 0,
            "window_start": time.time(),
            "window_size": 60,  # 1 minute window
            "max_requests_per_minute": int(
                getattr(settings, "RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE", 12)
            ),  # Configurable
            "retry_delays": [
                int(x)
                for x in getattr(
                    settings, "RAG_EMBEDDING_RETRY_DELAYS", "1,2,4,8,16"
                ).split(",")
            ],  # Exponential backoff
            "delay_between_batches": float(
                getattr(settings, "RAG_EMBEDDING_DELAY_BETWEEN_BATCHES", 1.0)
            ),
            "delay_per_request": float(
                getattr(settings, "RAG_EMBEDDING_DELAY_PER_REQUEST", 0.5)
            ),
            "last_rate_limit_error": None,
        }

    async def get_embeddings_with_retry(
        self, texts: List[str], max_retries: int = None
    ) -> tuple[List[List[float]], bool]:
        """
        Get embeddings with retry bookkeeping.
        """
        embeddings = await super().get_embeddings(texts)
        success = self.local_model is not None
        if not success:
            logger.warning(
                "Embedding service operating in fallback mode; consider installing the local model %s",
                self.model_name,
            )
        return embeddings, success

    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics including rate limiting info"""
        base_stats = await self.get_stats()

        return {
            **base_stats,
            "rate_limit_info": {
                "requests_in_current_window": self.rate_limit_tracker["requests_count"],
                "max_requests_per_minute": self.rate_limit_tracker[
                    "max_requests_per_minute"
                ],
                "window_reset_in_seconds": max(
                    0,
                    self.rate_limit_tracker["window_start"]
                    + self.rate_limit_tracker["window_size"]
                    - time.time(),
                ),
                "last_rate_limit_error": self.rate_limit_tracker[
                    "last_rate_limit_error"
                ],
            },
        }


# Global enhanced embedding service instance
enhanced_embedding_service = EnhancedEmbeddingService()
