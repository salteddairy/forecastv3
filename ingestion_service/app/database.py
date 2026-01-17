"""
Database connection and operations for ingestion service.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from typing import List, Dict, Any
import logging
import re

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


def extract_column_names(conflict_key_list: List[str]) -> List[str]:
    """
    Extract actual column names from conflict key list.
    Handles SQL expressions like 'COALESCE(region, '')' -> 'region'
    """
    column_names = []
    for key in conflict_key_list:
        # If it's a simple column name (no parentheses), use it as-is
        if '(' not in key:
            column_names.append(key)
        else:
            # Extract column name from SQL function calls
            # COALESCE(region, '') -> region
            match = re.search(r'COALESCE\((\w+)', key)
            if match:
                column_names.append(match.group(1))
            else:
                # Fallback: try to extract first word inside parentheses
                match = re.search(r'\((\w+)', key)
                if match:
                    column_names.append(match.group(1))
    return column_names


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

    # For each data type, define the conflict key (unique constraint)
    # Note: For order tables, use business keys for UPSERT (no order tracking needed)
    conflict_keys = {
        "items": "item_code",
        "vendors": "vendor_code",
        "warehouses": "warehouse_code",
        "inventory_current": ["item_code", "warehouse_code"],
        "sales_orders": ["item_code", "posting_date", "warehouse_code", "COALESCE(customer_code, '')"],
        "purchase_orders": ["item_code", "po_date", "warehouse_code", "vendor_code"],
        "costs": ["item_code", "effective_date", "COALESCE(vendor_code, '')"],
        "pricing": ["item_code", "price_level", "COALESCE(region, '')", "effective_date"],
    }

    conflict_key = conflict_keys.get(data_type, "id")

    try:
        with db.get_connection() as conn:
            # Start transaction
            trans = conn.begin()

            inserted = 0

            for record in records:
                # Build INSERT ... ON CONFLICT ... DO UPDATE query
                # Filter out None values to handle optional fields (order tracking columns)
                param_dict = {col: val for col, val in record.items() if val is not None}
                columns_filtered = list(param_dict.keys())

                column_names = ", ".join(columns_filtered)
                value_placeholders = ", ".join([f":{col}" for col in columns_filtered])

                # Handle composite conflict keys
                if isinstance(conflict_key, list):
                    conflict_target = ", ".join(conflict_key)
                    # Extract actual column names for UPDATE exclusion
                    exclude_columns = extract_column_names(conflict_key)
                else:
                    conflict_target = conflict_key
                    exclude_columns = [conflict_key]

                # Build UPDATE placeholders (exclude conflict key columns)
                update_placeholders = ", ".join([
                    f"{col} = EXCLUDED.{col}"
                    for col in columns_filtered
                    if col not in exclude_columns
                ])

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
