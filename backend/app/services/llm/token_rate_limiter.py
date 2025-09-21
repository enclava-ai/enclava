"""
Token-based rate limiting for LLM service
"""

import time
import redis
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class TokenRateLimiter:
    """Token-based rate limiting implementation"""

    def __init__(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            logger.info("Token rate limiter initialized with Redis backend")
        except Exception as e:
            logger.warning(f"Redis not available for token rate limiting: {e}")
            self.redis_client = None
            # Fall back to in-memory rate limiting
            self.in_memory_store = {}
            logger.info("Token rate limiter using in-memory fallback")

    async def check_token_limits(
        self,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int = 0
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Check if token usage is within limits

        Args:
            provider: Provider name (e.g., "privatemode")
            prompt_tokens: Number of prompt tokens to use
            completion_tokens: Number of completion tokens to use

        Returns:
            Tuple of (is_allowed, headers)
        """
        # Get token limits from configuration
        from .config import get_config
        config = get_config()
        token_limits = config.token_limits_per_minute

        # Check organization-wide limits
        org_key = f"tokens:org:{provider}"

        # Get current usage
        current_usage = await self._get_token_usage(org_key)

        # Calculate new usage
        new_prompt_tokens = current_usage.get("prompt_tokens", 0) + prompt_tokens
        new_completion_tokens = current_usage.get("completion_tokens", 0) + completion_tokens

        # Check limits
        prompt_limit = token_limits.get("prompt_tokens", 20000)
        completion_limit = token_limits.get("completion_tokens", 10000)

        is_allowed = (
            new_prompt_tokens <= prompt_limit and
            new_completion_tokens <= completion_limit
        )

        if is_allowed:
            # Update usage
            await self._update_token_usage(org_key, prompt_tokens, completion_tokens)
            logger.debug(f"Token usage updated: {new_prompt_tokens}/{prompt_limit} prompt, "
                        f"{new_completion_tokens}/{completion_limit} completion")

        # Calculate remaining tokens
        remaining_prompt = max(0, prompt_limit - new_prompt_tokens)
        remaining_completion = max(0, completion_limit - new_completion_tokens)

        # Create headers
        headers = {
            "X-TokenLimit-Prompt-Remaining": str(remaining_prompt),
            "X-TokenLimit-Completion-Remaining": str(remaining_completion),
            "X-TokenLimit-Prompt-Limit": str(prompt_limit),
            "X-TokenLimit-Completion-Limit": str(completion_limit),
            "X-TokenLimit-Reset": str(int(time.time() + 60))  # Reset in 1 minute
        }

        if not is_allowed:
            logger.warning(f"Token rate limit exceeded for {provider}. "
                          f"Requested: {prompt_tokens} prompt, {completion_tokens} completion. "
                          f"Current: {current_usage}")

        return is_allowed, headers

    async def _get_token_usage(self, key: str) -> Dict[str, int]:
        """Get current token usage"""
        if self.redis_client:
            try:
                data = self.redis_client.hgetall(key)
                if data:
                    return {
                        "prompt_tokens": int(data.get("prompt_tokens", 0)),
                        "completion_tokens": int(data.get("completion_tokens", 0)),
                        "updated_at": float(data.get("updated_at", time.time()))
                    }
            except Exception as e:
                logger.error(f"Error getting token usage from Redis: {e}")

        # Fallback to in-memory
        return self.in_memory_store.get(key, {"prompt_tokens": 0, "completion_tokens": 0})

    async def _update_token_usage(self, key: str, prompt_tokens: int, completion_tokens: int):
        """Update token usage"""
        if self.redis_client:
            try:
                pipe = self.redis_client.pipeline()
                pipe.hincrby(key, "prompt_tokens", prompt_tokens)
                pipe.hincrby(key, "completion_tokens", completion_tokens)
                pipe.hset(key, "updated_at", time.time())
                pipe.expire(key, 60)  # Expire after 1 minute
                pipe.execute()
            except Exception as e:
                logger.error(f"Error updating token usage in Redis: {e}")
                # Fallback to in-memory
                self._update_in_memory(key, prompt_tokens, completion_tokens)
        else:
            self._update_in_memory(key, prompt_tokens, completion_tokens)

    def _update_in_memory(self, key: str, prompt_tokens: int, completion_tokens: int):
        """Update in-memory token usage"""
        if key not in self.in_memory_store:
            self.in_memory_store[key] = {"prompt_tokens": 0, "completion_tokens": 0}

        self.in_memory_store[key]["prompt_tokens"] += prompt_tokens
        self.in_memory_store[key]["completion_tokens"] += completion_tokens
        self.in_memory_store[key]["updated_at"] = time.time()

    def cleanup_expired(self):
        """Clean up expired entries (for in-memory store)"""
        if not self.redis_client:
            current_time = time.time()
            expired_keys = [
                key for key, data in self.in_memory_store.items()
                if current_time - data.get("updated_at", 0) > 60
            ]
            for key in expired_keys:
                del self.in_memory_store[key]


# Global token rate limiter instance
token_rate_limiter = TokenRateLimiter()