# ============================================================================
# Database Connection Module
# SAP B1 Inventory & Forecast Analyzer - Railway Deployment
# ============================================================================
# Purpose: PostgreSQL connection pooling and database utilities
#
# Features:
# - SQLAlchemy connection pooling for efficient database connections
# - Streamlit-compatible (cached connection pool)
# - Context manager support for safe connection handling
# - Query execution helpers
# - Materialized view refresh utilities
# ============================================================================

import os
from contextlib import contextmanager
from typing import Generator, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool


# ============================================================================
# Configuration
# ============================================================================

def get_database_url() -> str:
    """
    Get database URL from environment or Streamlit secrets.

    Priority:
    1. Streamlit secrets (Railway production)
    2. Environment variable (local development)
    3. Fallback to SQLite (for local testing)

    Returns:
        Database connection URL
    """
    # Try Streamlit secrets first (Railway)
    if "DATABASE_URL" in st.secrets:
        return st.secrets["DATABASE_URL"]

    # Try environment variable
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Fallback to SQLite for local development
    # Note: This should only be used for development/testing
    return "sqlite:///./data/local.db"


# ============================================================================
# Connection Pool Management
# ============================================================================

@st.cache_resource
def get_engine() -> Engine:
    """
    Create and cache SQLAlchemy engine with connection pooling.

    Streamlit reruns the script on every interaction, so we use
    @st.cache_resource to maintain the connection pool across reruns.

    Connection Pool Settings:
    - poolclass: QueuePool (standard pooling)
    - pool_size: 5 connections (conservative for Railway shared tier)
    - max_overflow: 10 additional connections during spikes
    - pool_timeout: 30 seconds (wait for available connection)
    - pool_recycle: 3600 seconds (recycle connections after 1 hour)

    Returns:
        SQLAlchemy Engine instance
    """
    database_url = get_database_url()

    # Parse connection string for SQLite vs PostgreSQL
    if database_url.startswith("sqlite"):
        # SQLite doesn't support connection pooling
        engine_kwargs = {"connect_args": {"check_same_thread": False}}
    else:
        # PostgreSQL connection pooling
        engine_kwargs = {
            "poolclass": QueuePool,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_pre_ping": True,  # Verify connections before using
        }

    engine = create_engine(database_url, **engine_kwargs)
    return engine


@contextmanager
def get_connection() -> Generator:
    """
    Context manager for database connections.

    Usage:
        with get_connection() as conn:
            result = conn.execute(text("SELECT * FROM items"))

    Yields:
        SQLAlchemy connection object

    Raises:
        SQLAlchemyError: If database operation fails
    """
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============================================================================
# Query Execution Helpers
# ============================================================================

def execute_query(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a pandas DataFrame.

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        pandas DataFrame with query results

    Raises:
        SQLAlchemyError: If query execution fails
    """
    with get_connection() as conn:
        result = conn.execute(text(query), params or {})
        columns = result.keys()
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=columns)


def execute_write(query: str, params: Optional[dict] = None) -> int:
    """
    Execute a SQL write operation (INSERT, UPDATE, DELETE).

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        Number of rows affected

    Raises:
        SQLAlchemyError: If query execution fails
    """
    with get_connection() as conn:
        result = conn.execute(text(query), params or {})
        return result.rowcount


def execute_batch(queries: list[str]) -> bool:
    """
    Execute multiple SQL queries in a single transaction.

    Useful for migrations or bulk updates.

    Args:
        queries: List of SQL query strings

    Returns:
        True if all queries executed successfully

    Raises:
        SQLAlchemyError: If any query fails
    """
    with get_connection() as conn:
        for query in queries:
            conn.execute(text(query))
        return True


# ============================================================================
# Materialized View Management
# ============================================================================

def refresh_materialized_view(view_name: str) -> bool:
    """
    Refresh a PostgreSQL materialized view.

    Args:
        view_name: Name of the materialized view to refresh

    Returns:
        True if refresh succeeded

    Raises:
        SQLAlchemyError: If refresh fails
    """
    query = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"
    try:
        execute_write(query)
        return True
    except SQLAlchemyError as e:
        # If CONCURRENTLY fails (not enough indexes), try without
        if "CONCURRENTLY" in str(e):
            query = f"REFRESH MATERIALIZED VIEW {view_name}"
            execute_write(query)
            return True
        raise


def refresh_all_materialized_views() -> dict[str, bool]:
    """
    Refresh all materialized views in the database.

    Returns:
        Dictionary mapping view names to success status

    Example:
        {
            "mv_latest_costs": True,
            "mv_latest_pricing": True,
            "mv_vendor_lead_times": True
        }
    """
    # Get all materialized views
    query = """
        SELECT matviewname
        FROM pg_matviews
        WHERE schemaname = 'public'
    """
    views_df = execute_query(query)
    view_names = views_df["matviewname"].tolist()

    results = {}
    for view_name in view_names:
        try:
            results[view_name] = refresh_materialized_view(view_name)
        except Exception as e:
            results[view_name] = False
            print(f"Failed to refresh {view_name}: {e}")

    return results


# ============================================================================
# Database Health Check
# ============================================================================

def check_database_health() -> dict:
    """
    Check database connectivity and health.

    Returns:
        Dictionary with health status information

    Example:
        {
            "status": "healthy",
            "connection": "ok",
            "pool_size": 5,
            "active_connections": 2
        }
    """
    try:
        engine = get_engine()
        pool = engine.pool

        # Test connection
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "connection": "ok",
            "pool_size": pool.size(),
            "active_connections": pool.checkedout(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connection": "failed",
            "error": str(e),
        }


# ============================================================================
# Migration Helper
# ============================================================================

def run_migration(migration_file: str) -> bool:
    """
    Run a database migration from a SQL file.

    Args:
        migration_file: Path to SQL migration file

    Returns:
        True if migration succeeded

    Raises:
        FileNotFoundError: If migration file doesn't exist
        SQLAlchemyError: If migration fails
    """
    with open(migration_file, "r") as f:
        sql = f.read()

    # Split by semicolon and execute each statement
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with get_connection() as conn:
        for statement in statements:
            conn.execute(text(statement))

    return True


# ============================================================================
# Streamlit Utilities
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_inventory_summary() -> pd.DataFrame:
    """
    Load inventory summary with caching for Streamlit.

    This is cached to avoid hitting the database on every user interaction.

    Returns:
        DataFrame with inventory summary
    """
    query = """
        SELECT
            ic.item_code,
            i.item_description,
            ic.warehouse_code,
            ic.on_hand_qty,
            ic.on_order_qty,
            ic.committed_qty,
            ic.available_qty
        FROM inventory_current ic
        JOIN items i ON ic.item_code = i.item_code
        WHERE ic.available_qty < 100
        ORDER BY ic.available_qty ASC
    """
    return execute_query(query)


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_summary() -> pd.DataFrame:
    """
    Load forecast summary with caching for Streamlit.

    Returns:
        DataFrame with forecast summary
    """
    query = """
        SELECT * FROM v_inventory_status_with_forecast
        WHERE shortage_urgency IN ('Critical', 'High')
    """
    return execute_query(query)


# ============================================================================
# Main (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test database connection
    print("Testing database connection...")
    health = check_database_health()
    print(f"Database health: {health}")

    # Test query execution
    if health["status"] == "healthy":
        print("\nTesting query execution...")
        result = execute_query("SELECT COUNT(*) as count FROM items")
        print(f"Item count: {result['count'].iloc[0]}")

        print("\nMaterialized views:")
        views = execute_query("""
            SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'
        """)
        print(views["matviewname"].tolist())
