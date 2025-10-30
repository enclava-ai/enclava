"""
LLM Service Configuration

Configuration management for LLM providers and service settings.
"""

import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from dataclasses import dataclass

from app.core.config import settings
from .models import ResilienceConfig


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider"""
    name: str = Field(..., description="Provider name")
    provider_type: str = Field(..., description="Provider type (e.g., 'openai', 'privatemode')")
    enabled: bool = Field(True, description="Whether provider is enabled")
    base_url: str = Field(..., description="Provider base URL")
    api_key_env_var: str = Field(..., description="Environment variable for API key")
    default_model: Optional[str] = Field(None, description="Default model for this provider")
    supported_models: List[str] = Field(default_factory=list, description="List of supported models")
    capabilities: List[str] = Field(default_factory=list, description="Provider capabilities")
    priority: int = Field(1, description="Provider priority (lower = higher priority)")
    
    # Rate limiting
    max_requests_per_minute: Optional[int] = Field(None, description="Max requests per minute")
    max_requests_per_hour: Optional[int] = Field(None, description="Max requests per hour")
    
    # Model-specific settings
    supports_streaming: bool = Field(False, description="Whether provider supports streaming")
    supports_function_calling: bool = Field(False, description="Whether provider supports function calling")
    max_context_window: Optional[int] = Field(None, description="Maximum context window size")
    max_output_tokens: Optional[int] = Field(None, description="Maximum output tokens")
    
    # Resilience configuration
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig, description="Resilience settings")
    
    @validator('priority')
    def validate_priority(cls, v):
        if v < 1:
            raise ValueError("Priority must be >= 1")
        return v


class LLMServiceConfig(BaseModel):
    """Main LLM service configuration"""
    
    # Global settings
    default_provider: str = Field("privatemode", description="Default provider to use")
    enable_detailed_logging: bool = Field(False, description="Enable detailed request/response logging")
    enable_security_checks: bool = Field(True, description="Enable security validation")
    enable_metrics_collection: bool = Field(True, description="Enable metrics collection")
    
    max_prompt_length: int = Field(50000, ge=1000, description="Maximum prompt length")
    max_response_length: int = Field(32000, ge=1000, description="Maximum response length")
    
    # Performance settings
    default_timeout_ms: int = Field(30000, ge=1000, le=300000, description="Default request timeout")
    max_concurrent_requests: int = Field(100, ge=1, le=1000, description="Maximum concurrent requests")
    
    # Provider configurations
    providers: Dict[str, ProviderConfig] = Field(default_factory=dict, description="Provider configurations")

    # Token rate limiting (organization-wide)
    token_limits_per_minute: Dict[str, int] = Field(
        default_factory=lambda: {
            "prompt_tokens": 20000,    # PrivateMode Standard tier
            "completion_tokens": 10000  # PrivateMode Standard tier
        },
        description="Token rate limits per minute (organization-wide)"
    )

    # Model routing (model_name -> provider_name)
    model_routing: Dict[str, str] = Field(default_factory=dict, description="Model to provider routing")
    


def create_default_config(env_vars=None) -> LLMServiceConfig:
    """Create default LLM service configuration"""
    env = env_vars or EnvironmentVariables()

    # PrivateMode.ai configuration (via proxy)
    # Models will be fetched dynamically from proxy /models endpoint
    privatemode_config = ProviderConfig(
        name="privatemode",
        provider_type="privatemode",
        enabled=bool(env.PRIVATEMODE_API_KEY),
        base_url=settings.PRIVATEMODE_PROXY_URL,
        api_key_env_var="PRIVATEMODE_API_KEY",
        default_model="privatemode-latest",
        supported_models=[],  # Will be populated dynamically from proxy
        capabilities=["chat", "embeddings", "tee"],
        priority=1,
        max_requests_per_minute=20,    # PrivateMode Standard tier limit: 20 req/min
        max_requests_per_hour=1200,   # 20 req/min * 60 min
        supports_streaming=True,
        supports_function_calling=True,
        max_context_window=128000,
        max_output_tokens=8192,
        resilience=ResilienceConfig(
            max_retries=3,
            retry_delay_ms=1000,
            timeout_ms=60000,  # PrivateMode may be slower due to TEE
            circuit_breaker_threshold=5,
            circuit_breaker_reset_timeout_ms=120000
        )
    )
    
    providers: Dict[str, ProviderConfig] = {
        "privatemode": privatemode_config
    }

    if env.OPENAI_API_KEY:
        providers["openai"] = ProviderConfig(
            name="openai",
            provider_type="openai",
            enabled=True,
            base_url="https://api.openai.com/v1",
            api_key_env_var="OPENAI_API_KEY",
            default_model="gpt-4o-mini",
            supported_models=[
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-3.5-turbo",
                "text-embedding-3-large",
                "text-embedding-3-small"
            ],
            capabilities=["chat", "embeddings"],
            priority=2,
            supports_streaming=True,
            supports_function_calling=True,
            max_context_window=128000,
            max_output_tokens=8192,
            resilience=ResilienceConfig(
                max_retries=2,
                retry_delay_ms=750,
                timeout_ms=45000,
                circuit_breaker_threshold=6,
                circuit_breaker_reset_timeout_ms=60000
            )
        )
    
    if env.ANTHROPIC_API_KEY:
        providers["anthropic"] = ProviderConfig(
            name="anthropic",
            provider_type="anthropic",
            enabled=True,
            base_url="https://api.anthropic.com/v1",
            api_key_env_var="ANTHROPIC_API_KEY",
            default_model="claude-3-opus-20240229",
            supported_models=[
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ],
            capabilities=["chat"],
            priority=3,
            supports_streaming=True,
            supports_function_calling=False,
            max_context_window=200000,
            max_output_tokens=4096,
            resilience=ResilienceConfig(
                max_retries=3,
                retry_delay_ms=1000,
                timeout_ms=60000,
                circuit_breaker_threshold=5,
                circuit_breaker_reset_timeout_ms=90000
            )
        )
    
    if env.GOOGLE_API_KEY:
        providers["google"] = ProviderConfig(
            name="google",
            provider_type="google",
            enabled=True,
            base_url="https://generativelanguage.googleapis.com/v1beta",
            api_key_env_var="GOOGLE_API_KEY",
            default_model="models/gemini-1.5-pro-latest",
            supported_models=[
                "models/gemini-1.5-pro-latest",
                "models/gemini-1.5-flash-latest"
            ],
            capabilities=["chat", "multimodal"],
            priority=4,
            supports_streaming=True,
            supports_function_calling=True,
            max_context_window=200000,
            max_output_tokens=8192,
            resilience=ResilienceConfig(
                max_retries=2,
                retry_delay_ms=1000,
                timeout_ms=45000,
                circuit_breaker_threshold=4,
                circuit_breaker_reset_timeout_ms=60000
            )
        )
    
    default_provider = next(
        (name for name, provider in providers.items() if provider.enabled),
        "privatemode"
    )
    
    # Create main configuration
    config = LLMServiceConfig(
        default_provider=default_provider,
        enable_detailed_logging=settings.LOG_LLM_PROMPTS,
        providers=providers,
        model_routing={}  # Will be populated dynamically from provider models
    )
    
    return config


@dataclass
class EnvironmentVariables:
    """Environment variables used by LLM service"""
    
    # Provider API keys
    PRIVATEMODE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    
    # Service settings
    LOG_LLM_PROMPTS: bool = False
    
    def __post_init__(self):
        """Load values from environment"""
        self.PRIVATEMODE_API_KEY = os.getenv("PRIVATEMODE_API_KEY")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.LOG_LLM_PROMPTS = os.getenv("LOG_LLM_PROMPTS", "false").lower() == "true"
    
    def get_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key for a specific provider"""
        key_mapping = {
            "privatemode": self.PRIVATEMODE_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "google": self.GOOGLE_API_KEY
        }
        
        return key_mapping.get(provider_name.lower())
    
    def validate_required_keys(self, enabled_providers: List[str]) -> List[str]:
        """Validate that required API keys are present"""
        missing_keys = []
        
        for provider in enabled_providers:
            if not self.get_api_key(provider):
                missing_keys.append(f"{provider.upper()}_API_KEY")
        
        return missing_keys


