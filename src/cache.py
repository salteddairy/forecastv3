# ============================================================================
# Redis Cache Module
# SAP B1 Inventory & Forecast Analyzer - Railway Deployment
# ============================================================================
# Purpose: Redis caching layer for improved performance
#
# Features:
# - Redis connection management
# - Cache key generation and management
# - TTL-based caching with configurable expiration
# - Streamlit-compatible caching interface
# - Cache invalidation utilities
# ============================================================================

import json
import os
from functools import wraps
from typing import Any, Optional, Union

import pandas as pd
import redis
import streamlit as st


# ============================================================================
# Configuration
# ============================================================================

def get_redis_url() -> str:
    """
    Get Redis URL from environment or Streamlit secrets.

    Priority:
    1. Streamlit secrets (Railway production)
    2. Environment variable (local development)
    3. Fallback to localhost

    Returns:
        Redis connection URL
    """
    # Try Streamlit secrets first (Railway)
    if "REDIS_URL" in st.secrets:
        return st.secrets["REDIS_URL"]

    # Try environment variable
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    # Fallback to localhost for local development
    return "redis://localhost:6379/0"


def get_cache_ttl(ttl_type: str = "medium") -> int:
    """
    Get cache TTL (time-to-live) based on type.

    Args:
        ttl_type: Type of TTL ("short", "medium", "long")

    Returns:
        TTL in seconds
    """
    ttl_values = {
        "short": int(os.getenv("CACHE_TTL_SHORT", "300")),      # 5 minutes
        "medium": int(os.getenv("CACHE_TTL_MEDIUM", "3600")),   # 1 hour
        "long": int(os.getenv("CACHE_TTL_LONG", "86400")),      # 24 hours
    }
    return ttl_values.get(ttl_type, 3600)


# ============================================================================
# Redis Connection Management
# ============================================================================

@st.cache_resource
def get_redis_client() -> redis.Redis:
    """
    Create and cache Redis client.

    Streamlit reruns the script on every interaction, so we use
    @st.cache_resource to maintain the Redis client across reruns.

    Returns:
        Redis client instance
    """
    redis_url = get_redis_url()

    # Parse connection string
    if redis_url.startswith("rediss://"):
        # SSL connection
        client = redis.from_url(
            redis_url,
            decode_responses=True,
            ssl_cert_reqs=None,
        )
    else:
        # Regular connection
        client = redis.from_url(redis_url, decode_responses=True)

    return client


def check_redis_health() -> dict:
    """
    Check Redis connectivity and health.

    Returns:
        Dictionary with health status information
    """
    try:
        client = get_redis_client()
        client.ping()
        info = client.info()

        return {
            "status": "healthy",
            "connection": "ok",
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connection": "failed",
            "error": str(e),
        }


# ============================================================================
# Cache Key Generation
# ============================================================================

def make_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a consistent cache key from function arguments.

    Args:
        prefix: Cache key prefix (e.g., "inventory", "forecast")
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Cache key string

    Example:
        make_cache_key("inventory", "item123", warehouse="25")
        => "inventory:item123:warehouse:25"
    """
    parts = [prefix]

    # Add positional args
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            parts.append(str(arg))
        else:
            # For complex types, use hash or repr
            parts.append(str(hash(str(arg))))

    # Add keyword args
    for key, value in sorted(kwargs.items()):
        parts.append(f"{key}:{value}")

    return ":".join(parts)


# ============================================================================
# Basic Cache Operations
# ============================================================================

def cache_get(key: str) -> Optional[Any]:
    """
    Get a value from Redis cache.

    Args:
        key: Cache key

    Returns:
        Cached value, or None if not found or expired
    """
    try:
        client = get_redis_client()
        value = client.get(key)

        if value is None:
            return None

        # Try to deserialize JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Return as string if not JSON
            return value
    except Exception as e:
        print(f"Cache get error for key '{key}': {e}")
        return None


def cache_set(
    key: str,
    value: Any,
    ttl: Optional[int] = None,
    ttl_type: str = "medium"
) -> bool:
    """
    Set a value in Redis cache.

    Args:
        key: Cache key
        value: Value to cache (will be JSON serialized)
        ttl: Custom TTL in seconds (overrides ttl_type)
        ttl_type: TTL type ("short", "medium", "long")

    Returns:
        True if successful
    """
    try:
        client = get_redis_client()

        # Serialize to JSON
        if isinstance(value, pd.DataFrame):
            # Special handling for DataFrames
            value = value.to_dict(orient="records")
        serialized_value = json.dumps(value)

        # Set TTL
        if ttl is None:
            ttl = get_cache_ttl(ttl_type)

        client.setex(key, ttl, serialized_value)
        return True
    except Exception as e:
        print(f"Cache set error for key '{key}': {e}")
        return False


def cache_delete(key: str) -> bool:
    """
    Delete a value from Redis cache.

    Args:
        key: Cache key

    Returns:
        True if key was deleted
    """
    try:
        client = get_redis_client()
        return client.delete(key) > 0
    except Exception as e:
        print(f"Cache delete error for key '{key}': {e}")
        return False


def cache_clear_pattern(pattern: str) -> int:
    """
    Clear all keys matching a pattern.

    Args:
        pattern: Redis key pattern (e.g., "inventory:*")

    Returns:
        Number of keys deleted
    """
    try:
        client = get_redis_client()
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        print(f"Cache clear pattern error for '{pattern}': {e}")
        return 0


# ============================================================================
# Decorators for Caching Functions
# ============================================================================

def cached(
    prefix: str,
    ttl: Optional[int] = None,
    ttl_type: str = "medium",
    skip_args: Optional[list] = None
):
    """
    Decorator to cache function results in Redis.

    Args:
        prefix: Cache key prefix
        ttl: Custom TTL in seconds
        ttl_type: TTL type ("short", "medium", "long")
        skip_args: List of argument names to skip in key generation

    Usage:
        @cached(prefix="inventory", ttl_type="short")
        def get_inventory(item_code: str):
            return query_database(item_code)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            key_parts = [prefix, func.__name__]

            # Add relevant args to key
            arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]
            skip_set = set(skip_args or [])

            for i, (name, value) in enumerate(zip(arg_names, args)):
                if name not in skip_set:
                    key_parts.append(f"{name}:{value}")

            for name, value in sorted(kwargs.items()):
                if name not in skip_set:
                    key_parts.append(f"{name}:{value}")

            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_set(cache_key, result, ttl=ttl, ttl_type=ttl_type)

            return result

        return wrapper
    return decorator


