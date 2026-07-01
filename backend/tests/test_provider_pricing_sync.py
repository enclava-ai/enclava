"""
Unit tests for Provider Pricing Sync Service.

Tests ProviderPricingSyncService functionality including API fetching,
pricing conversion, database operations, and error handling.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.provider_pricing import PricingAuditLog, ProviderPricing
from app.services.provider_pricing_sync import (
    ProviderPricingSyncService,
    SyncResult,
    SyncResultModel,
)


@pytest.mark.unit
class TestSyncResultDataClasses:
    """Test SyncResult and SyncResultModel dataclasses."""

    def test_sync_result_model_creation(self):
        """Test SyncResultModel creation."""
        result = SyncResultModel(
            model_id="test-model",
            model_name="Test Model",
            action="created",
            old_input_price=None,
            old_output_price=None,
            new_input_price=100,
            new_output_price=200,
        )

        assert result.model_id == "test-model"
        assert result.model_name == "Test Model"
        assert result.action == "created"
        assert result.old_input_price is None
        assert result.new_input_price == 100
        assert result.new_output_price == 200

    def test_sync_result_creation(self):
        """Test SyncResult creation and duration calculation."""
        started = datetime(2025, 1, 15, 10, 0, 0)
        completed = datetime(2025, 1, 15, 10, 0, 5)  # 5 seconds later

        result = SyncResult(
            provider_id="redpill",
            sync_job_id=uuid4(),
            started_at=started,
            completed_at=completed,
            total_models=10,
            created_count=3,
            updated_count=2,
            unchanged_count=5,
            error_count=0,
        )

        assert result.provider_id == "redpill"
        assert result.total_models == 10
        assert result.created_count == 3
        assert result.updated_count == 2
        assert result.unchanged_count == 5
        assert result.duration_ms == 5000

    def test_sync_result_to_dict(self):
        """Test SyncResult to_dict method."""
        sync_job_id = uuid4()
        started = datetime(2025, 1, 15, 10, 0, 0)
        completed = datetime(2025, 1, 15, 10, 0, 2)

        result = SyncResult(
            provider_id="redpill",
            sync_job_id=sync_job_id,
            started_at=started,
            completed_at=completed,
            total_models=5,
            created_count=2,
            updated_count=1,
            unchanged_count=2,
            error_count=0,
            models=[
                SyncResultModel(
                    model_id="model-1",
                    model_name="Model 1",
                    action="created",
                    old_input_price=None,
                    old_output_price=None,
                    new_input_price=100,
                    new_output_price=200,
                )
            ],
        )

        data = result.to_dict()

        assert data["provider_id"] == "redpill"
        assert data["sync_job_id"] == str(sync_job_id)
        assert data["total_models"] == 5
        assert data["created_count"] == 2
        assert data["updated_count"] == 1
        assert data["unchanged_count"] == 2
        assert data["duration_ms"] == 2000
        assert len(data["models"]) == 1
        assert data["models"][0]["model_id"] == "model-1"


@pytest.mark.unit
class TestPricingConversion:
    """Test pricing conversion from RedPill API format."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def sync_service(self, mock_db):
        """Create sync service instance with mock db."""
        return ProviderPricingSyncService(mock_db)

    def test_convert_redpill_pricing_input_output_format(self, sync_service):
        """Test conversion of RedPill pricing with input/output format."""
        model_data = {
            "id": "test-model",
            "pricing": {
                "input": 0.40,  # $0.40 per million
                "output": 0.80,  # $0.80 per million
            },
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        assert input_cents == 40  # $0.40 = 40 cents
        assert output_cents == 80  # $0.80 = 80 cents

    def test_convert_redpill_pricing_prompt_completion_format(self, sync_service):
        """Test conversion of RedPill pricing with prompt/completion per-token format."""
        model_data = {
            "id": "test-model",
            "pricing": {
                "prompt": 0.0000004,  # $0.40 per million tokens (0.0000004 per token)
                "completion": 0.0000008,  # $0.80 per million tokens
            },
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        # prompt price per token * 1M * 100 = cents per million
        assert input_cents == 40  # 0.0000004 * 1,000,000 * 100 = 40
        assert output_cents == 80  # 0.0000008 * 1,000,000 * 100 = 80

    def test_convert_redpill_pricing_no_pricing_data(self, sync_service):
        """Test conversion falls back to defaults when no pricing data."""
        model_data = {
            "id": "test-model",
            # No pricing field
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        # Should use defaults
        assert input_cents == 100  # $1 per million
        assert output_cents == 200  # $2 per million

    def test_convert_redpill_pricing_empty_pricing(self, sync_service):
        """Test conversion with empty pricing object."""
        model_data = {
            "id": "test-model",
            "pricing": {},
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        # Should use defaults
        assert input_cents == 100
        assert output_cents == 200

    def test_convert_redpill_pricing_zero_prices(self, sync_service):
        """Test conversion handles zero prices correctly."""
        model_data = {
            "id": "free-model",
            "pricing": {
                "input": 0.0,
                "output": 0.0,
            },
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        assert input_cents == 0
        assert output_cents == 0

    def test_convert_redpill_pricing_large_prices(self, sync_service):
        """Test conversion handles large prices correctly."""
        model_data = {
            "id": "expensive-model",
            "pricing": {
                "input": 15.0,  # $15 per million
                "output": 60.0,  # $60 per million
            },
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        assert input_cents == 1500  # $15 = 1500 cents
        assert output_cents == 6000  # $60 = 6000 cents

    def test_convert_redpill_pricing_fractional_prices(self, sync_service):
        """Test conversion handles fractional prices correctly."""
        model_data = {
            "id": "cheap-model",
            "pricing": {
                "input": 0.55,  # $0.55 per million
                "output": 2.19,  # $2.19 per million
            },
        }

        input_cents, output_cents = sync_service._convert_redpill_pricing(model_data)

        assert input_cents == 55
        assert output_cents == 219


@pytest.mark.unit
@pytest.mark.asyncio
class TestSyncProviderOperations:
    """Test sync provider operations with mocked dependencies."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def sync_service(self, mock_db):
        """Create sync service with mock db."""
        return ProviderPricingSyncService(mock_db)

    async def test_sync_provider_invalid_provider(self, sync_service):
        """Test sync_provider raises error for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            await sync_service.sync_provider("unknown-provider")

        assert "not configured" in str(exc_info.value)

    async def test_sync_provider_missing_api_key(self, sync_service):
        """Test sync_provider handles missing API key."""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                sync_service,
                "_fetch_redpill_models",
                side_effect=ValueError("Missing API key: REDPILL_API_KEY"),
            ):
                result = await sync_service.sync_provider("redpill")

                assert result.provider_id == "redpill"
                assert len(result.errors) > 0
                assert "Missing API key" in result.errors[0]

    @patch("aiohttp.ClientSession")
    async def test_sync_provider_successful_sync(
        self, mock_session_class, sync_service, mock_db
    ):
        """Test successful sync from RedPill API."""
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "model-1",
                        "name": "Model One",
                        "pricing": {"input": 0.40, "output": 0.80},
                        "context_length": 32000,
                    },
                    {
                        "id": "model-2",
                        "name": "Model Two",
                        "pricing": {"input": 0.55, "output": 2.19},
                        "context_length": 128000,
                    },
                ],
                "object": "list",
            }
        )

        # Setup mock session context managers
        mock_session = AsyncMock()
        mock_session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_class.return_value.__aexit__ = AsyncMock()

        # Mock database query for existing pricing (no existing records)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.dict("os.environ", {"REDPILL_API_KEY": "test-key"}):
            result = await sync_service.sync_provider("redpill")

        assert result.provider_id == "redpill"
        assert result.total_models == 2
        assert result.created_count == 2
        assert result.updated_count == 0
        assert result.unchanged_count == 0
        assert result.error_count == 0

    async def test_process_model_creates_new_pricing(self, sync_service, mock_db):
        """Test _process_model creates new pricing when none exists."""
        # Mock database query returns no existing pricing
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "new-model",
            "name": "New Model",
            "pricing": {"input": 0.50, "output": 1.00},
            "context_length": 32000,
        }

        result = await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=uuid4(),
        )

        assert result is not None
        assert result.model_id == "new-model"
        assert result.action == "created"
        assert result.new_input_price == 50
        assert result.new_output_price == 100
        assert result.old_input_price is None
        assert result.old_output_price is None

        # Verify db.add was called for pricing and audit log
        assert mock_db.add.call_count == 2

    async def test_process_model_updates_existing_pricing(self, sync_service, mock_db):
        """Test _process_model updates pricing when price changed."""
        # Create existing pricing
        existing_pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="existing-model",
            input_price_per_million_cents=50,
            output_price_per_million_cents=100,
            price_source="api_sync",
            is_override=False,
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pricing
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "existing-model",
            "name": "Existing Model",
            "pricing": {"input": 0.60, "output": 1.20},  # Price increased
        }

        result = await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=uuid4(),
        )

        assert result is not None
        assert result.model_id == "existing-model"
        assert result.action == "updated"
        assert result.old_input_price == 50
        assert result.old_output_price == 100
        assert result.new_input_price == 60
        assert result.new_output_price == 120

        # Verify existing pricing was expired
        assert existing_pricing.effective_until is not None

    async def test_process_model_skips_override(self, sync_service, mock_db):
        """Test _process_model skips update for override pricing."""
        # Create existing pricing with override
        existing_pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="override-model",
            input_price_per_million_cents=40,
            output_price_per_million_cents=40,
            price_source="manual",
            is_override=True,  # This is an override
            override_reason="Custom pricing",
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pricing
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "override-model",
            "name": "Override Model",
            "pricing": {"input": 0.60, "output": 1.20},  # Different price
        }

        result = await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=uuid4(),
        )

        assert result is not None
        assert result.model_id == "override-model"
        assert result.action == "unchanged"  # Skipped due to override
        # Override pricing should not be expired
        assert existing_pricing.effective_until is None

    async def test_process_model_unchanged_when_same_price(self, sync_service, mock_db):
        """Test _process_model returns unchanged when price is the same."""
        # Create existing pricing with same prices
        existing_pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="same-price-model",
            input_price_per_million_cents=50,
            output_price_per_million_cents=100,
            price_source="api_sync",
            is_override=False,
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pricing
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "same-price-model",
            "name": "Same Price Model",
            "pricing": {"input": 0.50, "output": 1.00},  # Same price
        }

        result = await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=uuid4(),
        )

        assert result is not None
        assert result.model_id == "same-price-model"
        assert result.action == "unchanged"

    async def test_process_model_missing_id(self, sync_service, mock_db):
        """Test _process_model handles missing model ID."""
        model_data = {
            "name": "Model Without ID",
            "pricing": {"input": 0.50, "output": 1.00},
        }

        result = await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=uuid4(),
        )

        assert result is None

    async def test_sync_creates_audit_log_for_create(self, sync_service, mock_db):
        """Test sync creates audit log entry for new pricing."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "audit-test-model",
            "name": "Audit Test",
            "pricing": {"input": 0.50, "output": 1.00},
        }

        sync_job_id = uuid4()
        await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=sync_job_id,
        )

        # Check that add was called for both pricing and audit log
        assert mock_db.add.call_count == 2

        # Get the audit log from the calls
        calls = mock_db.add.call_args_list
        audit_log = None
        for call in calls:
            obj = call[0][0]
            if isinstance(obj, PricingAuditLog):
                audit_log = obj
                break

        assert audit_log is not None
        assert audit_log.action == "create"
        assert audit_log.change_source == "api_sync"
        assert audit_log.sync_job_id == sync_job_id

    async def test_sync_creates_audit_log_for_update(self, sync_service, mock_db):
        """Test sync creates audit log entry for price update."""
        existing_pricing = ProviderPricing(
            id=1,
            provider_id="redpill",
            model_id="update-audit-model",
            input_price_per_million_cents=50,
            output_price_per_million_cents=100,
            price_source="api_sync",
            is_override=False,
            effective_from=datetime.now(timezone.utc),
            effective_until=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pricing
        mock_db.execute = AsyncMock(return_value=mock_result)

        model_data = {
            "id": "update-audit-model",
            "pricing": {"input": 0.60, "output": 1.20},
        }

        sync_job_id = uuid4()
        await sync_service._process_model(
            provider_id="redpill",
            model_data=model_data,
            sync_job_id=sync_job_id,
        )

        # Get the audit log from the calls
        calls = mock_db.add.call_args_list
        audit_log = None
        for call in calls:
            obj = call[0][0]
            if isinstance(obj, PricingAuditLog):
                audit_log = obj
                break

        assert audit_log is not None
        assert audit_log.action == "update"
        assert audit_log.old_input_price_per_million_cents == 50
        assert audit_log.old_output_price_per_million_cents == 100
        assert audit_log.new_input_price_per_million_cents == 60
        assert audit_log.new_output_price_per_million_cents == 120


@pytest.mark.unit
@pytest.mark.asyncio
class TestSyncErrorHandling:
    """Test error handling in sync service."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock async database session."""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def sync_service(self, mock_db):
        """Create sync service with mock db."""
        return ProviderPricingSyncService(mock_db)

    @patch("aiohttp.ClientSession")
    async def test_sync_handles_api_error(self, mock_session_class, sync_service):
        """Test sync handles API HTTP error gracefully."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()
        mock_session.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_class.return_value.__aexit__ = AsyncMock()

        with patch.dict("os.environ", {"REDPILL_API_KEY": "test-key"}):
            result = await sync_service.sync_provider("redpill")

        assert result.provider_id == "redpill"
        assert len(result.errors) > 0
        assert "HTTP 500" in result.errors[0]

    @patch("aiohttp.ClientSession")
    async def test_sync_handles_connection_error(
        self, mock_session_class, sync_service, mock_db
    ):
        """Test sync handles connection error gracefully."""
        import aiohttp

        mock_session = AsyncMock()
        mock_session.get = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(
                    side_effect=aiohttp.ClientError("Connection refused")
                )
            )
        )
        mock_session_class.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_session_class.return_value.__aexit__ = AsyncMock()

        with patch.dict("os.environ", {"REDPILL_API_KEY": "test-key"}):
            result = await sync_service.sync_provider("redpill")

        assert result.provider_id == "redpill"
        assert len(result.errors) > 0
        # Rollback should be called on error
        mock_db.rollback.assert_called()

    async def test_sync_handles_model_processing_error(self, sync_service, mock_db):
        """Test sync continues after individual model processing error."""
        # First model succeeds, second fails
        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First model - no existing pricing
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                return mock_result
            else:
                # Second model - raise an error
                raise Exception("Database error")

        mock_db.execute = mock_execute

        # Mock the _fetch_redpill_models to return test data
        with patch.object(
            sync_service,
            "_fetch_redpill_models",
            return_value=[
                {"id": "model-1", "pricing": {"input": 0.5, "output": 1.0}},
                {"id": "model-2", "pricing": {"input": 0.5, "output": 1.0}},
            ],
        ):
            result = await sync_service.sync_provider("redpill")

        assert result.created_count == 1
        assert result.error_count == 1
        assert len(result.errors) == 1

    async def test_sync_handles_empty_model_list(self, sync_service, mock_db):
        """Test sync handles empty model list from API."""
        with patch.object(sync_service, "_fetch_redpill_models", return_value=[]):
            result = await sync_service.sync_provider("redpill")

        assert result.provider_id == "redpill"
        assert result.total_models == 0
        assert result.created_count == 0
        assert result.updated_count == 0
        assert result.unchanged_count == 0
        assert result.error_count == 0


@pytest.mark.unit
class TestGetSyncableProviders:
    """Test the get_syncable_providers class method."""

    def test_get_syncable_providers_returns_list(self):
        """Test get_syncable_providers returns list of providers."""
        providers = ProviderPricingSyncService.get_syncable_providers()

        assert isinstance(providers, list)
        assert "redpill" in providers

    def test_get_syncable_providers_not_empty(self):
        """Test get_syncable_providers returns at least one provider."""
        providers = ProviderPricingSyncService.get_syncable_providers()

        assert len(providers) >= 1
