"""
Cost calculation service for LLM model pricing
"""

from typing import Dict, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class CostCalculator:
    """Service for calculating costs based on model usage and token consumption"""

    # Model pricing in 1/10000ths of a dollar per 1000 tokens (input/output)
    MODEL_PRICING = {
        # OpenAI Models
        "gpt-4": {"input": 300, "output": 600},  # $0.03/$0.06 per 1K tokens
        "gpt-4-turbo": {"input": 100, "output": 300},  # $0.01/$0.03 per 1K tokens
        "gpt-3.5-turbo": {"input": 5, "output": 15},  # $0.0005/$0.0015 per 1K tokens
        # Anthropic Models
        "claude-3-opus": {"input": 150, "output": 750},  # $0.015/$0.075 per 1K tokens
        "claude-3-sonnet": {"input": 30, "output": 150},  # $0.003/$0.015 per 1K tokens
        "claude-3-haiku": {
            "input": 25,
            "output": 125,
        },  # $0.00025/$0.00125 per 1K tokens
        # Google Models
        "gemini-pro": {"input": 5, "output": 15},  # $0.0005/$0.0015 per 1K tokens
        "gemini-pro-vision": {
            "input": 5,
            "output": 15,
        },  # $0.0005/$0.0015 per 1K tokens
        # Privatemode.ai Models (estimated pricing)
        "privatemode-llama-70b": {"input": 40, "output": 80},  # Estimated pricing
        "privatemode-mixtral": {"input": 20, "output": 40},  # Estimated pricing
        # Embedding Models
        "text-embedding-ada-002": {"input": 1, "output": 0},  # $0.0001 per 1K tokens
        "text-embedding-3-small": {"input": 2, "output": 0},  # $0.00002 per 1K tokens
        "text-embedding-3-large": {"input": 13, "output": 0},  # $0.00013 per 1K tokens
    }

    # Default pricing for unknown models
    DEFAULT_PRICING = {"input": 10, "output": 20}  # $0.001/$0.002 per 1K tokens

    @classmethod
    def get_model_pricing(cls, model_name: str) -> Dict[str, int]:
        """Get pricing for a specific model"""
        # Normalize model name (remove provider prefixes)
        normalized_name = cls._normalize_model_name(model_name)

        # Look up pricing
        pricing = cls.MODEL_PRICING.get(normalized_name, cls.DEFAULT_PRICING)

        logger.debug(
            f"Pricing for model '{model_name}' (normalized: '{normalized_name}'): {pricing}"
        )
        return pricing

    @classmethod
    def _normalize_model_name(cls, model_name: str) -> str:
        """Normalize model name by removing provider prefixes"""
        # Remove common provider prefixes
        prefixes = ["openai/", "anthropic/", "google/", "gemini/", "privatemode/"]

        normalized = model_name.lower()
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break

        # Handle special cases
        if "claude-3-opus-20240229" in normalized:
            return "claude-3-opus"
        elif "claude-3-sonnet-20240229" in normalized:
            return "claude-3-sonnet"
        elif "claude-3-haiku-20240307" in normalized:
            return "claude-3-haiku"
        elif "meta-llama/llama-3.1-70b-instruct" in normalized:
            return "privatemode-llama-70b"
        elif "mistralai/mixtral-8x7b-instruct" in normalized:
            return "privatemode-mixtral"

        return normalized

    @classmethod
    def calculate_cost_cents(
        cls, model_name: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> int:
        """
        Calculate cost in cents for given token usage

        Args:
            model_name: Name of the LLM model
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens generated

        Returns:
            Total cost in cents
        """
        pricing = cls.get_model_pricing(model_name)

        # Calculate cost per token type
        input_cost_cents = (input_tokens * pricing["input"]) // 1000
        output_cost_cents = (output_tokens * pricing["output"]) // 1000

        total_cost_cents = input_cost_cents + output_cost_cents

        logger.debug(
            f"Cost calculation for {model_name}: "
            f"input_tokens={input_tokens} (${input_cost_cents/100:.4f}), "
            f"output_tokens={output_tokens} (${output_cost_cents/100:.4f}), "
            f"total=${total_cost_cents/100:.4f}"
        )

        return total_cost_cents

    @classmethod
    def estimate_cost_cents(cls, model_name: str, estimated_tokens: int) -> int:
        """
        Estimate cost for a request based on estimated total tokens
        Assumes 70% input, 30% output token distribution

        Args:
            model_name: Name of the LLM model
            estimated_tokens: Estimated total tokens for the request

        Returns:
            Estimated cost in cents
        """
        input_tokens = int(estimated_tokens * 0.7)  # 70% input
        output_tokens = int(estimated_tokens * 0.3)  # 30% output

        return cls.calculate_cost_cents(model_name, input_tokens, output_tokens)

    @classmethod
    def get_cost_per_1k_tokens(cls, model_name: str) -> Dict[str, float]:
        """
        Get cost per 1000 tokens in dollars for display purposes

        Args:
            model_name: Name of the LLM model

        Returns:
            Dictionary with input and output costs in dollars per 1K tokens
        """
        pricing_cents = cls.get_model_pricing(model_name)

        return {
            "input": pricing_cents["input"] / 10000,  # Convert 1/10000ths to dollars
            "output": pricing_cents["output"] / 10000,
            "currency": "USD",
        }

    @classmethod
    def get_all_model_pricing(cls) -> Dict[str, Dict[str, float]]:
        """Get pricing for all supported models in dollars"""
        pricing_data = {}

        for model_name in cls.MODEL_PRICING.keys():
            pricing_data[model_name] = cls.get_cost_per_1k_tokens(model_name)

        return pricing_data

    @classmethod
    def format_cost_display(cls, cost_cents: int) -> str:
        """Format cost in 1/1000ths of a dollar for display"""
        if cost_cents == 0:
            return "$0.00"
        elif cost_cents < 1000:
            return f"${cost_cents/1000:.4f}"
        else:
            return f"${cost_cents/1000:.2f}"


# Convenience functions for common operations
def calculate_request_cost(
    model_name: str, input_tokens: int, output_tokens: int
) -> int:
    """Calculate cost for a single request"""
    return CostCalculator.calculate_cost_cents(model_name, input_tokens, output_tokens)


def estimate_request_cost(model_name: str, estimated_tokens: int) -> int:
    """Estimate cost for a request"""
    return CostCalculator.estimate_cost_cents(model_name, estimated_tokens)


def get_model_pricing_display(model_name: str) -> Dict[str, float]:
    """Get model pricing for display"""
    return CostCalculator.get_cost_per_1k_tokens(model_name)
