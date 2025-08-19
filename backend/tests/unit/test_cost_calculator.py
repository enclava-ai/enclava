"""
Test cost calculation service.
"""
import pytest
from app.services.cost_calculator import CostCalculator


class TestCostCalculator:
    """Test cost calculation functionality."""

    def test_openai_gpt35_turbo_cost(self):
        """Test OpenAI GPT-3.5 Turbo cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gpt-3.5-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        # GPT-3.5 Turbo: $0.0005/1K input tokens, $0.0015/1K output tokens
        # Input: 1000 tokens * 5 units/1K = 5 units
        # Output: 500 tokens * 15 units/1K = 7 units
        expected_cost_cents = 5 + 7
        assert cost_cents == expected_cost_cents

    def test_openai_gpt4_cost(self):
        """Test OpenAI GPT-4 cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gpt-4",
            input_tokens=1000,
            output_tokens=500
        )
        
        # GPT-4: $0.03/1K input tokens, $0.06/1K output tokens
        # Input: 1000 tokens * 300 units/1K = 300 units
        # Output: 500 tokens * 600 units/1K = 300 units
        expected_cost_cents = 300 + 300
        assert cost_cents == expected_cost_cents

    def test_anthropic_claude_cost(self):
        """Test Anthropic Claude cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="claude-3-haiku",
            input_tokens=1000,
            output_tokens=500
        )
        
        # Claude-3 Haiku: $0.00025/1K input tokens, $0.00125/1K output tokens
        # Input: 1000 tokens * 25 cents/1K = 25 cents
        # Output: 500 tokens * 125 cents/1K = 62.5 cents -> 62 cents (integer division)
        expected_cost_cents = 25 + 62
        assert cost_cents == expected_cost_cents

    def test_google_gemini_cost(self):
        """Test Google Gemini cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gemini-pro",
            input_tokens=1000,
            output_tokens=500
        )
        
        # Gemini Pro: $0.0005/1K input tokens, $0.0015/1K output tokens
        # Input: 1000 tokens * 5 units/1K = 5 units
        # Output: 500 tokens * 15 units/1K = 7 units
        expected_cost_cents = 5 + 7
        assert cost_cents == expected_cost_cents

    def test_privatemode_tee_cost(self):
        """Test Privatemode.ai TEE cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="privatemode-llama-70b",
            input_tokens=1000,
            output_tokens=500
        )
        
        # Privatemode Llama 70B: $0.004/1K input tokens, $0.008/1K output tokens
        # Input: 1000 tokens * 40 units/1K = 40 units
        # Output: 500 tokens * 80 units/1K = 40 units
        expected_cost_cents = 40 + 40
        assert cost_cents == expected_cost_cents

    def test_embedding_cost(self):
        """Test embedding cost calculation."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="text-embedding-ada-002",
            input_tokens=1000,
            output_tokens=0
        )
        
        # text-embedding-ada-002: $0.0001/1K tokens
        # Input: 1000 tokens * 1 unit/1K = 1 unit
        # Output: 0 tokens * 0 units/1K = 0 units
        expected_cost_cents = 1
        assert cost_cents == expected_cost_cents

    def test_unknown_model_cost(self):
        """Test cost calculation for unknown model."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="unknown-model",
            input_tokens=1000,
            output_tokens=500
        )
        
        # Should use default pricing: $0.001/1K input, $0.002/1K output
        # Input: 1000 tokens * 10 units/1K = 10 units
        # Output: 500 tokens * 20 units/1K = 10 units
        expected_cost_cents = 10 + 10
        assert cost_cents == expected_cost_cents

    def test_zero_tokens_cost(self):
        """Test cost calculation with zero tokens."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gpt-3.5-turbo",
            input_tokens=0,
            output_tokens=0
        )
        
        assert cost_cents == 0

    def test_large_token_count_cost(self):
        """Test cost calculation with large token counts."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gpt-3.5-turbo",
            input_tokens=100000,
            output_tokens=50000
        )
        
        # GPT-3.5 Turbo: $0.0005/1K input tokens, $0.0015/1K output tokens
        # Input: 100000 tokens * 5 units/1K = 500 units
        # Output: 50000 tokens * 15 units/1K = 750 units
        expected_cost_cents = 500 + 750
        assert cost_cents == expected_cost_cents

    def test_estimate_request_cost(self):
        """Test request cost estimation."""
        cost_cents = CostCalculator.estimate_cost_cents(
            model_name="gpt-3.5-turbo",
            estimated_tokens=1000
        )
        
        # Should return a reasonable estimate
        # 1000 tokens * 70% input * 5 units/1K + 1000 tokens * 30% output * 15 units/1K
        # = 700 * 5/1000 + 300 * 15/1000 = 3 + 4 = 7 units
        expected_cost_cents = 3 + 4
        assert cost_cents == expected_cost_cents

    def test_cost_precision(self):
        """Test cost calculation precision."""
        cost_cents = CostCalculator.calculate_cost_cents(
            model_name="gpt-3.5-turbo",
            input_tokens=1,
            output_tokens=1
        )
        
        # Should maintain precision and handle small amounts
        # Input: 1 token * 5 units/1K = 0.005 units -> 0 units (integer division)
        # Output: 1 token * 15 units/1K = 0.015 units -> 0 units (integer division)
        expected_cost_cents = 0
        assert cost_cents == expected_cost_cents

    def test_model_normalization(self):
        """Test that model names are normalized correctly."""
        cost1 = CostCalculator.calculate_cost_cents(
            model_name="gpt-3.5-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        cost2 = CostCalculator.calculate_cost_cents(
            model_name="openai/gpt-3.5-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost1 == cost2

    def test_get_model_pricing(self):
        """Test getting model pricing information."""
        pricing = CostCalculator.get_model_pricing("gpt-3.5-turbo")
        
        assert "input" in pricing
        assert "output" in pricing
        assert pricing["input"] == 5  # $0.0005/1K in 1/10000ths
        assert pricing["output"] == 15  # $0.0015/1K in 1/10000ths

    def test_get_cost_per_1k_tokens(self):
        """Test getting cost per 1K tokens in dollars."""
        pricing = CostCalculator.get_cost_per_1k_tokens("gpt-3.5-turbo")
        
        assert "input" in pricing
        assert "output" in pricing
        assert "currency" in pricing
        assert pricing["input"] == 0.0005  # $0.0005/1K
        assert pricing["output"] == 0.0015  # $0.0015/1K
        assert pricing["currency"] == "USD"

    def test_format_cost_display(self):
        """Test cost formatting for display."""
        # Test zero cost
        assert CostCalculator.format_cost_display(0) == "$0.00"
        
        # Test small cost
        assert CostCalculator.format_cost_display(1) == "$0.0010"
        
        # Test larger cost
        assert CostCalculator.format_cost_display(1500) == "$1.50"