"""
Authentication and authorization security tests
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from datetime import datetime, timedelta
import jwt

from app.core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    verify_token,
    get_current_user
)
from app.core.config import settings
from app.models.user import User
from app.services.api_key_auth import validate_api_key, get_api_key_info
from app.services.permission_manager import permission_registry
from app.services.base_module import (
    BaseModule, 
    Permission,
    AuthenticationInterceptor,
    PermissionInterceptor,
    ValidationInterceptor,
    SecurityInterceptor
)
from app.utils.exceptions import AuthenticationError, ValidationError


class TestPasswordSecurity:
    """Test password security functions"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123!"
        hashed = get_password_hash(password)
        
        # Verify password can be verified
        assert verify_password(password, hashed) is True
        
        # Verify wrong password fails
        assert verify_password("wrong_password", hashed) is False
        
        # Verify hash is different each time
        hashed2 = get_password_hash(password)
        assert hashed != hashed2
        
        # But both verify correctly
        assert verify_password(password, hashed2) is True
    
    def test_password_hash_strength(self):
        """Test that password hashes are sufficiently strong"""
        password = "test_password_123!"
        hashed = get_password_hash(password)
        
        # Hash should be bcrypt format
        assert hashed.startswith("$2b$")
        
        # Hash should be at least 60 characters (bcrypt standard)
        assert len(hashed) >= 60
        
        # Should contain only valid bcrypt characters
        import re
        bcrypt_pattern = r"^\$2[aby]\$[0-9]{2}\$[A-Za-z0-9./]{53}$"
        assert re.match(bcrypt_pattern, hashed)


