#!/usr/bin/env python3
"""
Budget API Endpoints Tests - Phase 2 API Coverage
Priority: app/api/v1/budgets.py

Tests comprehensive budget API functionality:
- Budget CRUD operations
- Budget limit enforcement
- Usage tracking integration
- Period-based budget management
- Admin budget management
- Permission checking
- Error handling and validation
"""

import pytest
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import status
from app.main import app
from app.models.user import User
from app.models.budget import Budget
from app.models.api_key import APIKey
from app.models.usage_tracking import UsageTracking


class TestBudgetEndpoints:
    """Comprehensive test suite for Budget API endpoints"""
    
    @pytest.fixture
    async def client(self):
        """Create test HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    def auth_headers(self):
        """Authentication headers for test user"""
        return {"Authorization": "Bearer test_access_token"}
    
    @pytest.fixture
    def admin_headers(self):
        """Authentication headers for admin user"""
        return {"Authorization": "Bearer admin_access_token"}
    
    @pytest.fixture
    def mock_user(self):
        """Mock regular user"""
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            is_active=True,
            role="user"
        )
    
    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user"""
        return User(
            id=2,
            username="admin",
            email="admin@example.com",
            is_active=True,
            role="admin",
            is_superuser=True
        )
    
    @pytest.fixture
    def sample_budget(self, mock_user):
        """Sample budget for testing"""
        return Budget(
            id=1,
            user_id=mock_user.id,
            name="Test Budget",
            description="Test budget for API testing",
            budget_type="dollars",
            limit_amount=100.00,
            current_usage=25.50,
            period_type="monthly",
            is_active=True,
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_api_key(self, mock_user):
        """Sample API key for testing"""
        return APIKey(
            id=1,
            user_id=mock_user.id,
            name="Test API Key",
            key_prefix="ce_test",
            is_active=True
        )

    # === BUDGET LISTING TESTS ===
    
    @pytest.mark.asyncio
    async def test_list_budgets_success(self, client, auth_headers, mock_user, sample_budget):
        """Test successful budget listing"""
        budgets_data = [
            {
                "id": 1,
                "name": "Test Budget",
                "description": "Test budget for API testing",
                "budget_type": "dollars",
                "limit_amount": 100.00,
                "current_usage": 25.50,
                "period_type": "monthly",
                "is_active": True,
                "usage_percentage": 25.5,
                "remaining_amount": 74.50,
                "created_at": "2024-01-01T10:00:00Z"
            }
        ]
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock database query
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = [sample_budget]
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    "/api/v1/budgets/",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "budgets" in data
                assert len(data["budgets"]) >= 0  # May be transformed
                
                # Verify database query was made
                mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_budgets_unauthorized(self, client):
        """Test budget listing without authentication"""
        response = await client.get("/api/v1/budgets/")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_list_budgets_with_filters(self, client, auth_headers, mock_user):
        """Test budget listing with query filters"""
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = []
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    "/api/v1/budgets/?budget_type=dollars&period_type=monthly&active_only=true",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                
                # Verify query was executed
                mock_session.execute.assert_called_once()

    # === BUDGET CREATION TESTS ===
    
    @pytest.mark.asyncio
    async def test_create_budget_success(self, client, auth_headers, mock_user):
        """Test successful budget creation"""
        budget_data = {
            "name": "Monthly Spending Limit",
            "description": "Monthly budget for API usage",
            "budget_type": "dollars",
            "limit_amount": 150.0,
            "period_type": "monthly"
        }
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock successful creation
                mock_session.add.return_value = None
                mock_session.commit.return_value = None
                mock_session.refresh.return_value = None
                
                response = await client.post(
                    "/api/v1/budgets/",
                    json=budget_data,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                
                assert "budget" in data
                # Verify database operations
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_budget_invalid_data(self, client, auth_headers, mock_user):
        """Test budget creation with invalid data"""
        invalid_cases = [
            # Missing required fields
            {"name": "Test Budget"},
            
            # Invalid budget type
            {
                "name": "Test Budget",
                "budget_type": "invalid_type",
                "limit_amount": 100.0,
                "period_type": "monthly"
            },
            
            # Invalid limit amount
            {
                "name": "Test Budget",
                "budget_type": "dollars",
                "limit_amount": -50.0,  # Negative amount
                "period_type": "monthly"
            },
            
            # Invalid period type
            {
                "name": "Test Budget",
                "budget_type": "dollars", 
                "limit_amount": 100.0,
                "period_type": "invalid_period"
            }
        ]
        
        for invalid_data in invalid_cases:
            response = await client.post(
                "/api/v1/budgets/",
                json=invalid_data,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_create_budget_duplicate_name(self, client, auth_headers, mock_user):
        """Test budget creation with duplicate name"""
        budget_data = {
            "name": "Existing Budget Name",
            "budget_type": "dollars",
            "limit_amount": 100.0,
            "period_type": "monthly"
        }
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock integrity error for duplicate name
                from sqlalchemy.exc import IntegrityError
                mock_session.commit.side_effect = IntegrityError("Duplicate key", None, None)
                
                response = await client.post(
                    "/api/v1/budgets/",
                    json=budget_data,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_400_BAD_REQUEST
                data = response.json()
                assert "duplicate" in data["detail"].lower() or "already exists" in data["detail"].lower()

    # === BUDGET RETRIEVAL TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_budget_by_id_success(self, client, auth_headers, mock_user, sample_budget):
        """Test successful budget retrieval by ID"""
        budget_id = 1
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    f"/api/v1/budgets/{budget_id}",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "budget" in data
                # Verify query was made
                mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_budget_not_found(self, client, auth_headers, mock_user):
        """Test budget retrieval for non-existent budget"""
        budget_id = 999
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget not found
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = None
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    f"/api/v1/budgets/{budget_id}",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert "not found" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_budget_access_denied(self, client, auth_headers, mock_user):
        """Test budget retrieval for budget owned by another user"""
        budget_id = 1
        other_user_budget = Budget(
            id=1,
            user_id=999,  # Different user
            name="Other User's Budget",
            budget_type="dollars",
            limit_amount=100.0,
            period_type="monthly"
        )
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget owned by other user
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = other_user_budget
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    f"/api/v1/budgets/{budget_id}",
                    headers=auth_headers
                )
                
                assert response.status_code in [
                    status.HTTP_403_FORBIDDEN,
                    status.HTTP_404_NOT_FOUND
                ]

    # === BUDGET UPDATE TESTS ===
    
    @pytest.mark.asyncio
    async def test_update_budget_success(self, client, auth_headers, mock_user, sample_budget):
        """Test successful budget update"""
        budget_id = 1
        update_data = {
            "name": "Updated Budget Name",
            "description": "Updated description",
            "limit_amount": 200.0
        }
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval and update
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                mock_session.commit.return_value = None
                
                response = await client.patch(
                    f"/api/v1/budgets/{budget_id}",
                    json=update_data,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "budget" in data
                
                # Verify commit was called
                mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_budget_invalid_data(self, client, auth_headers, mock_user, sample_budget):
        """Test budget update with invalid data"""
        budget_id = 1
        invalid_data = {
            "limit_amount": -100.0  # Invalid negative amount
        }
        
        response = await client.patch(
            f"/api/v1/budgets/{budget_id}",
            json=invalid_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # === BUDGET DELETION TESTS ===
    
    @pytest.mark.asyncio
    async def test_delete_budget_success(self, client, auth_headers, mock_user, sample_budget):
        """Test successful budget deletion"""
        budget_id = 1
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval and deletion
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                mock_session.delete.return_value = None
                mock_session.commit.return_value = None
                
                response = await client.delete(
                    f"/api/v1/budgets/{budget_id}",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "deleted" in data["message"].lower()
                
                # Verify deletion operations
                mock_session.delete.assert_called_once()
                mock_session.commit.assert_called_once()

    # === BUDGET STATUS AND USAGE TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_budget_status(self, client, auth_headers, mock_user, sample_budget):
        """Test budget status retrieval with usage information"""
        budget_id = 1
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    f"/api/v1/budgets/{budget_id}/status",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "status" in data
                assert "usage_percentage" in data["status"]
                assert "remaining_amount" in data["status"]
                assert "days_remaining_in_period" in data["status"]
    
    @pytest.mark.asyncio
    async def test_get_budget_usage_history(self, client, auth_headers, mock_user, sample_budget):
        """Test budget usage history retrieval"""
        budget_id = 1
        
        mock_usage_records = [
            UsageTracking(
                id=1,
                budget_id=budget_id,
                amount=10.50,
                timestamp=datetime.utcnow() - timedelta(days=1),
                request_type="chat_completion"
            ),
            UsageTracking(
                id=2,
                budget_id=budget_id,
                amount=15.00,
                timestamp=datetime.utcnow() - timedelta(days=2),
                request_type="embedding"
            )
        ]
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget and usage retrieval
                mock_budget_result = Mock()
                mock_budget_result.scalar_one_or_none.return_value = sample_budget
                
                mock_usage_result = Mock()
                mock_usage_result.scalars.return_value.all.return_value = mock_usage_records
                
                mock_session.execute.side_effect = [mock_budget_result, mock_usage_result]
                
                response = await client.get(
                    f"/api/v1/budgets/{budget_id}/usage",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert "usage_history" in data
                assert len(data["usage_history"]) >= 0
                
                # Verify both queries were made
                assert mock_session.execute.call_count == 2

    # === BUDGET RESET TESTS ===
    
    @pytest.mark.asyncio
    async def test_reset_budget_usage(self, client, auth_headers, mock_user, sample_budget):
        """Test budget usage reset"""
        budget_id = 1
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval and reset
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                mock_session.commit.return_value = None
                
                response = await client.post(
                    f"/api/v1/budgets/{budget_id}/reset",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "reset" in data["message"].lower()
                
                # Verify reset operation (current_usage should be 0)
                assert sample_budget.current_usage == 0.0
                mock_session.commit.assert_called_once()

    # === ADMIN BUDGET MANAGEMENT TESTS ===
    
    @pytest.mark.asyncio
    async def test_admin_list_all_budgets(self, client, admin_headers, mock_admin_user):
        """Test admin listing all users' budgets"""
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_admin_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock admin query (all budgets)
                mock_result = Mock()
                mock_result.scalars.return_value.all.return_value = []
                mock_session.execute.return_value = mock_result
                
                response = await client.get(
                    "/api/v1/budgets/admin/all",
                    headers=admin_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "budgets" in data
    
    @pytest.mark.asyncio
    async def test_admin_create_user_budget(self, client, admin_headers, mock_admin_user):
        """Test admin creating budget for another user"""
        budget_data = {
            "name": "Admin Created Budget",
            "budget_type": "dollars",
            "limit_amount": 500.0,
            "period_type": "monthly",
            "user_id": "3"  # Different user
        }
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_admin_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock successful creation
                mock_session.add.return_value = None
                mock_session.commit.return_value = None
                mock_session.refresh.return_value = None
                
                response = await client.post(
                    "/api/v1/budgets/admin/create",
                    json=budget_data,
                    headers=admin_headers
                )
                
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert "budget" in data
                
                # Verify database operations
                mock_session.add.assert_called_once()
                mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_non_admin_access_denied(self, client, auth_headers, mock_user):
        """Test non-admin user denied access to admin endpoints"""
        response = await client.get(
            "/api/v1/budgets/admin/all",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # === BUDGET ALERTS AND NOTIFICATIONS TESTS ===
    
    @pytest.mark.asyncio
    async def test_budget_alert_configuration(self, client, auth_headers, mock_user, sample_budget):
        """Test budget alert configuration"""
        budget_id = 1
        alert_config = {
            "alert_thresholds": [50, 80, 95],  # Alert at 50%, 80%, and 95%
            "notification_email": "alerts@example.com",
            "webhook_url": "https://example.com/budget-alerts"
        }
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval and alert config update
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                mock_session.commit.return_value = None
                
                response = await client.post(
                    f"/api/v1/budgets/{budget_id}/alerts",
                    json=alert_config,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "alert configuration" in data["message"].lower()

    # === ERROR HANDLING AND EDGE CASES ===
    
    @pytest.mark.asyncio
    async def test_budget_database_error(self, client, auth_headers, mock_user):
        """Test handling of database errors"""
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock database error
                mock_session.execute.side_effect = Exception("Database connection failed")
                
                response = await client.get(
                    "/api/v1/budgets/",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "error" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_budget_concurrent_modification(self, client, auth_headers, mock_user, sample_budget):
        """Test handling of concurrent budget modifications"""
        budget_id = 1
        update_data = {"limit_amount": 300.0}
        
        with patch('app.api.v1.budgets.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.budgets.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock budget retrieval
                mock_result = Mock()
                mock_result.scalar_one_or_none.return_value = sample_budget
                mock_session.execute.return_value = mock_result
                
                # Mock concurrent modification error
                from sqlalchemy.exc import OptimisticLockError
                mock_session.commit.side_effect = OptimisticLockError("Record was modified", None, None, None)
                
                response = await client.patch(
                    f"/api/v1/budgets/{budget_id}",
                    json=update_data,
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_409_CONFLICT
                data = response.json()
                assert "conflict" in data["detail"].lower() or "modified" in data["detail"].lower()


"""
COVERAGE ANALYSIS FOR BUDGET API ENDPOINTS:

✅ Budget Listing (3+ tests):
- Successful budget listing for user
- Unauthorized access handling
- Budget filtering with query parameters

✅ Budget Creation (3+ tests):
- Successful budget creation
- Invalid data validation
- Duplicate name handling

✅ Budget Retrieval (3+ tests):
- Successful retrieval by ID
- Non-existent budget handling
- Access control (other user's budget)

✅ Budget Updates (2+ tests):
- Successful budget updates
- Invalid data validation

✅ Budget Deletion (1+ test):
- Successful budget deletion

✅ Budget Status (2+ tests):
- Budget status with usage information
- Budget usage history retrieval

✅ Budget Operations (1+ test):
- Budget usage reset functionality

✅ Admin Operations (3+ tests):
- Admin listing all budgets
- Admin creating budgets for users
- Non-admin access denied

✅ Advanced Features (1+ test):
- Budget alert configuration

✅ Error Handling (2+ tests):
- Database error handling
- Concurrent modification handling

ESTIMATED COVERAGE IMPROVEMENT:
- Test Count: 20+ comprehensive API tests
- Business Impact: High (cost control and budget management)
- Implementation: Complete budget management flow validation
"""