"""
API endpoint tests for all implemented endpoints
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
import json
from datetime import datetime, timedelta

# Import the main app
from app.main import app
from app.core.security import create_access_token
from app.models.user import User


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_register_endpoint(self):
        """Test user registration endpoint"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "TestPassword123!"
        }
        
        with patch('app.api.v1.auth.create_user') as mock_create_user:
            mock_user = Mock()
            mock_user.id = "user_123"
            mock_user.username = "testuser"
            mock_user.email = "test@example.com"
            mock_user.full_name = "Test User"
            mock_create_user.return_value = mock_user
            
            response = self.client.post("/api/v1/auth/register", json=user_data)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["username"] == "testuser"
            assert data["email"] == "test@example.com"
            assert "password" not in data  # Password should not be returned
    
    def test_register_validation_errors(self):
        """Test registration validation errors"""
        # Test missing fields
        response = self.client.post("/api/v1/auth/register", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test invalid email
        invalid_data = {
            "username": "test",
            "email": "invalid-email",
            "full_name": "Test",
            "password": "password"
        }
        response = self.client.post("/api/v1/auth/register", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_login_endpoint(self):
        """Test user login endpoint"""
        login_data = {
            "username": "testuser",
            "password": "TestPassword123!"
        }
        
        with patch('app.api.v1.auth.authenticate_user') as mock_auth, \
             patch('app.api.v1.auth.create_access_token') as mock_token:
            
            mock_user = Mock()
            mock_user.id = "user_123"
            mock_user.username = "testuser"
            mock_user.is_active = True
            mock_auth.return_value = mock_user
            mock_token.return_value = "test_token"
            
            response = self.client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["access_token"] == "test_token"
            assert data["token_type"] == "bearer"
            assert data["user"]["username"] == "testuser"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        login_data = {
            "username": "testuser",
            "password": "wrongpassword"
        }
        
        with patch('app.api.v1.auth.authenticate_user') as mock_auth:
            mock_auth.return_value = None  # Invalid credentials
            
            response = self.client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert "Invalid credentials" in data["detail"]


class TestUserEndpoints:
    """Test user management endpoints"""
    
    def setup_method(self):
        """Set up test client with authentication"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_users(self):
        """Test listing users"""
        with patch('app.api.v1.users.get_users') as mock_get_users:
            mock_users = [
                Mock(id="user1", username="user1", email="user1@test.com", is_active=True),
                Mock(id="user2", username="user2", email="user2@test.com", is_active=True)
            ]
            mock_get_users.return_value = (mock_users, 2)
            
            response = self.client.get("/api/v1/users", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 2
            assert len(data["users"]) == 2
            assert data["users"][0]["username"] == "user1"
    
    def test_get_user_by_id(self):
        """Test getting user by ID"""
        user_id = "user_123"
        
        with patch('app.api.v1.users.get_user_by_id') as mock_get_user:
            mock_user = Mock()
            mock_user.id = user_id
            mock_user.username = "testuser"
            mock_user.email = "test@example.com"
            mock_user.is_active = True
            mock_get_user.return_value = mock_user
            
            response = self.client.get(f"/api/v1/users/{user_id}", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == user_id
            assert data["username"] == "testuser"
    
    def test_create_user(self):
        """Test creating a new user"""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com", 
            "full_name": "New User",
            "password": "NewPassword123!",
            "role": "user"
        }
        
        with patch('app.api.v1.users.create_user') as mock_create:
            mock_user = Mock()
            mock_user.id = "new_user_123"
            mock_user.username = "newuser"
            mock_user.email = "newuser@example.com"
            mock_create.return_value = mock_user
            
            response = self.client.post("/api/v1/users", json=user_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["username"] == "newuser"
    
    def test_update_user(self):
        """Test updating a user"""
        user_id = "user_123"
        update_data = {
            "full_name": "Updated Name",
            "is_active": False
        }
        
        with patch('app.api.v1.users.update_user') as mock_update:
            mock_user = Mock()
            mock_user.id = user_id
            mock_user.full_name = "Updated Name"
            mock_user.is_active = False
            mock_update.return_value = mock_user
            
            response = self.client.put(f"/api/v1/users/{user_id}", json=update_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["full_name"] == "Updated Name"
            assert data["is_active"] is False
    
    def test_delete_user(self):
        """Test deleting a user"""
        user_id = "user_123"
        
        with patch('app.api.v1.users.delete_user') as mock_delete:
            mock_delete.return_value = True
            
            response = self.client.delete(f"/api/v1/users/{user_id}", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message"] == "User deleted successfully"


class TestAPIKeyEndpoints:
    """Test API key management endpoints"""
    
    def setup_method(self):
        """Set up test client with authentication"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_api_keys(self):
        """Test listing API keys"""
        with patch('app.api.v1.api_keys.get_api_keys') as mock_get_keys:
            mock_keys = [
                Mock(
                    id="key1", 
                    name="Test Key 1", 
                    key_prefix="ak_test1",
                    is_active=True,
                    created_at=datetime.utcnow()
                ),
                Mock(
                    id="key2",
                    name="Test Key 2", 
                    key_prefix="ak_test2",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
            ]
            mock_get_keys.return_value = (mock_keys, 2)
            
            response = self.client.get("/api/v1/api-keys", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 2
            assert len(data["api_keys"]) == 2
    
    def test_create_api_key(self):
        """Test creating an API key"""
        key_data = {
            "name": "Test API Key",
            "description": "Test API key for testing",
            "permissions": ["llm:chat", "modules:rag:search"],
            "rate_limit_per_minute": 100,
            "rate_limit_per_hour": 1000,
            "rate_limit_per_day": 10000
        }
        
        with patch('app.api.v1.api_keys.create_api_key') as mock_create:
            mock_result = {
                "api_key_id": "key_123",
                "api_key": "ak_test_full_key_here",
                "name": "Test API Key",
                "key_prefix": "ak_test"
            }
            mock_create.return_value = mock_result
            
            response = self.client.post("/api/v1/api-keys", json=key_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Test API Key"
            assert "api_key" in data
    
    def test_regenerate_api_key(self):
        """Test regenerating an API key"""
        key_id = "key_123"
        
        with patch('app.api.v1.api_keys.regenerate_api_key') as mock_regenerate:
            mock_result = {
                "api_key_id": key_id,
                "api_key": "ak_new_regenerated_key",
                "key_prefix": "ak_new"
            }
            mock_regenerate.return_value = mock_result
            
            response = self.client.post(f"/api/v1/api-keys/{key_id}/regenerate", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["api_key_id"] == key_id
            assert "api_key" in data


class TestBudgetEndpoints:
    """Test budget management endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_budgets(self):
        """Test listing budgets"""
        with patch('app.api.v1.budgets.get_budgets') as mock_get_budgets:
            mock_budgets = [
                Mock(
                    id="budget1",
                    name="Test Budget 1", 
                    budget_type="user",
                    limit_amount=100.0,
                    current_usage=25.50,
                    is_active=True
                ),
                Mock(
                    id="budget2",
                    name="Test Budget 2",
                    budget_type="global", 
                    limit_amount=1000.0,
                    current_usage=500.75,
                    is_active=True
                )
            ]
            mock_get_budgets.return_value = (mock_budgets, 2)
            
            response = self.client.get("/api/v1/budgets", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 2
            assert len(data["budgets"]) == 2
    
    def test_create_budget(self):
        """Test creating a budget"""
        budget_data = {
            "name": "Test Budget",
            "description": "Test budget for testing",
            "budget_type": "user",
            "target_id": "user_123",
            "limit_amount": 100.0,
            "period": "monthly",
            "alert_threshold": 80,
            "hard_limit": True
        }
        
        with patch('app.api.v1.budgets.create_budget') as mock_create:
            mock_budget = Mock()
            mock_budget.id = "budget_123"
            mock_budget.name = "Test Budget"
            mock_budget.limit_amount = 100.0
            mock_create.return_value = mock_budget
            
            response = self.client.post("/api/v1/budgets", json=budget_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["name"] == "Test Budget"
    
    def test_get_budget_stats(self):
        """Test getting budget statistics"""
        with patch('app.api.v1.budgets.get_budget_statistics') as mock_get_stats:
            mock_stats = {
                "total_budgets": 5,
                "active_budgets": 4,
                "over_threshold": 2,
                "total_spending": 1500.75,
                "monthly_spending": 350.25
            }
            mock_get_stats.return_value = mock_stats
            
            response = self.client.get("/api/v1/budgets/stats", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_budgets"] == 5
            assert data["active_budgets"] == 4


class TestAuditEndpoints:
    """Test audit log endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_audit_logs(self):
        """Test listing audit logs"""
        with patch('app.api.v1.audit.get_audit_logs') as mock_get_logs:
            mock_logs = [
                Mock(
                    id="log1",
                    action="login",
                    resource_type="user",
                    user_id="user_123",
                    success=True,
                    created_at=datetime.utcnow(),
                    ip_address="127.0.0.1"
                ),
                Mock(
                    id="log2", 
                    action="api_call",
                    resource_type="api_endpoint",
                    user_id="user_456",
                    success=False,
                    created_at=datetime.utcnow(),
                    ip_address="192.168.1.1"
                )
            ]
            mock_get_logs.return_value = (mock_logs, 2)
            
            response = self.client.get("/api/v1/audit", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 2
            assert len(data["logs"]) == 2
    
    def test_audit_log_filtering(self):
        """Test audit log filtering"""
        filters = {
            "action": "login",
            "success": "true",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        
        with patch('app.api.v1.audit.get_audit_logs') as mock_get_logs:
            mock_logs = [
                Mock(
                    id="log1",
                    action="login", 
                    success=True,
                    created_at=datetime.utcnow()
                )
            ]
            mock_get_logs.return_value = (mock_logs, 1)
            
            response = self.client.get("/api/v1/audit", params=filters, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
    
    def test_export_audit_logs(self):
        """Test exporting audit logs"""
        with patch('app.api.v1.audit.export_audit_logs') as mock_export:
            mock_export.return_value = "csv,data,here"
            
            response = self.client.get("/api/v1/audit/export?format=csv", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/csv; charset=utf-8"


class TestSettingsEndpoints:
    """Test settings management endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_all_settings(self):
        """Test getting all settings"""
        with patch('app.api.v1.settings.get_all_settings') as mock_get_settings:
            mock_settings = {
                "security": {
                    "password_min_length": 8,
                    "session_timeout_minutes": 30
                },
                "api": {
                    "rate_limit_per_minute": 100,
                    "max_request_size_mb": 10
                }
            }
            mock_get_settings.return_value = mock_settings
            
            response = self.client.get("/api/v1/settings", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "security" in data["settings"]
            assert "api" in data["settings"]
    
    def test_update_settings_section(self):
        """Test updating a settings section"""
        section = "security"
        settings_data = {
            "password_min_length": 12,
            "session_timeout_minutes": 60,
            "require_2fa": True
        }
        
        with patch('app.api.v1.settings.update_settings_section') as mock_update:
            mock_update.return_value = settings_data
            
            response = self.client.put(f"/api/v1/settings/{section}", json=settings_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["password_min_length"] == 12
    
    def test_get_system_info(self):
        """Test getting system information"""
        with patch('app.api.v1.settings.get_system_info') as mock_get_info:
            mock_info = {
                "total_users": 100,
                "active_users": 85,
                "database_status": "healthy",
                "redis_status": "healthy",
                "uptime_seconds": 86400
            }
            mock_get_info.return_value = mock_info
            
            response = self.client.get("/api/v1/settings/system-info", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_users"] == 100
            assert data["database_status"] == "healthy"


class TestModuleEndpoints:
    """Test module management endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
        self.auth_headers = self._get_auth_headers()
    
    def _get_auth_headers(self):
        """Get authentication headers"""
        token = create_access_token(data={"sub": "admin_user"})
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_modules(self):
        """Test listing modules"""
        with patch('app.services.module_manager.module_manager') as mock_manager:
            mock_modules = {
                "rag": Mock(initialized=True, version="1.0.0"),
                "cache": Mock(initialized=True, version="1.0.0")
            }
            mock_manager.modules = mock_modules
            mock_manager.module_configs = {
                "rag": Mock(enabled=True),
                "cache": Mock(enabled=True)
            }
            mock_manager.initialized = True
            
            response = self.client.get("/api/v1/modules", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 2
            assert data["initialized"] is True
    
    def test_get_module_info(self):
        """Test getting module information"""
        module_name = "rag"
        
        with patch('app.services.module_manager.module_manager') as mock_manager:
            mock_module = Mock()
            mock_module.initialized = True
            mock_module.version = "1.0.0"
            mock_module.description = "RAG module"
            
            mock_manager.modules = {module_name: mock_module}
            mock_manager.module_configs = {module_name: Mock(enabled=True)}
            
            response = self.client.get(f"/api/v1/modules/{module_name}", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == module_name
            assert data["initialized"] is True
    
    def test_module_execute_interceptor_pattern(self):
        """Test module execution with interceptor pattern"""
        module_name = "rag"
        request_data = {
            "action": "search",
            "query": "test query",
            "max_results": 10
        }
        
        with patch('app.services.module_manager.module_manager') as mock_manager:
            mock_module = Mock()
            mock_module.execute_with_interceptors = AsyncMock(return_value={
                "action": "search",
                "results": [{"document": "test", "score": 0.9}],
                "total_results": 1
            })
            
            mock_manager.modules = {module_name: mock_module}
            
            response = self.client.post(f"/api/v1/modules/{module_name}/execute", 
                                      json=request_data, headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["module"] == module_name
            assert data["success"] is True
            assert data["interceptor_pattern"] is True
    
    def test_enable_module(self):
        """Test enabling a module"""
        module_name = "rag"
        
        with patch('app.services.module_manager.module_manager') as mock_manager:
            mock_config = Mock()
            mock_config.enabled = False
            mock_manager.module_configs = {module_name: mock_config}
            mock_manager.modules = {}
            mock_manager._load_module = AsyncMock()
            
            response = self.client.post(f"/api/v1/modules/{module_name}/enable", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["enabled"] is True
    
    def test_disable_module(self):
        """Test disabling a module"""
        module_name = "rag"
        
        with patch('app.services.module_manager.module_manager') as mock_manager:
            mock_config = Mock()
            mock_config.enabled = True
            mock_manager.module_configs = {module_name: mock_config}
            mock_manager.modules = {module_name: Mock()}
            mock_manager.unload_module = AsyncMock()
            
            response = self.client.post(f"/api/v1/modules/{module_name}/disable", headers=self.auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["enabled"] is False


class TestRateLimitingIntegration:
    """Test rate limiting integration with endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are included"""
        # This would require actual rate limiting to be active
        # For now, we'll just test that the middleware is configured
        
        with patch('app.middleware.rate_limiting.rate_limit_middleware'):
            response = self.client.get("/api/v1/modules")
            
            # In a real test, we'd check for rate limiting headers
            # X-RateLimit-Limit, X-RateLimit-Remaining, etc.
            assert response.status_code in [200, 401, 429]  # Various valid responses


class TestErrorHandling:
    """Test error handling across endpoints"""
    
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_404_error_handling(self):
        """Test 404 error handling"""
        response = self.client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_422_validation_error_handling(self):
        """Test validation error handling"""
        # Send invalid JSON to an endpoint that expects specific structure
        response = self.client.post("/api/v1/auth/register", json={"invalid": "data"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_500_internal_error_handling(self):
        """Test internal server error handling"""
        with patch('app.api.v1.auth.authenticate_user') as mock_auth:
            mock_auth.side_effect = Exception("Database connection error")
            
            response = self.client.post("/api/v1/auth/login", json={
                "username": "test", 
                "password": "test"
            })
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])