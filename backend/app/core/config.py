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
    
    # Detailed logging for LLM interactions
    LOG_LLM_PROMPTS: bool = os.getenv("LOG_LLM_PROMPTS", "False").lower() == "true"  # Set to True to log prompts and context sent to LLM
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://empire_user:empire_pass@localhost:5432/empire_db")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-here")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days
    SESSION_EXPIRE_MINUTES: int = int(os.getenv("SESSION_EXPIRE_MINUTES", "1440"))  # 24 hours
    API_KEY_PREFIX: str = os.getenv("API_KEY_PREFIX", "en_")
    
    # Admin user provisioning (used only on first startup)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
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
    
    # API & Security Settings
    API_SECURITY_ENABLED: bool = os.getenv("API_SECURITY_ENABLED", "True").lower() == "true"
    API_THREAT_DETECTION_ENABLED: bool = os.getenv("API_THREAT_DETECTION_ENABLED", "True").lower() == "true"
    API_IP_REPUTATION_ENABLED: bool = os.getenv("API_IP_REPUTATION_ENABLED", "True").lower() == "true"
    API_ANOMALY_DETECTION_ENABLED: bool = os.getenv("API_ANOMALY_DETECTION_ENABLED", "True").lower() == "true"
    
    # Rate Limiting Configuration
    API_RATE_LIMITING_ENABLED: bool = os.getenv("API_RATE_LIMITING_ENABLED", "True").lower() == "true"
    
    # Authenticated users (JWT token)
    API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE", "300"))
    API_RATE_LIMIT_AUTHENTICATED_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_AUTHENTICATED_PER_HOUR", "5000"))
    
    # API key users (programmatic access)
    API_RATE_LIMIT_API_KEY_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_API_KEY_PER_MINUTE", "1000"))
    API_RATE_LIMIT_API_KEY_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_API_KEY_PER_HOUR", "20000"))
    
    # Premium/Enterprise API keys
    API_RATE_LIMIT_PREMIUM_PER_MINUTE: int = int(os.getenv("API_RATE_LIMIT_PREMIUM_PER_MINUTE", "5000"))
    API_RATE_LIMIT_PREMIUM_PER_HOUR: int = int(os.getenv("API_RATE_LIMIT_PREMIUM_PER_HOUR", "100000"))
    
    # Security Thresholds
    API_SECURITY_RISK_THRESHOLD: float = float(os.getenv("API_SECURITY_RISK_THRESHOLD", "0.8"))  # Block requests above this risk score
    API_SECURITY_WARNING_THRESHOLD: float = float(os.getenv("API_SECURITY_WARNING_THRESHOLD", "0.6"))  # Log warnings above this threshold
    API_SECURITY_ANOMALY_THRESHOLD: float = float(os.getenv("API_SECURITY_ANOMALY_THRESHOLD", "0.7"))  # Flag anomalies above this threshold
    
    # Request Size Limits
    API_MAX_REQUEST_BODY_SIZE: int = int(os.getenv("API_MAX_REQUEST_BODY_SIZE", "10485760"))  # 10MB
    API_MAX_REQUEST_BODY_SIZE_PREMIUM: int = int(os.getenv("API_MAX_REQUEST_BODY_SIZE_PREMIUM", "52428800"))  # 50MB for premium
    
    # IP Security
    API_BLOCKED_IPS: List[str] = os.getenv("API_BLOCKED_IPS", "").split(",") if os.getenv("API_BLOCKED_IPS") else []
    API_ALLOWED_IPS: List[str] = os.getenv("API_ALLOWED_IPS", "").split(",") if os.getenv("API_ALLOWED_IPS") else []
    API_IP_REPUTATION_CACHE_TTL: int = int(os.getenv("API_IP_REPUTATION_CACHE_TTL", "3600"))  # 1 hour
    
    # Security Headers
    API_SECURITY_HEADERS_ENABLED: bool = os.getenv("API_SECURITY_HEADERS_ENABLED", "True").lower() == "true"
    API_CSP_HEADER: str = os.getenv("API_CSP_HEADER", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true"
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9090"))
    
    # File uploads
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB
    
    # Module configuration
    MODULES_CONFIG_PATH: str = os.getenv("MODULES_CONFIG_PATH", "config/modules.yaml")
    
    # Plugin configuration
    PLUGINS_DIR: str = os.getenv("PLUGINS_DIR", "/plugins")
    PLUGINS_CONFIG_PATH: str = os.getenv("PLUGINS_CONFIG_PATH", "config/plugins.yaml")
    PLUGIN_REPOSITORY_URL: str = os.getenv("PLUGIN_REPOSITORY_URL", "https://plugins.enclava.com")
    
    # Logging
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# Global settings instance
settings = Settings()