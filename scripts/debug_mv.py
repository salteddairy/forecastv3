#!/usr/bin/env python3
"""Debug materialized view."""
import psycopg2

DATABASE_URL = "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@interchange.proxy.rlwy.net:46687/railway"


def debug_mv():
    """Check materialized view schema."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Checking mv_latest_pricing columns...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'mv_latest_pricing'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[0]}: {col[1]}")

    # The view needs to include region_key explicitly
    print("\nFixing mv_latest_pricing to include region_key...")
    cursor.execute("DROP MATERIALIZED VIEW IF EXISTS mv_latest_pricing CASCADE;")

    cursor.execute("""
        CREATE MATERIALIZED VIEW mv_latest_pricing AS
        SELECT
            item_code,
            price_level,
            region,
            region_key,
            unit_price,
            currency,
            effective_date,
            price_source
        FROM pricing
        WHERE is_active = TRUE
        GROUP BY item_code, price_level, region, region_key, unit_price, currency, effective_date, price_source
        ORDER BY item_code, price_level, region_key, effective_date DESC;
    """)
    print("  [OK] Created mv_latest_pricing with region_key")

    # Create index
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key
        ON mv_latest_pricing(item_code, price_level, region_key);
    """)
    print("  [OK] Created index")

    cursor.close()
    conn.close()
    print("\nFix complete!")


if __name__ == "__main__":
    debug_mv()
