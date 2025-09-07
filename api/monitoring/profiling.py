"""
Performance profiling and analysis tools.

Provides profiling capabilities for debugging performance issues
and identifying bottlenecks.
"""

import cProfile
import io
import pstats
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable for profiling state
_profiling_enabled: ContextVar[bool] = ContextVar('profiling_enabled', default=False)

# Global profiling data storage
_profile_data: Dict[str, 'ProfileData'] = {}
_profile_lock = threading.Lock()


@dataclass
class ProfileData:
    """Performance profile data for a request or operation."""
    
    profile_id: str
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    profiler: Optional[cProfile.Profile] = None
    stats: Optional[pstats.Stats] = None
    memory_usage: Dict[str, int] = field(default_factory=dict)
    custom_timings: Dict[str, float] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get total duration in seconds."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time
    
    def finish(self):
        """Finish profiling and generate stats."""
        self.end_time = time.time()
        
        if self.profiler:
            self.profiler.disable()
            
            # Generate stats
            stats_buffer = io.StringIO()
            self.stats = pstats.Stats(self.profiler, stream=stats_buffer)
            self.stats.sort_stats('cumulative')
    
    def get_top_functions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get top functions by cumulative time."""
        if not self.stats:
            return []
        
        # Capture stats output
        stats_buffer = io.StringIO()
        temp_stats = pstats.Stats(self.profiler, stream=stats_buffer)
        temp_stats.sort_stats('cumulative')
        temp_stats.print_stats(count)
        
        # Parse the output (simplified parsing)
        output = stats_buffer.getvalue()
        lines = output.split('\n')
        
        functions = []
        parsing_data = False
        
        for line in lines:
            if 'cumulative' in line and 'percall' in line:
                parsing_data = True
                continue
            
            if parsing_data and line.strip():
                # Parse function data (simplified)
                parts = line.split()
                if len(parts) >= 6:
                    functions.append({
                        'ncalls': parts[0],
                        'tottime': parts[1],
                        'percall': parts[2],
                        'cumtime': parts[3],
                        'percall_cum': parts[4],
                        'filename_function': ' '.join(parts[5:])
                    })
                
                if len(functions) >= count:
                    break
        
        return functions
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of profiling results."""
        summary = {
            'profile_id': self.profile_id,
            'operation_name': self.operation_name,
            'duration': self.duration,
            'memory_usage': self.memory_usage,
            'custom_timings': self.custom_timings
        }
        
        if self.stats:
            # Add basic stats
            stats_dict = self.stats.get_stats_profile()
            summary['total_calls'] = stats_dict.total_calls
            summary['primitive_calls'] = getattr(stats_dict, 'prim_calls', 0)
            summary['top_functions'] = self.get_top_functions(5)
        
        return summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.get_summary()


class Profiler:
    """Main profiler class for managing performance profiling."""
    
    def __init__(self):
        self.enabled = False
    
    def enable(self):
        """Enable profiling globally."""
        self.enabled = True
        logger.info("Profiling enabled globally")
    
    def disable(self):
        """Disable profiling globally."""
        self.enabled = False
        logger.info("Profiling disabled globally")
    
    def start_profile(self, profile_id: str, operation_name: str) -> Optional[ProfileData]:
        """Start profiling an operation."""
        if not self.enabled:
            return None
        
        # Create profiler
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Create profile data
        profile_data = ProfileData(
            profile_id=profile_id,
            operation_name=operation_name,
            start_time=time.time(),
            profiler=profiler
        )
        
        # Store profile data
        with _profile_lock:
            _profile_data[profile_id] = profile_data
        
        # Set profiling context
        _profiling_enabled.set(True)
        
        return profile_data
    
    def finish_profile(self, profile_id: str) -> Optional[ProfileData]:
        """Finish profiling an operation."""
        with _profile_lock:
            profile_data = _profile_data.get(profile_id)
        
        if profile_data:
            profile_data.finish()
            _profiling_enabled.set(False)
            logger.debug(f"Profile {profile_id} finished in {profile_data.duration:.3f}s")
        
        return profile_data
    
    def get_profile(self, profile_id: str) -> Optional[ProfileData]:
        """Get profile data by ID."""
        with _profile_lock:
            return _profile_data.get(profile_id)
    
    def clear_old_profiles(self, max_age_seconds: int = 3600):
        """Clear old profile data."""
        current_time = time.time()
        expired_ids = []
        
        with _profile_lock:
            for profile_id, profile_data in _profile_data.items():
                if profile_data.end_time and (current_time - profile_data.end_time) > max_age_seconds:
                    expired_ids.append(profile_id)
        
        for profile_id in expired_ids:
            with _profile_lock:
                del _profile_data[profile_id]
        
        if expired_ids:
            logger.debug(f"Cleared {len(expired_ids)} old profiles")


# Global profiler instance
_profiler = Profiler()


def get_profiler() -> Profiler:
    """Get the global profiler instance."""
    return _profiler


