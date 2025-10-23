"""
Configuration settings for the application
"""

import os
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = os.getenv("APP_NAME", "Enclava")
    APP_DEBUG: bool = os.getenv("APP_DEBUG", "False").lower() == "true"
    APP_LOG_LEVEL: str = os.getenv("APP_LOG_LEVEL", "INFO")
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    BACKEND_INTERNAL_PORT: int = int(os.getenv("BACKEND_INTERNAL_PORT", "8000"))
    FRONTEND_INTERNAL_PORT: int = int(os.getenv("FRONTEND_INTERNAL_PORT", "3000"))
    
    # Detailed logging for LLM interactions
    LOG_LLM_PROMPTS: bool = os.getenv("LOG_LLM_PROMPTS", "False").lower() == "true"  # Set to True to log prompts and context sent to LLM
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days
    SESSION_EXPIRE_MINUTES: int = int(os.getenv("SESSION_EXPIRE_MINUTES", "1440"))  # 24 hours
    API_KEY_PREFIX: str = os.getenv("API_KEY_PREFIX", "en_")
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "6"))  # Bcrypt work factor - lower for production performance
    
    # Admin user provisioning (used only on first startup)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")
    
    # Base URL for deriving CORS origins
    BASE_URL: str = os.getenv("BASE_URL", "localhost")
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def derive_cors_origins(cls, v, info):
        """Derive CORS origins from BASE_URL if not explicitly set"""
        if v is None:
            base_url = info.data.get('BASE_URL', 'localhost')
            # Support both HTTP and HTTPS for production environments
            return [f"http://{base_url}", f"https://{base_url}"]
        return v if isinstance(v, list) else [v]
    
    # CORS origins (derived from BASE_URL)
    CORS_ORIGINS: Optional[List[str]] = None
    
    # LLM Service Configuration (replaced LiteLLM)
    # LLM service configuration is now handled in app/services/llm/config.py
    
    # LLM Service Security (removed encryption - credentials handled by proxy)
    
    # Plugin System Security
    PLUGIN_ENCRYPTION_KEY: Optional[str] = os.getenv("PLUGIN_ENCRYPTION_KEY")  # Key for encrypting plugin secrets and configurations
    
    # API Keys for LLM providers
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    PRIVATEMODE_API_KEY: Optional[str] = os.getenv("PRIVATEMODE_API_KEY")
    PRIVATEMODE_PROXY_URL: str = os.getenv("PRIVATEMODE_PROXY_URL", "http://privatemode-proxy:8080/v1")
    
    # Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    
      
    # Rate Limiting Configuration
  
    # PrivateMode Standard tier limits (organization-level, not per user)
    # These are shared across all API keys and users in the organization
    PRIVATEMODE_REQUESTS_PER_MINUTE: int = int(os.getenv("PRIVATEMODE_REQUESTS_PER_MINUTE", "20"))
    PRIVATEMODE_REQUESTS_PER_HOUR: int = int(os.getenv("PRIVATEMODE_REQUESTS_PER_HOUR", "1200"))
    PRIVATEMODE_PROMPT_TOKENS_PER_MINUTE: int = int(os.getenv("PRIVATEMODE_PROMPT_TOKENS_PER_MINUTE", "20000"))
    PRIVATEMODE_COMPLETION_TOKENS_PER_MINUTE: int = int(os.getenv("PRIVATEMODE_COMPLETION_TOKENS_PER_MINUTE", "10000"))

    # Per-user limits (additional protection on top of organization limits)
    API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "20"))  # Match PrivateMode
    API_RATE_LIMIT_AUTHENTICATED_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_HOUR", "1200"))

    # API key users (programmatic access)
    API_RATE_LIMIT_API_KEY_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_API_KEY_PER_MINUTE", "20"))  # Match PrivateMode
    API_RATE_LIMIT_API_KEY_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_API_KEY_PER_HOUR", "1200"))

    # Premium/Enterprise API keys
    API_RATE_LIMIT_PREMIUM_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_PREMIUM_PER_MINUTE", "20"))  # Match PrivateMode
    API_RATE_LIMIT_PREMIUM_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_PREMIUM_PER_HOUR", "1200"))
  
    # Request Size Limits
    API_MAX_REQUEST_BODY_SIZE: int = int(os.getenv("API_MAX_REQUEST_BODY_SIZE", "10485760"))  # 10MB
    API_MAX_REQUEST_BODY_SIZE_PREMIUM: int = int(os.getenv("API_MAX_REQUEST_BODY_SIZE_PREMIUM", "52428800"))  # 50MB for premium
    
    # IP Security
    
    # Security Headers
    API_CSP_HEADER: str = os.getenv("API_CSP_HEADER", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true"
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))
    
    # File uploads
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB
    
    # Module configuration
    MODULES_CONFIG_PATH: str = os.getenv("MODULES_CONFIG_PATH", "config/modules.yaml")

    # RAG Embedding Configuration
    RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("RAG_EMBEDDING_MAX_REQUESTS_PER_MINUTE", "12"))
    RAG_EMBEDDING_BATCH_SIZE: int = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "3"))
    RAG_EMBEDDING_RETRY_COUNT: int = int(os.getenv("RAG_EMBEDDING_RETRY_COUNT", "3"))
    RAG_EMBEDDING_RETRY_DELAYS: str = os.getenv("RAG_EMBEDDING_RETRY_DELAYS", "1,2,4,8,16")
    RAG_EMBEDDING_DELAY_BETWEEN_BATCHES: float = float(os.getenv("RAG_EMBEDDING_DELAY_BETWEEN_BATCHES", "1.0"))
    RAG_EMBEDDING_DELAY_PER_REQUEST: float = float(os.getenv("RAG_EMBEDDING_DELAY_PER_REQUEST", "0.5"))
    RAG_ALLOW_FALLBACK_EMBEDDINGS: bool = os.getenv("RAG_ALLOW_FALLBACK_EMBEDDINGS", "True").lower() == "true"
    RAG_WARN_ON_FALLBACK: bool = os.getenv("RAG_WARN_ON_FALLBACK", "True").lower() == "true"
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "bge-m3")
    RAG_DOCUMENT_PROCESSING_TIMEOUT: int = int(os.getenv("RAG_DOCUMENT_PROCESSING_TIMEOUT", "300"))
    RAG_EMBEDDING_GENERATION_TIMEOUT: int = int(os.getenv("RAG_EMBEDDING_GENERATION_TIMEOUT", "120"))
    RAG_INDEXING_TIMEOUT: int = int(os.getenv("RAG_INDEXING_TIMEOUT", "120"))
    
    # Plugin configuration
    PLUGINS_DIR: str = os.getenv("PLUGINS_DIR", "/plugins")
    PLUGINS_CONFIG_PATH: str = os.getenv("PLUGINS_CONFIG_PATH", "config/plugins.yaml")
    PLUGIN_REPOSITORY_URL: str = os.getenv("PLUGIN_REPOSITORY_URL", "https://plugins.enclava.com")
    
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


# Global settings instance
settings = Settings()
