#!/usr/bin/env python3
# ============================================================================
# TSV to PostgreSQL Migration Script
# SAP B1 Inventory & Forecast Analyzer
# ============================================================================
# Purpose: Import existing TSV data into PostgreSQL database
#
# Prerequisites:
# - PostgreSQL database running with schema applied
# - TSV files in data/raw/ directory
# - Python dependencies installed
#
# Usage:
#   python scripts/migrate_tsv_data.py
# ============================================================================

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from sqlalchemy import create_engine, text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_database_url, execute_query, execute_write

# Define data directory
DATA_RAW_DIR = project_root / "data" / "raw"


# ============================================================================
# Configuration
# ============================================================================

TSV_FILES = {
    "items": "items.tsv",
    "sales": "sales.tsv",
    "supply": "supply.tsv",
}

# ============================================================================
# Data Loading Functions
# ============================================================================

def load_tsv(file_path: str) -> pd.DataFrame:
    """Load TSV file into DataFrame."""
    return pd.read_csv(file_path, sep="\t", encoding="utf-8", low_memory=False)


def extract_region_from_item_code(item_code: str) -> str:
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


# ============================================================================
# Migration Functions
# ============================================================================

def migrate_warehouses(df: pd.DataFrame):
    """Migrate warehouses from TSV data."""
    print("Migrating warehouses...")

    # Get unique warehouses from data
    warehouses = df["Warehouse"].dropna().unique()

    # Insert warehouses
    for wh in warehouses:
        wh_code = str(wh).strip()
        execute_write(
            """
            INSERT INTO warehouses (warehouse_code, warehouse_name, region)
            VALUES (%s, %s, %s)
            ON CONFLICT (warehouse_code) DO NOTHING
            """,
            {"wh_code": wh_code, "name": f"Warehouse {wh_code}", "region": "Unknown"}
        )

    print(f"  Migrated {len(warehouses)} warehouses")


def migrate_vendors(df_supply: pd.DataFrame):
    """Migrate vendors from supply TSV."""
    print("Migrating vendors...")

    # Get unique vendors
    vendors = df_supply[["VendorCode", "VendorName"]].dropna().drop_duplicates()

    for _, row in vendors.iterrows():
        execute_write(
            """
            INSERT INTO vendors (vendor_code, vendor_name)
            VALUES (%(vendor_code)s, %(vendor_name)s)
            ON CONFLICT (vendor_code) DO UPDATE
            SET vendor_name = EXCLUDED.vendor_name
            """,
            {"vendor_code": row["VendorCode"], "vendor_name": row["VendorName"]}
        )

    print(f"  Migrated {len(vendors)} vendors")


def migrate_items(df_items: pd.DataFrame):
    """Migrate items from TSV."""
    print("Migrating items...")

    migrated = 0
    for _, row in df_items.iterrows():
        item_code = str(row["Item No."]).strip()

        # Extract region from item code
        region = extract_region_from_item_code(item_code)

        # Map columns
        data = {
            "item_code": item_code,
            "item_description": row.get("Description", ""),
            "item_group": row.get("ItemGroup", ""),
            "region": region,
            "base_uom": row.get("BaseUoM", "ea"),
            "purch_uom": row.get("PurchUoM", None),
            "qty_per_purch_uom": row.get("QtyPerPurchUoM", None),
            "sales_uom": row.get("SalesUoM", None),
            "qty_per_sales_uom": row.get("QtyPerSalesUoM", None),
            "preferred_vendor_code": row.get("PreferredVendor", None),
            "last_vendor_code": row.get("LastVendorCode_Fallback", None),
            "last_purchase_date": None,  # Parse date if available
            "moq": row.get("MOQ", 0),
            "order_multiple": row.get("OrderMultiple", 1),
        }

        # Clean NaN values
        data = {k: (v if pd.notna(v) else None) for k, v in data.items()}

        try:
            execute_write(
                """
                INSERT INTO items (
                    item_code, item_description, item_group, region,
                    base_uom, purch_uom, qty_per_purch_uom, sales_uom, qty_per_sales_uom,
                    preferred_vendor_code, last_vendor_code, moq, order_multiple
                )
                VALUES (
                    %(item_code)s, %(item_description)s, %(item_group)s, %(region)s,
                    %(base_uom)s, %(purch_uom)s, %(qty_per_purch_uom)s, %(sales_uom)s, %(qty_per_sales_uom)s,
                    %(preferred_vendor_code)s, %(last_vendor_code)s, %(moq)s, %(order_multiple)s
                )
                ON CONFLICT (item_code) DO UPDATE
                SET item_description = EXCLUDED.item_description,
                    region = EXCLUDED.region,
                    moq = EXCLUDED.moq,
                    order_multiple = EXCLUDED.order_multiple
                """,
                data
            )
            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate item {item_code}: {e}")

    print(f"  Migrated {migrated} items")