class ConfigurationManager:
    """Manages LLM service configuration"""
    
    def __init__(self):
        self._config: Optional[LLMServiceConfig] = None
        self._env_vars = EnvironmentVariables()
    
    def get_config(self) -> LLMServiceConfig:
        """Get current configuration"""
        if self._config is None:
            self._config = create_default_config(self._env_vars)
            self._validate_configuration()
        
        return self._config
    
    def update_config(self, config: LLMServiceConfig):
        """Update configuration"""
        self._config = config
        self._validate_configuration()
    
    def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """Get configuration for a specific provider"""
        config = self.get_config()
        return config.providers.get(provider_name)
    
    def get_provider_for_model(self, model_name: str) -> Optional[str]:
        """Get provider name for a specific model"""
        config = self.get_config()
        return config.model_routing.get(model_name)
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled providers"""
        config = self.get_config()
        return [name for name, provider in config.providers.items() if provider.enabled]
    
    def get_api_key(self, provider_name: str) -> Optional[str]:
        """Get API key for provider"""
        return self._env_vars.get_api_key(provider_name)
    
    def _validate_configuration(self):
        """Validate current configuration"""
        if not self._config:
            return
        
        # Check for enabled providers without API keys
        enabled_providers = self.get_enabled_providers()
        missing_keys = self._env_vars.validate_required_keys(enabled_providers)
        
        if missing_keys:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Missing API keys for enabled providers: {', '.join(missing_keys)}")
        
        # Validate default provider is enabled
        default_provider = self._config.default_provider
        if default_provider not in enabled_providers:
            raise ValueError(f"Default provider '{default_provider}' is not enabled")
        
        # Validate model routing points to enabled providers
        invalid_routes = []
        for model, provider in self._config.model_routing.items():
            if provider not in enabled_providers:
                invalid_routes.append(f"{model} -> {provider}")
        
        if invalid_routes:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Model routes point to disabled providers: {', '.join(invalid_routes)}")
    
    async def refresh_provider_models(self, provider_name: str, models: List[str]):
        """Update supported models for a provider dynamically"""
        if not self._config:
            return
        
        provider_config = self._config.providers.get(provider_name)
        if not provider_config:
            return
        
        # Update supported models
        provider_config.supported_models = models
        
        # Update model routing - map all models to this provider
        for model in models:
            self._config.model_routing[model] = provider_name
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Updated {provider_name} with {len(models)} models: {models}")
    
    async def get_all_available_models(self) -> Dict[str, List[str]]:
        """Get all available models grouped by provider"""
        config = self.get_config()
        models_by_provider = {}
        
        for provider_name, provider_config in config.providers.items():
            if provider_config.enabled:
                models_by_provider[provider_name] = provider_config.supported_models
        
        return models_by_provider
    
    def get_model_provider_mapping(self) -> Dict[str, str]:
        """Get current model to provider mapping"""
        config = self.get_config()
        return config.model_routing.copy()


# Global configuration manager
config_manager = ConfigurationManager()
