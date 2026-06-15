"""
Configuration settings for the application
"""

import os
import sys
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = os.getenv("APP_NAME", "Enclava")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "False").lower() == "true"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_LOG_LEVEL: str = os.getenv("APP_LOG_LEVEL", "INFO")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    BACKEND_INTERNAL_PORT: int = int(os.getenv("BACKEND_INTERNAL_PORT", "8000"))
    FRONTEND_INTERNAL_PORT: int = int(os.getenv("FRONTEND_INTERNAL_PORT", "3000"))

    # Detailed logging for LLM interactions
    LOG_LLM_PROMPTS: bool = (
        os.getenv("LOG_LLM_PROMPTS", "False").lower() == "true"
    )  # Set to True to log prompts and context sent to LLM

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )  # 24 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080")
    )  # 7 days
    SESSION_EXPIRE_MINUTES: int = int(
        os.getenv("SESSION_EXPIRE_MINUTES", "1440")
    )  # 24 hours
    API_KEY_PREFIX: str = os.getenv("API_KEY_PREFIX", "en_")
    # SECURITY FIX #28: Increased default bcrypt rounds from 6 to 12
    # 12 is the minimum recommended for production security
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Admin user provisioning (used only on first startup)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")

    # Base URL for deriving CORS origins
    BASE_URL: str = os.getenv("BASE_URL", "localhost")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def derive_cors_origins(cls, v, info):
        """Derive CORS origins from BASE_URL if not explicitly set"""
        if v is None:
            base_url = info.data.get("BASE_URL", "localhost")
            origins = [f"http://{base_url}", f"https://{base_url}"]
            # Add development ports if base_url is localhost (without port)
            if base_url == "localhost" or base_url.startswith("localhost:"):
                origins.extend([
                    "http://localhost:1080",  # Main nginx proxy
                    "http://localhost:3000",  # Next.js default
                    "http://localhost:3002",  # Next.js dev server
                ])
            return origins
        return v if isinstance(v, list) else [v]

    # CORS origins (derived from BASE_URL)
    CORS_ORIGINS: Optional[List[str]] = None

    # LLM Service Configuration (replaced LiteLLM)
    # LLM service configuration is now handled in app/services/llm/config.py

    # LLM Service Security (removed encryption - credentials handled by proxy)

    # Plugin System Security
    PLUGIN_ENCRYPTION_KEY: Optional[str] = os.getenv(
        "PLUGIN_ENCRYPTION_KEY"
    )  # Key for encrypting plugin secrets and configurations

    # Connector OAuth settings
    NOTION_CLIENT_ID: Optional[str] = os.getenv("NOTION_CLIENT_ID")
    NOTION_CLIENT_SECRET: Optional[str] = os.getenv("NOTION_CLIENT_SECRET")
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    SLACK_BOT_TOKEN: Optional[str] = os.getenv("SLACK_BOT_TOKEN")  # for bot-token auth (non-OAuth)
    LINEAR_API_KEY: Optional[str] = os.getenv("LINEAR_API_KEY")    # for API key auth (non-OAuth)
    CONNECTOR_CREDENTIALS_KEY: Optional[str] = os.getenv("CONNECTOR_CREDENTIALS_KEY")

    # API Keys for LLM providers (only integrated providers: privatemode, redpill)
    PRIVATEMODE_API_KEY: Optional[str] = os.getenv("PRIVATEMODE_API_KEY")
    PRIVATEMODE_PROXY_URL: str = os.getenv(
        "PRIVATEMODE_PROXY_URL", "http://privatemode-proxy:8080/v1"
    )

    # RedPill.ai (confidential computing provider)
    REDPILL_API_KEY: Optional[str] = os.getenv("REDPILL_API_KEY")
    REDPILL_BASE_URL: str = os.getenv("REDPILL_BASE_URL", "https://api.redpill.ai/v1")
    REDPILL_TEST_MODEL: str = os.getenv("REDPILL_TEST_MODEL", "phala/deepseek-v3.2")
    # Confidential model prefixes (comma-separated)
    REDPILL_CONFIDENTIAL_MODEL_PREFIXES: str = os.getenv(
        "REDPILL_CONFIDENTIAL_MODEL_PREFIXES", "phala/,tinfoil/,nearai/"
    )

    # Attestation verification endpoints
    NVIDIA_NRAS_API_URL: str = os.getenv(
        "NVIDIA_NRAS_API_URL", "https://nras.attestation.nvidia.com/v3/attest/gpu"
    )
    PHALA_TDX_VERIFIER_URL: str = os.getenv(
        "PHALA_TDX_VERIFIER_URL", "https://cloud-api.phala.network/api/v1/attestations/verify"
    )

    # Attestation scheduler configuration
    ATTESTATION_VERIFICATION_INTERVAL_SECONDS: int = int(
        os.getenv("ATTESTATION_VERIFICATION_INTERVAL_SECONDS", "300")
    )  # 5 minutes

    # Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    # Rate Limiting Configuration

    # PrivateMode Standard tier limits (organization-level, not per user)
    # These are shared across all API keys and users in the organization
    PRIVATEMODE_REQUESTS_PER_MINUTE: int = int(
        os.getenv("PRIVATEMODE_REQUESTS_PER_MINUTE", "20")
    )
    PRIVATEMODE_REQUESTS_PER_HOUR: int = int(
        os.getenv("PRIVATEMODE_REQUESTS_PER_HOUR", "1200")
    )
    PRIVATEMODE_PROMPT_TOKENS_PER_MINUTE: int = int(
        os.getenv("PRIVATEMODE_PROMPT_TOKENS_PER_MINUTE", "20000")
    )
    PRIVATEMODE_COMPLETION_TOKENS_PER_MINUTE: int = int(
        os.getenv("PRIVATEMODE_COMPLETION_TOKENS_PER_MINUTE", "10000")
    )

    # Per-user limits (additional protection on top of organization limits)
    API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "20")
    )  # Match PrivateMode
    API_RATE_LIMIT_AUTHENTICATED_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_HOUR", "1200")
    )

    # API key users (programmatic access)
    API_RATE_LIMIT_API_KEY_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_API_KEY_PER_MINUTE", "20")
    )  # Match PrivateMode
    API_RATE_LIMIT_API_KEY_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_API_KEY_PER_HOUR", "1200")
    )

    # Premium/Enterprise API keys
    API_RATE_LIMIT_PREMIUM_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_PREMIUM_PER_MINUTE", "20")
    )  # Match PrivateMode
    API_RATE_LIMIT_PREMIUM_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_PREMIUM_PER_HOUR", "1200")
    )

    # Rate limiting master switch (set to false to disable for dev/testing)
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # Anonymous/unauthenticated rate limits
    API_RATE_LIMIT_ANONYMOUS_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_ANONYMOUS_PER_MINUTE", "10")
    )
    API_RATE_LIMIT_ANONYMOUS_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_ANONYMOUS_PER_HOUR", "100")
    )

    # Strict endpoint limits (login, register, refresh)
    API_RATE_LIMIT_LOGIN_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_LOGIN_PER_MINUTE", "15")
    )
    API_RATE_LIMIT_LOGIN_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_LOGIN_PER_HOUR", "90")
    )
    API_RATE_LIMIT_REGISTER_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_REGISTER_PER_MINUTE", "9")
    )
    API_RATE_LIMIT_REGISTER_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_REGISTER_PER_HOUR", "30")
    )
    API_RATE_LIMIT_REFRESH_PER_MINUTE: int = int(
        os.getenv("API_RATE_LIMIT_REFRESH_PER_MINUTE", "5")
    )
    API_RATE_LIMIT_REFRESH_PER_HOUR: int = int(
        os.getenv("API_RATE_LIMIT_REFRESH_PER_HOUR", "30")
    )

    # Request Size Limits
    API_MAX_REQUEST_BODY_SIZE: int = int(
        os.getenv("API_MAX_REQUEST_BODY_SIZE", "10485760")
    )  # 10MB
    API_MAX_REQUEST_BODY_SIZE_PREMIUM: int = int(
        os.getenv("API_MAX_REQUEST_BODY_SIZE_PREMIUM", "52428800")
    )  # 50MB for premium

    # IP Security

    # Security Headers
    API_CSP_HEADER: str = os.getenv(
        "API_CSP_HEADER",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    )

    # Monitoring
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true"
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))

    # Alerting Configuration
    ALERT_EMAIL_ENABLED: bool = os.getenv("ALERT_EMAIL_ENABLED", "False").lower() == "true"
    ALERT_SMTP_HOST: Optional[str] = os.getenv("ALERT_SMTP_HOST")
    ALERT_SMTP_PORT: int = int(os.getenv("ALERT_SMTP_PORT", "587"))
    ALERT_SMTP_USERNAME: Optional[str] = os.getenv("ALERT_SMTP_USERNAME")
    ALERT_SMTP_PASSWORD: Optional[str] = os.getenv("ALERT_SMTP_PASSWORD")
    ALERT_FROM_EMAIL: str = os.getenv("ALERT_FROM_EMAIL", "alerts@enclava.com")
    ALERT_TO_EMAILS: Union[str, List[str]] = os.getenv("ALERT_TO_EMAILS", "")
    ALERT_SLACK_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_SLACK_WEBHOOK_URL")
    ALERT_PAGERDUTY_KEY: Optional[str] = os.getenv("ALERT_PAGERDUTY_KEY")

    # File uploads
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB

    # Module configuration
    MODULES_CONFIG_PATH: str = os.getenv("MODULES_CONFIG_PATH", "config/modules.yaml")

    # RAG Embedding Configuration
    RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE: int = int(
        os.getenv("RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE", "12")
    )
    RAG_EMBEDDING_BATCH_SIZE: int = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "3"))
    RAG_EMBEDDING_RETRY_COUNT: int = int(os.getenv("RAG_EMBEDDING_RETRY_COUNT", "3"))
    RAG_EMBEDDING_RETRY_DELAYS: str = os.getenv(
        "RAG_EMBEDDING_RETRY_DELAYS", "1,2,4,8,16"
    )
    RAG_EMBEDDING_DELAY_BETWEEN_BATCHES: float = float(
        os.getenv("RAG_EMBEDDING_DELAY_BETWEEN_BATCHES", "1.0")
    )
    RAG_EMBEDDING_DELAY_PER_REQUEST: float = float(
        os.getenv("RAG_EMBEDDING_DELAY_PER_REQUEST", "0.5")
    )
    RAG_ALLOW_FALLBACK_EMBEDDINGS: bool = (
        os.getenv("RAG_ALLOW_FALLBACK_EMBEDDINGS", "True").lower() == "true"
    )
    RAG_WARN_ON_FALLBACK: bool = (
        os.getenv("RAG_WARN_ON_FALLBACK", "True").lower() == "true"
    )
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    RAG_DOCUMENT_PROCESSING_TIMEOUT: int = int(
        os.getenv("RAG_DOCUMENT_PROCESSING_TIMEOUT", "300")
    )
    RAG_EMBEDDING_GENERATION_TIMEOUT: int = int(
        os.getenv("RAG_EMBEDDING_GENERATION_TIMEOUT", "120")
    )
    RAG_INDEXING_TIMEOUT: int = int(os.getenv("RAG_INDEXING_TIMEOUT", "120"))

    # Plugin configuration
    PLUGINS_DIR: str = os.getenv("PLUGINS_DIR", "/plugins")
    PLUGINS_CONFIG_PATH: str = os.getenv("PLUGINS_CONFIG_PATH", "config/plugins.yaml")
    PLUGIN_REPOSITORY_URL: str = os.getenv(
        "PLUGIN_REPOSITORY_URL", "https://plugins.enclava.com"
    )

    # Logging
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        # Ignore unknown environment variables to avoid validation errors
        # when optional/deprecated flags are present in .env
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """
        Validate critical security settings at startup.

        Security mitigations:
        - #1: Ensure secrets are present and have minimum strength
        - #6: Validate JWT secret is present and strong
        - #53: Prevent APP_DEBUG in production
        """
        errors = []
        warnings = []

        # Check if running in production
        is_production = self.APP_ENV.lower() in ("production", "prod")

        # #53: Prevent APP_DEBUG in production
        if is_production and self.APP_DEBUG:
            errors.append(
                "SECURITY ERROR: APP_DEBUG=true is not allowed in production. "
                "Set APP_DEBUG=false or APP_ENV to a non-production value."
            )

        # #6: Validate JWT secret presence and strength
        if not self.JWT_SECRET:
            errors.append(
                "SECURITY ERROR: JWT_SECRET is required. "
                "Generate a secure random secret of at least 32 characters."
            )
        elif len(self.JWT_SECRET) < 32:
            if is_production:
                errors.append(
                    f"SECURITY ERROR: JWT_SECRET is too short ({len(self.JWT_SECRET)} chars). "
                    "Production requires at least 32 characters."
                )
            else:
                warnings.append(
                    f"SECURITY WARNING: JWT_SECRET is short ({len(self.JWT_SECRET)} chars). "
                    "Use at least 32 characters for production."
                )

        # Check for default/weak JWT secret patterns
        weak_secrets = ["secret", "changeme", "development", "test", "jwt_secret"]
        if self.JWT_SECRET and self.JWT_SECRET.lower() in weak_secrets:
            if is_production:
                errors.append(
                    "SECURITY ERROR: JWT_SECRET appears to be a default/weak value. "
                    "Generate a secure random secret."
                )
            else:
                warnings.append(
                    "SECURITY WARNING: JWT_SECRET appears to be a default/weak value."
                )

        # #1: Check for required API keys in production
        if is_production:
            if not self.PRIVATEMODE_API_KEY and not self.REDPILL_API_KEY:
                warnings.append(
                    "SECURITY WARNING: No LLM provider API keys configured. "
                    "At least one of PRIVATEMODE_API_KEY or REDPILL_API_KEY should be set."
                )

        # Validate bcrypt rounds (#28)
        if self.BCRYPT_ROUNDS < 10:
            if is_production:
                warnings.append(
                    f"SECURITY WARNING: BCRYPT_ROUNDS={self.BCRYPT_ROUNDS} is low for production. "
                    "Consider using 12 or higher."
                )

        # Print warnings
        for warning in warnings:
            print(f"\033[93m{warning}\033[0m", file=sys.stderr)

        # Fail on errors
        if errors:
            for error in errors:
                print(f"\033[91m{error}\033[0m", file=sys.stderr)
            raise ValueError(
                "Security validation failed. See above errors. "
                "Fix the configuration before starting the application."
            )

        return self


# Global settings instance
settings = Settings()
