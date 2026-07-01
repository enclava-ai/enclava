"""
Test pricing service for LLM model pricing management.

Tests cover:
- Static pricing lookup for known models
- Prefix-based pricing fallback
- Default pricing for unknown models
- Model name normalization
- Cost calculation with ceiling division
- Small token counts producing non-zero costs
"""

from datetime import datetime, timezone

import pytest

from app.services.pricing import (
    DEFAULT_PRICING,
    STATIC_PRICING,
    ModelPricing,
    PricingService,
    calculate_cost_cents_simple,
)


class TestPricingService:
    """Test PricingService functionality."""

    @pytest.fixture
    def pricing_service(self):
        """Create a PricingService instance."""
        return PricingService()

    # --- Static Pricing Lookup Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_known_model(self, pricing_service):
        """Test pricing lookup for a known model returns correct pricing."""
        pricing = await pricing_service.get_pricing(
            provider_id="privatemode", model_id="meta-llama/llama-3.1-70b-instruct"
        )

        assert pricing.provider_id == "privatemode"
        assert pricing.model_id == "meta-llama/llama-3.1-70b-instruct"
        assert pricing.input_price_per_million_cents == 40
        assert pricing.output_price_per_million_cents == 40
        assert pricing.price_source == "manual"
        assert isinstance(pricing.effective_from, datetime)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_privatemode_llama_8b(self, pricing_service):
        """Test pricing for smaller Llama model."""
        pricing = await pricing_service.get_pricing(
            provider_id="privatemode", model_id="meta-llama/llama-3.1-8b-instruct"
        )

        assert pricing.input_price_per_million_cents == 10
        assert pricing.output_price_per_million_cents == 10

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_redpill_provider(self, pricing_service):
        """Test pricing lookup for redpill provider."""
        pricing = await pricing_service.get_pricing(
            provider_id="redpill", model_id="phala/deepseek-chat-v3-0324"
        )

        assert pricing.provider_id == "redpill"
        assert pricing.input_price_per_million_cents == 14
        assert pricing.output_price_per_million_cents == 28

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_openai_provider(self, pricing_service):
        """Test pricing lookup for OpenAI models."""
        pricing = await pricing_service.get_pricing(
            provider_id="openai", model_id="gpt-4o"
        )

        assert pricing.input_price_per_million_cents == 250
        assert pricing.output_price_per_million_cents == 1000

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_anthropic_provider(self, pricing_service):
        """Test pricing lookup for Anthropic models."""
        pricing = await pricing_service.get_pricing(
            provider_id="anthropic", model_id="claude-3.5-sonnet"
        )

        assert pricing.input_price_per_million_cents == 300
        assert pricing.output_price_per_million_cents == 1500

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_static_pricing_lookup_embedding_model(self, pricing_service):
        """Test pricing lookup for embedding models (output is 0)."""
        pricing = await pricing_service.get_pricing(
            provider_id="privatemode", model_id="baai/bge-large-en-v1.5"
        )

        assert pricing.input_price_per_million_cents == 2
        assert (
            pricing.output_price_per_million_cents == 0
        )  # Embeddings have no output cost

    # --- Fuzzy Matching / Prefix-based Pricing Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fuzzy_matching_partial_model_name(self, pricing_service):
        """Test fuzzy matching when model name partially matches known model."""
        # Using a model name that contains a known model substring
        pricing = await pricing_service.get_pricing(
            provider_id="privatemode",
            model_id="llama-3.1-70b-instruct-latest",  # Contains "llama-3.1-70b-instruct"
        )

        # Should fuzzy match to meta-llama/llama-3.1-70b-instruct
        assert pricing.input_price_per_million_cents == 40
        assert pricing.output_price_per_million_cents == 40
        assert pricing.price_source == "manual"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_provider_case_insensitive(self, pricing_service):
        """Test that provider lookup is case-insensitive."""
        pricing = await pricing_service.get_pricing(
            provider_id="PRIVATEMODE",  # Uppercase
            model_id="meta-llama/llama-3.1-70b-instruct",
        )

        assert pricing.input_price_per_million_cents == 40

    # --- Default Pricing Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_default_pricing_unknown_model(self, pricing_service):
        """Test that unknown models get default pricing."""
        pricing = await pricing_service.get_pricing(
            provider_id="privatemode", model_id="unknown-model-xyz-123"
        )

        assert pricing.input_price_per_million_cents == DEFAULT_PRICING["input"]
        assert pricing.output_price_per_million_cents == DEFAULT_PRICING["output"]
        assert pricing.price_source == "default"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_default_pricing_unknown_provider(self, pricing_service):
        """Test that unknown providers get default pricing."""
        pricing = await pricing_service.get_pricing(
            provider_id="unknown-provider", model_id="some-model"
        )

        assert pricing.input_price_per_million_cents == DEFAULT_PRICING["input"]
        assert pricing.output_price_per_million_cents == DEFAULT_PRICING["output"]
        assert pricing.price_source == "default"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_default_pricing_values(self, pricing_service):
        """Test that default pricing values are conservative."""
        # Default should be reasonably high to avoid under-charging
        assert DEFAULT_PRICING["input"] == 100  # $1 per 1M
        assert DEFAULT_PRICING["output"] == 200  # $2 per 1M

    # --- Model Name Normalization Tests ---

    @pytest.mark.unit
    def test_normalize_model_lowercase(self, pricing_service):
        """Test that model names are lowercased."""
        normalized = pricing_service.normalize_model("GPT-4-TURBO")
        assert normalized == normalized.lower()

    @pytest.mark.unit
    def test_normalize_model_strips_whitespace(self, pricing_service):
        """Test that model names have whitespace stripped."""
        normalized = pricing_service.normalize_model("  gpt-4-turbo  ")
        assert normalized == "gpt-4-turbo"

    @pytest.mark.unit
    def test_normalize_model_removes_date_suffix(self, pricing_service):
        """Test that date suffixes like -20240229 are removed."""
        normalized = pricing_service.normalize_model("gpt-4-20240229")
        assert normalized == "gpt-4"

    @pytest.mark.unit
    def test_normalize_model_removes_version_suffix(self, pricing_service):
        """Test that version suffixes like -v1.0 are removed."""
        normalized = pricing_service.normalize_model("model-v1.0")
        assert normalized == "model"

        normalized2 = pricing_service.normalize_model("model-v2.1.3")
        assert normalized2 == "model"

    @pytest.mark.unit
    def test_normalize_model_removes_provider_prefix(self, pricing_service):
        """Test that provider prefixes are removed."""
        assert pricing_service.normalize_model("openai/gpt-4") == "gpt-4"
        assert pricing_service.normalize_model("anthropic/claude-3") == "claude-3"
        assert pricing_service.normalize_model("google/gemini-pro") == "gemini-pro"
        assert pricing_service.normalize_model("phala/deepseek-chat") == "deepseek-chat"

    # --- Cost Calculation Tests ---

    @pytest.mark.unit
    def test_calculate_cost_cents_basic(self, pricing_service):
        """Test basic cost calculation."""
        pricing = ModelPricing(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=100,  # $1 per 1M
            output_price_per_million_cents=200,  # $2 per 1M
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=1_000_000, output_tokens=1_000_000, pricing=pricing
        )

        assert input_cost == 100  # $1
        assert output_cost == 200  # $2
        assert total_cost == 300  # $3

    @pytest.mark.unit
    def test_calculate_cost_cents_ceiling_division(self, pricing_service):
        """Test that ceiling division is used (rounds up, never under-charge)."""
        pricing = ModelPricing(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=1,  # 1 cent per 1M
            output_price_per_million_cents=1,  # 1 cent per 1M
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        # With 1 token at 1 cent per million, floor would give 0
        # Ceiling should give 1
        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=1, output_tokens=1, pricing=pricing
        )

        # Ceiling division should round up
        assert input_cost == 1
        assert output_cost == 1
        assert total_cost == 2

    @pytest.mark.unit
    def test_calculate_cost_cents_small_token_count(self, pricing_service):
        """Test that small token counts still produce non-zero costs."""
        pricing = ModelPricing(
            provider_id="privatemode",
            model_id="test-model",
            input_price_per_million_cents=40,  # 40 cents per 1M
            output_price_per_million_cents=40,  # 40 cents per 1M
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        # 10 tokens should still produce cost due to ceiling division
        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=10, output_tokens=10, pricing=pricing
        )

        # With ceiling division, even small amounts should be at least 1
        assert input_cost >= 1
        assert output_cost >= 1
        assert total_cost >= 2

    @pytest.mark.unit
    def test_calculate_cost_cents_zero_tokens(self, pricing_service):
        """Test cost calculation with zero tokens."""
        pricing = ModelPricing(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=0, output_tokens=0, pricing=pricing
        )

        # Zero tokens should result in zero cost
        # (0 + 999_999) // 1_000_000 = 0
        assert input_cost == 0
        assert output_cost == 0
        assert total_cost == 0

    @pytest.mark.unit
    def test_calculate_cost_cents_large_token_count(self, pricing_service):
        """Test cost calculation with large token counts."""
        pricing = ModelPricing(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=300,  # Claude pricing
            output_price_per_million_cents=1500,
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        # 10M tokens should be straightforward
        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=10_000_000, output_tokens=5_000_000, pricing=pricing
        )

        # 10M * 300 / 1M = 3000 cents ($30)
        assert input_cost == 3000
        # 5M * 1500 / 1M = 7500 cents ($75)
        assert output_cost == 7500
        assert total_cost == 10500

    @pytest.mark.unit
    def test_calculate_cost_cents_embedding_zero_output(self, pricing_service):
        """Test cost calculation for embeddings (zero output cost)."""
        pricing = ModelPricing(
            provider_id="test",
            model_id="text-embedding-3-small",
            input_price_per_million_cents=2,
            output_price_per_million_cents=0,  # Embeddings have no output
            price_source="manual",
            effective_from=datetime.now(timezone.utc),
        )

        input_cost, output_cost, total_cost = pricing_service.calculate_cost_cents(
            input_tokens=1_000_000, output_tokens=0, pricing=pricing
        )

        assert input_cost == 2
        assert output_cost == 0
        assert total_cost == 2

    # --- Convenience Function Tests ---

    @pytest.mark.unit
    def test_calculate_cost_cents_simple_known_model(self):
        """Test the simple synchronous cost calculation helper."""
        cost = calculate_cost_cents_simple(
            model_name="meta-llama/llama-3.1-70b-instruct",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            provider_id="privatemode",
        )

        # 40 cents per 1M for both input and output
        assert cost == 80

    @pytest.mark.unit
    def test_calculate_cost_cents_simple_unknown_model(self):
        """Test simple calculation falls back to default for unknown model."""
        cost = calculate_cost_cents_simple(
            model_name="unknown-model",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            provider_id="unknown-provider",
        )

        # Should use default pricing: 100 + 200 = 300
        assert cost == 300

    # --- get_all_supported_models Tests ---

    @pytest.mark.unit
    def test_get_all_supported_models_all_providers(self, pricing_service):
        """Test getting all models across all providers."""
        models = pricing_service.get_all_supported_models()

        assert "privatemode" in models
        assert "redpill" in models
        assert "openai" in models
        assert "anthropic" in models

        # Verify some models exist
        assert "meta-llama/llama-3.1-70b-instruct" in models["privatemode"]

    @pytest.mark.unit
    def test_get_all_supported_models_single_provider(self, pricing_service):
        """Test getting models for a single provider."""
        models = pricing_service.get_all_supported_models(provider_id="privatemode")

        assert len(models) == 1
        assert "privatemode" in models
        assert "meta-llama/llama-3.1-70b-instruct" in models["privatemode"]

    @pytest.mark.unit
    def test_get_all_supported_models_unknown_provider(self, pricing_service):
        """Test getting models for unknown provider returns empty list."""
        models = pricing_service.get_all_supported_models(provider_id="unknown")

        assert "unknown" in models
        assert len(models["unknown"]) == 0


