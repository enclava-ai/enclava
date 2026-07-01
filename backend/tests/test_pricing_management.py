"""
Unit tests for Pricing Management Service and Pydantic Schemas.

Tests PricingManagementService functionality including manual pricing,
override management, querying, and search operations.
Also tests Pydantic schema validation.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pydantic import ValidationError

from app.models.provider_pricing import PricingAuditLog, ProviderPricing
from app.schemas.pricing import (
    BulkPricingRequest,
    PricingAuditLogResponse,
    PricingHistoryResponse,
    PricingResponse,
    PricingSummary,
    RemoveOverrideResponse,
    SetPricingRequest,
    SyncResultResponse,
)
from app.services.pricing_management import PricingManagementService


@pytest.mark.unit
class TestSetPricingRequestSchema:
    """Test SetPricingRequest Pydantic schema validation."""

    def test_valid_pricing_request(self):
        """Test valid pricing request creation."""
        request = SetPricingRequest(
            provider_id="privatemode",
            model_id="meta-llama/llama-3.1-70b-instruct",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            reason="Initial pricing for PrivateMode",
            model_name="Llama 3.1 70B",
        )

        assert request.provider_id == "privatemode"
        assert request.model_id == "meta-llama/llama-3.1-70b-instruct"
        assert request.input_price_per_million_cents == 40
        assert request.output_price_per_million_cents == 40
        assert request.reason == "Initial pricing for PrivateMode"
        assert request.model_name == "Llama 3.1 70B"

    def test_provider_id_normalized_to_lowercase(self):
        """Test provider_id is normalized to lowercase."""
        request = SetPricingRequest(
            provider_id="PrivateMode",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            reason="Test",
        )

        assert request.provider_id == "privatemode"

    def test_provider_id_allows_hyphens_and_underscores(self):
        """Test provider_id allows hyphens and underscores."""
        request1 = SetPricingRequest(
            provider_id="private-mode",
            model_id="test",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            reason="Test",
        )
        assert request1.provider_id == "private-mode"

        request2 = SetPricingRequest(
            provider_id="private_mode",
            model_id="test",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            reason="Test",
        )
        assert request2.provider_id == "private_mode"

    def test_provider_id_rejects_special_chars(self):
        """Test provider_id rejects special characters."""
        with pytest.raises(ValidationError) as exc_info:
            SetPricingRequest(
                provider_id="provider@invalid",
                model_id="test",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                reason="Test",
            )

        assert "alphanumeric" in str(exc_info.value).lower()

    def test_provider_id_min_length(self):
        """Test provider_id minimum length validation."""
        with pytest.raises(ValidationError):
            SetPricingRequest(
                provider_id="",
                model_id="test",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                reason="Test",
            )

    def test_model_id_min_length(self):
        """Test model_id minimum length validation."""
        with pytest.raises(ValidationError):
            SetPricingRequest(
                provider_id="test",
                model_id="",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                reason="Test",
            )

    def test_input_price_negative_rejected(self):
        """Test negative input price is rejected."""
        with pytest.raises(ValidationError):
            SetPricingRequest(
                provider_id="test",
                model_id="test-model",
                input_price_per_million_cents=-1,
                output_price_per_million_cents=100,
                reason="Test",
            )

    def test_output_price_negative_rejected(self):
        """Test negative output price is rejected."""
        with pytest.raises(ValidationError):
            SetPricingRequest(
                provider_id="test",
                model_id="test-model",
                input_price_per_million_cents=100,
                output_price_per_million_cents=-1,
                reason="Test",
            )

    def test_zero_prices_allowed(self):
        """Test zero prices are allowed (free models)."""
        request = SetPricingRequest(
            provider_id="test",
            model_id="free-model",
            input_price_per_million_cents=0,
            output_price_per_million_cents=0,
            reason="Free model",
        )

        assert request.input_price_per_million_cents == 0
        assert request.output_price_per_million_cents == 0

    def test_reason_required(self):
        """Test reason field is required."""
        with pytest.raises(ValidationError):
            SetPricingRequest(
                provider_id="test",
                model_id="test-model",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                reason="",  # Empty string should fail min_length
            )

    def test_model_name_optional(self):
        """Test model_name is optional."""
        request = SetPricingRequest(
            provider_id="test",
            model_id="test-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            reason="Test",
        )

        assert request.model_name is None

    def test_large_price_values(self):
        """Test very large price values are accepted."""
        request = SetPricingRequest(
            provider_id="test",
            model_id="expensive-model",
            input_price_per_million_cents=1000000,  # $10,000 per million
            output_price_per_million_cents=5000000,  # $50,000 per million
            reason="Very expensive model",
        )

        assert request.input_price_per_million_cents == 1000000
        assert request.output_price_per_million_cents == 5000000


@pytest.mark.unit
class TestPricingResponseSchema:
    """Test PricingResponse Pydantic schema."""

    def test_pricing_response_serialization(self):
        """Test PricingResponse can be created from dict."""
        now = datetime.now(timezone.utc)
        response = PricingResponse(
            id=1,
            provider_id="redpill",
            model_id="test-model",
            model_name="Test Model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            input_price_per_million_dollars=1.0,
            output_price_per_million_dollars=2.0,
            price_source="api_sync",
            is_override=False,
            override_reason=None,
            override_by_user_id=None,
            context_length=32000,
            architecture={"type": "transformer"},
            quantization="fp16",
            effective_from=now,
            effective_until=None,
            is_current=True,
            created_at=now,
            updated_at=now,
        )

        assert response.id == 1
        assert response.provider_id == "redpill"
        assert response.input_price_per_million_dollars == 1.0
        assert response.is_current is True

    def test_pricing_response_handles_optional_fields(self):
        """Test PricingResponse handles optional fields correctly."""
        now = datetime.now(timezone.utc)
        response = PricingResponse(
            id=1,
            provider_id="test",
            model_id="test",
            model_name=None,  # Optional
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            input_price_per_million_dollars=1.0,
            output_price_per_million_dollars=2.0,
            price_source="manual",
            is_override=False,
            override_reason=None,
            override_by_user_id=None,
            context_length=None,
            architecture=None,
            quantization=None,
            effective_from=now,
            effective_until=None,
            is_current=True,
            created_at=now,
            updated_at=now,
        )

        assert response.model_name is None
        assert response.context_length is None
        assert response.architecture is None
        assert response.quantization is None


@pytest.mark.unit
class TestBulkPricingRequestSchema:
    """Test BulkPricingRequest Pydantic schema."""

    def test_bulk_request_with_multiple_updates(self):
        """Test bulk request with multiple pricing updates."""
        request = BulkPricingRequest(
            pricing_updates=[
                SetPricingRequest(
                    provider_id="test",
                    model_id="model-1",
                    input_price_per_million_cents=100,
                    output_price_per_million_cents=200,
                    reason="Update 1",
                ),
                SetPricingRequest(
                    provider_id="test",
                    model_id="model-2",
                    input_price_per_million_cents=150,
                    output_price_per_million_cents=300,
                    reason="Update 2",
                ),
            ]
        )

        assert len(request.pricing_updates) == 2

    def test_bulk_request_max_limit(self):
        """Test bulk request rejects more than 100 updates."""
        with pytest.raises(ValidationError) as exc_info:
            BulkPricingRequest(
                pricing_updates=[
                    SetPricingRequest(
                        provider_id="test",
                        model_id=f"model-{i}",
                        input_price_per_million_cents=100,
                        output_price_per_million_cents=200,
                        reason="Test",
                    )
                    for i in range(101)
                ]
            )

        assert "100" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
class TestPricingManagementService:
    """Test PricingManagementService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance with mock db."""
        return PricingManagementService(mock_db)

    async def test_set_manual_pricing_new_model(self, service, mock_db):
        """Test set_manual_pricing creates new pricing for new model."""
        # Mock no existing pricing
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.set_manual_pricing(
            provider_id="privatemode",
            model_id="new-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            reason="Initial pricing",
            user_id=123,
            model_name="New Model",
        )

        # Verify add was called for pricing and audit log
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    async def test_set_manual_pricing_updates_existing(self, service, mock_db):
        """Test set_manual_pricing expires existing and creates new."""
        # Create existing pricing
        existing = ProviderPricing(
            id=1,
            provider_id="privatemode",
            model_id="existing-model",
            model_name="Existing Model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            is_override=False,
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        await service.set_manual_pricing(
            provider_id="privatemode",
            model_id="existing-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            reason="Override pricing",
            user_id=123,
        )

        # Verify existing pricing was expired
        assert existing.effective_until is not None

    async def test_set_manual_pricing_creates_audit_log(self, service, mock_db):
        """Test set_manual_pricing creates audit log entry."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        await service.set_manual_pricing(
            provider_id="privatemode",
            model_id="test-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            reason="Test reason",
            user_id=123,
        )

        # Find the audit log in add calls
        calls = mock_db.add.call_args_list
        audit_log = None
        for call in calls:
            obj = call[0][0]
            if isinstance(obj, PricingAuditLog):
                audit_log = obj
                break

        assert audit_log is not None
        assert audit_log.change_source == "admin_manual"
        assert audit_log.changed_by_user_id == 123
        assert audit_log.change_reason == "Test reason"

    async def test_set_manual_pricing_inherits_model_name(self, service, mock_db):
        """Test set_manual_pricing inherits model_name from existing."""
        existing = ProviderPricing(
            id=1,
            provider_id="privatemode",
            model_id="test-model",
            model_name="Inherited Name",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            is_override=False,
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        await service.set_manual_pricing(
            provider_id="privatemode",
            model_id="test-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            reason="Override",
            user_id=123,
            # No model_name provided - should inherit
        )

        # Find the new pricing in add calls
        calls = mock_db.add.call_args_list
        new_pricing = None
        for call in calls:
            obj = call[0][0]
            if isinstance(obj, ProviderPricing):
                new_pricing = obj
                break

        assert new_pricing is not None
        assert new_pricing.model_name == "Inherited Name"

    async def test_remove_override_success(self, service, mock_db):
        """Test remove_override successfully removes override."""
        existing = ProviderPricing(
            id=1,
            provider_id="privatemode",
            model_id="override-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            price_source="manual",
            is_override=True,
            override_reason="Manual pricing",
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.remove_override(
            provider_id="privatemode",
            model_id="override-model",
            user_id=123,
        )

        assert result is True
        assert existing.effective_until is not None
        mock_db.commit.assert_called_once()

    async def test_remove_override_returns_false_when_not_override(
        self, service, mock_db
    ):
        """Test remove_override returns False for non-override pricing."""
        existing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="normal-model",
            input_price_per_million_cents=100,
            output_price_per_million_cents=200,
            price_source="api_sync",
            is_override=False,  # Not an override
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.remove_override(
            provider_id="redpill",
            model_id="normal-model",
            user_id=123,
        )

        assert result is False
        # Should not expire non-override pricing
        assert existing.effective_until is None

    async def test_remove_override_returns_false_when_no_pricing(
        self, service, mock_db
    ):
        """Test remove_override returns False when no pricing exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.remove_override(
            provider_id="unknown",
            model_id="unknown-model",
            user_id=123,
        )

        assert result is False

    async def test_get_current_pricing_all_providers(self, service, mock_db):
        """Test get_current_pricing returns all current pricing."""
        pricing_list = [
            ProviderPricing(
                id=1,
                provider_id="redpill",
                model_id="model-1",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                price_source="api_sync",
                effective_until=None,
            ),
            ProviderPricing(
                id=2,
                provider_id="privatemode",
                model_id="model-2",
                input_price_per_million_cents=40,
                output_price_per_million_cents=40,
                price_source="manual",
                effective_until=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = pricing_list
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_current_pricing()

        assert len(result) == 2

    async def test_get_current_pricing_filtered_by_provider(self, service, mock_db):
        """Test get_current_pricing filters by provider."""
        pricing_list = [
            ProviderPricing(
                id=1,
                provider_id="redpill",
                model_id="model-1",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                price_source="api_sync",
                effective_until=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = pricing_list
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_current_pricing(provider_id="redpill")

        assert len(result) == 1
        assert result[0].provider_id == "redpill"

    async def test_get_pricing_history(self, service, mock_db):
        """Test get_pricing_history returns all versions."""
        now = datetime.now(timezone.utc)
        history = [
            ProviderPricing(
                id=3,
                provider_id="redpill",
                model_id="test-model",
                input_price_per_million_cents=150,
                output_price_per_million_cents=300,
                price_source="api_sync",
                effective_from=now,
                effective_until=None,
            ),
            ProviderPricing(
                id=2,
                provider_id="redpill",
                model_id="test-model",
                input_price_per_million_cents=120,
                output_price_per_million_cents=240,
                price_source="api_sync",
                effective_from=now - timedelta(days=30),
                effective_until=now,
            ),
            ProviderPricing(
                id=1,
                provider_id="redpill",
                model_id="test-model",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                price_source="api_sync",
                effective_from=now - timedelta(days=60),
                effective_until=now - timedelta(days=30),
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_pricing_history(
            provider_id="redpill",
            model_id="test-model",
        )

        assert len(result) == 3
        # Most recent first
        assert result[0].id == 3
        assert result[0].effective_until is None  # Current

    async def test_search_models_partial_match(self, service, mock_db):
        """Test search_models works with partial matches."""
        matching = [
            ProviderPricing(
                id=1,
                provider_id="redpill",
                model_id="meta-llama/llama-3.1-70b-instruct",
                model_name="Llama 3.1 70B Instruct",
                input_price_per_million_cents=100,
                output_price_per_million_cents=200,
                price_source="api_sync",
                effective_until=None,
            ),
            ProviderPricing(
                id=2,
                provider_id="redpill",
                model_id="meta-llama/llama-3.1-8b-instruct",
                model_name="Llama 3.1 8B Instruct",
                input_price_per_million_cents=50,
                output_price_per_million_cents=100,
                price_source="api_sync",
                effective_until=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.search_models(query="llama")

        assert len(result) == 2

    async def test_search_models_by_model_name(self, service, mock_db):
        """Test search_models searches model_name field."""
        matching = [
            ProviderPricing(
                id=1,
                provider_id="redpill",
                model_id="phala/deepseek-r1-0528",
                model_name="DeepSeek R1",
                input_price_per_million_cents=55,
                output_price_per_million_cents=219,
                price_source="api_sync",
                effective_until=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.search_models(query="deepseek")

        assert len(result) == 1
        assert "deepseek" in result[0].model_name.lower()

    async def test_search_models_with_provider_filter(self, service, mock_db):
        """Test search_models filters by provider."""
        matching = [
            ProviderPricing(
                id=1,
                provider_id="privatemode",
                model_id="llama-70b",
                model_name="Llama 70B",
                input_price_per_million_cents=40,
                output_price_per_million_cents=40,
                price_source="manual",
                effective_until=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.search_models(
            query="llama",
            provider_id="privatemode",
        )

        assert len(result) == 1
        assert result[0].provider_id == "privatemode"

    async def test_get_pricing_summary(self, service, mock_db):
        """Test get_pricing_summary returns correct statistics."""

        # Setup mock returns for various queries
        async def mock_execute(stmt):
            result = MagicMock()
            # Determine what kind of query this is based on call order
            if "total_models" not in str(mock_execute.call_count):
                mock_execute.call_count = getattr(mock_execute, "call_count", 0) + 1

            call_num = getattr(mock_execute, "call_count", 1)

            if call_num == 1:  # Total count
                result.scalar.return_value = 10
            elif call_num == 2:  # By provider
                result.__iter__ = lambda self: iter(
                    [
                        MagicMock(provider_id="redpill", count=7),
                        MagicMock(provider_id="privatemode", count=3),
                    ]
                )
            elif call_num == 3:  # Override count
                result.scalar.return_value = 3
            elif call_num == 4:  # API sync count
                result.scalar.return_value = 7
            elif call_num == 5:  # Manual count
                result.scalar.return_value = 3
            elif call_num == 6:  # Last sync
                result.scalar.return_value = datetime.now(timezone.utc)

            mock_execute.call_count = call_num + 1
            return result

        mock_db.execute = mock_execute

        result = await service.get_pricing_summary()

        assert "total_models" in result
        assert "models_by_provider" in result
        assert "override_count" in result
        assert "api_sync_count" in result
        assert "manual_count" in result
        assert "last_sync_at" in result

    async def test_get_providers(self, service, mock_db):
        """Test get_providers returns unique provider list."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([("redpill",), ("privatemode",)])
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_providers()

        assert isinstance(result, list)
        assert len(result) == 2
        assert "redpill" in result
        assert "privatemode" in result

    async def test_get_audit_log(self, service, mock_db):
        """Test get_audit_log returns audit entries."""
        audit_entries = [
            PricingAuditLog(
                id=1,
                provider_id="redpill",
                model_id="test-model",
                action="create",
                new_input_price_per_million_cents=100,
                new_output_price_per_million_cents=200,
                change_source="api_sync",
                created_at=datetime.now(timezone.utc),
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = audit_entries
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_audit_log()

        assert len(result) == 1
        assert result[0].action == "create"

    async def test_get_audit_log_with_filters(self, service, mock_db):
        """Test get_audit_log filters correctly."""
        audit_entries = [
            PricingAuditLog(
                id=2,
                provider_id="privatemode",
                model_id="llama-70b",
                action="override",
                new_input_price_per_million_cents=40,
                new_output_price_per_million_cents=40,
                change_source="admin_manual",
                changed_by_user_id=123,
                created_at=datetime.now(timezone.utc),
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = audit_entries
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_audit_log(
            provider_id="privatemode",
            model_id="llama-70b",
            user_id=123,
        )

        assert len(result) == 1
        assert result[0].changed_by_user_id == 123


@pytest.mark.unit
class TestPricingAuditLogResponseSchema:
    """Test PricingAuditLogResponse schema."""

    def test_audit_log_response_serialization(self):
        """Test PricingAuditLogResponse serialization."""
        response = PricingAuditLogResponse(
            id=1,
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
            sync_job_id="123e4567-e89b-12d3-a456-426614174000",
            created_at=datetime.now(timezone.utc),
        )

        assert response.action == "update"
        assert response.old_input_price_per_million_cents == 100
        assert response.new_input_price_per_million_cents == 150


@pytest.mark.unit
class TestSyncResultResponseSchema:
    """Test SyncResultResponse schema."""

    def test_sync_result_response(self):
        """Test SyncResultResponse serialization."""
        from app.schemas.pricing import SyncResultModel as SchemaSyncResultModel

        response = SyncResultResponse(
            provider_id="redpill",
            sync_job_id="123e4567-e89b-12d3-a456-426614174000",
            started_at=datetime(2025, 1, 15, 10, 0, 0),
            completed_at=datetime(2025, 1, 15, 10, 0, 5),
            duration_ms=5000,
            total_models=10,
            created_count=2,
            updated_count=1,
            unchanged_count=7,
            error_count=0,
            models=[
                SchemaSyncResultModel(
                    model_id="test-model",
                    model_name="Test Model",
                    action="created",
                    old_input_price=None,
                    old_output_price=None,
                    new_input_price=100,
                    new_output_price=200,
                )
            ],
            errors=[],
        )

        assert response.provider_id == "redpill"
        assert response.total_models == 10
        assert len(response.models) == 1


@pytest.mark.unit
class TestPricingSummarySchema:
    """Test PricingSummary schema."""

    def test_pricing_summary_serialization(self):
        """Test PricingSummary serialization."""
        summary = PricingSummary(
            total_models=50,
            models_by_provider={"redpill": 45, "privatemode": 5},
            override_count=5,
            api_sync_count=45,
            manual_count=5,
            last_sync_at=datetime.now(timezone.utc),
        )

        assert summary.total_models == 50
        assert summary.models_by_provider["redpill"] == 45
        assert summary.override_count == 5

    def test_pricing_summary_last_sync_optional(self):
        """Test PricingSummary allows None for last_sync_at."""
        summary = PricingSummary(
            total_models=0,
            models_by_provider={},
            override_count=0,
            api_sync_count=0,
            manual_count=0,
            last_sync_at=None,
        )

        assert summary.last_sync_at is None
