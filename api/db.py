"""
Minimal database layer for Pulse using asyncpg.

Provides connection pooling and basic query execution functions.
"""

import asyncpg
import os
import logging
import datetime
import json
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

__all__ = [
    "get_pool",
    "close_pool",
    "exec",
    "fetch",
    "fetchone",
    "fetchval",
    "transaction",
    "health_check",
    "insert_event",
    "get_recent_events"
]

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.

    Returns:
        asyncpg.Pool: Database connection pool

    Raises:
        ValueError: If DATABASE_URL is not set
        asyncpg.PostgresError: If connection fails
    """
    global _pool

    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # Connection pool configuration
        min_connections = int(os.getenv("DB_MIN_CONNECTIONS", "1"))
        max_connections = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
        command_timeout = int(os.getenv("DB_COMMAND_TIMEOUT", "60"))

        logger.info(f"Creating database pool with {min_connections}-{max_connections} connections")

        _pool = await asyncpg.create_pool(
            database_url,
            min_size=min_connections,
            max_size=max_connections,
            command_timeout=command_timeout
        )

        logger.info("Database pool created successfully")

    assert _pool is not None  # Type checker hint: _pool is guaranteed to be set above
    return _pool


async def close_pool():
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def exec(sql: str, *params) -> str:
    """
    Execute a SQL command that doesn't return results (INSERT, UPDATE, DELETE).

    Args:
        sql: SQL command to execute
        *params: Parameters for the SQL command

    Returns:
        str: Result status from the database

    Raises:
        asyncpg.PostgresError: If query execution fails
    """
    pool = await get_pool()

    async with pool.acquire() as connection:
        result = await connection.execute(sql, *params)
        logger.debug(f"Executed SQL: {sql[:100]}... | Result: {result}")
        return result


async def fetch(sql: str, *params) -> List[Dict[str, Any]]:
    """
    Execute a SQL query that returns results (SELECT).

    Args:
        sql: SQL query to execute
        *params: Parameters for the SQL query

    Returns:
        List[Dict[str, Any]]: Query results as list of dictionaries

    Raises:
        asyncpg.PostgresError: If query execution fails
    """
    pool = await get_pool()

    async with pool.acquire() as connection:
        rows = await connection.fetch(sql, *params)

        # Convert asyncpg.Record objects to dictionaries
        result = [dict(row) for row in rows]

        logger.debug(f"Fetched SQL: {sql[:100]}... | Rows: {len(result)}")
        return result


async def fetchone(sql: str, *params) -> Optional[Dict[str, Any]]:
    """
    Execute a SQL query that returns a single result.

    Args:
        sql: SQL query to execute
        *params: Parameters for the SQL query

    Returns:
        Optional[Dict[str, Any]]: Single result as dictionary, or None if no results

    Raises:
        asyncpg.PostgresError: If query execution fails
    """
    pool = await get_pool()

    async with pool.acquire() as connection:
        row = await connection.fetchrow(sql, *params)

        result = dict(row) if row else None
        logger.debug(f"Fetched one SQL: {sql[:100]}... | Found: {result is not None}")
        return result


async def fetchval(sql: str, *params) -> Any:
    """
    Execute a SQL query that returns a single value.

    Args:
        sql: SQL query to execute
        *params: Parameters for the SQL query

    Returns:
        Any: Single value result

    Raises:
        asyncpg.PostgresError: If query execution fails
    """
    pool = await get_pool()

    async with pool.acquire() as connection:
        result = await connection.fetchval(sql, *params)
        logger.debug(f"Fetched value SQL: {sql[:100]}... | Value: {result}")
        return result


@asynccontextmanager
async def transaction():
    """
    Context manager for database transactions.

    Usage:
        async with transaction() as tx:
            await exec("INSERT INTO ...", param1, param2)
            await exec("UPDATE ...", param3)
    """
    pool = await get_pool()

    async with pool.acquire() as connection:
        async with connection.transaction():
            # Provide the connection for transaction-scoped operations
            yield connection


async def health_check() -> Dict[str, Any]:
    """
    Perform a database health check.

    Returns:
        Dict[str, Any]: Health status information
    """
    try:
        pool = await get_pool()

        async with pool.acquire() as connection:
            # Test basic connectivity
            version = await connection.fetchval("SELECT version()")
            pool_size = pool.get_size()

            return {
                "status": "healthy",
                "postgres_version": version,
                "pool_size": pool_size,
                "pool_max_size": pool.get_max_size(),
                "pool_min_size": pool.get_min_size()
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Convenience functions for common operations
async def insert_event(
    ts: Union[str, datetime.datetime],
    source: str,
    actor: str,
    event_type: str,
    ref_id: str,
    title: Optional[str] = None,
    url: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> str:
    """Insert an event record."""
    sql = """
        INSERT INTO events (ts, source, actor, type, ref_id, title, url, meta)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (source, ref_id, type, ts) DO NOTHING
    """
    # Convert meta dict to JSON string for JSONB storage
    meta_json = json.dumps(meta or {})
    return await exec(sql, ts, source, actor, event_type, ref_id, title, url, meta_json)


async def get_recent_events(hours: int = 48, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent events within the specified hours."""
    sql = """
        SELECT * FROM events
        WHERE ts >= NOW() - INTERVAL '%s hours'
        ORDER BY ts DESC
        LIMIT $1
    """ % hours  # Use string formatting for interval, parameter for limit
    return await fetch(sql, limit)
