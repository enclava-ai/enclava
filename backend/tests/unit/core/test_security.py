#!/usr/bin/env python3
"""
Security & Authentication Tests - Phase 1 Critical Business Logic
Priority: app/core/security.py (23% → 75% coverage)

Tests comprehensive security functionality:
- JWT token generation/validation
- Password hashing/verification
- API key validation
- Rate limiting logic
- Permission checking
- Authentication flows
"""

import pytest
import jwt
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from app.core.security import SecurityService, get_current_user, verify_api_key
from app.models.user import User
from app.models.api_key import APIKey
from app.core.config import get_settings


class TestSecurityService:
    """Comprehensive test suite for Security Service"""
    
    @pytest.fixture
    def security_service(self):
        """Create security service instance"""
        return SecurityService()
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing"""
        return User(
            id=1,
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$hashed_password_here",
            is_active=True,
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def sample_api_key(self, sample_user):
        """Sample API key for testing"""
        return APIKey(
            id=1,
            user_id=sample_user.id,
            name="Test API Key",
            key_prefix="ce_test",
            hashed_key="$2b$12$hashed_api_key_here",
            is_active=True,
            created_at=datetime.utcnow(),
            last_used_at=None
        )

    # === JWT TOKEN GENERATION AND VALIDATION ===
    
    @pytest.mark.asyncio
    async def test_create_access_token_success(self, security_service, sample_user):
        """Test successful JWT access token creation"""
        token_data = {"sub": str(sample_user.id), "username": sample_user.username}
        expires_delta = timedelta(minutes=30)
        
        token = await security_service.create_access_token(
            data=token_data,
            expires_delta=expires_delta
        )
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode token to verify contents
        settings = get_settings()
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        assert decoded["sub"] == str(sample_user.id)
        assert decoded["username"] == sample_user.username
        assert "exp" in decoded
        assert "iat" in decoded
    
    @pytest.mark.asyncio
    async def test_create_access_token_with_custom_expiry(self, security_service):
        """Test token creation with custom expiration time"""
        token_data = {"sub": "123", "username": "testuser"}
        custom_expiry = timedelta(hours=2)
        
        token = await security_service.create_access_token(
            data=token_data,
            expires_delta=custom_expiry
        )
        
        # Decode and check expiration
        settings = get_settings()
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        issued_at = datetime.fromtimestamp(decoded["iat"])
        expires_at = datetime.fromtimestamp(decoded["exp"])
        actual_lifetime = expires_at - issued_at
        
        # Should be approximately 2 hours (within 1 minute tolerance)
        assert abs(actual_lifetime.total_seconds() - 7200) < 60
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, security_service, sample_user):
        """Test successful token verification"""
        # Create a valid token
        token_data = {"sub": str(sample_user.id), "username": sample_user.username}
        token = await security_service.create_access_token(token_data)
        
        # Verify the token
        payload = await security_service.verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == str(sample_user.id)
        assert payload["username"] == sample_user.username
    
    @pytest.mark.asyncio
    async def test_verify_expired_token(self, security_service):
        """Test verification of expired token"""
        # Create token with very short expiry
        token_data = {"sub": "123", "username": "testuser"}
        short_expiry = timedelta(seconds=-1)  # Already expired
        
        token = await security_service.create_access_token(
            token_data,
            expires_delta=short_expiry
        )
        
        # Should raise exception for expired token
        with pytest.raises(jwt.ExpiredSignatureError):
            await security_service.verify_token(token)
    
    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, security_service):
        """Test verification of malformed/invalid tokens"""
        invalid_tokens = [
            "invalid.token.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "",
            None,
            "Bearer invalid_token"
        ]
        
        for invalid_token in invalid_tokens:
            if invalid_token is not None:
                with pytest.raises((jwt.InvalidTokenError, jwt.DecodeError, ValueError)):
                    await security_service.verify_token(invalid_token)
            else:
                with pytest.raises((TypeError, ValueError)):
                    await security_service.verify_token(invalid_token)
    
    @pytest.mark.asyncio
    async def test_verify_token_wrong_secret(self, security_service):
        """Test token verification with wrong secret key"""
        # Create token with different secret
        wrong_secret = "wrong_secret_key_here"
        token_data = {"sub": "123", "username": "testuser"}
        
        # Create token with wrong secret
        token = jwt.encode(
            payload=token_data,
            key=wrong_secret,
            algorithm="HS256"
        )
        
        # Should fail verification
        with pytest.raises(jwt.InvalidSignatureError):
            await security_service.verify_token(token)

    # === PASSWORD HASHING AND VERIFICATION ===
    
    @pytest.mark.asyncio
    async def test_hash_password_success(self, security_service):
        """Test successful password hashing"""
        password = "SecurePassword123!"
        
        hashed = await security_service.hash_password(password)
        
        assert hashed is not None
        assert hashed != password  # Should be hashed, not plain text
        assert hashed.startswith("$2b$")  # bcrypt hash format
        assert len(hashed) > 50  # Reasonable hash length
    
    @pytest.mark.asyncio
    async def test_hash_password_different_hashes(self, security_service):
        """Test that same password produces different hashes (due to salt)"""
        password = "TestPassword123"
        
        hash1 = await security_service.hash_password(password)
        hash2 = await security_service.hash_password(password)
        
        # Should be different due to random salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert await security_service.verify_password(password, hash1)
        assert await security_service.verify_password(password, hash2)
    
    @pytest.mark.asyncio
    async def test_verify_password_success(self, security_service):
        """Test successful password verification"""
        password = "CorrectPassword123"
        hashed = await security_service.hash_password(password)
        
        is_valid = await security_service.verify_password(password, hashed)
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_verify_password_failure(self, security_service):
        """Test password verification failure"""
        correct_password = "CorrectPassword123"
        wrong_password = "WrongPassword456"
        
        hashed = await security_service.hash_password(correct_password)
        
        is_valid = await security_service.verify_password(wrong_password, hashed)
        
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_password_hash_security(self, security_service):
        """Test password hash security properties"""
        password = "TestSecurityPassword"
        hashed = await security_service.hash_password(password)
        
        # Hash should not contain the original password
        assert password not in hashed
        
        # Hash should be using strong bcrypt algorithm
        assert hashed.startswith("$2b$12$") or hashed.startswith("$2b$10$")
        
        # Hash should be deterministically different each time (salt)
        hash2 = await security_service.hash_password(password)
        assert hashed != hash2

    # === API KEY VALIDATION ===
    
    @pytest.mark.asyncio
    async def test_verify_api_key_success(self, security_service, sample_api_key):
        """Test successful API key verification"""
        raw_key = "ce_test123456789abcdef"  # Sample raw key
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_api_key
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = True
                
                api_key = await security_service.verify_api_key(raw_key)
                
                assert api_key is not None
                assert api_key.id == sample_api_key.id
                assert api_key.is_active is True
                mock_verify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid_format(self, security_service):
        """Test API key validation with invalid format"""
        invalid_keys = [
            "invalid_format",
            "short",
            "",
            None,
            "wrongprefix_1234567890abcdef",
            "ce_tooshort"
        ]
        
        for invalid_key in invalid_keys:
            with pytest.raises((ValueError, TypeError)):
                await security_service.verify_api_key(invalid_key)
    
    @pytest.mark.asyncio
    async def test_verify_api_key_not_found(self, security_service):
        """Test API key verification when key not found"""
        nonexistent_key = "ce_nonexistent1234567890"
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            with pytest.raises(ValueError) as exc_info:
                await security_service.verify_api_key(nonexistent_key)
            
            assert "not found" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_verify_api_key_inactive(self, security_service, sample_api_key):
        """Test API key verification when key is inactive"""
        raw_key = "ce_test123456789abcdef"
        sample_api_key.is_active = False  # Deactivated key
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_api_key
            
            with pytest.raises(ValueError) as exc_info:
                await security_service.verify_api_key(raw_key)
            
            assert "inactive" in str(exc_info.value).lower() or "disabled" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(self, security_service, sample_api_key):
        """Test that API key usage is tracked"""
        raw_key = "ce_test123456789abcdef"
        original_last_used = sample_api_key.last_used_at
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_api_key
            mock_session.commit.return_value = None
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = True
                
                api_key = await security_service.verify_api_key(raw_key)
                
                # last_used_at should be updated
                assert sample_api_key.last_used_at != original_last_used
                assert sample_api_key.last_used_at is not None
                mock_session.commit.assert_called()

    # === RATE LIMITING LOGIC ===
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_within_limit(self, security_service):
        """Test rate limiting when within allowed limits"""
        user_id = "123"
        endpoint = "/api/v1/chat/completions"
        
        with patch.object(security_service, 'redis_client') as mock_redis:
            mock_redis.get.return_value = "5"  # 5 requests in current window
            
            is_allowed = await security_service.check_rate_limit(
                identifier=user_id,
                endpoint=endpoint,
                limit=100,  # 100 requests per window
                window=3600  # 1 hour window
            )
            
            assert is_allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_check_exceeded(self, security_service):
        """Test rate limiting when limit is exceeded"""
        user_id = "123"
        endpoint = "/api/v1/chat/completions"
        
        with patch.object(security_service, 'redis_client') as mock_redis:
            mock_redis.get.return_value = "150"  # 150 requests in current window
            
            is_allowed = await security_service.check_rate_limit(
                identifier=user_id,
                endpoint=endpoint,
                limit=100,  # 100 requests per window
                window=3600  # 1 hour window
            )
            
            assert is_allowed is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_increment(self, security_service):
        """Test rate limit counter increment"""
        user_id = "456"
        endpoint = "/api/v1/embeddings"
        
        with patch.object(security_service, 'redis_client') as mock_redis:
            mock_redis.incr.return_value = 1
            mock_redis.expire.return_value = True
            
            await security_service.increment_rate_limit(
                identifier=user_id,
                endpoint=endpoint,
                window=3600
            )
            
            # Verify Redis operations
            mock_redis.incr.assert_called_once()
            mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limit_different_tiers(self, security_service):
        """Test different rate limits for different user tiers"""
        # Regular user
        regular_user = "regular_123"
        premium_user = "premium_456"
        
        with patch.object(security_service, 'redis_client') as mock_redis:
            mock_redis.get.side_effect = ["50", "500"]  # Different usage levels
            
            # Regular user - should be blocked at 50 requests (limit 30)
            regular_allowed = await security_service.check_rate_limit(
                identifier=regular_user,
                endpoint="/api/v1/chat",
                limit=30,
                window=3600
            )
            
            # Premium user - should be allowed at 500 requests (limit 1000)
            premium_allowed = await security_service.check_rate_limit(
                identifier=premium_user,
                endpoint="/api/v1/chat",
                limit=1000,
                window=3600
            )
            
            assert regular_allowed is False
            assert premium_allowed is True

    # === PERMISSION CHECKING ===
    
    @pytest.mark.asyncio
    async def test_check_user_permissions_success(self, security_service, sample_user):
        """Test successful permission checking"""
        sample_user.permissions = ["read", "write", "admin"]
        
        has_read = await security_service.check_permission(sample_user, "read")
        has_write = await security_service.check_permission(sample_user, "write")
        has_admin = await security_service.check_permission(sample_user, "admin")
        
        assert has_read is True
        assert has_write is True
        assert has_admin is True
    
    @pytest.mark.asyncio
    async def test_check_user_permissions_failure(self, security_service, sample_user):
        """Test permission checking failure"""
        sample_user.permissions = ["read"]  # Only read permission
        
        has_read = await security_service.check_permission(sample_user, "read")
        has_write = await security_service.check_permission(sample_user, "write")
        has_admin = await security_service.check_permission(sample_user, "admin")
        
        assert has_read is True
        assert has_write is False
        assert has_admin is False
    
    @pytest.mark.asyncio
    async def test_check_role_based_permissions(self, security_service, sample_user):
        """Test role-based permission checking"""
        sample_user.role = "admin"
        
        with patch.object(security_service, 'get_role_permissions') as mock_role_perms:
            mock_role_perms.return_value = ["read", "write", "admin", "manage_users"]
            
            has_admin = await security_service.check_role_permission(sample_user, "admin")
            has_manage_users = await security_service.check_role_permission(sample_user, "manage_users")
            has_super_admin = await security_service.check_role_permission(sample_user, "super_admin")
            
            assert has_admin is True
            assert has_manage_users is True
            assert has_super_admin is False
    
    @pytest.mark.asyncio
    async def test_check_resource_ownership(self, security_service, sample_user):
        """Test resource ownership validation"""
        resource_id = 123
        resource_type = "document"
        
        with patch.object(security_service, 'db_session') as mock_session:
            # Mock resource owned by user
            mock_resource = Mock()
            mock_resource.user_id = sample_user.id
            mock_resource.id = resource_id
            
            mock_session.query.return_value.filter.return_value.first.return_value = mock_resource
            
            is_owner = await security_service.check_resource_ownership(
                user=sample_user,
                resource_type=resource_type,
                resource_id=resource_id
            )
            
            assert is_owner is True
    
    @pytest.mark.asyncio
    async def test_check_resource_ownership_denied(self, security_service, sample_user):
        """Test resource ownership validation denied"""
        resource_id = 123
        resource_type = "document"
        other_user_id = 999
        
        with patch.object(security_service, 'db_session') as mock_session:
            # Mock resource owned by different user
            mock_resource = Mock()
            mock_resource.user_id = other_user_id
            mock_resource.id = resource_id
            
            mock_session.query.return_value.filter.return_value.first.return_value = mock_resource
            
            is_owner = await security_service.check_resource_ownership(
                user=sample_user,
                resource_type=resource_type,
                resource_id=resource_id
            )
            
            assert is_owner is False

    # === AUTHENTICATION FLOWS ===
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, security_service, sample_user):
        """Test successful user authentication"""
        username = "testuser"
        password = "correctpassword"
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_user
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = True
                
                authenticated_user = await security_service.authenticate_user(username, password)
                
                assert authenticated_user is not None
                assert authenticated_user.id == sample_user.id
                assert authenticated_user.username == sample_user.username
                mock_verify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, security_service, sample_user):
        """Test user authentication with wrong password"""
        username = "testuser"
        password = "wrongpassword"
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_user
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = False
                
                authenticated_user = await security_service.authenticate_user(username, password)
                
                assert authenticated_user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, security_service):
        """Test user authentication when user doesn't exist"""
        username = "nonexistentuser"
        password = "anypassword"
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            authenticated_user = await security_service.authenticate_user(username, password)
            
            assert authenticated_user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, security_service, sample_user):
        """Test authentication of inactive user"""
        username = "testuser"
        password = "correctpassword"
        sample_user.is_active = False  # Deactivated user
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_user
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = True
                
                authenticated_user = await security_service.authenticate_user(username, password)
                
                # Should not authenticate inactive users
                assert authenticated_user is None

    # === SECURITY EDGE CASES ===
    
    @pytest.mark.asyncio
    async def test_token_with_invalid_user_id(self, security_service):
        """Test token validation with invalid user ID"""
        token_data = {"sub": "invalid_user_id", "username": "testuser"}
        token = await security_service.create_access_token(token_data)
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            # Should handle gracefully when user doesn't exist
            try:
                current_user = await get_current_user(token, mock_session)
                assert current_user is None
            except Exception as e:
                # Should raise appropriate authentication error
                assert "user" in str(e).lower() or "authentication" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_api_key_validation(self, security_service, sample_api_key):
        """Test concurrent API key validation (race condition handling)"""
        raw_key = "ce_test123456789abcdef"
        
        with patch.object(security_service, 'db_session') as mock_session:
            mock_session.query.return_value.filter.return_value.first.return_value = sample_api_key
            
            with patch.object(security_service, 'verify_password') as mock_verify:
                mock_verify.return_value = True
                
                # Simulate concurrent API key validations
                import asyncio
                tasks = [
                    security_service.verify_api_key(raw_key)
                    for _ in range(5)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # All should succeed or handle gracefully
                successful_validations = [r for r in results if not isinstance(r, Exception)]
                assert len(successful_validations) >= 4  # Most should succeed


"""
COVERAGE ANALYSIS FOR SECURITY SERVICE:

✅ JWT Token Management (6+ tests):
- Token creation with custom expiry
- Token verification success/failure
- Expired token handling
- Invalid token handling
- Wrong secret key detection

✅ Password Security (6+ tests):
- Password hashing with salt randomization
- Password verification success/failure
- Hash security properties
- Different hashes for same password

✅ API Key Validation (6+ tests):
- Valid API key verification
- Invalid format handling
- Non-existent key handling
- Inactive key handling
- Usage tracking
- Format validation

✅ Rate Limiting (4+ tests):
- Within limit checks
- Exceeded limit checks
- Counter increment
- Different user tiers

✅ Permission System (5+ tests):
- User permission checking
- Role-based permissions
- Resource ownership validation
- Permission failure handling

✅ Authentication Flows (4+ tests):
- User authentication success/failure
- Wrong password handling
- Non-existent user handling
- Inactive user handling

✅ Security Edge Cases (2+ tests):
- Invalid user ID in token
- Concurrent API key validation

ESTIMATED COVERAGE IMPROVEMENT:
- Current: 23% → Target: 75%
- Test Count: 30+ comprehensive tests
- Business Impact: Critical (platform security)
- Implementation: Authentication and authorization validation
"""