# ============================================================================
# DataFrame-Specific Caching
# ============================================================================

def cache_dataframe(
    key: str,
    df: pd.DataFrame,
    ttl: Optional[int] = None,
    ttl_type: str = "medium"
) -> bool:
    """
    Cache a pandas DataFrame in Redis.

    Args:
        key: Cache key
        df: DataFrame to cache
        ttl: Custom TTL in seconds
        ttl_type: TTL type

    Returns:
        True if successful
    """
    try:
        # Convert DataFrame to dict for JSON serialization
        value = {
            "columns": df.columns.tolist(),
            "data": df.to_dict(orient="records"),
            "index": df.index.tolist(),
        }
        return cache_set(key, value, ttl=ttl, ttl_type=ttl_type)
    except Exception as e:
        print(f"Cache DataFrame error for key '{key}': {e}")
        return False


def get_cached_dataframe(key: str) -> Optional[pd.DataFrame]:
    """
    Get a cached DataFrame from Redis.

    Args:
        key: Cache key

    Returns:
        Cached DataFrame, or None if not found
    """
    value = cache_get(key)

    if value is None:
        return None

    try:
        # Reconstruct DataFrame from cached dict
        if isinstance(value, dict) and "columns" in value and "data" in value:
            df = pd.DataFrame(value["data"])
            df = df[value["columns"]]
            return df
        return None
    except Exception as e:
        print(f"Get cached DataFrame error for key '{key}': {e}")
        return None


# ============================================================================
# Streamlit Integration
# ============================================================================

@st.cache_data(ttl=300)
def load_with_cache(
    key_prefix: str,
    query_func,
    *args,
    ttl_type: str = "medium",
    **kwargs
) -> Any:
    """
    Load data with both Streamlit and Redis caching.

    This provides a two-layer caching strategy:
    1. Streamlit in-memory cache (per session)
    2. Redis cache (shared across sessions)

    Args:
        key_prefix: Cache key prefix
        query_func: Function to execute if cache miss
        *args: Arguments to pass to query_func
        ttl_type: Redis TTL type
        **kwargs: Keyword arguments to pass to query_func

    Returns:
        Cached or freshly loaded data
    """
    # Try Redis first
    cache_key = make_cache_key(key_prefix, *args, **kwargs)
    cached_value = cache_get(cache_key)

    if cached_value is not None:
        return cached_value

    # Execute function
    result = query_func(*args, **kwargs)

    # Cache in Redis
    cache_set(cache_key, result, ttl_type=ttl_type)

    return result


# ============================================================================
# Cache Invalidation Utilities
# ============================================================================

def invalidate_inventory_cache() -> int:
    """
    Invalidate all inventory-related cache entries.

    Returns:
        Number of keys deleted
    """
    patterns = [
        "inventory:*",
        "items:*",
        "warehouses:*",
    ]
    count = 0
    for pattern in patterns:
        count += cache_clear_pattern(pattern)
    return count


def invalidate_forecast_cache() -> int:
    """
    Invalidate all forecast-related cache entries.

    Returns:
        Number of keys deleted
    """
    patterns = [
        "forecast:*",
        "forecasts:*",
        "mv_forecast_summary:*",
    ]
    count = 0
    for pattern in patterns:
        count += cache_clear_pattern(pattern)
    return count


def invalidate_pricing_cache() -> int:
    """
    Invalidate all pricing-related cache entries.

    Returns:
        Number of keys deleted
    """
    patterns = [
        "pricing:*",
        "costs:*",
        "margins:*",
    ]
    count = 0
    for pattern in patterns:
        count += cache_clear_pattern(pattern)
    return count


def invalidate_all_cache() -> int:
    """
    Invalidate ALL cache entries (use with caution).

    Returns:
        Number of keys deleted
    """
    return cache_clear_pattern("*")


# ============================================================================
# Main (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test Redis connection
    print("Testing Redis connection...")
    health = check_redis_health()
    print(f"Redis health: {health}")

    # Test basic operations
    if health["status"] == "healthy":
        print("\nTesting cache operations...")

        # Test set/get
        cache_set("test_key", {"message": "Hello, Redis!"}, ttl_type="short")
        value = cache_get("test_key")
        print(f"Cached value: {value}")

        # Test DataFrame caching
        import numpy as np
        df = pd.DataFrame({
            "item_code": ["A", "B", "C"],
            "quantity": [10, 20, 30],
        })
        cache_dataframe("test_df", df, ttl_type="short")
        cached_df = get_cached_dataframe("test_df")
        print(f"Cached DataFrame:\n{cached_df}")

        # Cleanup
        cache_delete("test_key")
        cache_delete("test_df")
        print("\nCache test completed successfully!")
