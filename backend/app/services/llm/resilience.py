"""
Resilience Patterns for LLM Service

Implements retry logic, circuit breaker, and timeout management.
"""

import asyncio
import logging
import time
from typing import Callable, Any, Optional, Dict, Type
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .exceptions import LLMError, TimeoutError, RateLimitError
from .models import ResilienceConfig

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: datetime = field(default_factory=datetime.utcnow)


class CircuitBreaker:
    """Circuit breaker implementation for provider resilience"""
    
    def __init__(self, config: ResilienceConfig, provider_name: str):
        self.config = config
        self.provider_name = provider_name
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if reset timeout has passed
            if (datetime.utcnow() - self.stats.state_change_time).total_seconds() * 1000 > self.config.circuit_breaker_reset_timeout_ms:
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record successful request"""
        self.stats.success_count += 1
        self.stats.last_success_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_closed()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.stats.failure_count = 0
        
        logger.debug(f"Circuit breaker [{self.provider_name}]: Success recorded, state={self.state.value}")
    
    def record_failure(self):
        """Record failed request"""
        self.stats.failure_count += 1
        self.stats.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.stats.failure_count >= self.config.circuit_breaker_threshold:
                self._transition_to_open()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_open()
        
        logger.warning(f"Circuit breaker [{self.provider_name}]: Failure recorded, "
                      f"count={self.stats.failure_count}, state={self.state.value}")
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        self.state = CircuitBreakerState.OPEN
        self.stats.state_change_time = datetime.utcnow()
        logger.error(f"Circuit breaker [{self.provider_name}]: OPENED after {self.stats.failure_count} failures")
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.stats.state_change_time = datetime.utcnow()
        logger.info(f"Circuit breaker [{self.provider_name}]: Transitioning to HALF_OPEN for testing")
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitBreakerState.CLOSED
        self.stats.state_change_time = datetime.utcnow()
        self.stats.failure_count = 0  # Reset failure count
        logger.info(f"Circuit breaker [{self.provider_name}]: CLOSED - service recovered")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "state": self.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "last_failure_time": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            "last_success_time": self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
            "state_change_time": self.stats.state_change_time.isoformat(),
            "time_in_current_state_ms": (datetime.utcnow() - self.stats.state_change_time).total_seconds() * 1000
        }


class RetryManager:
    """Manages retry logic with exponential backoff"""
    
    def __init__(self, config: ResilienceConfig):
        self.config = config
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        non_retryable_exceptions: tuple = (RateLimitError,),
        **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            
            except non_retryable_exceptions as e:
                logger.warning(f"Non-retryable exception on attempt {attempt + 1}: {e}")
                raise
            
            except retryable_exceptions as e:
                last_exception = e
                
                if attempt == self.config.max_retries:
                    logger.error(f"All {self.config.max_retries + 1} attempts failed. Last error: {e}")
                    raise
                
                delay = self._calculate_delay(attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}ms...")
                
                await asyncio.sleep(delay / 1000.0)
        
        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise LLMError("Unexpected error in retry logic")
    
    def _calculate_delay(self, attempt: int) -> int:
        """Calculate delay for exponential backoff"""
        delay = self.config.retry_delay_ms * (self.config.retry_exponential_base ** attempt)
        
        # Add some jitter to prevent thundering herd
        import random
        jitter = random.uniform(0.8, 1.2)
        
        return int(delay * jitter)


class TimeoutManager:
    """Manages request timeouts"""
    
    def __init__(self, config: ResilienceConfig):
        self.config = config
    
    async def execute_with_timeout(
        self,
        func: Callable,
        *args,
        timeout_override: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Execute function with timeout"""
        timeout_ms = timeout_override or self.config.timeout_ms
        timeout_seconds = timeout_ms / 1000.0
        
        try:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            error_msg = f"Request timed out after {timeout_ms}ms"
            logger.error(error_msg)
            raise TimeoutError(error_msg, timeout_duration=timeout_seconds)


