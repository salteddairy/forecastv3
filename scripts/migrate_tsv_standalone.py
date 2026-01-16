#!/usr/bin/env python3
"""
Standalone TSV to PostgreSQL migration script.
Does not depend on Streamlit.
"""
import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

# Database connection
DATABASE_URL = "postgresql://postgres:jNlZpTSycHzhYZrJuXRBBtGdWpNTAmZZ@interchange.proxy.rlwy.net:46687/railway"

# Data directory
DATA_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# TSV files
TSV_FILES = {
    "items": "items.tsv",
    "sales": "sales.tsv",
    "supply": "supply.tsv",
}


def get_connection():
    """Get database connection."""
    return psycopg2.connect(DATABASE_URL)


def load_tsv(file_path):
    """Load TSV file."""
    return pd.read_csv(file_path, sep="\t", encoding="utf-8", low_memory=False)


def extract_region_from_item_code(item_code):
    """Extract region from item code suffix."""
    if pd.isna(item_code):
        return "Delta"

    suffixes = {
        "-CGY": "Calgary",
        "-DEL": "Delta",
        "-EDM": "Edmonton",
        "-SAS": "Saskatoon",
        "-REG": "Regina",
        "-WPG": "Winnipeg",
        "-TOR": "Toronto",
        "-VGH": "Vaughan",
        "-MTL": "Montreal",
    }

    item_str = str(item_code).strip().upper()
    for suffix, region in suffixes.items():
        if item_str.endswith(suffix):
            return region
    return "Delta"


def migrate_warehouses(df):
    """Migrate warehouses."""
    print("Migrating warehouses...")
    conn = get_connection()
    cursor = conn.cursor()

    warehouses = df["Warehouse"].dropna().unique()
    count = 0
    for wh in warehouses:
        wh_code = str(wh).strip()
        try:
            cursor.execute(
                """
                INSERT INTO warehouses (warehouse_code, warehouse_name, region)
                VALUES (%s, %s, %s)
                ON CONFLICT (warehouse_code) DO NOTHING
                """,
                (wh_code, f"Warehouse {wh_code}", "Unknown")
            )
            count += 1
        except Exception as e:
            print(f"  Warning: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Migrated {count} warehouses")


def migrate_vendors(df):
    """Migrate vendors."""
    print("Migrating vendors...")
    conn = get_connection()
    cursor = conn.cursor()

    vendors = df[["VendorCode", "VendorName"]].dropna().drop_duplicates()
    count = 0
    for _, row in vendors.iterrows():
        try:
            cursor.execute(
                """
                INSERT INTO vendors (vendor_code, vendor_name)
                VALUES (%s, %s)
                ON CONFLICT (vendor_code) DO UPDATE
                SET vendor_name = EXCLUDED.vendor_name
                """,
                (row["VendorCode"], row["VendorName"])
            )
            count += 1
        except Exception as e:
            print(f"  Warning: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Migrated {count} vendors")


def migrate_items(df):
    """Migrate items."""
    print("Migrating items...")
    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    for _, row in df.iterrows():
        item_code = str(row["Item No."]).strip()
        region = extract_region_from_item_code(item_code)

        # Map columns
        data = (
            item_code,
            row.get("Description", ""),
            row.get("ItemGroup", ""),
            region,
            row.get("BaseUoM", "ea"),
            row.get("PurchUoM"),
            row.get("QtyPerPurchUoM"),
            row.get("SalesUoM"),
            row.get("QtyPerSalesUoM"),
            row.get("PreferredVendor"),
            row.get("LastVendorCode_Fallback"),
            None,  # last_purchase_date
            row.get("MOQ", 0),
            row.get("OrderMultiple", 1),
        )

        try:
            cursor.execute(
                """
                INSERT INTO items (
                    item_code, item_description, item_group, region,
                    base_uom, purch_uom, qty_per_purch_uom, sales_uom, qty_per_sales_uom,
                    preferred_vendor_code, last_vendor_code, moq, order_multiple
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (item_code) DO UPDATE
                SET item_description = EXCLUDED.item_description
                """,
                data
            )
            count += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate {item_code}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Migrated {count} items")


