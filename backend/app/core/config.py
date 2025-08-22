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
    APP_NAME: str = "Enclava"
    APP_DEBUG: bool = False
    APP_LOG_LEVEL: str = "INFO"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # Detailed logging for LLM interactions
    LOG_LLM_PROMPTS: bool = False  # Set to True to log prompts and context sent to LLM
    
    # Database
    DATABASE_URL: str = "postgresql://empire_user:empire_pass@localhost:5432/empire_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    JWT_SECRET: str = "your-super-secret-jwt-key-here"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    SESSION_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    API_KEY_PREFIX: str = "en_"
    
    # Admin user provisioning
    ADMIN_USER: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_EMAIL: Optional[str] = None
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # LLM Service Configuration (replaced LiteLLM)
    # LLM service configuration is now handled in app/services/llm/config.py
    
    # LLM Service Security
    LLM_ENCRYPTION_KEY: Optional[str] = None  # Key for encrypting LLM provider API keys
    
    # Plugin System Security
    PLUGIN_ENCRYPTION_KEY: Optional[str] = None  # Key for encrypting plugin secrets and configurations
    
    # API Keys for LLM providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    PRIVATEMODE_API_KEY: Optional[str] = None
    PRIVATEMODE_PROXY_URL: str = "http://privatemode-proxy:8080/v1"
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None
    
    # API & Security Settings
    API_SECURITY_ENABLED: bool = True
    API_THREAT_DETECTION_ENABLED: bool = True
    API_IP_REPUTATION_ENABLED: bool = True
    API_ANOMALY_DETECTION_ENABLED: bool = True
    
    # Rate Limiting Configuration
    API_RATE_LIMITING_ENABLED: bool = True
    
    # Authenticated users (JWT token)
    API_RATE_LIMIT_AUTHENTICATED_PER_MINUTE: int = 300
    API_RATE_LIMIT_AUTHENTICATED_PER_HOUR: int = 5000
    
    # API key users (programmatic access)
    API_RATE_LIMIT_API_KEY_PER_MINUTE: int = 1000
    API_RATE_LIMIT_API_KEY_PER_HOUR: int = 20000
    
    # Premium/Enterprise API keys
    API_RATE_LIMIT_PREMIUM_PER_MINUTE: int = 5000
    API_RATE_LIMIT_PREMIUM_PER_HOUR: int = 100000
    
    # Security Thresholds
    API_SECURITY_RISK_THRESHOLD: float = 0.8  # Block requests above this risk score
    API_SECURITY_WARNING_THRESHOLD: float = 0.6  # Log warnings above this threshold
    API_SECURITY_ANOMALY_THRESHOLD: float = 0.7  # Flag anomalies above this threshold
    
    # Request Size Limits
    API_MAX_REQUEST_BODY_SIZE: int = 10 * 1024 * 1024  # 10MB
    API_MAX_REQUEST_BODY_SIZE_PREMIUM: int = 50 * 1024 * 1024  # 50MB for premium
    
    # IP Security
    API_BLOCKED_IPS: List[str] = []  # IPs to always block
    API_ALLOWED_IPS: List[str] = []  # IPs to always allow (empty = allow all)
    API_IP_REPUTATION_CACHE_TTL: int = 3600  # 1 hour
    
    # Security Headers
    API_SECURITY_HEADERS_ENABLED: bool = True
    API_CSP_HEADER: str = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    
    # File uploads
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Module configuration
    MODULES_CONFIG_PATH: str = "config/modules.yaml"
    
    # Plugin configuration
    PLUGINS_DIR: str = "/plugins"
    PLUGINS_CONFIG_PATH: str = "config/plugins.yaml"
    PLUGIN_REPOSITORY_URL: str = "https://plugins.enclava.com"
    
    # Logging
    LOG_FORMAT: str = "json"
    LOG_LEVEL: str = "INFO"
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# Global settings instance
settings = Settings()