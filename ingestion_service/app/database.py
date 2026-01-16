"""
Database connection and operations for ingestion service.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from typing import List, Dict, Any
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager."""

    def __init__(self):
        """Initialize database connection pool."""
        settings = get_settings()
        self.engine = create_engine(
            settings.database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=settings.debug,
        )

    def get_connection(self):
        """Get a database connection from the pool."""
        return self.engine.connect()

    def health(self) -> bool:
        """Check if database is accessible."""
        try:
            with self.get_connection() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Table mappings
TABLE_MAPPING = {
    "items": "items",
    "vendors": "vendors",
    "warehouses": "warehouses",
    "inventory_current": "inventory_current",
    "sales_orders": "sales_orders",
    "purchase_orders": "purchase_orders",
    "costs": "costs",
    "pricing": "pricing",
}


def insert_records(data_type: str, records: List[Dict[str, Any]]) -> int:
    """
    Insert records into the database.

    Args:
        data_type: Type of data (must match TABLE_MAPPING key)
        records: List of validated record dictionaries

    Returns:
        Number of records inserted

    Raises:
        ValueError: If data_type is invalid
    """
    table_name = TABLE_MAPPING.get(data_type)
    if not table_name:
        raise ValueError(f"Unknown data_type: {data_type}")

    db = Database()

    if not records:
        return 0

    # Build INSERT query with ON CONFLICT handling
    first_record = records[0]
    columns = list(first_record.keys())

    # For each data type, define the conflict key (unique constraint)
    conflict_keys = {
        "items": "item_code",
        "vendors": "vendor_code",
        "warehouses": "warehouse_code",
        "inventory_current": ["item_code", "warehouse_code"],
        "sales_orders": "order_id",
        "purchase_orders": "order_id",
        "costs": ["item_code", "effective_date", "vendor_code"],
        "pricing": ["item_code", "price_level", "region"],
    }

    conflict_key = conflict_keys.get(data_type, "id")

    try:
        with db.get_connection() as conn:
            # Start transaction
            trans = conn.begin()

            inserted = 0

            for record in records:
                # Build INSERT ... ON CONFLICT ... DO UPDATE query
                # Use named parameters for each column
                param_dict = {}
                for i, (col, val) in enumerate(record.items()):
                    param_dict[col] = val

                column_names = ", ".join(columns)
                value_placeholders = ", ".join([f":{col}" for col in columns])
                update_placeholders = ", ".join([
                    f"{col} = EXCLUDED.{col}"
                    for col in columns
                    if col not in ([conflict_key] if isinstance(conflict_key, str) else conflict_key)
                ])

                # Handle composite conflict keys
                if isinstance(conflict_key, list):
                    conflict_target = ", ".join(conflict_key)
                else:
                    conflict_target = conflict_key

                query = text(f"""
                    INSERT INTO {table_name} ({column_names})
                    VALUES ({value_placeholders})
                    ON CONFLICT ({conflict_target})
                    DO UPDATE SET {update_placeholders}
                """)

                conn.execute(query, param_dict)
                inserted += 1

            # Commit transaction
            trans.commit()
            logger.info(f"Inserted {inserted} records into {table_name}")

            return inserted

    except Exception as e:
        logger.error(f"Failed to insert records into {table_name}: {e}")
        raise


def refresh_materialized_views() -> None:
    """Refresh all materialized views after data ingestion."""
    db = Database()

    views = [
        "mv_latest_costs",
        "mv_latest_pricing",
        "mv_vendor_lead_times",
        "mv_forecast_summary",
        "mv_forecast_accuracy_summary",
    ]

    try:
        with db.get_connection() as conn:
            for view in views:
                try:
                    conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
                    logger.info(f"Refreshed materialized view: {view}")
                except Exception as e:
                    logger.warning(f"Could not refresh {view}: {e}")
                    # Non-concurrent refresh as fallback
                    try:
                        conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
                        logger.info(f"Refreshed materialized view (non-concurrent): {view}")
                    except Exception as e2:
                        logger.error(f"Failed to refresh {view}: {e2}")
    except Exception as e:
        logger.error(f"Failed to refresh materialized views: {e}")
        # Don't raise - this is non-critical
