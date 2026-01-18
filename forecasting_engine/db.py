"""
Database connection and session management.
Uses SQLAlchemy with connection pooling for Railway PostgreSQL.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator

from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


# Global engine and session factory (initialized lazily)
_engine = None
_SessionLocal = None


def _initialize_engine():
    """Initialize database engine if not already initialized."""
    global _engine, _SessionLocal

    if _engine is not None:
        return

    if not settings.database_url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set it before using database operations."
        )

    # Create engine with connection pooling
    _engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=5,           # Number of connections to maintain
        max_overflow=10,       # Additional connections when needed
        pool_pre_ping=True,    # Verify connections before using
        pool_recycle=3600,     # Recycle connections after 1 hour
        echo=settings.log_level == "DEBUG",  # Log SQL if DEBUG
    )

    # Create session factory
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )

    logger.info("Database engine initialized")


def get_engine():
    """Get the database engine (initializes if needed)."""
    _initialize_engine()
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Get a database session with automatic cleanup.

    Yields:
        Session: SQLAlchemy database session

    Example:
        >>> with get_session() as session:
        ...     result = session.execute(text("SELECT 1"))
    """
    _initialize_engine()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> bool:
    """
    Test database connection.

    Returns:
        bool: True if connection successful
    """
    try:
        with get_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def get_database_version() -> str:
    """
    Get PostgreSQL version.

    Returns:
        str: Database version string
    """
    try:
        with get_session() as session:
            result = session.execute(text("SELECT version()")).scalar()
            return result
    except Exception as e:
        logger.error(f"Failed to get database version: {e}")
        return "Unknown"