class TestJWTSecurity:
    """Test JWT token security"""
    
    def test_jwt_token_creation(self):
        """Test JWT token creation"""
        user_id = "test_user_123"
        token = create_access_token(data={"sub": user_id})
        
        # Token should be a string
        assert isinstance(token, str)
        
        # Token should have 3 parts (header.payload.signature)
        parts = token.split('.')
        assert len(parts) == 3
        
        # Should be able to decode without verification
        import base64
        import json
        
        # Decode header
        header = json.loads(base64.urlsafe_b64decode(parts[0] + '==').decode())
        assert header["alg"] == "HS256"
        assert header["typ"] == "JWT"
        
        # Decode payload
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '==').decode())
        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload
    
    def test_jwt_token_verification(self):
        """Test JWT token verification"""
        user_id = "test_user_123"
        token = create_access_token(data={"sub": user_id})
        
        # Should verify correctly
        payload = verify_token(token)
        assert payload["sub"] == user_id
        
        # Should reject invalid token
        with pytest.raises(Exception):
            verify_token("invalid_token")
        
        # Should reject tampered token
        tampered_token = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            verify_token(tampered_token)
    
    def test_jwt_token_expiration(self):
        """Test JWT token expiration"""
        user_id = "test_user_123"
        
        # Create token with short expiration
        token = create_access_token(
            data={"sub": user_id}, 
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        # Should reject expired token
        with pytest.raises(Exception):
            verify_token(token)
    
    def test_jwt_token_custom_claims(self):
        """Test JWT tokens with custom claims"""
        user_id = "test_user_123"
        custom_data = {
            "sub": user_id,
            "role": "admin",
            "permissions": ["read", "write", "admin"]
        }
        
        token = create_access_token(data=custom_data)
        payload = verify_token(token)
        
        assert payload["sub"] == user_id
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write", "admin"]


class TestAPIKeySecurity:
    """Test API key security"""
    
    @pytest.mark.asyncio
    async def test_api_key_validation(self):
        """Test API key validation"""
        # Mock API key data
        mock_api_key_data = {
            "id": "key_123",
            "user_id": "user_123",
            "key_hash": get_password_hash("test_api_key"),
            "is_active": True,
            "permissions": ["llm:chat", "modules:rag:search"],
            "rate_limit_per_minute": 100,
            "rate_limit_per_hour": 1000,
            "expires_at": None
        }
        
        with patch('app.services.api_key_auth.get_api_key_from_db', return_value=mock_api_key_data):
            # Valid API key should work
            result = await validate_api_key("test_api_key")
            assert result is True
            
            # Invalid API key should fail
            result = await validate_api_key("invalid_key")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_api_key_info_retrieval(self):
        """Test API key information retrieval"""
        mock_api_key_data = {
            "id": "key_123",
            "user_id": "user_123",
            "key_hash": get_password_hash("test_api_key"),
            "is_active": True,
            "permissions": ["llm:chat", "modules:rag:search"],
            "rate_limit_per_minute": 100,
            "rate_limit_per_hour": 1000,
            "expires_at": None
        }
        
        with patch('app.services.api_key_auth.get_api_key_from_db', return_value=mock_api_key_data):
            info = await get_api_key_info("test_api_key")
            
            assert info["id"] == "key_123"
            assert info["user_id"] == "user_123"
            assert info["is_active"] is True
            assert "llm:chat" in info["permissions"]
            assert "modules:rag:search" in info["permissions"]
    
    @pytest.mark.asyncio
    async def test_expired_api_key(self):
        """Test expired API key handling"""
        expired_api_key_data = {
            "id": "key_123",
            "user_id": "user_123", 
            "key_hash": get_password_hash("test_api_key"),
            "is_active": True,
            "permissions": ["llm:chat"],
            "expires_at": datetime.utcnow() - timedelta(days=1)  # Expired
        }
        
        with patch('app.services.api_key_auth.get_api_key_from_db', return_value=expired_api_key_data):
            result = await validate_api_key("test_api_key")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_disabled_api_key(self):
        """Test disabled API key handling"""
        disabled_api_key_data = {
            "id": "key_123",
            "user_id": "user_123",
            "key_hash": get_password_hash("test_api_key"),
            "is_active": False,  # Disabled
            "permissions": ["llm:chat"],
            "expires_at": None
        }
        
        with patch('app.services.api_key_auth.get_api_key_from_db', return_value=disabled_api_key_data):
            result = await validate_api_key("test_api_key")
            assert result is False


class TestPermissionSystem:
    """Test permission system"""
    
    def setup_method(self):
        """Set up test permissions"""
        self.permission_registry = permission_registry
        
    def test_permission_creation(self):
        """Test permission object creation"""
        perm = Permission("documents", "read", "Read documents")
        
        assert perm.resource == "documents"
        assert perm.action == "read"
        assert perm.description == "Read documents"
        assert str(perm) == "documents:read"
    
    def test_permission_checking(self):
        """Test permission checking logic"""
        user_permissions = [
            "modules:rag:search",
            "modules:rag:index",
            "llm:chat",
            "admin:*"
        ]
        
        # Exact match should work
        assert self.permission_registry.check_permission(user_permissions, "modules:rag:search")
        assert self.permission_registry.check_permission(user_permissions, "llm:chat")
        
        # Wildcard match should work
        assert self.permission_registry.check_permission(user_permissions, "admin:users")
        assert self.permission_registry.check_permission(user_permissions, "admin:settings")
        
        # Non-matching should fail
        assert not self.permission_registry.check_permission(user_permissions, "modules:rag:delete")
        assert not self.permission_registry.check_permission(user_permissions, "llm:embeddings")
    
    def test_module_permission_registration(self):
        """Test module permission registration"""
        test_permissions = [
            Permission("documents", "read", "Read documents"),
            Permission("documents", "write", "Write documents"),
            Permission("settings", "configure", "Configure settings")
        ]
        
        self.permission_registry.register_module("test_module", test_permissions)
        
        # Should be able to check module permissions
        user_perms = ["modules:test_module:documents:read", "modules:test_module:settings:*"]
        
        assert self.permission_registry.check_permission(user_perms, "modules:test_module:documents:read")
        assert self.permission_registry.check_permission(user_perms, "modules:test_module:settings:configure")
        assert not self.permission_registry.check_permission(user_perms, "modules:test_module:documents:write")


class TestModuleInterceptors:
    """Test module interceptor security"""
    
    def setup_method(self):
        """Set up test module"""
        class TestModule(BaseModule):
            def __init__(self):
                super().__init__("test_module", {})
            
            async def initialize(self):
                self.initialized = True
            
            async def cleanup(self):
                pass
            
            def get_required_permissions(self):
                return [
                    Permission("documents", "read", "Read documents"),
                    Permission("documents", "write", "Write documents")
                ]
            
            async def process_request(self, request, context):
                return {"result": "success", "data": request.get("data")}
        
        self.test_module = TestModule()
    
    @pytest.mark.asyncio
    async def test_authentication_interceptor(self):
        """Test authentication interceptor"""
        interceptor = AuthenticationInterceptor()
        
        # Should pass with valid context
        request = {"action": "test"}
        context = {"user_id": "user_123", "api_key_id": "key_123"}
        
        result_request, result_context = await interceptor.pre_process(request, context)
        assert result_request == request
        assert result_context == context
        
        # Should fail without authentication
        empty_context = {}
        with pytest.raises(AuthenticationError):
            await interceptor.pre_process(request, empty_context)
    
    @pytest.mark.asyncio  
    async def test_permission_interceptor(self):
        """Test permission interceptor"""
        interceptor = PermissionInterceptor(self.test_module)
        
        # Should pass with sufficient permissions
        request = {"action": "documents:read"}
        context = {"user_permissions": ["modules:test_module:documents:read"]}
        
        result_request, result_context = await interceptor.pre_process(request, context)
        assert result_request == request
        
        # Should fail with insufficient permissions
        context_no_perms = {"user_permissions": ["modules:other:documents:read"]}
        with pytest.raises(AuthenticationError):
            await interceptor.pre_process(request, context_no_perms)
    
    @pytest.mark.asyncio
    async def test_validation_interceptor(self):
        """Test validation interceptor"""
        interceptor = ValidationInterceptor()
        
        # Should sanitize dangerous content
        dangerous_request = {
            "content": "<script>alert('xss')</script>Hello World",
            "data": {
                "code": "eval('malicious code')",
                "safe": "This is safe content"
            }
        }
        
        sanitized_request, context = await interceptor.pre_process(dangerous_request, {})
        
        # Dangerous patterns should be removed
        assert "<script>" not in sanitized_request["content"]
        assert "eval(" not in sanitized_request["data"]["code"]
        
        # Safe content should remain
        assert "Hello World" in sanitized_request["content"]
        assert sanitized_request["data"]["safe"] == "This is safe content"
    
    @pytest.mark.asyncio
    async def test_validation_interceptor_size_limits(self):
        """Test validation interceptor size limits"""
        interceptor = ValidationInterceptor()
        
        # Test string length limit
        long_string = "A" * 20000  # Very long string
        request = {"content": long_string}
        
        sanitized_request, context = await interceptor.pre_process(request, {})
        
        # String should be truncated
        assert len(sanitized_request["content"]) <= 10000
    
    @pytest.mark.asyncio
    async def test_security_interceptor(self):
        """Test security interceptor"""
        interceptor = SecurityInterceptor()
        
        # Should add security headers to context
        request = {"action": "test"}
        context = {}
        
        result_request, result_context = await interceptor.pre_process(request, context)
        
        assert "security_headers" in result_context
        headers = result_context["security_headers"]
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
    
    @pytest.mark.asyncio
    async def test_security_interceptor_suspicious_patterns(self):
        """Test security interceptor pattern detection"""
        interceptor = SecurityInterceptor()
        
        # Test with suspicious SQL injection patterns
        suspicious_request = {
            "query": "SELECT * FROM users WHERE id = 1 UNION SELECT password FROM admin",
            "action": "search"
        }
        
        # Should not raise exception but log warning
        # In a real implementation, this might block the request
        result_request, result_context = await interceptor.pre_process(suspicious_request, {})
        
        # Request should still process (we're just logging warnings)
        assert result_request == suspicious_request


class TestEndToEndSecurity:
    """Test end-to-end security scenarios"""
    
    @pytest.mark.asyncio
    async def test_full_interceptor_chain(self):
        """Test complete interceptor chain execution"""
        class TestModule(BaseModule):
            def __init__(self):
                super().__init__("test_module", {})
            
            async def initialize(self):
                self.initialized = True
            
            async def cleanup(self):
                pass
            
            def get_required_permissions(self):
                return [Permission("test", "execute", "Execute test")]
            
            async def process_request(self, request, context):
                return {"success": True, "processed": request.get("data")}
        
        module = TestModule()
        
        # Test successful execution
        request = {
            "action": "execute",
            "data": "test data"
        }
        context = {
            "user_id": "user_123",
            "api_key_id": "key_123", 
            "user_permissions": ["modules:test_module:*"]
        }
        
        response = await module.execute_with_interceptors(request, context)
        
        assert response["success"] is True
        assert response["processed"] == "test data"
        
        # Verify metrics were updated
        assert module.metrics.requests_processed > 0
        assert module.metrics.average_response_time >= 0
    
    @pytest.mark.asyncio
    async def test_interceptor_chain_authentication_failure(self):
        """Test interceptor chain with authentication failure"""
        class TestModule(BaseModule):
            def __init__(self):
                super().__init__("test_module", {})
            
            async def initialize(self):
                self.initialized = True
            
            async def cleanup(self):
                pass
            
            def get_required_permissions(self):
                return []
            
            async def process_request(self, request, context):
                return {"success": True}
        
        module = TestModule()
        
        # Test with no authentication
        request = {"action": "execute"}
        context = {}  # No authentication
        
        with pytest.raises(AuthenticationError):
            await module.execute_with_interceptors(request, context)
        
        # Verify error metrics were updated
        assert module.metrics.total_errors > 0
        assert module.metrics.error_rate > 0
    
    @pytest.mark.asyncio
    async def test_interceptor_chain_permission_failure(self):
        """Test interceptor chain with permission failure"""
        class TestModule(BaseModule):
            def __init__(self):
                super().__init__("test_module", {})
            
            async def initialize(self):
                self.initialized = True
            
            async def cleanup(self):
                pass
            
            def get_required_permissions(self):
                return [Permission("admin", "execute", "Admin execute")]
            
            async def process_request(self, request, context):
                return {"success": True}
        
        module = TestModule()
        
        # Test with insufficient permissions
        request = {"action": "execute"}
        context = {
            "user_id": "user_123",
            "api_key_id": "key_123",
            "user_permissions": ["modules:test_module:read"]  # Insufficient
        }
        
        with pytest.raises(AuthenticationError):
            await module.execute_with_interceptors(request, context)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])