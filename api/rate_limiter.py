"""
Simple in-memory rate limiter for public endpoints.
"""

import time
import logging
from typing import Dict, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter using sliding window approach.
    
    Note: This is for MVP only. For production, use Redis or similar.
    """
    
    def __init__(self):
        # Store requests as: ip -> [(timestamp, count), ...]
        self._requests: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 300  # Clean up old entries every 5 minutes
        self._last_cleanup = time.time()
    
    def is_allowed(self, ip: str, limit: int = 5, window_seconds: int = 60) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request from IP is allowed within rate limit.
        
        Args:
            ip: Client IP address
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds (default 60 for per-minute)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        current_time = time.time()
        
        # Cleanup old entries periodically
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(current_time)
            self._last_cleanup = current_time
        
        # Get recent requests for this IP
        ip_requests = self._requests[ip]
        window_start = current_time - window_seconds
        
        # Remove old requests outside the window
        self._requests[ip] = [
            (timestamp, count) for timestamp, count in ip_requests
            if timestamp > window_start
        ]
        
        # Count requests in current window
        current_requests = sum(count for timestamp, count in self._requests[ip])
        
        # Calculate rate limit info
        rate_limit_info = {
            "limit": limit,
            "remaining": max(0, limit - current_requests),
            "reset": int(current_time + window_seconds),
            "window": window_seconds
        }
        
        # Check if request is allowed
        if current_requests >= limit:
            logger.warning(f"Rate limit exceeded for IP {ip}: {current_requests}/{limit}")
            return False, rate_limit_info
        
        # Add this request to the tracking
        self._requests[ip].append((current_time, 1))
        rate_limit_info["remaining"] -= 1
        
        return True, rate_limit_info
    
    def _cleanup_old_entries(self, current_time: float) -> None:
        """Remove entries older than 1 hour to prevent memory leaks."""
        cleanup_threshold = current_time - 3600  # 1 hour
        
        ips_to_remove = []
        for ip, requests in self._requests.items():
            # Remove old requests
            self._requests[ip] = [
                (timestamp, count) for timestamp, count in requests
                if timestamp > cleanup_threshold
            ]
            
            # Mark IPs with no recent requests for removal
            if not self._requests[ip]:
                ips_to_remove.append(ip)
        
        # Remove IPs with no recent activity
        for ip in ips_to_remove:
            del self._requests[ip]
        
        logger.debug(f"Rate limiter cleanup: removed {len(ips_to_remove)} inactive IPs")
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics for debugging."""
        current_time = time.time()
        active_ips = 0
        total_requests_last_hour = 0
        
        for ip, requests in self._requests.items():
            if requests:
                active_ips += 1
                # Count requests in last hour
                hour_ago = current_time - 3600
                total_requests_last_hour += sum(
                    count for timestamp, count in requests
                    if timestamp > hour_ago
                )
        
        return {
            "active_ips": active_ips,
            "total_requests_last_hour": total_requests_last_hour,
            "last_cleanup": self._last_cleanup
        }


# Global rate limiter instance
# TODO: Consider using Redis for distributed rate limiting in production
rate_limiter = InMemoryRateLimiter()
