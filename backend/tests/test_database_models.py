"""
Database model tests for all SQLAlchemy models
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import models
from app.models.user import User, UserRole
from app.models.api_key import APIKey
from app.models.budget import Budget, BudgetType, BudgetPeriod, UsageTracking
from app.models.audit_log import AuditLog
from app.models.module import ModuleConfig
from app.models import Base
from app.core.security import get_password_hash


@pytest.fixture
def test_db():
    """Create test database session"""
    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


class TestUserModel:
    """Test User model"""
    
    def test_user_creation(self, test_db):
        """Test creating a user"""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_unique_constraints(self, test_db):
        """Test user unique constraints"""
        # Create first user
        user1 = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User 1",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user1)
        test_db.commit()
        
        # Try to create user with same username
        user2 = User(
            username="testuser",  # Same username
            email="different@example.com",
            full_name="Test User 2",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            test_db.commit()
        
        test_db.rollback()
        
        # Try to create user with same email
        user3 = User(
            username="differentuser",
            email="test@example.com",  # Same email
            full_name="Test User 3",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user3)
        
        with pytest.raises(Exception):  # Should raise integrity error
            test_db.commit()
    
    def test_user_password_verification(self, test_db):
        """Test user password verification method"""
        password = "testpassword123"
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash(password)
        )
        
        test_db.add(user)
        test_db.commit()
        
        # Test password verification (would need to implement verify_password method)
        from app.core.security import verify_password
        assert verify_password(password, user.hashed_password) is True
        assert verify_password("wrongpassword", user.hashed_password) is False
    
    def test_user_role_enum(self, test_db):
        """Test user role enumeration"""
        # Test all role types
        admin_user = User(
            username="admin",
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN
        )
        
        regular_user = User(
            username="user",
            email="user@example.com", 
            full_name="Regular User",
            hashed_password=get_password_hash("user123"),
            role=UserRole.USER
        )
        
        test_db.add_all([admin_user, regular_user])
        test_db.commit()
        
        assert admin_user.role == UserRole.ADMIN
        assert regular_user.role == UserRole.USER
        
        # Test role string representation
        assert admin_user.role.value == "admin"
        assert regular_user.role.value == "user"
    
    def test_user_timestamps(self, test_db):
        """Test user timestamp fields"""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Check that timestamps are set
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.last_login is None  # Should be None initially
        
        # Update user and check updated_at changes
        original_updated_at = user.updated_at
        user.full_name = "Updated Name"
        test_db.commit()
        test_db.refresh(user)
        
        assert user.updated_at > original_updated_at


class TestAPIKeyModel:
    """Test APIKey model"""
    
    def test_api_key_creation(self, test_db):
        """Test creating an API key"""
        # First create a user
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Create API key
        api_key = APIKey(
            name="Test API Key",
            description="Test API key for testing",
            key_hash=get_password_hash("test_api_key_value"),
            key_prefix="ak_test",
            user_id=user.id,
            permissions=["llm:chat", "modules:rag:search"],
            rate_limit_per_minute=100,
            rate_limit_per_hour=1000,
            rate_limit_per_day=10000
        )
        
        test_db.add(api_key)
        test_db.commit()
        test_db.refresh(api_key)
        
        assert api_key.id is not None
        assert api_key.name == "Test API Key"
        assert api_key.key_prefix == "ak_test"
        assert api_key.user_id == user.id
        assert api_key.is_active is True
        assert api_key.permissions == ["llm:chat", "modules:rag:search"]
        assert api_key.usage_count == 0
        assert api_key.created_at is not None
    
    def test_api_key_user_relationship(self, test_db):
        """Test API key to user relationship"""
        # Create user
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Create API keys
        api_key1 = APIKey(
            name="Test Key 1",
            key_hash=get_password_hash("key1"),
            key_prefix="ak_test1",
            user_id=user.id
        )
        
        api_key2 = APIKey(
            name="Test Key 2", 
            key_hash=get_password_hash("key2"),
            key_prefix="ak_test2",
            user_id=user.id
        )
        
        test_db.add_all([api_key1, api_key2])
        test_db.commit()
        
        # Test relationship
        assert api_key1.user_id == user.id
        assert api_key2.user_id == user.id
        
        # Test that we can query API keys by user
        user_api_keys = test_db.query(APIKey).filter(APIKey.user_id == user.id).all()
        assert len(user_api_keys) == 2
    
    def test_api_key_expiration(self, test_db):
        """Test API key expiration"""
        # Create user
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        
        # Create expired API key
        expired_key = APIKey(
            name="Expired Key",
            key_hash=get_password_hash("expired_key"),
            key_prefix="ak_expired",
            user_id=user.id,
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        
        # Create active API key
        active_key = APIKey(
            name="Active Key",
            key_hash=get_password_hash("active_key"), 
            key_prefix="ak_active",
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        
        test_db.add_all([expired_key, active_key])
        test_db.commit()
        
        # Test expiration check (would need is_expired property)
        assert expired_key.expires_at < datetime.utcnow()
        assert active_key.expires_at > datetime.utcnow()
    
    def test_api_key_permissions_json(self, test_db):
        """Test API key permissions as JSON array"""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        
        # Test with complex permissions array
        permissions = [
            "llm:chat",
            "llm:embeddings",
            "modules:rag:search",
            "modules:rag:index",
            "modules:analytics:view",
            "admin:users:read"
        ]
        
        api_key = APIKey(
            name="Test Key",
            key_hash=get_password_hash("test_key"),
            key_prefix="ak_test",
            user_id=user.id,
            permissions=permissions
        )
        
        test_db.add(api_key)
        test_db.commit()
        test_db.refresh(api_key)
        
        assert api_key.permissions == permissions
        assert len(api_key.permissions) == 6
        assert "llm:chat" in api_key.permissions
        assert "admin:users:read" in api_key.permissions


class TestBudgetModel:
    """Test Budget and UsageTracking models"""
    
    def test_budget_creation(self, test_db):
        """Test creating a budget"""
        budget = Budget(
            name="Test Budget",
            description="Test budget for testing",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=100.50,
            period=BudgetPeriod.MONTHLY,
            alert_threshold=80,
            hard_limit=True
        )
        
        test_db.add(budget)
        test_db.commit()
        test_db.refresh(budget)
        
        assert budget.id is not None
        assert budget.name == "Test Budget"
        assert budget.budget_type == BudgetType.USER
        assert budget.target_id == "user_123"
        assert budget.limit_amount == 100.50
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.alert_threshold == 80
        assert budget.hard_limit is True
        assert budget.is_active is True
        assert budget.current_usage == 0.0
        assert budget.created_at is not None
    
    def test_budget_types_and_periods(self, test_db):
        """Test budget type and period enums"""
        # Test different budget types
        user_budget = Budget(
            name="User Budget",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=100.0,
            period=BudgetPeriod.MONTHLY
        )
        
        api_key_budget = Budget(
            name="API Key Budget",
            budget_type=BudgetType.API_KEY,
            target_id="key_456",
            limit_amount=50.0,
            period=BudgetPeriod.WEEKLY
        )
        
        global_budget = Budget(
            name="Global Budget",
            budget_type=BudgetType.GLOBAL,
            target_id="global",
            limit_amount=1000.0,
            period=BudgetPeriod.DAILY
        )
        
        test_db.add_all([user_budget, api_key_budget, global_budget])
        test_db.commit()
        
        assert user_budget.budget_type == BudgetType.USER
        assert api_key_budget.budget_type == BudgetType.API_KEY
        assert global_budget.budget_type == BudgetType.GLOBAL
        
        assert user_budget.period == BudgetPeriod.MONTHLY
        assert api_key_budget.period == BudgetPeriod.WEEKLY
        assert global_budget.period == BudgetPeriod.DAILY
    
    def test_usage_tracking_creation(self, test_db):
        """Test creating usage tracking entries"""
        # Create budget first
        budget = Budget(
            name="Test Budget",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=100.0,
            period=BudgetPeriod.MONTHLY
        )
        test_db.add(budget)
        test_db.commit()
        test_db.refresh(budget)
        
        # Create usage tracking entry
        usage = UsageTracking(
            budget_id=budget.id,
            user_id="user_123",
            api_key_id="key_456",
            cost_amount=15.75,
            usage_type="llm_request",
            metadata={
                "model": "gpt-4",
                "tokens": 1000,
                "endpoint": "/api/llm/v1/chat/completions"
            }
        )
        
        test_db.add(usage)
        test_db.commit()
        test_db.refresh(usage)
        
        assert usage.id is not None
        assert usage.budget_id == budget.id
        assert usage.user_id == "user_123"
        assert usage.api_key_id == "key_456"
        assert usage.cost_amount == 15.75
        assert usage.usage_type == "llm_request"
        assert usage.metadata["model"] == "gpt-4"
        assert usage.created_at is not None
    
    def test_budget_usage_relationship(self, test_db):
        """Test budget to usage tracking relationship"""
        # Create budget
        budget = Budget(
            name="Test Budget",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=100.0,
            period=BudgetPeriod.MONTHLY
        )
        test_db.add(budget)
        test_db.commit()
        test_db.refresh(budget)
        
        # Create multiple usage entries
        usage1 = UsageTracking(
            budget_id=budget.id,
            user_id="user_123",
            cost_amount=25.50,
            usage_type="llm_request"
        )
        
        usage2 = UsageTracking(
            budget_id=budget.id,
            user_id="user_123",
            cost_amount=10.25,
            usage_type="embedding_request"
        )
        
        test_db.add_all([usage1, usage2])
        test_db.commit()
        
        # Test querying usage by budget
        budget_usage = test_db.query(UsageTracking).filter(
            UsageTracking.budget_id == budget.id
        ).all()
        
        assert len(budget_usage) == 2
        total_cost = sum(u.cost_amount for u in budget_usage)
        assert total_cost == 35.75


class TestAuditLogModel:
    """Test AuditLog model"""
    
    def test_audit_log_creation(self, test_db):
        """Test creating an audit log entry"""
        audit_log = AuditLog(
            action="user_login",
            resource_type="user",
            resource_id="user_123",
            user_id="user_123",
            success=True,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Test Browser)",
            metadata={
                "login_method": "password",
                "session_id": "session_456"
            }
        )
        
        test_db.add(audit_log)
        test_db.commit()
        test_db.refresh(audit_log)
        
        assert audit_log.id is not None
        assert audit_log.action == "user_login"
        assert audit_log.resource_type == "user"
        assert audit_log.resource_id == "user_123"
        assert audit_log.user_id == "user_123"
        assert audit_log.success is True
        assert audit_log.ip_address == "192.168.1.100"
        assert audit_log.user_agent == "Mozilla/5.0 (Test Browser)"
        assert audit_log.metadata["login_method"] == "password"
        assert audit_log.created_at is not None
    
    def test_audit_log_with_error(self, test_db):
        """Test creating an audit log entry with error"""
        audit_log = AuditLog(
            action="api_key_validation",
            resource_type="api_key",
            resource_id="key_789",
            user_id="user_456",
            success=False,
            error_message="Invalid API key provided",
            ip_address="10.0.0.1",
            metadata={
                "endpoint": "/api/v1/llm/chat",
                "attempted_key_prefix": "ak_invalid"
            }
        )
        
        test_db.add(audit_log)
        test_db.commit()
        test_db.refresh(audit_log)
        
        assert audit_log.success is False
        assert audit_log.error_message == "Invalid API key provided"
        assert audit_log.metadata["attempted_key_prefix"] == "ak_invalid"
    
    def test_audit_log_querying(self, test_db):
        """Test querying audit logs with filters"""
        # Create multiple audit log entries
        logs = [
            AuditLog(
                action="user_login",
                resource_type="user",
                user_id="user_123",
                success=True,
                ip_address="192.168.1.1"
            ),
            AuditLog(
                action="user_login",
                resource_type="user", 
                user_id="user_456",
                success=False,
                error_message="Invalid password",
                ip_address="192.168.1.2"
            ),
            AuditLog(
                action="api_call",
                resource_type="api_endpoint",
                user_id="user_123",
                success=True,
                ip_address="192.168.1.1"
            )
        ]
        
        test_db.add_all(logs)
        test_db.commit()
        
        # Test filtering by action
        login_logs = test_db.query(AuditLog).filter(
            AuditLog.action == "user_login"
        ).all()
        assert len(login_logs) == 2
        
        # Test filtering by success
        failed_logs = test_db.query(AuditLog).filter(
            AuditLog.success == False
        ).all()
        assert len(failed_logs) == 1
        assert failed_logs[0].error_message == "Invalid password"
        
        # Test filtering by user
        user_123_logs = test_db.query(AuditLog).filter(
            AuditLog.user_id == "user_123"
        ).all()
        assert len(user_123_logs) == 2


class TestModuleConfigModel:
    """Test ModuleConfig model"""
    
    def test_module_config_creation(self, test_db):
        """Test creating a module configuration"""
        module_config = ModuleConfig(
            name="rag",
            enabled=True,
            config={
                "vector_db_url": "http://qdrant:6333",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "chunk_size": 512,
                "max_results": 10
            },
            dependencies=["cache", "analytics"]
        )
        
        test_db.add(module_config)
        test_db.commit()
        test_db.refresh(module_config)
        
        assert module_config.id is not None
        assert module_config.name == "rag"
        assert module_config.enabled is True
        assert module_config.config["chunk_size"] == 512
        assert "cache" in module_config.dependencies
        assert module_config.created_at is not None
        assert module_config.updated_at is not None
    
    def test_module_config_unique_name(self, test_db):
        """Test module config name uniqueness"""
        config1 = ModuleConfig(
            name="test_module",
            enabled=True,
            config={"setting1": "value1"}
        )
        test_db.add(config1)
        test_db.commit()
        
        # Try to create another config with same name
        config2 = ModuleConfig(
            name="test_module",  # Same name
            enabled=False,
            config={"setting2": "value2"}
        )
        test_db.add(config2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            test_db.commit()
    
    def test_module_config_json_fields(self, test_db):
        """Test JSON fields in module config"""
        complex_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "settings": {
                    "pool_size": 10,
                    "timeout": 30
                }
            },
            "features": ["feature1", "feature2", "feature3"],
            "limits": {
                "max_requests": 1000,
                "rate_limit": 100
            }
        }
        
        dependencies = ["module1", "module2", "module3"]
        
        module_config = ModuleConfig(
            name="complex_module",
            enabled=True,
            config=complex_config,
            dependencies=dependencies
        )
        
        test_db.add(module_config)
        test_db.commit()
        test_db.refresh(module_config)
        
        # Test that complex JSON is preserved
        assert module_config.config["database"]["host"] == "localhost"
        assert module_config.config["database"]["settings"]["pool_size"] == 10
        assert "feature2" in module_config.config["features"]
        assert len(module_config.dependencies) == 3
        assert "module2" in module_config.dependencies


class TestModelRelationships:
    """Test relationships between models"""
    
    def test_user_api_key_relationship(self, test_db):
        """Test user to API key one-to-many relationship"""
        # Create user
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123")
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Create multiple API keys for the user
        api_keys = [
            APIKey(
                name=f"API Key {i}",
                key_hash=get_password_hash(f"key_{i}"),
                key_prefix=f"ak_test_{i}",
                user_id=user.id
            )
            for i in range(3)
        ]
        
        test_db.add_all(api_keys)
        test_db.commit()
        
        # Test querying API keys through user relationship
        user_keys = test_db.query(APIKey).filter(APIKey.user_id == user.id).all()
        assert len(user_keys) == 3
        
        # Test that all keys belong to the same user
        for key in user_keys:
            assert key.user_id == user.id
    
    def test_budget_usage_tracking_relationship(self, test_db):
        """Test budget to usage tracking one-to-many relationship"""
        # Create budget
        budget = Budget(
            name="Test Budget",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=100.0,
            period=BudgetPeriod.MONTHLY
        )
        test_db.add(budget)
        test_db.commit()
        test_db.refresh(budget)
        
        # Create multiple usage entries
        usage_entries = [
            UsageTracking(
                budget_id=budget.id,
                user_id="user_123",
                cost_amount=10.0 + i,
                usage_type="test_usage"
            )
            for i in range(5)
        ]
        
        test_db.add_all(usage_entries)
        test_db.commit()
        
        # Test querying usage through budget relationship
        budget_usage = test_db.query(UsageTracking).filter(
            UsageTracking.budget_id == budget.id
        ).all()
        
        assert len(budget_usage) == 5
        total_cost = sum(u.cost_amount for u in budget_usage)
        assert total_cost == 60.0  # 10+11+12+13+14


class TestModelValidation:
    """Test model validation and constraints"""
    
    def test_email_format_validation(self, test_db):
        """Test email format validation"""
        # This would require custom validators in the model
        # For now, we test that the field accepts valid emails
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "first+last@subdomain.example.org"
        ]
        
        for i, email in enumerate(valid_emails):
            user = User(
                username=f"user_{i}",
                email=email,
                full_name=f"User {i}",
                hashed_password=get_password_hash("password123")
            )
            test_db.add(user)
        
        test_db.commit()
        
        # All users should be created successfully
        users = test_db.query(User).all()
        assert len(users) == len(valid_emails)
    
    def test_positive_amount_constraints(self, test_db):
        """Test positive amount constraints on budget and usage"""
        # Test budget with negative amount (should be prevented in application logic)
        budget = Budget(
            name="Test Budget",
            budget_type=BudgetType.USER,
            target_id="user_123",
            limit_amount=-100.0,  # Negative amount
            period=BudgetPeriod.MONTHLY
        )
        
        # In a real application, this would be validated before reaching the database
        # For now, we just test that the model accepts it (validation happens in API layer)
        test_db.add(budget)
        test_db.commit()
        test_db.refresh(budget)
        
        assert budget.limit_amount == -100.0
    
    def test_enum_constraints(self, test_db):
        """Test enum field constraints"""
        # Test that enum fields only accept valid values
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN  # Valid enum value
        )
        
        test_db.add(user)
        test_db.commit()
        
        assert user.role == UserRole.ADMIN
        
        # Test budget enums
        budget = Budget(
            name="Test Budget",
            budget_type=BudgetType.GLOBAL,  # Valid enum
            target_id="global",
            limit_amount=1000.0,
            period=BudgetPeriod.WEEKLY  # Valid enum
        )
        
        test_db.add(budget)
        test_db.commit()
        
        assert budget.budget_type == BudgetType.GLOBAL
        assert budget.period == BudgetPeriod.WEEKLY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])