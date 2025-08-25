#!/usr/bin/env python3
"""
Analytics API Endpoints Tests - Phase 2 API Coverage
Priority: app/api/v1/analytics.py

Tests comprehensive analytics API functionality:
- Usage metrics retrieval
- Cost analysis and trends
- System health monitoring
- Endpoint statistics
- Admin vs user access control
- Error handling and validation
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import status
from app.main import app
from app.models.user import User
from app.models.usage_tracking import UsageTracking


class TestAnalyticsEndpoints:
    """Comprehensive test suite for Analytics API endpoints"""
    
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
        return {
            'id': 1,
            'username': 'testuser',
            'email': 'test@example.com',
            'is_active': True,
            'role': 'user',
            'is_superuser': False
        }
    
    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user"""
        return {
            'id': 2,
            'username': 'admin',
            'email': 'admin@example.com',
            'is_active': True,
            'role': 'admin',
            'is_superuser': True
        }
    
    @pytest.fixture
    def sample_metrics(self):
        """Sample usage metrics data"""
        return {
            'total_requests': 150,
            'total_cost_cents': 2500,  # $25.00
            'avg_response_time': 250.5,
            'error_rate': 0.02,  # 2%
            'budget_usage_percentage': 15.5,
            'tokens_used': 50000,
            'unique_users': 5,
            'top_models': ['gpt-3.5-turbo', 'gpt-4'],
            'period_start': '2024-01-01T00:00:00Z',
            'period_end': '2024-01-01T23:59:59Z'
        }
    
    @pytest.fixture
    def sample_health_data(self):
        """Sample system health data"""
        return {
            'status': 'healthy',
            'score': 95,
            'database_status': 'connected',
            'qdrant_status': 'connected',
            'redis_status': 'connected',
            'llm_service_status': 'operational',
            'uptime_seconds': 86400,
            'memory_usage_percent': 45.2,
            'cpu_usage_percent': 12.8
        }

    # === USAGE METRICS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_usage_metrics_success(self, client, auth_headers, mock_user, sample_metrics):
        """Test successful usage metrics retrieval"""
        from app.main import app
        from app.core.security import get_current_user
        from app.db.database import get_db
        
        mock_analytics_service = Mock()
        mock_analytics_service.get_usage_metrics = AsyncMock(return_value=Mock(**sample_metrics))
        
        # Override app dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        
        try:
            with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/metrics?hours=24",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert data["period_hours"] == 24
                
                # Verify service was called with correct parameters
                mock_analytics_service.get_usage_metrics.assert_called_once_with(
                    hours=24, 
                    user_id=mock_user['id']
                )
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_get_usage_metrics_custom_period(self, client, auth_headers, mock_user):
        """Test usage metrics with custom time period"""
        mock_analytics_service = Mock()
        mock_analytics_service.get_usage_metrics = AsyncMock(return_value=Mock())
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/metrics?hours=168",  # 7 days
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["period_hours"] == 168
    
    @pytest.mark.asyncio
    async def test_get_usage_metrics_invalid_hours(self, client, auth_headers, mock_user):
        """Test usage metrics with invalid hours parameter"""
        test_cases = [
            {"hours": 0, "description": "zero hours"},
            {"hours": -5, "description": "negative hours"},
            {"hours": 200, "description": "too many hours (>168)"}
        ]
        
        for case in test_cases:
            response = await client.get(
                f"/api/v1/analytics/metrics?hours={case['hours']}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_get_usage_metrics_unauthorized(self, client):
        """Test usage metrics without authentication"""
        response = await client.get("/api/v1/analytics/metrics")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === SYSTEM METRICS TESTS (ADMIN ONLY) ===
    
    @pytest.mark.asyncio
    async def test_get_system_metrics_admin_success(self, client, admin_headers, mock_admin_user, sample_metrics):
        """Test successful system metrics retrieval by admin"""
        mock_analytics_service = Mock()
        mock_analytics_service.get_usage_metrics = AsyncMock(return_value=Mock(**sample_metrics))
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_admin_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/metrics/system?hours=48",
                    headers=admin_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert data["period_hours"] == 48
                
                # Verify service was called without user_id (system-wide)
                mock_analytics_service.get_usage_metrics.assert_called_once_with(hours=48)
    
    @pytest.mark.asyncio
    async def test_get_system_metrics_non_admin_denied(self, client, auth_headers, mock_user):
        """Test system metrics access denied for non-admin users"""
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            response = await client.get(
                "/api/v1/analytics/metrics/system",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
            data = response.json()
            assert "admin access required" in data["detail"].lower()

    # === SYSTEM HEALTH TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_system_health_success(self, client, auth_headers, mock_user, sample_health_data):
        """Test successful system health retrieval"""
        mock_analytics_service = Mock()
        mock_analytics_service.get_system_health = AsyncMock(return_value=Mock(**sample_health_data))
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/health",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                
                # Verify service was called
                mock_analytics_service.get_system_health.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_system_health_service_error(self, client, auth_headers, mock_user):
        """Test system health with service error"""
        mock_analytics_service = Mock()
        mock_analytics_service.get_system_health = AsyncMock(
            side_effect=Exception("Service connection failed")
        )
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/health",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "connection failed" in data["detail"].lower()

    # === COST ANALYSIS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_cost_analysis_success(self, client, auth_headers, mock_user):
        """Test successful cost analysis retrieval"""
        cost_analysis_data = {
            'total_cost_cents': 5000,  # $50.00
            'daily_costs': [
                {'date': '2024-01-01', 'cost_cents': 1000},
                {'date': '2024-01-02', 'cost_cents': 1500},
                {'date': '2024-01-03', 'cost_cents': 2500}
            ],
            'cost_by_model': {
                'gpt-3.5-turbo': 2000,
                'gpt-4': 3000
            },
            'projected_monthly_cost': 15000,  # $150.00
            'period_days': 30
        }
        
        mock_analytics_service = Mock()
        mock_analytics_service.get_cost_analysis = AsyncMock(return_value=Mock(**cost_analysis_data))
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/costs?days=30",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert data["period_days"] == 30
                
                # Verify service was called with correct parameters
                mock_analytics_service.get_cost_analysis.assert_called_once_with(
                    days=30,
                    user_id=mock_user['id']
                )
    
    @pytest.mark.asyncio
    async def test_get_system_cost_analysis_admin(self, client, admin_headers, mock_admin_user):
        """Test system-wide cost analysis by admin"""
        mock_analytics_service = Mock()
        mock_analytics_service.get_cost_analysis = AsyncMock(return_value=Mock())
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_admin_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/costs/system?days=7",
                    headers=admin_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                
                # Verify service was called without user_id (system-wide)
                mock_analytics_service.get_cost_analysis.assert_called_once_with(days=7)

    # === ENDPOINT STATISTICS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_endpoint_stats_success(self, client, auth_headers, mock_user):
        """Test successful endpoint statistics retrieval"""
        endpoint_stats = {
            '/api/v1/llm/chat/completions': 150,
            '/api/v1/rag/search': 75,
            '/api/v1/budgets': 25
        }
        
        status_codes = {
            200: 220,
            400: 20,
            401: 5,
            500: 5
        }
        
        model_stats = {
            'gpt-3.5-turbo': 100,
            'gpt-4': 50
        }
        
        mock_analytics_service = Mock()
        mock_analytics_service.endpoint_stats = endpoint_stats
        mock_analytics_service.status_codes = status_codes
        mock_analytics_service.model_stats = model_stats
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/endpoints",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert "endpoint_stats" in data["data"]
                assert "status_codes" in data["data"]
                assert "model_stats" in data["data"]

    # === USAGE TRENDS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_usage_trends_success(self, client, auth_headers, mock_user):
        """Test successful usage trends retrieval"""
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                # Mock database query results
                mock_usage_data = [
                    (datetime(2024, 1, 1).date(), 50, 5000, 500),  # date, requests, tokens, cost_cents
                    (datetime(2024, 1, 2).date(), 75, 7500, 750),
                    (datetime(2024, 1, 3).date(), 60, 6000, 600)
                ]
                
                mock_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = mock_usage_data
                
                response = await client.get(
                    "/api/v1/analytics/usage-trends?days=7",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert "trends" in data["data"]
                assert data["data"]["period_days"] == 7
                assert len(data["data"]["trends"]) == 3
                
                # Verify trend data structure
                first_trend = data["data"]["trends"][0]
                assert "date" in first_trend
                assert "requests" in first_trend
                assert "tokens" in first_trend
                assert "cost_cents" in first_trend
                assert "cost_dollars" in first_trend

    # === ANALYTICS OVERVIEW TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_analytics_overview_success(self, client, auth_headers, mock_user):
        """Test successful analytics overview retrieval"""
        mock_metrics = Mock(
            total_requests=100,
            total_cost_cents=2000,
            avg_response_time=150.5,
            error_rate=0.01,
            budget_usage_percentage=20.5
        )
        
        mock_health = Mock(
            status='healthy',
            score=98
        )
        
        mock_analytics_service = Mock()
        mock_analytics_service.get_usage_metrics = AsyncMock(return_value=mock_metrics)
        mock_analytics_service.get_system_health = AsyncMock(return_value=mock_health)
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                    mock_get_analytics.return_value = mock_analytics_service
                
                response = await client.get(
                    "/api/v1/analytics/overview",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                
                overview = data["data"]
                assert overview["total_requests"] == 100
                assert overview["total_cost_dollars"] == 20.0  # 2000 cents = $20
                assert overview["avg_response_time"] == 150.5
                assert overview["error_rate"] == 0.01
                assert overview["budget_usage_percentage"] == 20.5
                assert overview["system_health"] == "healthy"
                assert overview["health_score"] == 98

    # === MODULE ANALYTICS TESTS ===
    
    @pytest.mark.asyncio
    async def test_get_module_analytics_success(self, client, auth_headers, mock_user):
        """Test successful module analytics retrieval"""
        mock_modules = {
            'chatbot': Mock(initialized=True),
            'rag': Mock(initialized=True),
            'cache': Mock(initialized=False)
        }
        
        # Mock module with get_stats method
        mock_chatbot_stats = {'requests': 150, 'conversations': 25}
        mock_modules['chatbot'].get_stats = Mock(return_value=mock_chatbot_stats)
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.module_manager') as mock_module_manager:
                    mock_module_manager.modules = mock_modules
                
                response = await client.get(
                    "/api/v1/analytics/modules",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                assert "data" in data
                assert "modules" in data["data"]
                assert data["data"]["total_modules"] == 3
                
                # Find chatbot module in results
                chatbot_module = None
                for module in data["data"]["modules"]:
                    if module["name"] == "chatbot":
                        chatbot_module = module
                        break
                
                assert chatbot_module is not None
                assert chatbot_module["initialized"] is True
                assert chatbot_module["requests"] == 150
    
    @pytest.mark.asyncio
    async def test_get_module_analytics_with_errors(self, client, auth_headers, mock_user):
        """Test module analytics with some modules having errors"""
        mock_modules = {
            'working_module': Mock(initialized=True),
            'broken_module': Mock(initialized=True)
        }
        
        # Mock working module
        mock_modules['working_module'].get_stats = Mock(return_value={'status': 'ok'})
        
        # Mock broken module that throws error
        mock_modules['broken_module'].get_stats = Mock(side_effect=Exception("Module error"))
        
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = AsyncMock()
                mock_get_db.return_value = mock_session
                
                with patch('app.api.v1.analytics.module_manager') as mock_module_manager:
                    mock_module_manager.modules = mock_modules
                
                response = await client.get(
                    "/api/v1/analytics/modules",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                assert data["success"] is True
                
                # Find broken module in results
                broken_module = None
                for module in data["data"]["modules"]:
                    if module["name"] == "broken_module":
                        broken_module = module
                        break
                
                assert broken_module is not None
                assert "error" in broken_module
                assert "Module error" in broken_module["error"]

    # === ERROR HANDLING AND EDGE CASES ===
    
    @pytest.mark.asyncio
    async def test_analytics_service_unavailable(self, client, auth_headers, mock_user):
        """Test handling of analytics service unavailability"""
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_analytics_service') as mock_get_analytics:
                mock_get_analytics.side_effect = Exception("Analytics service unavailable")
                
                response = await client.get(
                    "/api/v1/analytics/metrics",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "unavailable" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self, client, auth_headers, mock_user):
        """Test handling of database connection errors in trends"""
        with patch('app.api.v1.analytics.get_current_user') as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch('app.api.v1.analytics.get_db') as mock_get_db:
                mock_session = Mock()
                mock_get_db.return_value = mock_session
                
                # Mock database connection error
                mock_session.query.side_effect = Exception("Database connection failed")
                
                response = await client.get(
                    "/api/v1/analytics/usage-trends",
                    headers=auth_headers
                )
                
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                data = response.json()
                assert "connection failed" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_cost_analysis_invalid_period(self, client, auth_headers, mock_user):
        """Test cost analysis with invalid period"""
        invalid_periods = [0, -5, 400]  # 0, negative, > 365
        
        for days in invalid_periods:
            response = await client.get(
                f"/api/v1/analytics/costs?days={days}",
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


"""
COVERAGE ANALYSIS FOR ANALYTICS API ENDPOINTS:

✅ Usage Metrics (4+ tests):
- Successful metrics retrieval for user
- Custom time period handling
- Invalid parameters validation
- Unauthorized access handling

✅ System Metrics - Admin Only (2+ tests):
- Admin access to system-wide metrics
- Non-admin access denial

✅ System Health (2+ tests):
- Successful health status retrieval
- Service error handling

✅ Cost Analysis (2+ tests):
- User cost analysis retrieval
- System-wide cost analysis (admin)

✅ Endpoint Statistics (1+ test):
- Endpoint usage statistics retrieval

✅ Usage Trends (1+ test):
- Daily usage trends from database

✅ Analytics Overview (1+ test):
- Combined metrics and health overview

✅ Module Analytics (2+ tests):
- Module statistics with working modules
- Module error handling

✅ Error Handling (3+ tests):
- Analytics service unavailability
- Database connection errors
- Invalid parameter handling

ESTIMATED COVERAGE IMPROVEMENT:
- Test Count: 18+ comprehensive API tests
- Business Impact: Medium-High (monitoring and insights)
- Implementation: Complete analytics API flow validation
- Phase 2 Completion: All major API endpoints now tested
"""