class TestModelPricingDataclass:
    """Test the ModelPricing dataclass."""

    @pytest.mark.unit
    def test_model_pricing_creation(self):
        """Test creating a ModelPricing instance."""
        now = datetime.now(timezone.utc)
        pricing = ModelPricing(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            effective_from=now,
        )

        assert pricing.provider_id == "test"
        assert pricing.model_id == "test-model"
        assert pricing.input_price_per_million_cents == 100
        assert pricing.output_price_per_million_cents == 200
        assert pricing.price_source == "api_sync"
        assert pricing.effective_from == now

    @pytest.mark.unit
    def test_model_pricing_source_values(self):
        """Test that valid price sources are documented."""
        # Valid price_source values: 'api_sync', 'manual', 'default'
        valid_sources = ["api_sync", "manual", "default"]

        for source in valid_sources:
            pricing = ModelPricing(
                provider_id="test",
                model_id="test-model",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                price_source=source,
                effective_from=datetime.now(timezone.utc),
            )
            assert pricing.price_source == source


class TestStaticPricingData:
    """Test the static pricing data structure."""

    @pytest.mark.unit
    def test_static_pricing_has_required_providers(self):
        """Test that static pricing has all expected providers."""
        assert "privatemode" in STATIC_PRICING
        assert "redpill" in STATIC_PRICING
        assert "openai" in STATIC_PRICING
        assert "anthropic" in STATIC_PRICING

    @pytest.mark.unit
    def test_static_pricing_model_structure(self):
        """Test that each model has input and output pricing."""
        for provider, models in STATIC_PRICING.items():
            for model_id, pricing in models.items():
                assert "input" in pricing, f"{provider}/{model_id} missing 'input'"
                assert "output" in pricing, f"{provider}/{model_id} missing 'output'"
                assert isinstance(
                    pricing["input"], int
                ), f"{provider}/{model_id} input must be int"
                assert isinstance(
                    pricing["output"], int
                ), f"{provider}/{model_id} output must be int"

    @pytest.mark.unit
    def test_static_pricing_non_negative(self):
        """Test that all pricing values are non-negative."""
        for provider, models in STATIC_PRICING.items():
            for model_id, pricing in models.items():
                assert (
                    pricing["input"] >= 0
                ), f"{provider}/{model_id} has negative input price"
                assert (
                    pricing["output"] >= 0
                ), f"{provider}/{model_id} has negative output price"
