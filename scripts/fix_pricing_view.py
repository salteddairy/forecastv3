#!/usr/bin/env python3
"""Fix pricing materialized view with new schema."""
import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")


def fix_pricing_view():
    """Drop and recreate the pricing materialized view."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Fixing pricing materialized view...")

    # Drop the old materialized view
    try:
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS mv_latest_pricing CASCADE;")
        print("  [OK] Dropped old mv_latest_pricing")
    except Exception as e:
        print(f"  [X] Error dropping view: {e}")

    # Recreate the materialized view with the correct schema
    try:
        cursor.execute("""
            CREATE MATERIALIZED VIEW mv_latest_pricing AS
            SELECT DISTINCT ON (item_code, price_level, region_key)
                item_code,
                price_level,
                region,
                unit_price,
                currency,
                effective_date,
                price_source
            FROM pricing
            WHERE is_active = TRUE
            ORDER BY item_code, price_level, region_key, effective_date DESC;
        """)
        print("  [OK] Created new mv_latest_pricing")
    except Exception as e:
        print(f"  [X] Error creating view: {e}")

    # Create the unique index
    try:
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key
            ON mv_latest_pricing(item_code, price_level, region_key);
        """)
        print("  [OK] Created index on mv_latest_pricing")
    except Exception as e:
        print(f"  [X] Error creating index: {e}")

    cursor.close()
    conn.close()
    print("\nFix complete!")


if __name__ == "__main__":
    fix_pricing_view()