def setup_profiling(enabled: bool = False):
    """Setup profiling with initial state."""
    if enabled:
        _profiler.enable()
    else:
        _profiler.disable()
    
    logger.info(f"Profiling setup complete, enabled: {enabled}")


def profile_operation(operation_name: str = None):
    """
    Decorator to profile a function or method.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__qualname__}"
        
        async def async_wrapper(*args, **kwargs):
            profiler = get_profiler()
            if not profiler.enabled:
                return await func(*args, **kwargs)
            
            profile_id = f"{operation_name}_{int(time.time() * 1000)}"
            profile_data = profiler.start_profile(profile_id, operation_name)
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                if profile_data:
                    profiler.finish_profile(profile_id)
        
        def sync_wrapper(*args, **kwargs):
            profiler = get_profiler()
            if not profiler.enabled:
                return func(*args, **kwargs)
            
            profile_id = f"{operation_name}_{int(time.time() * 1000)}"
            profile_data = profiler.start_profile(profile_id, operation_name)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if profile_data:
                    profiler.finish_profile(profile_id)
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def add_timing(name: str, duration: float):
    """Add a custom timing measurement to the current profile."""
    if not _profiling_enabled.get(False):
        return
    
    # Find the current profile (simplified approach)
    current_time = time.time()
    with _profile_lock:
        for profile_data in _profile_data.values():
            if profile_data.end_time is None and (current_time - profile_data.start_time) < 300:
                profile_data.custom_timings[name] = duration
                break


def record_memory_usage(checkpoint: str):
    """Record memory usage at a specific checkpoint."""
    if not _profiling_enabled.get(False):
        return
    
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Find current profile and add memory data
        current_time = time.time()
        with _profile_lock:
            for profile_data in _profile_data.values():
                if profile_data.end_time is None and (current_time - profile_data.start_time) < 300:
                    profile_data.memory_usage[checkpoint] = memory_info.rss
                    break
    
    except ImportError:
        logger.warning("psutil not available for memory profiling")


class ProfilerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to profile HTTP requests when profiling is enabled.
    """
    
    def __init__(self, app, profile_slow_requests: bool = True, slow_threshold: float = 1.0):
        super().__init__(app)
        self.profile_slow_requests = profile_slow_requests
        self.slow_threshold = slow_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if profiling should be enabled for this request
        should_profile = self._should_profile_request(request)
        
        if not should_profile:
            return await call_next(request)
        
        # Generate profile ID
        profile_id = f"http_{request.method}_{request.url.path}_{int(time.time() * 1000)}"
        operation_name = f"{request.method} {request.url.path}"
        
        # Start profiling
        profiler = get_profiler()
        profile_data = profiler.start_profile(profile_id, operation_name)
        
        if profile_data:
            # Add request metadata
            profile_data.custom_timings['request_start'] = time.time()
            record_memory_usage('request_start')
        
        try:
            response = await call_next(request)
            
            if profile_data:
                # Record completion
                profile_data.custom_timings['request_end'] = time.time()
                record_memory_usage('request_end')
            
            return response
        
        finally:
            if profile_data:
                profiler.finish_profile(profile_id)
                
                # Log slow requests
                if profile_data.duration and profile_data.duration > self.slow_threshold:
                    logger.warning(
                        f"Slow request profiled: {operation_name} took {profile_data.duration:.3f}s "
                        f"(profile_id: {profile_id})"
                    )
    
    def _should_profile_request(self, request: Request) -> bool:
        """Determine if a request should be profiled."""
        profiler = get_profiler()
        
        # Check if profiling is globally enabled
        if not profiler.enabled:
            return False
        
        # Check for profiling header
        if request.headers.get("X-Enable-Profiling") == "true":
            return True
        
        # Check for profiling query parameter
        if request.query_params.get("profile") == "true":
            return True
        
        # Profile slow requests if enabled
        if self.profile_slow_requests:
            return True
        
        return False


def get_performance_stats() -> Dict[str, Any]:
    """Get overall performance statistics."""
    with _profile_lock:
        active_profiles = len([p for p in _profile_data.values() if p.end_time is None])
        completed_profiles = len([p for p in _profile_data.values() if p.end_time is not None])
        
        # Calculate average duration for completed profiles
        durations = [p.duration for p in _profile_data.values() if p.duration is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'profiler_enabled': _profiler.enabled,
            'active_profiles': active_profiles,
            'completed_profiles': completed_profiles,
            'total_profiles': len(_profile_data),
            'average_duration': avg_duration,
            'recent_profiles': [
                p.get_summary() for p in 
                sorted(_profile_data.values(), key=lambda x: x.start_time, reverse=True)[:5]
            ]
        }


def get_all_profiles() -> Dict[str, Any]:
    """Get all profile data (for debugging)."""
    with _profile_lock:
        return {pid: profile.to_dict() for pid, profile in _profile_data.items()}