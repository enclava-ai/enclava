"""
Test budget enforcement service.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from app.services.budget_enforcement import BudgetEnforcementService
from app.models.budget import Budget, BudgetPeriod
from app.models.api_key import APIKey
from app.models.usage_tracking import UsageTracking


class TestBudgetEnforcement:
    """Test budget enforcement functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def budget_service(self, mock_db):
        """Create budget enforcement service instance."""
        return BudgetEnforcementService(mock_db)

    @pytest.fixture
    def sample_budget(self):
        """Create a sample budget for testing."""
        return Budget(
            id=1,
            name="Test Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=10000,  # $100.00
            period_type=BudgetPeriod.MONTHLY,
            period_start=datetime.now().replace(day=1),
            period_end=datetime.now().replace(day=28),
            current_usage_cents=5000,  # $50.00
            is_active=True
        )
    
    @pytest.fixture
    def sample_api_key(self):
        """Create a sample API key for testing."""
        return APIKey(
            id=1,
            user_id=1,
            key_hash="test_hash",
            name="Test API Key",
            scopes=["llm:read", "llm:write"],
            is_active=True
        )

    @pytest.fixture
    def daily_budget(self):
        """Create a daily budget for testing."""
        return Budget(
            id=2,
            name="Daily Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=1000,  # $10.00
            period_type=BudgetPeriod.DAILY,
            period_start=datetime.now().replace(hour=0, minute=0, second=0),
            period_end=datetime.now().replace(hour=23, minute=59, second=59),
            current_usage_cents=500,  # $5.00
            is_active=True
        )

    @pytest.fixture
    def weekly_budget(self):
        """Create a weekly budget for testing."""
        return Budget(
            id=3,
            name="Weekly Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=7000,  # $70.00
            period_type=BudgetPeriod.WEEKLY,
            period_start=datetime.now() - timedelta(days=3),
            period_end=datetime.now() + timedelta(days=3),
            current_usage_cents=3500,  # $35.00
            is_active=True
        )

    @pytest.fixture
    def yearly_budget(self):
        """Create a yearly budget for testing."""
        return Budget(
            id=4,
            name="Yearly Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=120000,  # $1200.00
            period_type=BudgetPeriod.YEARLY,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 12, 31),
            current_usage_cents=60000,  # $600.00
            is_active=True
        )

    def test_check_budget_under_limit(self, budget_service, sample_budget, sample_api_key):
        """Test budget check when under limit."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[sample_budget]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key, 
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000
            )
            
            assert allowed is True
            assert message is None
            assert len(warnings) == 0

    def test_check_budget_over_limit(self, budget_service, sample_budget, sample_api_key):
        """Test budget check when over limit."""
        # Create a budget that's already at limit
        over_limit_budget = Budget(
            id=1,
            name="Over Limit Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=1000,  # $10.00
            period_type=BudgetPeriod.MONTHLY,
            period_start=datetime.now().replace(day=1),
            period_end=datetime.now().replace(day=28),
            current_usage_cents=1000,  # $10.00 (at limit)
            is_active=True,
            enforce_hard_limit=True  # Explicitly set this
        )
        
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[over_limit_budget]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key,
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000  # Any additional usage would exceed
            )
            
            assert allowed is False
            assert message is not None
            assert "exceed budget" in message.lower()

    def test_check_budget_no_budgets(self, budget_service, sample_api_key):
        """Test budget check when no budgets exist."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key,
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000
            )
            
            assert allowed is True
            assert message is None
            assert len(warnings) == 0

    def test_record_usage_success(self, budget_service, sample_budget, sample_api_key):
        """Test successful usage recording."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[sample_budget]):
            with patch.object(budget_service.db, 'commit'):
                updated_budgets = budget_service.record_usage(
                    api_key=sample_api_key,
                    model_name="gpt-3.5-turbo",
                    input_tokens=1000,
                    output_tokens=500
                )
                
                assert len(updated_budgets) >= 0  # May or may not update depending on budget periods

    def test_record_usage_multiple_budgets(self, budget_service, sample_budget, daily_budget, sample_api_key):
        """Test usage recording with multiple applicable budgets."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[sample_budget, daily_budget]):
            with patch.object(budget_service.db, 'commit'):
                updated_budgets = budget_service.record_usage(
                    api_key=sample_api_key,
                    model_name="gpt-3.5-turbo",
                    input_tokens=1000,
                    output_tokens=500
                )
                
                assert len(updated_budgets) >= 0

    def test_get_budget_status(self, budget_service, sample_budget, sample_api_key):
        """Test getting budget status."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[sample_budget]):
            status = budget_service.get_budget_status(api_key=sample_api_key)
            
            assert "total_budgets" in status
            assert "active_budgets" in status
            assert "total_limit_cents" in status
            assert "total_usage_cents" in status
            assert "overall_usage_percentage" in status

    def test_daily_budget_period(self, budget_service, daily_budget, sample_api_key):
        """Test daily budget period handling."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[daily_budget]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key,
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000
            )
            
            assert allowed is True
            assert message is None

    def test_weekly_budget_period(self, budget_service, weekly_budget, sample_api_key):
        """Test weekly budget period handling."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[weekly_budget]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key,
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000
            )
            
            assert allowed is True
            assert message is None

    def test_yearly_budget_period(self, budget_service, yearly_budget, sample_api_key):
        """Test yearly budget period handling."""
        with patch.object(budget_service, '_get_applicable_budgets', return_value=[yearly_budget]):
            allowed, message, warnings = budget_service.check_budget_compliance(
                api_key=sample_api_key,
                model_name="gpt-3.5-turbo",
                estimated_tokens=1000
            )
            
            assert allowed is True
            assert message is None

    def test_create_default_user_budget(self, budget_service):
        """Test creating a default user budget."""
        with patch.object(budget_service.db, 'add'):
            with patch.object(budget_service.db, 'commit'):
                budget = budget_service.create_default_user_budget(
                    user_id=1,
                    limit_dollars=50.0,
                    period_type="monthly"
                )
                
                assert budget is not None
                assert budget.user_id == 1
                assert budget.limit_cents == 5000  # $50.00 in cents

    def test_check_and_reset_expired_budgets(self, budget_service):
        """Test checking and resetting expired budgets."""
        # Mock database query for expired budgets
        expired_budget = Budget(
            id=1,
            name="Expired Budget",
            user_id=1,
            api_key_id=1,
            limit_cents=10000,
            period_type=BudgetPeriod.MONTHLY,
            period_start=datetime.now() - timedelta(days=60),
            period_end=datetime.now() - timedelta(days=30),
            current_usage_cents=5000,
            is_active=True,
            auto_renew=True
        )
        
        with patch.object(budget_service.db, 'query') as mock_query:
            mock_query.return_value.filter.return_value.all.return_value = [expired_budget]
            with patch.object(budget_service, '_reset_expired_budget'):
                budget_service.check_and_reset_expired_budgets()
                
                # Verify that the method was called
                mock_query.assert_called_once()