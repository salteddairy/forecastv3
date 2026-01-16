#!/usr/bin/env python3
"""
Check what database objects exist in Railway PostgreSQL.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text


def check_database(database_url: str):
    """Check what objects exist in the database."""
    sys.stdout.reconfigure(encoding='utf-8')

    print("Connecting to Railway PostgreSQL...")
    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Check tables
        result = conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """))
        tables = [row[0] for row in result]

        print(f"\n=== TABLES ({len(tables)}) ===")
        for table in tables:
            # Get row count
            count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = count_result.scalar()
            print(f"  {table}: {count:,} rows")

        # Check materialized views
        result = conn.execute(text("""
            SELECT matviewname
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname;
        """))
        matviews = [row[0] for row in result]

        if matviews:
            print(f"\n=== MATERIALIZED VIEWS ({len(matviews)}) ===")
            for mv in matviews:
                print(f"  {mv}")

        # Check regular views
        result = conn.execute(text("""
            SELECT viewname
            FROM pg_views
            WHERE schemaname = 'public'
            ORDER BY viewname;
        """))
        views = [row[0] for row in result]

        if views:
            print(f"\n=== VIEWS ({len(views)}) ===")
            for view in views:
                print(f"  {view}")

        # Expected schema
        expected_tables = [
            'warehouses', 'vendors', 'items', 'inventory_current',
            'sales_orders', 'purchase_orders', 'costs', 'pricing',
            'forecasts', 'forecast_accuracy', 'margin_alerts'
        ]

        expected_matviews = [
            'mv_latest_costs', 'mv_latest_pricing', 'mv_vendor_lead_times'
        ]

        expected_views = [
            'v_inventory_status_with_forecast', 'v_item_margins'
        ]

        # Check completeness
        print(f"\n=== SCHEMA COMPLETENESS ===")
        print(f"Tables: {len(tables)}/{len(expected_tables)} expected")
        missing_tables = set(expected_tables) - set(tables)
        if missing_tables:
            print(f"  Missing: {missing_tables}")

        print(f"Materialized Views: {len(matviews)}/{len(expected_matviews)} expected")
        missing_matviews = set(expected_matviews) - set(matviews)
        if missing_matviews:
            print(f"  Missing: {missing_matviews}")

        print(f"Views: {len(views)}/{len(expected_views)} expected")
        missing_views = set(expected_views) - set(views)
        if missing_views:
            print(f"  Missing: {missing_views}")

        if len(tables) == len(expected_tables) and \
           len(matviews) == len(expected_matviews) and \
           len(views) == len(expected_views):
            print("\nSchema is complete!")
        else:
            print("\nSchema is incomplete. Some objects need to be created.")


if __name__ == "__main__":
    import os

    database_url = os.environ.get("DATABASE_URL")
    if not database_url and len(sys.argv) > 1:
        database_url = sys.argv[1]

    if not database_url:
        print("DATABASE_URL not set!")
        print("Usage: python scripts/check_schema.py <DATABASE_URL>")
        sys.exit(1)

    check_database(database_url)
