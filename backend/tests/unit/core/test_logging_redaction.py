"""
Tests for the logging redaction functionality.

SECURITY FIX P3-24: Verify that sensitive data is properly redacted from logs.
"""

import pytest

from app.core.logging import (
    SensitiveDataRedactor,
    get_redactor,
    redact_sensitive_data,
)


class TestSensitiveDataRedactor:
    """Test the SensitiveDataRedactor class."""

    @pytest.fixture
    def redactor(self):
        """Create a fresh redactor instance for each test."""
        return SensitiveDataRedactor()

    # Test fully redacted keys
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "PASSWORD",
            "Password",
            "secret",
            "jwt_secret",
            "access_token",
            "refresh_token",
            "authorization",
            "cookie",
            "credit_card",
            "ssn",
            "pgpassword",
            "db_password",
            "aws_secret_access_key",
        ],
    )
    def test_fully_redacted_keys(self, redactor, key):
        """Test that sensitive keys are fully redacted."""
        data = {key: "sensitive_value_123"}
        result = redactor.redact(data)
        assert result[key] == "[REDACTED]"

    # Test pattern-based redaction
    @pytest.mark.parametrize(
        "key",
        [
            "user_password",
            "admin_password",
            "my_secret_key",
            "api_token",
            "bearer_token",
            "auth_credentials",
            "db_credentials",
        ],
    )
    def test_pattern_based_redaction(self, redactor, key):
        """Test that keys matching patterns are redacted."""
        data = {key: "sensitive_value_123"}
        result = redactor.redact(data)
        assert result[key] == "[REDACTED]"

    # Test partially redacted keys
    def test_email_partial_redaction(self, redactor):
        """Test email addresses show only domain."""
        data = {"email": "user@example.com"}
        result = redactor.redact(data)
        assert result["email"] == "***@example.com"

    def test_email_address_partial_redaction(self, redactor):
        """Test email_address key is partially redacted."""
        data = {"email_address": "admin@company.org"}
        result = redactor.redact(data)
        assert result["email_address"] == "***@company.org"

    def test_api_key_partial_redaction(self, redactor):
        """Test API keys show last 4 characters."""
        data = {"api_key": "en_abc123xyz789"}
        result = redactor.redact(data)
        assert result["api_key"] == "****9789"

    def test_key_prefix_partial_redaction(self, redactor):
        """Test key_prefix shows last 4 characters."""
        data = {"key_prefix": "en_abcd"}
        result = redactor.redact(data)
        assert result["key_prefix"] == "****abcd"

    def test_username_partial_redaction(self, redactor):
        """Test usernames show first 2 characters."""
        data = {"username": "johndoe"}
        result = redactor.redact(data)
        assert result["username"] == "jo***"

    def test_ip_address_partial_redaction(self, redactor):
        """Test IP addresses show first octet only."""
        data = {"ip_address": "192.168.1.100"}
        result = redactor.redact(data)
        assert result["ip_address"] == "192.***.***"

    def test_phone_partial_redaction(self, redactor):
        """Test phone numbers show last 4 digits."""
        data = {"phone": "+1-555-123-4567"}
        result = redactor.redact(data)
        assert result["phone"] == "***4567"

    # Test nested structures
    def test_nested_dict_redaction(self, redactor):
        """Test redaction in nested dictionaries."""
        data = {
            "user": {
                "email": "test@test.com",
                "password": "secret123",
                "profile": {
                    "phone": "555-1234",
                },
            }
        }
        result = redactor.redact(data)
        assert result["user"]["email"] == "***@test.com"
        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["profile"]["phone"] == "***1234"

    def test_list_redaction(self, redactor):
        """Test redaction in lists."""
        data = {
            "users": [
                {"email": "user1@test.com", "password": "pass1"},
                {"email": "user2@test.com", "password": "pass2"},
            ]
        }
        result = redactor.redact(data)
        assert result["users"][0]["email"] == "***@test.com"
        assert result["users"][0]["password"] == "[REDACTED]"
        assert result["users"][1]["email"] == "***@test.com"
        assert result["users"][1]["password"] == "[REDACTED]"

    # Test value pattern detection
    def test_jwt_in_string_value(self, redactor):
        """Test JWT tokens are redacted from string values."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        data = {"message": f"Token is {jwt}"}
        result = redactor.redact(data)
        assert "eyJ" not in result["message"]
        assert "[JWT_REDACTED]" in result["message"]

    def test_bearer_token_in_string(self, redactor):
        """Test Bearer tokens are redacted from strings."""
        data = {"header": "Bearer abc123xyz789token"}
        result = redactor.redact(data)
        assert "abc123" not in result["header"]
        assert "Bearer [REDACTED]" in result["header"]

    def test_api_key_pattern_in_string(self, redactor):
        """Test API key patterns are redacted from strings."""
        data = {"log": "User used key en_abcdefghij1234567890123"}
        result = redactor.redact(data)
        assert "en_abcdefghij" not in result["log"]
        assert "[API_KEY_REDACTED]" in result["log"]

    # Test non-sensitive data preservation
    def test_non_sensitive_data_preserved(self, redactor):
        """Test that non-sensitive data is not modified."""
        data = {
            "name": "John Doe",
            "age": 30,
            "active": True,
            "score": 95.5,
            "tags": ["admin", "user"],
        }
        result = redactor.redact(data)
        assert result == data

    def test_short_strings_preserved(self, redactor):
        """Test that short strings are not checked for patterns."""
        data = {"code": "ABC123"}
        result = redactor.redact(data)
        assert result["code"] == "ABC123"

    # Test disabled redactor
    def test_disabled_redactor(self):
        """Test that disabled redactor passes data through unchanged."""
        redactor = SensitiveDataRedactor(enabled=False)
        data = {"password": "secret123", "email": "test@test.com"}
        result = redactor.redact(data)
        assert result == data

    # Test None and empty handling
    def test_none_value(self, redactor):
        """Test None values are handled correctly."""
        data = {"password": None}
        result = redactor.redact(data)
        assert result["password"] == "[REDACTED]"  # Key triggers redaction

    def test_empty_string(self, redactor):
        """Test empty strings are preserved."""
        data = {"name": ""}
        result = redactor.redact(data)
        assert result["name"] == ""


class TestGlobalRedactionFunctions:
    """Test the global redaction functions."""

    def test_redact_sensitive_data_function(self):
        """Test the global redact_sensitive_data function."""
        data = {"email": "test@example.com", "password": "secret"}
        result = redact_sensitive_data(data)
        assert result["email"] == "***@example.com"
        assert result["password"] == "[REDACTED]"

    def test_get_redactor_returns_instance(self):
        """Test get_redactor returns a SensitiveDataRedactor instance."""
        redactor = get_redactor()
        assert isinstance(redactor, SensitiveDataRedactor)


class TestRealWorldScenarios:
    """Test real-world logging scenarios."""

    @pytest.fixture
    def redactor(self):
        return SensitiveDataRedactor()

    def test_login_attempt_log(self, redactor):
        """Test redaction of login attempt logs."""
        log_data = {
            "event": "LOGIN_ATTEMPT",
            "email": "user@company.com",
            "password": "MySecretPass123!",
            "ip_address": "203.0.113.50",
            "user_agent": "Mozilla/5.0",
        }
        result = redactor.redact(log_data)
        assert result["email"] == "***@company.com"
        assert result["password"] == "[REDACTED]"
        assert result["ip_address"] == "203.***.***"
        assert result["user_agent"] == "Mozilla/5.0"

    def test_api_request_log(self, redactor):
        """Test redaction of API request logs."""
        log_data = {
            "method": "POST",
            "path": "/api/v1/chat/completions",
            "api_key": "en_live_abc123xyz789def456",
            "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig",
            "request_body": {
                "messages": [{"role": "user", "content": "Hello"}],
            },
        }
        result = redactor.redact(log_data)
        assert result["api_key"] == "****f456"
        assert result["authorization"] == "[REDACTED]"
        assert result["method"] == "POST"
        assert result["request_body"]["messages"][0]["content"] == "Hello"

    def test_database_connection_log(self, redactor):
        """Test redaction of database connection logs."""
        log_data = {
            "event": "DB_CONNECT",
            "host": "db.example.com",
            "port": 5432,
            "database": "myapp",
            "username": "appuser",
            "db_password": "super_secret_db_pass",
            "pgpassword": "another_secret",
        }
        result = redactor.redact(log_data)
        assert result["username"] == "ap***"
        assert result["db_password"] == "[REDACTED]"
        assert result["pgpassword"] == "[REDACTED]"
        assert result["host"] == "db.example.com"

    def test_user_registration_log(self, redactor):
        """Test redaction of user registration logs."""
        log_data = {
            "event": "USER_REGISTERED",
            "user": {
                "email": "newuser@gmail.com",
                "username": "newuser123",
                "password": "InitialPass123!",
                "phone_number": "+1-555-867-5309",
            },
            "verification_token": "abc123xyz789",
        }
        result = redactor.redact(log_data)
        assert result["user"]["email"] == "***@gmail.com"
        assert result["user"]["username"] == "ne***"
        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["phone_number"] == "***5309"
        assert result["verification_token"] == "[REDACTED]"  # Contains 'token'
