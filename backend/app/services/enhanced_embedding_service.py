# Enhanced Embedding Service with Rate Limiting Handling
"""
Enhanced embedding service with robust rate limiting and retry logic
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime, timedelta

from .embedding_service import EmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancedEmbeddingService(EmbeddingService):
    """Enhanced embedding service with rate limiting handling"""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-large-instruct"):
        super().__init__(model_name)
        self.rate_limit_tracker = {
            'requests_count': 0,
            'window_start': time.time(),
            'window_size': 60,  # 1 minute window
            'max_requests_per_minute': int(getattr(settings, 'RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE', 60)),  # Configurable
            'retry_delays': [int(x) for x in getattr(settings, 'RAG_EMBEDDING_RETRY_DELAYS', '1,2,4,8,16').split(',')],  # Exponential backoff
            'delay_between_batches': float(getattr(settings, 'RAG_EMBEDDING_DELAY_BETWEEN_BATCHES', 0.5)),
            'last_rate_limit_error': None
        }

    async def get_embeddings_with_retry(self, texts: List[str], max_retries: int = None) -> tuple[List[List[float]], bool]:
        """
        Get embeddings with rate limiting and retry logic
        """
        if max_retries is None:
            max_retries = int(getattr(settings, 'RAG_EMBEDDING_RETRY_COUNT', 3))

        batch_size = int(getattr(settings, 'RAG_EMBEDDING_BATCH_SIZE', 5))

        if not self.initialized:
            logger.warning("Embedding service not initialized, using fallback")
            return self._generate_fallback_embeddings(texts), False

        embeddings = []
        success = True

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings, batch_success = await self._get_batch_embeddings_with_retry(batch, max_retries)
            embeddings.extend(batch_embeddings)
            success = success and batch_success

            # Add delay between batches to avoid rate limiting
            if i + batch_size < len(texts):
                delay = self.rate_limit_tracker['delay_between_batches']
                await asyncio.sleep(delay)  # Configurable delay between batches

        return embeddings, success

    async def _get_batch_embeddings_with_retry(self, texts: List[str], max_retries: int) -> tuple[List[List[float]], bool]:
        """Get embeddings for a batch with retry logic"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Check rate limit before making request
                if self._is_rate_limited():
                    delay = self._get_rate_limit_delay()
                    logger.warning(f"Rate limit detected, waiting {delay} seconds")
                    await asyncio.sleep(delay)
                    continue

                # Make the request
                embeddings = await self._get_embeddings_batch_impl(texts)

                # Update rate limit tracker on success
                self._update_rate_limit_tracker(success=True)

                return embeddings, True

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Check if it's a rate limit error
                if any(indicator in error_msg for indicator in ['429', 'rate limit', 'too many requests', 'quota exceeded']):
                    logger.warning(f"Rate limit error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    self._update_rate_limit_tracker(success=False)

                    if attempt < max_retries:
                        delay = self.rate_limit_tracker['retry_delays'][min(attempt, len(self.rate_limit_tracker['retry_delays']) - 1)]
                        logger.info(f"Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for rate limit, using fallback embeddings")
                        return self._generate_fallback_embeddings(texts), False
                else:
                    # Non-rate-limit error
                    logger.error(f"Error generating embeddings: {e}")
                    if attempt < max_retries:
                        delay = self.rate_limit_tracker['retry_delays'][min(attempt, len(self.rate_limit_tracker['retry_delays']) - 1)]
                        await asyncio.sleep(delay)
                    else:
                        logger.error("Max retries exceeded, using fallback embeddings")
                        return self._generate_fallback_embeddings(texts), False

        # If we get here, all retries failed
        logger.error(f"All retries failed, last error: {last_error}")
        return self._generate_fallback_embeddings(texts), False

    async def _get_embeddings_batch_impl(self, texts: List[str]) -> List[List[float]]:
        """Implementation of getting embeddings for a batch"""
        from app.services.llm.service import llm_service
        from app.services.llm.models import EmbeddingRequest

        embeddings = []

        for text in texts:
            # Truncate text if needed
            max_chars = 1600
            truncated_text = text[:max_chars] if len(text) > max_chars else text

            llm_request = EmbeddingRequest(
                model=self.model_name,
                input=truncated_text,
                user_id="rag_system",
                api_key_id=0
            )

            response = await llm_service.create_embedding(llm_request)

            if response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                if embedding:
                    embeddings.append(embedding)
                    if not hasattr(self, '_dimension_confirmed'):
                        self.dimension = len(embedding)
                        self._dimension_confirmed = True
                else:
                    raise ValueError("Empty embedding in response")
            else:
                raise ValueError("Invalid response structure")

        return embeddings

    def _is_rate_limited(self) -> bool:
        """Check if we're currently rate limited"""
        now = time.time()
        window_start = self.rate_limit_tracker['window_start']

        # Reset window if it's expired
        if now - window_start > self.rate_limit_tracker['window_size']:
            self.rate_limit_tracker['requests_count'] = 0
            self.rate_limit_tracker['window_start'] = now
            return False

        # Check if we've exceeded the limit
        return self.rate_limit_tracker['requests_count'] >= self.rate_limit_tracker['max_requests_per_minute']

    def _get_rate_limit_delay(self) -> float:
        """Get delay to wait for rate limit reset"""
        now = time.time()
        window_end = self.rate_limit_tracker['window_start'] + self.rate_limit_tracker['window_size']
        return max(0, window_end - now)

    def _update_rate_limit_tracker(self, success: bool):
        """Update the rate limit tracker"""
        now = time.time()

        # Reset window if it's expired
        if now - self.rate_limit_tracker['window_start'] > self.rate_limit_tracker['window_size']:
            self.rate_limit_tracker['requests_count'] = 0
            self.rate_limit_tracker['window_start'] = now

        # Increment counter on successful requests
        if success:
            self.rate_limit_tracker['requests_count'] += 1

    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics including rate limiting info"""
        base_stats = await self.get_stats()

        return {
            **base_stats,
            "rate_limit_info": {
                "requests_in_current_window": self.rate_limit_tracker['requests_count'],
                "max_requests_per_minute": self.rate_limit_tracker['max_requests_per_minute'],
                "window_reset_in_seconds": max(0,
                    self.rate_limit_tracker['window_start'] + self.rate_limit_tracker['window_size'] - time.time()
                ),
                "last_rate_limit_error": self.rate_limit_tracker['last_rate_limit_error']
            }
        }


# Global enhanced embedding service instance
enhanced_embedding_service = EnhancedEmbeddingService()