def migrate_inventory(df_items: pd.DataFrame):
    """Migrate current inventory levels."""
    print("Migrating inventory...")

    migrated = 0
    for _, row in df_items.iterrows():
        item_code = str(row["Item No."]).strip()
        warehouse = str(row.get("Warehouse", "25")).strip()

        data = {
            "item_code": item_code,
            "warehouse_code": warehouse,
            "on_hand_qty": row.get("CurrentStock", 0),
            "on_order_qty": row.get("IncomingStock", 0),
            "committed_qty": row.get("CommittedStock", 0),
            "uom": row.get("BaseUoM", "ea"),
            "unit_cost": row.get("UnitCost", None),
        }

        # Clean NaN values
        data = {k: (v if pd.notna(v) else None) for k, v in data.items()}

        try:
            execute_write(
                """
                INSERT INTO inventory_current (
                    item_code, warehouse_code, on_hand_qty, on_order_qty,
                    committed_qty, uom, unit_cost
                )
                VALUES (
                    %(item_code)s, %(warehouse_code)s, %(on_hand_qty)s, %(on_order_qty)s,
                    %(committed_qty)s, %(uom)s, %(unit_cost)s
                )
                ON CONFLICT (item_code, warehouse_code) DO UPDATE
                SET on_hand_qty = EXCLUDED.on_hand_qty,
                    on_order_qty = EXCLUDED.on_order_qty,
                    committed_qty = EXCLUDED.committed_qty,
                    updated_at = NOW()
                """,
                data
            )
            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate inventory for {item_code}: {e}")

    print(f"  Migrated {migrated} inventory records")


def migrate_sales(df_sales: pd.DataFrame):
    """Migrate sales orders."""
    print("Migrating sales orders...")

    # Sample: migrate first 1000 for testing
    df_sample = df_sales.head(1000)

    migrated = 0
    for _, row in df_sample.iterrows():
        data = {
            "order_number": str(row.get("DocNum", f"SO-{migrated}")).strip(),
            "line_number": row.get("LineNum", 0),
            "posting_date": pd.to_datetime(row.get("Posting Date", datetime.now())),
            "promise_date": pd.to_datetime(row.get("PromiseDate", None)) if pd.notna(row.get("PromiseDate")) else None,
            "customer_code": row.get("CustomerCode", None),
            "customer_name": row.get("CustomerName", None),
            "item_code": str(row["Item No."]).strip(),
            "item_description": row.get("Description", ""),
            "ordered_qty": row.get("OrderedQty", 0),
            "shipped_qty": 0,  # Default to 0
            "row_value": row.get("RowValue", None),
            "warehouse_code": str(row.get("Warehouse", "25")).strip(),
            "linked_special_order_num": row.get("Linked_SpecialOrder_Num", None),
            "document_type": row.get("Document Type", "SalesOrder"),
        }

        # Clean NaN values
        data = {k: (v if pd.notna(v) else None) for k, v in data.items()}

        try:
            execute_write(
                """
                INSERT INTO sales_orders (
                    order_number, line_number, posting_date, promise_date,
                    customer_code, customer_name, item_code, item_description,
                    ordered_qty, row_value, warehouse_code, linked_special_order_num,
                    document_type
                )
                VALUES (
                    %(order_number)s, %(line_number)s, %(posting_date)s, %(promise_date)s,
                    %(customer_code)s, %(customer_name)s, %(item_code)s, %(item_description)s,
                    %(ordered_qty)s, %(row_value)s, %(warehouse_code)s, %(linked_special_order_num)s,
                    %(document_type)s
                )
                ON CONFLICT (order_number, line_number) DO NOTHING
                """,
                data
            )
            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate sales order: {e}")

    print(f"  Migrated {migrated} sales orders")