class ResilienceManager:
    """Comprehensive resilience manager combining all patterns"""
    
    def __init__(self, config: ResilienceConfig, provider_name: str):
        self.config = config
        self.provider_name = provider_name
        self.circuit_breaker = CircuitBreaker(config, provider_name)
        self.retry_manager = RetryManager(config)
        self.timeout_manager = TimeoutManager(config)
    
    async def execute(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        non_retryable_exceptions: tuple = (RateLimitError,),
        timeout_override: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Execute function with full resilience patterns"""
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            error_msg = f"Circuit breaker is OPEN for provider {self.provider_name}"
            logger.error(error_msg)
            raise LLMError(error_msg, error_code="CIRCUIT_BREAKER_OPEN")
        
        start_time = time.time()
        
        try:
            # Execute with timeout and retry
            result = await self.retry_manager.execute_with_retry(
                self.timeout_manager.execute_with_timeout,
                func,
                *args,
                retryable_exceptions=retryable_exceptions,
                non_retryable_exceptions=non_retryable_exceptions,
                timeout_override=timeout_override,
                **kwargs
            )
            
            # Record success
            self.circuit_breaker.record_success()
            
            execution_time = (time.time() - start_time) * 1000
            logger.debug(f"Resilient execution succeeded for {self.provider_name} in {execution_time:.2f}ms")
            
            return result
        
        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure()
            
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Resilient execution failed for {self.provider_name} after {execution_time:.2f}ms: {e}")
            
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        cb_stats = self.circuit_breaker.get_stats()
        
        # Determine overall health
        if cb_stats["state"] == "open":
            health = "unhealthy"
        elif cb_stats["state"] == "half_open":
            health = "degraded"
        else:
            # Check recent failure rate
            recent_failures = cb_stats["failure_count"]
            if recent_failures > self.config.circuit_breaker_threshold // 2:
                health = "degraded"
            else:
                health = "healthy"
        
        return {
            "provider": self.provider_name,
            "health": health,
            "circuit_breaker": cb_stats,
            "config": {
                "max_retries": self.config.max_retries,
                "timeout_ms": self.config.timeout_ms,
                "circuit_breaker_threshold": self.config.circuit_breaker_threshold
            }
        }


class ResilienceManagerFactory:
    """Factory for creating resilience managers"""
    
    _managers: Dict[str, ResilienceManager] = {}
    _default_config = ResilienceConfig()
    
    @classmethod
    def get_manager(cls, provider_name: str, config: Optional[ResilienceConfig] = None) -> ResilienceManager:
        """Get or create resilience manager for provider"""
        if provider_name not in cls._managers:
            manager_config = config or cls._default_config
            cls._managers[provider_name] = ResilienceManager(manager_config, provider_name)
        
        return cls._managers[provider_name]
    
    @classmethod
    def get_all_health_status(cls) -> Dict[str, Dict[str, Any]]:
        """Get health status for all managed providers"""
        return {
            name: manager.get_health_status()
            for name, manager in cls._managers.items()
        }
    
    @classmethod
    def update_config(cls, provider_name: str, config: ResilienceConfig):
        """Update configuration for a specific provider"""
        if provider_name in cls._managers:
            cls._managers[provider_name].config = config
            cls._managers[provider_name].circuit_breaker.config = config
            cls._managers[provider_name].retry_manager.config = config
            cls._managers[provider_name].timeout_manager.config = config
    
    @classmethod
    def reset_circuit_breaker(cls, provider_name: str):
        """Manually reset circuit breaker for a provider"""
        if provider_name in cls._managers:
            manager = cls._managers[provider_name]
            manager.circuit_breaker._transition_to_closed()
            logger.info(f"Manually reset circuit breaker for {provider_name}")
    
    @classmethod
    def set_default_config(cls, config: ResilienceConfig):
        """Set default configuration for new managers"""
        cls._default_config = config