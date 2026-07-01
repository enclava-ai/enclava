"""
Test usage recording service for tracking LLM request usage.

Tests cover:
- Recording a successful request creates UsageRecord
- Cost calculation is correct
- Error classification (rate_limit, timeout, etc.)
- record_error convenience method
- request_id is generated if not provided
- Validation error when neither user_id nor api_key_id provided
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.models.usage_record import UsageRecord
from app.services.usage_recording import (
    UsageRecordingService,
    get_usage_recording_service,
)


class TestUsageRecordingService:
    """Test UsageRecordingService functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        db.add = Mock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def usage_service(self, mock_db):
        """Create a UsageRecordingService instance with mock db."""
        return UsageRecordingService(mock_db)

    # --- Basic Recording Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_creates_usage_record(self, usage_service, mock_db):
        """Test that recording a request creates a UsageRecord."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="meta-llama/llama-3.1-70b-instruct",
            input_tokens=100,
            output_tokens=50,
            endpoint="/api/v1/chat/completions",
            method="POST",
        )

        # Verify record was created
        assert record is not None
        assert isinstance(record, UsageRecord)
        assert record.user_id == 1
        assert record.provider_id == "privatemode"
        assert record.provider_model == "meta-llama/llama-3.1-70b-instruct"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.total_tokens == 150
        assert record.endpoint == "/api/v1/chat/completions"
        assert record.method == "POST"
        assert record.status == "success"

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_with_api_key_id(self, usage_service, mock_db):
        """Test recording a request with API key ID instead of user_id."""
        record = await usage_service.record_request(
            api_key_id=42,
            user_id=1,  # Still required by model
            provider_id="privatemode",
            provider_model="meta-llama/llama-3.1-8b-instruct",
            input_tokens=50,
            output_tokens=25,
            endpoint="/api/v1/chat/completions",
        )

        assert record.api_key_id == 42
        assert record.user_id == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_generates_request_id(self, usage_service, mock_db):
        """Test that request_id is generated if not provided."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="test-model",
            endpoint="/api/v1/test",
        )

        assert record.request_id is not None
        assert isinstance(record.request_id, UUID)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_uses_provided_request_id(
        self, usage_service, mock_db
    ):
        """Test that provided request_id is used."""
        custom_request_id = uuid4()

        record = await usage_service.record_request(
            request_id=custom_request_id,
            user_id=1,
            provider_id="privatemode",
            provider_model="test-model",
            endpoint="/api/v1/test",
        )

        assert record.request_id == custom_request_id

    # --- Validation Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_requires_user_id_or_api_key_id(self, usage_service):
        """Test that ValueError is raised when neither user_id nor api_key_id provided."""
        with pytest.raises(ValueError) as exc_info:
            await usage_service.record_request(
                provider_id="privatemode",
                provider_model="test-model",
                endpoint="/api/v1/test",
                # Neither user_id nor api_key_id provided
            )

        assert "user_id or api_key_id must be provided" in str(exc_info.value)

    # --- Cost Calculation Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_calculates_cost_correctly(
        self, usage_service, mock_db
    ):
        """Test that cost is calculated correctly for known models."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="meta-llama/llama-3.1-70b-instruct",
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=1_000_000,  # 1M tokens
            endpoint="/api/v1/chat/completions",
        )

        # Pricing: 40 cents per 1M for both input and output
        assert record.input_cost_cents == 40
        assert record.output_cost_cents == 40
        assert record.total_cost_cents == 80

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_stores_pricing_snapshot(self, usage_service, mock_db):
        """Test that pricing snapshot is stored for audit trail."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="meta-llama/llama-3.1-70b-instruct",
            input_tokens=100,
            output_tokens=50,
            endpoint="/api/v1/chat/completions",
        )

        assert record.input_price_per_million_cents == 40
        assert record.output_price_per_million_cents == 40
        assert record.pricing_source in ["manual", "api_sync", "default"]
        assert record.pricing_effective_from is not None
        assert isinstance(record.pricing_effective_from, datetime)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_normalizes_model_name(self, usage_service, mock_db):
        """Test that model name is normalized."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="Meta-Llama/Llama-3.1-70B-Instruct",  # Mixed case
            input_tokens=100,
            output_tokens=50,
            endpoint="/api/v1/chat/completions",
        )

        # Original model is preserved
        assert record.provider_model == "Meta-Llama/Llama-3.1-70B-Instruct"
        # Normalized model is lowercase
        assert record.normalized_model == record.normalized_model.lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_uses_default_pricing_for_unknown_model(
        self, usage_service, mock_db
    ):
        """Test that default pricing is used for unknown models."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="unknown-provider",
            provider_model="unknown-model-xyz",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            endpoint="/api/v1/chat/completions",
        )

        # Default pricing: 100 cents input, 200 cents output per 1M
        assert record.input_cost_cents == 100
        assert record.output_cost_cents == 200
        assert record.total_cost_cents == 300
        assert record.pricing_source == "default"

    # --- Request Context Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_with_full_context(self, usage_service, mock_db):
        """Test recording a request with all context fields."""
        record = await usage_service.record_request(
            user_id=1,
            api_key_id=42,
            provider_id="privatemode",
            provider_model="test-model",
            input_tokens=100,
            output_tokens=50,
            endpoint="/api/v1/chat/completions",
            method="POST",
            agent_config_id=5,
            session_id="session-abc",
            is_streaming=True,
            is_tool_calling=True,
            message_count=3,
            latency_ms=250,
            ttft_ms=50,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Client",
        )

        assert record.agent_config_id == 5
        assert record.session_id == "session-abc"
        assert record.is_streaming is True
        assert record.is_tool_calling is True
        assert record.message_count == 3
        assert record.latency_ms == 250
        assert record.ttft_ms == 50
        assert record.ip_address == "192.168.1.1"
        assert record.user_agent == "Mozilla/5.0 Test Client"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_truncates_long_error_message(
        self, usage_service, mock_db
    ):
        """Test that long error messages are truncated."""
        long_error = "x" * 2000  # 2000 characters

        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="test-model",
            endpoint="/api/v1/test",
            status="error",
            error_message=long_error,
        )

        assert len(record.error_message) == 1000  # Truncated to 1000

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_truncates_long_user_agent(
        self, usage_service, mock_db
    ):
        """Test that long user agents are truncated."""
        long_ua = "x" * 1000  # 1000 characters

        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="test-model",
            endpoint="/api/v1/test",
            user_agent=long_ua,
        )

        assert len(record.user_agent) == 500  # Truncated to 500

    # --- Error Recording Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_error_convenience_method(self, usage_service, mock_db):
        """Test the record_error convenience method."""
        error = Exception("Connection failed")

        record = await usage_service.record_error(
            user_id=1,
            api_key_id=None,
            provider_id="privatemode",
            model="test-model",
            endpoint="/api/v1/chat/completions",
            error=error,
            latency_ms=5000,
        )

        assert record.status == "error"
        assert record.error_message == "Connection failed"
        assert record.error_type == "connection_error"  # Classified based on message
        assert record.latency_ms == 5000
        assert record.input_tokens == 0  # Unknown for errors
        assert record.output_tokens == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_error_with_request_context(self, usage_service, mock_db):
        """Test record_error with additional context."""
        error = TimeoutError("Request timed out")

        record = await usage_service.record_error(
            user_id=1,
            api_key_id=42,
            provider_id="privatemode",
            model="test-model",
            endpoint="/api/v1/chat/completions",
            error=error,
            latency_ms=30000,
            ip_address="10.0.0.1",
            user_agent="API Client v1",
            message_count=5,
            is_streaming=True,
        )

        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "API Client v1"
        assert record.message_count == 5
        assert record.is_streaming is True

    # --- Error Classification Tests ---

    @pytest.mark.unit
    def test_classify_error_rate_limit(self, usage_service):
        """Test rate limit error classification."""
        error1 = Exception("Rate limit exceeded")
        error2 = Exception("Error 429: Too Many Requests")

        assert usage_service._classify_error(error1) == "rate_limit"
        assert usage_service._classify_error(error2) == "rate_limit"

    @pytest.mark.unit
    def test_classify_error_timeout(self, usage_service):
        """Test timeout error classification."""
        error1 = TimeoutError("Request timed out")
        error2 = Exception("timeout waiting for response")

        assert usage_service._classify_error(error1) == "timeout"
        assert usage_service._classify_error(error2) == "timeout"

    @pytest.mark.unit
    def test_classify_error_auth_error(self, usage_service):
        """Test authentication error classification."""
        error1 = Exception("Authentication failed")
        error2 = Exception("HTTP 401 Unauthorized")

        assert usage_service._classify_error(error1) == "auth_error"
        assert usage_service._classify_error(error2) == "auth_error"

    @pytest.mark.unit
    def test_classify_error_permission_error(self, usage_service):
        """Test permission error classification."""
        error1 = Exception("Permission denied")
        error2 = Exception("Error 403: Forbidden")

        assert usage_service._classify_error(error1) == "permission_error"
        assert usage_service._classify_error(error2) == "permission_error"

    @pytest.mark.unit
    def test_classify_error_not_found(self, usage_service):
        """Test not found error classification."""
        error1 = Exception("Resource not found")
        error2 = Exception("Error 404")

        assert usage_service._classify_error(error1) == "not_found"
        assert usage_service._classify_error(error2) == "not_found"

    @pytest.mark.unit
    def test_classify_error_validation_error(self, usage_service):
        """Test validation error classification."""
        error1 = Exception("Validation error: invalid input")

        # Create a mock ValidationError class
        class ValidationError(Exception):
            pass

        error2 = ValidationError("Invalid field")

        assert usage_service._classify_error(error1) == "validation_error"
        assert usage_service._classify_error(error2) == "validation_error"

    @pytest.mark.unit
    def test_classify_error_budget_exceeded(self, usage_service):
        """Test budget exceeded error classification."""
        error = Exception("Budget limit exceeded")

        assert usage_service._classify_error(error) == "budget_exceeded"

    @pytest.mark.unit
    def test_classify_error_provider_error(self, usage_service):
        """Test provider error classification."""
        error1 = Exception("Provider returned an error")

        # Create a mock ProviderError class
        class ProviderError(Exception):
            pass

        error2 = ProviderError("Internal provider error")

        assert usage_service._classify_error(error1) == "provider_error"
        assert usage_service._classify_error(error2) == "provider_error"

    @pytest.mark.unit
    def test_classify_error_connection_error(self, usage_service):
        """Test connection error classification."""
        error = Exception("Connection refused")

        assert usage_service._classify_error(error) == "connection_error"

    @pytest.mark.unit
    def test_classify_error_unknown(self, usage_service):
        """Test unknown error classification."""
        error = Exception("Some random error occurred")

        assert usage_service._classify_error(error) == "unknown_error"

    # --- Status Recording Tests ---

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_different_statuses(self, usage_service, mock_db):
        """Test recording requests with different statuses."""
        for status in ["success", "error", "timeout", "budget_exceeded"]:
            record = await usage_service.record_request(
                user_id=1,
                provider_id="privatemode",
                provider_model="test-model",
                endpoint="/api/v1/test",
                status=status,
            )
            assert record.status == status

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_record_request_with_error_details(self, usage_service, mock_db):
        """Test recording a failed request with error details."""
        record = await usage_service.record_request(
            user_id=1,
            provider_id="privatemode",
            provider_model="test-model",
            endpoint="/api/v1/test",
            status="error",
            error_type="rate_limit",
            error_message="Rate limit exceeded. Please retry after 60 seconds.",
        )

        assert record.status == "error"
        assert record.error_type == "rate_limit"
        assert "Rate limit exceeded" in record.error_message