def migrate_inventory(df):
    """Migrate inventory."""
    print("Migrating inventory...")
    conn = get_connection()
    cursor = conn.cursor()

    # First, ensure all warehouse codes exist
    print("  Checking warehouse codes...")
    warehouses = df["Warehouse"].dropna().unique()
    for wh in warehouses:
        wh_code = str(wh).strip()
        cursor.execute(
            """
            INSERT INTO warehouses (warehouse_code, warehouse_name, region)
            VALUES (%s, %s, %s)
            ON CONFLICT (warehouse_code) DO NOTHING
            """,
            (wh_code, f"Warehouse {wh_code}", "Unknown")
        )

    count = 0
    batch_size = 100
    current_batch = []

    for idx, row in df.iterrows():
        item_code = str(row["Item No."]).strip()
        warehouse = str(row.get("Warehouse", "25")).strip()

        # Check if item exists first
        cursor.execute("SELECT 1 FROM items WHERE item_code = %s", (item_code,))
        if not cursor.fetchone():
            print(f"  Warning: Item {item_code} not found, skipping inventory")
            continue

        # Check if warehouse exists
        cursor.execute("SELECT 1 FROM warehouses WHERE warehouse_code = %s", (warehouse,))
        if not cursor.fetchone():
            print(f"  Warning: Warehouse {warehouse} not found, skipping inventory for {item_code}")
            continue

        data = (
            item_code,
            warehouse,
            row.get("CurrentStock", 0),
            row.get("IncomingStock", 0),
            row.get("CommittedStock", 0),
            row.get("BaseUoM", "ea"),
            row.get("UnitCost"),
        )

        try:
            cursor.execute(
                """
                INSERT INTO inventory_current (
                    item_code, warehouse_code, on_hand_qty, on_order_qty,
                    committed_qty, uom, unit_cost
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (item_code, warehouse_code) DO UPDATE
                SET on_hand_qty = EXCLUDED.on_hand_qty,
                    on_order_qty = EXCLUDED.on_order_qty,
                    committed_qty = EXCLUDED.committed_qty,
                    updated_at = NOW()
                """,
                data
            )
            count += 1

            # Commit every batch_size records
            if count % batch_size == 0:
                conn.commit()
                print(f"  Progress: {count} records migrated...")

        except Exception as e:
            print(f"  Warning: Failed to migrate inventory for {item_code}: {e}")
            # Rollback on error to continue with next record
            conn.rollback()

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Migrated {count} inventory records")


def run_migration():
    """Run the complete migration."""
    print("=" * 60)
    print("TSV to PostgreSQL Migration")
    print("=" * 60)
    print()

    # Check TSV files
    tsv_paths = {}
    for key, filename in TSV_FILES.items():
        path = DATA_RAW_DIR / filename
        if not path.exists():
            print(f"ERROR: TSV file not found: {path}")
            return False
        tsv_paths[key] = path
        print(f"Found: {filename}")

    print()
    print("Loading TSV files...")

    # Load TSV files (sample for faster testing)
    df_items = load_tsv(tsv_paths["items"])
    df_sales = load_tsv(tsv_paths["sales"])
    df_supply = load_tsv(tsv_paths["supply"])

    print(f"  Items: {len(df_items)} rows")
    print(f"  Sales: {len(df_sales)} rows")
    print(f"  Supply: {len(df_supply)} rows")
    print()

    # Run migrations
    print("Starting migration...")
    print("-" * 60)

    try:
        migrate_warehouses(df_items)
        migrate_vendors(df_supply)
        migrate_items(df_items)
        migrate_inventory(df_items)

        print("-" * 60)
        print()
        print("Migration completed successfully!")
        print()

        # Verify data
        print("Verifying data...")
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM items")
        items_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM inventory_current")
        inventory_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM vendors")
        vendors_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        print(f"  Items: {items_count}")
        print(f"  Inventory records: {inventory_count}")
        print(f"  Vendors: {vendors_count}")

        return True

    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
