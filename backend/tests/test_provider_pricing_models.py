"""
Unit tests for Provider Pricing models.

Tests ProviderPricing and PricingAuditLog model creation,
properties, methods, and edge cases.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.models.provider_pricing import PricingAuditLog, ProviderPricing


@pytest.mark.unit
class TestProviderPricingModel:
    """Test ProviderPricing model functionality."""

    def test_create_provider_pricing_with_all_fields(self):
        """Test ProviderPricing model creation with all fields."""
        pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="meta-llama/llama-3.1-70b-instruct",
            model_name="Llama 3.1 70B Instruct",
            input_price_per_million_cents=40,
            output_price_per_million_cents=80,
            price_source="api_sync",
            source_api_response={"id": "test", "pricing": {"input": 0.40}},
            is_override=False,
            override_reason=None,
            override_by_user_id=None,
            context_length=128000,
            architecture={"type": "transformer"},
            quantization="fp16",
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert pricing.id == 1
        assert pricing.provider_id == "redpill"
        assert pricing.model_id == "meta-llama/llama-3.1-70b-instruct"
        assert pricing.model_name == "Llama 3.1 70B Instruct"
        assert pricing.input_price_per_million_cents == 40
        assert pricing.output_price_per_million_cents == 80
        assert pricing.price_source == "api_sync"
        assert pricing.context_length == 128000
        assert pricing.quantization == "fp16"
        assert pricing.is_override is False

    def test_create_provider_pricing_minimal(self):
        """Test ProviderPricing model creation with minimal required fields."""
        pricing = ProviderPricing(
            provider_id="privatemode",
            model_id="llama-70b",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="manual",
        )

        assert pricing.provider_id == "privatemode"
        assert pricing.model_id == "llama-70b"
        assert pricing.input_price_per_million_cents == 100
        assert pricing.output_price_per_million_cents == 200
        assert pricing.price_source == "manual"
        assert pricing.is_override is False  # Default

    def test_is_current_property_true_when_effective_until_none(self):
        """Test is_current property returns True when effective_until is None."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            effective_until=None,
        )

        assert pricing.is_current is True

    def test_is_current_property_false_when_effective_until_set(self):
        """Test is_current property returns False when effective_until is set."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            effective_until=datetime.now(timezone.utc),
        )

        assert pricing.is_current is False

    def test_input_price_dollars_property(self):
        """Test input_price_dollars property converts cents to dollars."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=250,
            output_price_per_million_cents=500,
            price_source="api_sync",
        )

        assert pricing.input_price_dollars == 2.50

    def test_output_price_dollars_property(self):
        """Test output_price_dollars property converts cents to dollars."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=250,
            output_price_per_million_cents=500,
            price_source="api_sync",
        )

        assert pricing.output_price_dollars == 5.00

    def test_price_dollars_properties_with_fractional_cents(self):
        """Test price dollars properties handle fractional values correctly."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=55,  # $0.55
            output_price_per_million_cents=219,  # $2.19
            price_source="api_sync",
        )

        assert pricing.input_price_dollars == 0.55
        assert pricing.output_price_dollars == 2.19

    def test_calculate_cost_cents_basic(self):
        """Test calculate_cost_cents with basic token counts."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,  # $1.00 per million
            output_price_per_million_cents=200,  # $2.00 per million
            price_source="api_sync",
        )

        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=1_000_000,
            output_tokens=500_000,
        )

        assert input_cost == 100  # 1M tokens at $1/M = $1 = 100 cents
        assert output_cost == 100  # 500K tokens at $2/M = $1 = 100 cents
        assert total_cost == 200

    def test_calculate_cost_cents_ceiling_division(self):
        """Test calculate_cost_cents uses ceiling division (never under-charges)."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
        )

        # Small token count that should round up
        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=1,  # Very small amount
            output_tokens=1,
        )

        # Due to ceiling division, even 1 token should result in at least 1 cent
        assert input_cost >= 1
        assert output_cost >= 1

    def test_calculate_cost_cents_zero_tokens(self):
        """Test calculate_cost_cents with zero tokens."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
        )

        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=0,
            output_tokens=0,
        )

        assert input_cost == 0
        assert output_cost == 0
        assert total_cost == 0

    def test_calculate_cost_cents_large_tokens(self):
        """Test calculate_cost_cents with large token counts."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,  # $1.00 per million
            output_price_per_million_cents=200,  # $2.00 per million
            price_source="api_sync",
        )

        # 100 million input, 50 million output
        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=100_000_000,
            output_tokens=50_000_000,
        )

        assert input_cost == 10000  # 100M at $1/M = $100
        assert output_cost == 10000  # 50M at $2/M = $100
        assert total_cost == 20000

    def test_calculate_cost_cents_very_large_prices(self):
        """Test calculate_cost_cents with very large prices per million."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="expensive-model",
            input_price_per_million_cents=150000,  # $1500 per million
            output_price_per_million_cents=300000,  # $3000 per million
            price_source="api_sync",
        )

        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=10_000,
            output_tokens=5_000,
        )

        # 10K tokens at $1500/M = $15 = 1500 cents
        # 5K tokens at $3000/M = $15 = 1500 cents
        assert input_cost == 1500
        assert output_cost == 1500
        assert total_cost == 3000

    def test_expire_method(self):
        """Test expire method marks pricing as no longer current."""
        pricing = ProviderPricing(
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
            effective_until=None,
        )

        assert pricing.is_current is True

        before_expire = datetime.now(timezone.utc)
        pricing.expire()

        assert pricing.is_current is False
        assert pricing.effective_until is not None
        assert pricing.effective_until >= before_expire

    def test_create_from_api_sync_factory_method(self):
        """Test create_from_api_sync class method."""
        api_response = {
            "id": "phala/deepseek-r1-0528",
            "pricing": {"input": 0.55, "output": 2.19},
        }

        pricing = ProviderPricing.create_from_api_sync(
            provider_id="redpill",
            model_id="phala/deepseek-r1-0528",
            input_price_cents=55,
            output_price_cents=219,
            model_name="DeepSeek R1",
            api_response=api_response,
            context_length=128000,
            architecture={"type": "moe"},
            quantization="fp16",
        )

        assert pricing.provider_id == "redpill"
        assert pricing.model_id == "phala/deepseek-r1-0528"
        assert pricing.model_name == "DeepSeek R1"
        assert pricing.input_price_per_million_cents == 55
        assert pricing.output_price_per_million_cents == 219
        assert pricing.price_source == "api_sync"
        assert pricing.source_api_response == api_response
        assert pricing.is_override is False
        assert pricing.context_length == 128000
        assert pricing.quantization == "fp16"
        assert pricing.effective_from is not None

    def test_create_manual_factory_method(self):
        """Test create_manual class method for manual overrides."""
        pricing = ProviderPricing.create_manual(
            provider_id="privatemode",
            model_id="meta-llama/llama-3.1-70b-instruct",
            input_price_cents=40,
            output_price_cents=40,
            reason="Initial PrivateMode pricing",
            user_id=123,
            model_name="Llama 3.1 70B",
        )

        assert pricing.provider_id == "privatemode"
        assert pricing.model_id == "meta-llama/llama-3.1-70b-instruct"
        assert pricing.model_name == "Llama 3.1 70B"
        assert pricing.input_price_per_million_cents == 40
        assert pricing.output_price_per_million_cents == 40
        assert pricing.price_source == "manual"
        assert pricing.is_override is True
        assert pricing.override_reason == "Initial PrivateMode pricing"
        assert pricing.override_by_user_id == 123
        assert pricing.effective_from is not None

    def test_to_dict_method(self):
        """Test to_dict method converts model to dictionary correctly."""
        now = datetime.now(timezone.utc)
        pricing = ProviderPricing(
            id=42,
            provider_id="redpill",
            model_id="test-model",
            model_name="Test Model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            is_override=False,
            override_reason=None,
            override_by_user_id=None,
            context_length=32000,
            architecture={"type": "transformer"},
            quantization="int8",
            effective_from=now,
            effective_until=None,
            created_at=now,
            updated_at=now,
        )

        result = pricing.to_dict()

        assert result["id"] == 42
        assert result["provider_id"] == "redpill"
        assert result["model_id"] == "test-model"
        assert result["model_name"] == "Test Model"
        assert result["input_price_per_million_cents"] == 100
        assert result["output_price_per_million_cents"] == 200
        assert result["input_price_per_million_dollars"] == 1.0
        assert result["output_price_per_million_dollars"] == 2.0
        assert result["price_source"] == "api_sync"
        assert result["is_override"] is False
        assert result["override_reason"] is None
        assert result["context_length"] == 32000
        assert result["architecture"] == {"type": "transformer"}
        assert result["quantization"] == "int8"
        assert result["is_current"] is True
        assert result["effective_until"] is None

    def test_repr_method(self):
        """Test __repr__ method returns useful string representation."""
        pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
        )

        repr_str = repr(pricing)

        assert "ProviderPricing" in repr_str
        assert "redpill" in repr_str
        assert "test-model" in repr_str
        assert "100" in repr_str
        assert "200" in repr_str

    def test_zero_pricing(self):
        """Test model handles zero pricing correctly."""
        pricing = ProviderPricing(
            provider_id="test",
            model_id="free-model",
            input_price_per_million_cents=0,
            output_price_per_million_cents=0,
            price_source="manual",
        )

        assert pricing.input_price_dollars == 0.0
        assert pricing.output_price_dollars == 0.0

        input_cost, output_cost, total_cost = pricing.calculate_cost_cents(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        assert input_cost == 0
        assert output_cost == 0
        assert total_cost == 0


@pytest.mark.unit
class TestPricingAuditLogModel:
    """Test PricingAuditLog model functionality."""

    def test_create_pricing_audit_log_all_fields(self):
        """Test PricingAuditLog creation with all fields."""
        sync_job_id = uuid4()
        now = datetime.now(timezone.utc)

        audit = PricingAuditLog(
            id=1,
            provider_id="redpill",
            model_id="test-model",
            action="create",
            old_input_price_per_million_cents=None,
            old_output_price_per_million_cents=None,
            new_input_price_per_million_cents=100,
            new_output_price_per_million_cents=200,
            change_source="api_sync",
            changed_by_user_id=None,
            change_reason=None,
            sync_job_id=sync_job_id,
            api_response_snapshot={"id": "test"},
            created_at=now,
        )

        assert audit.id == 1
        assert audit.provider_id == "redpill"
        assert audit.model_id == "test-model"
        assert audit.action == "create"
        assert audit.old_input_price_per_million_cents is None
        assert audit.new_input_price_per_million_cents == 100
        assert audit.new_output_price_per_million_cents == 200
        assert audit.change_source == "api_sync"
        assert audit.sync_job_id == sync_job_id

    def test_create_for_sync_factory_method(self):
        """Test create_for_sync class method."""
        sync_job_id = uuid4()
        api_response = {"id": "model-id", "pricing": {"input": 0.1}}

        audit = PricingAuditLog.create_for_sync(
            provider_id="redpill",
            model_id="test-model",
            action="create",
            new_input_price=100,
            new_output_price=200,
            sync_job_id=sync_job_id,
            api_response=api_response,
        )

        assert audit.provider_id == "redpill"
        assert audit.model_id == "test-model"
        assert audit.action == "create"
        assert audit.old_input_price_per_million_cents is None
        assert audit.old_output_price_per_million_cents is None
        assert audit.new_input_price_per_million_cents == 100
        assert audit.new_output_price_per_million_cents == 200
        assert audit.change_source == "api_sync"
        assert audit.sync_job_id == sync_job_id
        assert audit.api_response_snapshot == api_response
        assert audit.changed_by_user_id is None

    def test_create_for_sync_with_old_prices(self):
        """Test create_for_sync with old prices for update action."""
        sync_job_id = uuid4()

        audit = PricingAuditLog.create_for_sync(
            provider_id="redpill",
            model_id="test-model",
            action="update",
            new_input_price=150,
            new_output_price=300,
            old_input_price=100,
            old_output_price=200,
            sync_job_id=sync_job_id,
        )

        assert audit.action == "update"
        assert audit.old_input_price_per_million_cents == 100
        assert audit.old_output_price_per_million_cents == 200
        assert audit.new_input_price_per_million_cents == 150
        assert audit.new_output_price_per_million_cents == 300

    def test_create_for_manual_change_factory_method(self):
        """Test create_for_manual_change class method."""
        audit = PricingAuditLog.create_for_manual_change(
            provider_id="privatemode",
            model_id="llama-70b",
            action="override",
            new_input_price=40,
            new_output_price=40,
            user_id=123,
            reason="Setting PrivateMode pricing",
            old_input_price=100,
            old_output_price=200,
        )

        assert audit.provider_id == "privatemode"
        assert audit.model_id == "llama-70b"
        assert audit.action == "override"
        assert audit.old_input_price_per_million_cents == 100
        assert audit.old_output_price_per_million_cents == 200
        assert audit.new_input_price_per_million_cents == 40
        assert audit.new_output_price_per_million_cents == 40
        assert audit.change_source == "admin_manual"
        assert audit.changed_by_user_id == 123
        assert audit.change_reason == "Setting PrivateMode pricing"
        assert audit.sync_job_id is None

    def test_to_dict_method(self):
        """Test to_dict method for audit log."""
        sync_job_id = uuid4()
        now = datetime.now(timezone.utc)

        audit = PricingAuditLog(
            id=42,
            provider_id="redpill",
            model_id="test-model",
            action="update",
            old_input_price_per_million_cents=100,
            old_output_price_per_million_cents=200,
            new_input_price_per_million_cents=150,
            new_output_price_per_million_cents=300,
            change_source="api_sync",
            changed_by_user_id=None,
            change_reason=None,
            sync_job_id=sync_job_id,
            created_at=now,
        )

        result = audit.to_dict()

        assert result["id"] == 42
        assert result["provider_id"] == "redpill"
        assert result["model_id"] == "test-model"
        assert result["action"] == "update"
        assert result["old_input_price_per_million_cents"] == 100
        assert result["old_output_price_per_million_cents"] == 200
        assert result["new_input_price_per_million_cents"] == 150
        assert result["new_output_price_per_million_cents"] == 300
        assert result["change_source"] == "api_sync"
        assert result["sync_job_id"] == str(sync_job_id)
        assert result["created_at"] == now.isoformat()

    def test_to_dict_with_no_sync_job_id(self):
        """Test to_dict handles None sync_job_id correctly."""
        audit = PricingAuditLog(
            id=1,
            provider_id="privatemode",
            model_id="test",
            action="override",
            new_input_price_per_million_cents=100,
            new_output_price_per_million_cents=200,
            change_source="admin_manual",
            changed_by_user_id=1,
            sync_job_id=None,
            created_at=datetime.now(timezone.utc),
        )

        result = audit.to_dict()

        assert result["sync_job_id"] is None

    def test_repr_method(self):
        """Test __repr__ method returns useful string representation."""
        audit = PricingAuditLog(
            id=1,
            provider_id="redpill",
            model_id="test-model",
            action="create",
            new_input_price_per_million_cents=100,
            new_output_price_per_million_cents=200,
            change_source="api_sync",
        )

        repr_str = repr(audit)

        assert "PricingAuditLog" in repr_str
        assert "create" in repr_str
        assert "redpill" in repr_str
        assert "test-model" in repr_str

    def test_action_types(self):
        """Test various action types are handled correctly."""
        action_types = ["create", "update", "sync", "override", "remove_override"]

        for action in action_types:
            audit = PricingAuditLog(
                provider_id="test",
                model_id="test-model",
                action=action,
                new_input_price_per_million_cents=100,
                new_output_price_per_million_cents=200,
                change_source=(
                    "api_sync"
                    if action in ["create", "update", "sync"]
                    else "admin_manual"
                ),
            )

            assert audit.action == action

    def test_price_change_tracking(self):
        """Test audit log correctly tracks price changes."""
        # Price increase scenario
        audit_increase = PricingAuditLog.create_for_sync(
            provider_id="redpill",
            model_id="test",
            action="update",
            old_input_price=100,
            old_output_price=200,
            new_input_price=150,  # 50% increase
            new_output_price=300,  # 50% increase
        )

        assert audit_increase.old_input_price_per_million_cents == 100
        assert audit_increase.new_input_price_per_million_cents == 150

        # Price decrease scenario
        audit_decrease = PricingAuditLog.create_for_sync(
            provider_id="redpill",
            model_id="test",
            action="update",
            old_input_price=200,
            old_output_price=400,
            new_input_price=100,  # 50% decrease
            new_output_price=200,  # 50% decrease
        )

        assert audit_decrease.old_input_price_per_million_cents == 200
        assert audit_decrease.new_input_price_per_million_cents == 100