class TestGetUsageRecordingService:
    """Test the factory function."""

    @pytest.mark.unit
    def test_get_usage_recording_service(self):
        """Test the factory function creates a service."""
        mock_db = AsyncMock()
        service = get_usage_recording_service(mock_db)

        assert isinstance(service, UsageRecordingService)
        assert service.db == mock_db


class TestUsageRecordModel:
    """Test the UsageRecord model properties."""

    @pytest.mark.unit
    def test_usage_record_total_cost_dollars(self):
        """Test the total_cost_dollars property."""
        record = UsageRecord()
        record.total_cost_cents = 250

        assert record.total_cost_dollars == 2.50

    @pytest.mark.unit
    def test_usage_record_is_successful_true(self):
        """Test is_successful returns True for success status."""
        record = UsageRecord()
        record.status = "success"

        assert record.is_successful is True

    @pytest.mark.unit
    def test_usage_record_is_successful_false(self):
        """Test is_successful returns False for non-success status."""
        for status in ["error", "timeout", "budget_exceeded"]:
            record = UsageRecord()
            record.status = status
            assert record.is_successful is False

    @pytest.mark.unit
    def test_usage_record_repr(self):
        """Test the string representation."""
        record = UsageRecord()
        record.id = 123
        record.request_id = uuid4()
        record.provider_id = "privatemode"
        record.normalized_model = "llama-70b"
        record.total_tokens = 150
        record.total_cost_cents = 10

        repr_str = repr(record)
        assert "123" in repr_str
        assert "privatemode" in repr_str
        assert "llama-70b" in repr_str
        assert "150" in repr_str
        assert "10" in repr_str

    @pytest.mark.unit
    def test_usage_record_to_dict(self):
        """Test converting record to dictionary."""
        now = datetime.now(timezone.utc)
        request_id = uuid4()

        record = UsageRecord()
        record.id = 1
        record.request_id = request_id
        record.api_key_id = 42
        record.user_id = 5
        record.provider_id = "privatemode"
        record.provider_model = "meta-llama/llama-3.1-70b-instruct"
        record.normalized_model = "llama-3.1-70b-instruct"
        record.input_tokens = 100
        record.output_tokens = 50
        record.total_tokens = 150
        record.input_cost_cents = 5
        record.output_cost_cents = 2
        record.total_cost_cents = 7
        record.input_price_per_million_cents = 40
        record.output_price_per_million_cents = 40
        record.pricing_source = "manual"
        record.pricing_effective_from = now
        record.endpoint = "/api/v1/chat/completions"
        record.method = "POST"
        record.agent_config_id = 5
        record.session_id = "sess-abc"
        record.is_streaming = True
        record.is_tool_calling = False
        record.message_count = 3
        record.latency_ms = 250
        record.ttft_ms = 50
        record.status = "success"
        record.error_type = None
        record.error_message = None
        record.ip_address = None
        record.user_agent = "Test Client"
        record.created_at = now

        data = record.to_dict()

        assert data["id"] == 1
        assert data["request_id"] == str(request_id)
        assert data["api_key_id"] == 42
        assert data["user_id"] == 5
        assert data["provider_id"] == "privatemode"
        assert data["input_tokens"] == 100
        assert data["output_tokens"] == 50
        assert data["total_tokens"] == 150
        assert data["total_cost_cents"] == 7
        assert data["status"] == "success"
        assert data["is_streaming"] is True
        assert data["agent_config_id"] == 5
        assert data["created_at"] == now.isoformat()
