"""
Streaming Token Tracker for tracking token usage across streaming chunks.

This module provides real-time token accumulation for SSE streaming responses
where token counts may come incrementally or only in the final chunk.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StreamingUsage:
    """Final usage statistics from a streaming session."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    ttft_ms: Optional[int]  # Time to first token
    total_duration_ms: int
    chunk_count: int


class StreamingTokenTracker:
    """
    Tracks token usage across streaming chunks.

    Handles different provider behaviors:
    - Providers that include usage in every chunk (accumulating)
    - Providers that only include usage in the final chunk
    - Providers that don't include usage at all (requires estimation)
    """

    def __init__(self, model: str, estimated_input_tokens: int = 0):
        """
        Initialize the streaming token tracker.

        Args:
            model: Model name for potential token estimation
            estimated_input_tokens: Pre-computed estimate of input tokens
        """
        self.model = model
        self._estimated_input_tokens = estimated_input_tokens

        # Token tracking
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self._accumulated_content: str = ""

        # Timing
        self._start_time: float = time.time()
        self._first_chunk_time: Optional[float] = None
        self._end_time: Optional[float] = None

        # Chunk tracking
        self._chunk_count: int = 0
        self._has_usage_data: bool = False
        self._finish_reason: Optional[str] = None

        # Provider-specific tracking
        self._last_usage_snapshot: Dict[str, int] = {}

    def process_chunk(self, chunk: Dict[str, Any]) -> None:
        """
        Process a streaming chunk and accumulate usage.

        Args:
            chunk: The streaming chunk from the provider
        """
        self._chunk_count += 1

        # Track first chunk time for TTFT calculation
        if self._first_chunk_time is None:
            self._first_chunk_time = time.time()
            logger.debug(
                f"Streaming first chunk received for model {self.model}, "
                f"TTFT={self.ttft_ms}ms"
            )

        # Extract content delta for token estimation (if no usage data)
        choices = chunk.get("choices", [])
        for choice in choices:
            # Track content for potential estimation
            delta = choice.get("delta", {})
            content = delta.get("content", "")
            if content:
                self._accumulated_content += content

            # Check for finish_reason (indicates final chunk)
            if choice.get("finish_reason"):
                self._finish_reason = choice.get("finish_reason")

        # Extract usage from chunk if present
        if "usage" in chunk:
            self._process_usage(chunk["usage"])

        # Some providers include usage in x_groq or other custom fields
        if "x_groq" in chunk and "usage" in chunk.get("x_groq", {}):
            self._process_usage(chunk["x_groq"]["usage"])

    def _process_usage(self, usage: Dict[str, Any]) -> None:
        """
        Process usage data from a chunk.

        Args:
            usage: Usage dictionary from the chunk
        """
        self._has_usage_data = True

        # Get token counts (may be cumulative or per-chunk depending on provider)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Most providers send cumulative usage in the final chunk
        # So we take the maximum values seen
        if prompt_tokens > 0:
            self.input_tokens = max(self.input_tokens, prompt_tokens)
        if completion_tokens > 0:
            self.output_tokens = max(self.output_tokens, completion_tokens)

        self._last_usage_snapshot = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": usage.get(
                "total_tokens", prompt_tokens + completion_tokens
            ),
        }

        logger.debug(
            f"Streaming usage update: input={self.input_tokens}, output={self.output_tokens}"
        )

    def finalize(self) -> StreamingUsage:
        """
        Finalize the streaming session and return usage statistics.

        Should be called after the stream is complete.

        Returns:
            StreamingUsage with final token counts
        """
        self._end_time = time.time()

        # If no usage data was received, estimate from content
        if not self._has_usage_data:
            self._estimate_tokens()

        # Use estimated input tokens if we didn't get them from provider
        if self.input_tokens == 0 and self._estimated_input_tokens > 0:
            self.input_tokens = self._estimated_input_tokens

        total_duration_ms = int((self._end_time - self._start_time) * 1000)

        usage = StreamingUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.input_tokens + self.output_tokens,
            ttft_ms=self.ttft_ms,
            total_duration_ms=total_duration_ms,
            chunk_count=self._chunk_count,
        )

        logger.info(
            f"Streaming finalized for model {self.model}: "
            f"input={usage.input_tokens}, output={usage.output_tokens}, "
            f"total={usage.total_tokens}, chunks={usage.chunk_count}, "
            f"duration={usage.total_duration_ms}ms, ttft={usage.ttft_ms}ms"
        )

        return usage

    def _estimate_tokens(self) -> None:
        """
        Estimate tokens when provider doesn't include usage data.

        Uses a rough word-to-token ratio for estimation.
        """
        if self._accumulated_content:
            # Rough estimation: ~1.3 tokens per word (varies by language/content)
            word_count = len(self._accumulated_content.split())
            self.output_tokens = int(word_count * 1.3)

            logger.warning(
                f"Estimating output tokens for {self.model}: "
                f"~{word_count} words -> {self.output_tokens} tokens (estimated)"
            )

    @property
    def ttft_ms(self) -> Optional[int]:
        """Time to first token in milliseconds."""
        if self._first_chunk_time is not None:
            return int((self._first_chunk_time - self._start_time) * 1000)
        return None

    @property
    def elapsed_ms(self) -> int:
        """Elapsed time since stream started in milliseconds."""
        end = self._end_time or time.time()
        return int((end - self._start_time) * 1000)

    @property
    def is_complete(self) -> bool:
        """Check if the stream has completed (finish_reason received)."""
        return self._finish_reason is not None

    @property
    def finish_reason(self) -> Optional[str]:
        """The finish reason from the final chunk."""
        return self._finish_reason

    def get_current_usage(self) -> Dict[str, int]:
        """
        Get current token counts (useful for partial progress reporting).

        Returns:
            Dictionary with current token counts
        """
        return {
            "input_tokens": self.input_tokens or self._estimated_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": (self.input_tokens or self._estimated_input_tokens)
            + self.output_tokens,
            "chunk_count": self._chunk_count,
        }


class StreamingUsageRecorder:
    """
    Context manager for tracking streaming usage and recording it when complete.

    Example usage:
        async with StreamingUsageRecorder(db, tracker, context) as recorder:
            async for chunk in stream:
                recorder.process_chunk(chunk)
                yield chunk
        # Usage is automatically recorded when context exits
    """

    def __init__(
        self,
        tracker: StreamingTokenTracker,
        request_id,
        user_id: Optional[int],
        api_key_id: Optional[int],
        provider_id: str,
        endpoint: str,
    ):
        self.tracker = tracker
        self.request_id = request_id
        self.user_id = user_id
        self.api_key_id = api_key_id
        self.provider_id = provider_id
        self.endpoint = endpoint
        self._error: Optional[Exception] = None

    def process_chunk(self, chunk: Dict[str, Any]) -> None:
        """Process a streaming chunk."""
        self.tracker.process_chunk(chunk)

    def set_error(self, error: Exception) -> None:
        """Record an error that occurred during streaming."""
        self._error = error

    def get_final_usage(self) -> StreamingUsage:
        """Get the final usage after streaming completes."""
        return self.tracker.finalize()

    @property
    def had_error(self) -> bool:
        """Check if an error occurred during streaming."""
        return self._error is not None

    @property
    def error(self) -> Optional[Exception]:
        """Get the error that occurred, if any."""
        return self._error
