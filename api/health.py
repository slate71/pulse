"""
Enhanced health checking system for production readiness.

Provides comprehensive health checks for all system dependencies.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

from config import get_settings
from db import get_pool


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Base health check interface."""
    
    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    async def check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Dict with status, latency_ms, and optional details
        """
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(self._perform_check(), timeout=self.timeout)
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "status": HealthStatus.HEALTHY,
                "latency_ms": round(latency_ms, 2),
                **result
            }
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Health check timeout after {self.timeout}s")
            return {
                "status": HealthStatus.UNHEALTHY,
                "latency_ms": round(latency_ms, 2),
                "error": f"Timeout after {self.timeout}s"
            }
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": HealthStatus.UNHEALTHY,
                "latency_ms": round(latency_ms, 2),
                "error": str(e)
            }
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Override this method to implement specific health check logic."""
        raise NotImplementedError


class DatabaseHealthCheck(HealthCheck):
    """Database connectivity and performance health check."""
    
    def __init__(self):
        super().__init__("database", timeout=10.0)
    
    async def _perform_check(self) -> Dict[str, Any]:
        pool = await get_pool()
        
        async with pool.acquire() as connection:
            # Test basic connectivity
            version = await connection.fetchval("SELECT version()")
            
            # Test query performance
            start_time = time.time()
            await connection.fetchval("SELECT 1")
            query_time = (time.time() - start_time) * 1000
            
            # Get pool statistics
            pool_size = pool.get_size()
            pool_idle = pool.get_idle_size()
            
            # Get database statistics
            db_stats = await connection.fetchrow("""
                SELECT 
                    pg_database_size(current_database()) as db_size_bytes,
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                    (SELECT count(*) FROM pg_stat_activity) as total_connections
            """)
            
            return {
                "version": version.split(" ")[1] if version else "unknown",
                "query_time_ms": round(query_time, 2),
                "pool": {
                    "size": pool_size,
                    "idle": pool_idle,
                    "active": pool_size - pool_idle
                },
                "database": {
                    "size_mb": round(db_stats["db_size_bytes"] / (1024 * 1024), 2),
                    "active_connections": db_stats["active_connections"],
                    "total_connections": db_stats["total_connections"]
                }
            }


class ExternalAPIHealthCheck(HealthCheck):
    """Health check for external API dependencies."""
    
    def __init__(self, api_name: str, check_func):
        super().__init__(f"external_api_{api_name}", timeout=15.0)
        self.api_name = api_name
        self.check_func = check_func
    
    async def _perform_check(self) -> Dict[str, Any]:
        return await self.check_func()


class SystemHealthCheck(HealthCheck):
    """System-level health checks."""
    
    def __init__(self):
        super().__init__("system", timeout=5.0)
    
    async def _perform_check(self) -> Dict[str, Any]:
        import psutil
        import sys
        
        # Memory usage
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        # Python/process info
        process = psutil.Process()
        
        return {
            "python_version": sys.version.split()[0],
            "uptime_seconds": int(time.time() - process.create_time()),
            "memory": {
                "total_mb": round(memory.total / (1024 * 1024), 2),
                "available_mb": round(memory.available / (1024 * 1024), 2),
                "percent_used": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "percent_used": round((disk.used / disk.total) * 100, 2)
            },
            "process": {
                "memory_mb": round(process.memory_info().rss / (1024 * 1024), 2),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads()
            }
        }


class HealthChecker:
    """Main health checking coordinator."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self.health_checks: List[HealthCheck] = []
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks."""
        
        # Always check database
        self.health_checks.append(DatabaseHealthCheck())
        
        # Always check system
        try:
            self.health_checks.append(SystemHealthCheck())
        except ImportError:
            self.logger.warning("psutil not available, skipping system health checks")
        
        # External API checks (if enabled)
        if self.settings.external_apis.github_enabled:
            self.health_checks.append(
                ExternalAPIHealthCheck("github", self._check_github_api)
            )
        
        if self.settings.external_apis.linear_enabled:
            self.health_checks.append(
                ExternalAPIHealthCheck("linear", self._check_linear_api)
            )
        
        if self.settings.external_apis.openai_enabled:
            self.health_checks.append(
                ExternalAPIHealthCheck("openai", self._check_openai_api)
            )
    
    async def _check_github_api(self) -> Dict[str, Any]:
        """Check GitHub API connectivity."""
        import aiohttp
        
        headers = {"Authorization": f"token {self.settings.external_apis.github_token}"}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://api.github.com/user", headers=headers) as response:
                return {
                    "status_code": response.status,
                    "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining", "unknown")
                }
    
    async def _check_linear_api(self) -> Dict[str, Any]:
        """Check Linear API connectivity."""
        import aiohttp
        
        headers = {"Authorization": self.settings.external_apis.linear_api_key}
        query = {"query": "query { viewer { id name } }"}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                "https://api.linear.app/graphql", 
                headers=headers, 
                json=query
            ) as response:
                data = await response.json()
                return {
                    "status_code": response.status,
                    "has_viewer": "viewer" in data.get("data", {})
                }
    
    async def _check_openai_api(self) -> Dict[str, Any]:
        """Check OpenAI API connectivity."""
        import aiohttp
        
        headers = {"Authorization": f"Bearer {self.settings.external_apis.openai_api_key}"}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(
                "https://api.openai.com/v1/models", 
                headers=headers
            ) as response:
                return {
                    "status_code": response.status,
                    "models_available": response.status == 200
                }
    
    async def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks and return comprehensive status.
        
        Returns:
            Dict with overall status and individual check results
        """
        start_time = time.time()
        
        # Run all checks concurrently
        tasks = [check.check() for check in self.health_checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        checks = {}
        overall_status = HealthStatus.HEALTHY
        
        for i, (check, result) in enumerate(zip(self.health_checks, results)):
            if isinstance(result, Exception):
                checks[check.name] = {
                    "status": HealthStatus.UNHEALTHY,
                    "error": str(result)
                }
                overall_status = HealthStatus.UNHEALTHY
            else:
                checks[check.name] = result
                
                # Determine overall status
                if result["status"] == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result["status"] == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        total_time = (time.time() - start_time) * 1000
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self.settings.app.version,
            "environment": self.settings.app.environment.value,
            "total_check_time_ms": round(total_time, 2),
            "checks": checks
        }
    
    async def check_readiness(self) -> Dict[str, Any]:
        """
        Readiness check - lighter version for kubernetes/load balancer probes.
        
        Only checks critical dependencies required for the app to function.
        """
        start_time = time.time()
        
        # Only check database for readiness (most critical)
        db_check = DatabaseHealthCheck()
        db_result = await db_check.check()
        
        total_time = (time.time() - start_time) * 1000
        ready = db_result["status"] == HealthStatus.HEALTHY
        
        return {
            "ready": ready,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check_time_ms": round(total_time, 2),
            "database": db_result
        }
    
    async def check_liveness(self) -> Dict[str, Any]:
        """
        Liveness check - minimal check to verify app is responsive.
        
        Used by kubernetes/load balancers to determine if app should be restarted.
        """
        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self.settings.app.version
        }


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker