"""
Circuit breaker pattern implementation for external service resilience.

Provides automatic failure detection and recovery for external dependencies.
"""

import time
import asyncio
import logging
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: int = 60          # Seconds to wait before trying recovery
    success_threshold: int = 3          # Successes needed to close circuit from half-open
    timeout: float = 30.0               # Request timeout in seconds
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, circuit_name: str, state: CircuitState):
        self.circuit_name = circuit_name
        self.state = state
        super().__init__(f"Circuit breaker '{circuit_name}' is {state.value}")


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against external service failures.
    
    Implements the circuit breaker pattern to prevent cascading failures
    and provide graceful degradation.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = threading.Lock()
        
        # Recovery tracking
        self._last_failure_time = 0.0
        self._half_open_requests = 0
        
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset to half-open."""
        return (
            self.state == CircuitState.OPEN and
            time.time() - self._last_failure_time >= self.config.recovery_timeout
        )
    
    def _record_success(self):
        """Record a successful operation."""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._close_circuit()
    
    def _record_failure(self, exception: Exception):
        """Record a failed operation."""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            self._last_failure_time = self.stats.last_failure_time
            
            if isinstance(exception, asyncio.TimeoutError):
                self.stats.timeouts += 1
            
            # Open circuit if failure threshold is reached
            if (self.state == CircuitState.CLOSED and 
                self.stats.consecutive_failures >= self.config.failure_threshold):
                self._open_circuit()
            elif self.state == CircuitState.HALF_OPEN:
                self._open_circuit()
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        self.state = CircuitState.OPEN
        self.stats.circuit_opens += 1
        self._half_open_requests = 0
        logger.warning(f"Circuit breaker '{self.name}' opened after {self.stats.consecutive_failures} consecutive failures")
    
    def _close_circuit(self):
        """Close the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.stats.circuit_closes += 1
        self.stats.consecutive_failures = 0
        logger.info(f"Circuit breaker '{self.name}' closed after {self.stats.consecutive_successes} consecutive successes")
    
    def _transition_to_half_open(self):
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self._half_open_requests = 0
        self.stats.consecutive_successes = 0
        logger.info(f"Circuit breaker '{self.name}' transitioned to half-open")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception if function fails
        """
        # Check if circuit should attempt reset
        if self._should_attempt_reset():
            self._transition_to_half_open()
        
        # Fail fast if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(self.name, self.state)
        
        # Limit concurrent requests in half-open state
        if self.state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_requests >= 1:  # Only allow one request in half-open
                    raise CircuitBreakerError(self.name, self.state)
                self._half_open_requests += 1
        
        try:
            # Execute function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            self._record_success()
            return result
            
        except self.config.expected_exception as e:
            self._record_failure(e)
            raise
        
        finally:
            if self.state == CircuitState.HALF_OPEN:
                with self._lock:
                    self._half_open_requests = max(0, self._half_open_requests - 1)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state and statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "stats": {
                    "total_requests": self.stats.total_requests,
                    "successful_requests": self.stats.successful_requests,
                    "failed_requests": self.stats.failed_requests,
                    "timeouts": self.stats.timeouts,
                    "circuit_opens": self.stats.circuit_opens,
                    "circuit_closes": self.stats.circuit_closes,
                    "consecutive_failures": self.stats.consecutive_failures,
                    "consecutive_successes": self.stats.consecutive_successes,
                    "failure_rate": self.stats.failure_rate,
                    "success_rate": self.stats.success_rate,
                    "last_failure_time": self.stats.last_failure_time,
                    "last_success_time": self.stats.last_success_time
                },
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout
                }
            }
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
            self._half_open_requests = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_or_create(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get existing circuit breaker or create a new one."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get existing circuit breaker."""
        with self._lock:
            return self._breakers.get(name)
    
    def remove(self, name: str) -> bool:
        """Remove circuit breaker from registry."""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers."""
        with self._lock:
            return {name: breaker.get_state() for name, breaker in self._breakers.items()}
    
    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("All circuit breakers reset")


# Global circuit breaker registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    return _registry


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    success_threshold: int = 3,
    timeout: float = 30.0,
    expected_exception: tuple = (Exception,)
):
    """
    Decorator to protect function with circuit breaker.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds to wait before trying recovery
        success_threshold: Successes needed to close circuit from half-open
        timeout: Request timeout in seconds
        expected_exception: Exceptions that count as failures
    """
    def decorator(func: Callable) -> Callable:
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exception=expected_exception
        )
        
        breaker = _registry.get_or_create(name, config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        return wrapper
    return decorator


class CircuitBreakerHealthCheck:
    """Health check that monitors circuit breaker states."""
    
    def __init__(self, registry: CircuitBreakerRegistry = None):
        self.registry = registry or get_circuit_breaker_registry()
    
    def check_health(self) -> Dict[str, Any]:
        """Check health of all circuit breakers."""
        states = self.registry.get_all_states()
        
        healthy_count = 0
        degraded_count = 0
        failed_count = 0
        
        circuit_details = {}
        
        for name, state in states.items():
            circuit_state = state["state"]
            stats = state["stats"]
            
            # Determine health status
            if circuit_state == CircuitState.CLOSED.value:
                if stats["failure_rate"] < 0.1:  # Less than 10% failure rate
                    status = "healthy"
                    healthy_count += 1
                else:
                    status = "degraded"
                    degraded_count += 1
            elif circuit_state == CircuitState.HALF_OPEN.value:
                status = "degraded"
                degraded_count += 1
            else:  # OPEN
                status = "failed"
                failed_count += 1
            
            circuit_details[name] = {
                "status": status,
                "state": circuit_state,
                "failure_rate": stats["failure_rate"],
                "total_requests": stats["total_requests"],
                "consecutive_failures": stats["consecutive_failures"]
            }
        
        # Overall health status
        if failed_count > 0:
            overall_status = "failed"
        elif degraded_count > 0:
            overall_status = "degraded" 
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "summary": {
                "healthy": healthy_count,
                "degraded": degraded_count,
                "failed": failed_count,
                "total": len(states)
            },
            "circuits": circuit_details
        }