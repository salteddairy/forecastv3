#!/usr/bin/env python3
"""Check and fix table schema."""
import psycopg2

DATABASE_URL = "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@interchange.proxy.rlwy.net:46687/railway"


def check_and_fix_schema():
    """Check table columns and fix schema."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Checking pricing table columns...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'pricing'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[0]}: {col[1]}")

    # Check if region_key column exists
    has_region_key = any(col[0] == 'region_key' for col in columns)

    if not has_region_key:
        print("\nAdding region_key column to pricing table...")
        cursor.execute("""
            ALTER TABLE pricing
            ADD COLUMN region_key VARCHAR(50)
            GENERATED ALWAYS AS (COALESCE(region, '')) STORED;
        """)
        print("  [OK] Added region_key column")
    else:
        print("\nregion_key column already exists")

    # Same for costs table
    print("\nChecking costs table columns...")
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'costs'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[0]}: {col[1]}")

    has_vendor_code_key = any(col[0] == 'vendor_code_key' for col in columns)

    if not has_vendor_code_key:
        print("\nAdding vendor_code_key column to costs table...")
        cursor.execute("""
            ALTER TABLE costs
            ADD COLUMN vendor_code_key VARCHAR(50)
            GENERATED ALWAYS AS (COALESCE(vendor_code, '')) STORED;
        """)
        print("  [OK] Added vendor_code_key column")
    else:
        print("\nvendor_code_key column already exists")

    # Recreate the materialized view
    print("\nRecreating mv_latest_pricing...")
    cursor.execute("DROP MATERIALIZED VIEW IF EXISTS mv_latest_pricing CASCADE;")
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
    print("  [OK] Created mv_latest_pricing")

    # Create index
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key
        ON mv_latest_pricing(item_code, price_level, region_key);
    """)
    print("  [OK] Created index")

    cursor.close()
    conn.close()
    print("\nSchema fix complete!")


if __name__ == "__main__":
    check_and_fix_schema()