def migrate_purchase_orders(df_supply: pd.DataFrame):
    """Migrate purchase orders."""
    print("Migrating purchase orders...")

    # Sample: migrate first 1000 for testing
    df_sample = df_supply.head(1000)

    migrated = 0
    for _, row in df_sample.iterrows():
        data = {
            "po_number": str(row.get("DocNum", f"PO-{migrated}")).strip(),
            "line_number": row.get("LineNum", 0),
            "po_date": pd.to_datetime(row.get("PO Date", datetime.now())),
            "event_date": pd.to_datetime(row.get("EventDate", None)) if pd.notna(row.get("EventDate")) else None,
            "vendor_code": str(row.get("VendorCode", "")).strip(),
            "vendor_name": row.get("VendorName", ""),
            "item_code": str(row.get("ItemCode", "")).strip(),
            "ordered_qty": row.get("Quantity", 0),
            "received_qty": row.get("Quantity", 0),  # Assume all received
            "row_value": row.get("RowValue_SourceCurrency", None),
            "currency": row.get("Currency", "CAD"),
            "exchange_rate": row.get("ExchangeRate", 1.0),
            "warehouse_code": str(row.get("Warehouse", "25")).strip(),
            "freight_terms": row.get("FreightTerms", None),
            "fob": row.get("FOB", None),
            "lead_time_days": row.get("LeadTimeDays", None),
        }

        # Clean NaN values
        data = {k: (v if pd.notna(v) else None) for k, v in data.items()}

        try:
            execute_write(
                """
                INSERT INTO purchase_orders (
                    po_number, line_number, po_date, event_date,
                    vendor_code, vendor_name, item_code, ordered_qty, received_qty,
                    row_value, currency, exchange_rate, warehouse_code,
                    freight_terms, fob, lead_time_days
                )
                VALUES (
                    %(po_number)s, %(line_number)s, %(po_date)s, %(event_date)s,
                    %(vendor_code)s, %(vendor_name)s, %(item_code)s, %(ordered_qty)s, %(received_qty)s,
                    %(row_value)s, %(currency)s, %(exchange_rate)s, %(warehouse_code)s,
                    %(freight_terms)s, %(fob)s, %(lead_time_days)s
                )
                ON CONFLICT (po_number, line_number) DO NOTHING
                """,
                data
            )
            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate purchase order: {e}")

    print(f"  Migrated {migrated} purchase orders")


def migrate_costs(df_items: pd.DataFrame, df_supply: pd.DataFrame):
    """Migrate cost data."""
    print("Migrating costs...")

    migrated = 0
    for _, row in df_items.iterrows():
        item_code = str(row["Item No."]).strip()
        unit_cost = row.get("LastPurchasePrice_Fallback", row.get("UnitCost", None))

        if pd.isna(unit_cost):
            continue

        effective_date = datetime.now().date()

        try:
            execute_write(
                """
                INSERT INTO costs (item_code, effective_date, unit_cost, cost_source)
                VALUES (%(item_code)s, %(effective_date)s, %(unit_cost)s, %(cost_source)s)
                ON CONFLICT (item_code, effective_date, '') DO UPDATE
                SET unit_cost = EXCLUDED.unit_cost
                """,
                {
                    "item_code": item_code,
                    "effective_date": effective_date,
                    "unit_cost": float(unit_cost),
                    "cost_source": "SAP TSV Import"
                }
            )
            migrated += 1
        except Exception as e:
            print(f"  Warning: Failed to migrate cost for {item_code}: {e}")

    print(f"  Migrated {migrated} cost records")


# ============================================================================
# Main Migration Function
# ============================================================================

def run_migration():
    """Run the complete migration from TSV to PostgreSQL."""
    print("=" * 60)
    print("TSV to PostgreSQL Migration")
    print("=" * 60)
    print()

    # Check if TSV files exist
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

    # Load TSV files
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
        migrate_sales(df_sales)
        migrate_purchase_orders(df_supply)
        migrate_costs(df_items, df_supply)

        print("-" * 60)
        print()
        print("Migration completed successfully!")
        print()

        # Verify data
        print("Verifying data...")
        counts = execute_query("""
            SELECT
                (SELECT COUNT(*) FROM items) as items,
                (SELECT COUNT(*) FROM inventory_current) as inventory,
                (SELECT COUNT(*) FROM sales_orders) as sales,
                (SELECT COUNT(*) FROM purchase_orders) as purchases,
                (SELECT COUNT(*) FROM costs) as costs
        """)
        print(counts.to_string(index=False))

        return True

    except Exception as e:
        print(f"\nERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
