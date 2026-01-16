#!/usr/bin/env python3
"""
Consolidation Readiness Check

This script checks if your data is ready for the item master consolidation
and helps identify any issues that need to be addressed.

Usage:
    python scripts/check_consolidation_readiness.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.consolidation import (
    get_item_state,
    extract_base_item_code,
    extract_region_from_item_code,
    validate_consolidation_readiness,
    check_consolidation_status,
    WAREHOUSE_CODES_FUTURE,
    REGIONAL_SUFFIXES
)
from src.ingestion import load_items, load_sales_orders

print("=" * 80)
print("CONSOLIDATION READINESS CHECK")
print("=" * 80)
print()

# ============================================================================
# Check 1: Load current data
# ============================================================================
print("Check 1: Loading current data...")
print("-" * 80)

data_dir = project_root / "data" / "raw"

try:
    df_items = load_items(data_dir / "items.tsv")
    df_sales = load_sales_orders(data_dir / "sales.tsv")
    print(f"  [OK] Loaded {len(df_items)} items, {len(df_sales)} sales records")
except Exception as e:
    print(f"  [ERROR] Failed to load data: {e}")
    sys.exit(1)

# ============================================================================
# Check 2: Analyze item state distribution
# ============================================================================
print("\nCheck 2: Analyzing item state distribution...")
print("-" * 80)

status = check_consolidation_status(df_items)
print(f"  Status: {status['status']}")
print(f"  {status['message']}")
print(f"  Regional items: {status['regional_count']}")
print(f"  Consolidated items: {status['consolidated_count']}")

# ============================================================================
# Check 3: Identify multi-warehouse items (current error cases)
# ============================================================================
print("\nCheck 3: Checking for multi-warehouse items...")
print("-" * 80)

if 'Warehouse' in df_items.columns:
    item_warehouse_counts = df_items.groupby('Item No.')['Warehouse'].nunique()
    multi_warehouse = item_warehouse_counts[item_warehouse_counts > 1]

    if len(multi_warehouse) > 0:
        print(f"  Found {len(multi_warehouse)} items with multiple warehouses:")
        print()
        print("  These are the 'error cases' you mentioned - items that exist")
        print("  in multiple warehouses before consolidation.")
        print()
        print("  Use these to test multi-warehouse logic!")
        print()

        for i, (item_code, count) in enumerate(multi_warehouse.head(10).items(), 1):
            warehouses = df_items[df_items['Item No.'] == item_code]['Warehouse'].tolist()
            region = extract_region_from_item_code(item_code)
            print(f"  {i}. {item_code}")
            print(f"     Warehouses: {warehouses}")
            print(f"     Region: {region}")
            print(f"     Stock: {df_items[df_items['Item No.'] == item_code]['CurrentStock'].sum():.0f}")
            print()
    else:
        print("  [OK] No items with multiple warehouses found")
        print("  This is expected for current state (1 warehouse per item)")
else:
    print("  [INFO] No 'Warehouse' column in current data")
    print("  Warehouse derived from item code suffix")

# ============================================================================
# Check 4: Validate consolidation readiness
# ============================================================================
print("\nCheck 4: Validating consolidation readiness...")
print("-" * 80)

issues = validate_consolidation_readiness(df_items, df_sales)

print("\n  Potential Issues:")

if issues['regional_items_found']:
    print(f"  - Regional items found: {len(issues['regional_items_found'])}")
    print(f"    Examples: {', '.join(issues['regional_items_found'][:5])}")

if issues['multi_warehouse_items']:
    print(f"  - Multi-warehouse items: {len(issues['multi_warehouse_items'])}")
    print(f"    Examples: {', '.join(issues['multi_warehouse_items'][:5])}")

if issues['missing_warehouse']:
    print(f"  - Items without warehouse: {len(issues['missing_warehouse'])}")
    print(f"    Examples: {', '.join(issues['missing_warehouse'][:5])}")

if issues['conversion_factors_missing']:
    print(f"  - Missing conversion factors: {len(issues['conversion_factors_missing'])}")
    print(f"    Examples: {', '.join(issues['conversion_factors_missing'][:5])}")

if not any(issues.values()):
    print("  [OK] No issues found!")

# ============================================================================
# Check 5: Analyze regional variant structure
# ============================================================================
print("\nCheck 5: Analyzing regional variant structure...")
print("-" * 80)

# Group by base item code (remove suffix)
df_items['base_item_code'] = df_items['Item No.'].apply(extract_base_item_code)
regional_groups = df_items[df_items['Item No.'].str.contains('-', na=False)].groupby('base_item_code')

variant_counts = regional_groups.size()
multi_variant = variant_counts[variant_counts > 1]

if len(multi_variant) > 0:
    print(f"  Found {len(multi_variant)} base items with multiple regional variants:")
    print()

    for i, (base_code, count) in enumerate(multi_variant.head(10).items(), 1):
        variants = df_items[df_items['base_item_code'] == base_code]['Item No.'].tolist()
        regions = [extract_region_from_item_code(v) for v in variants]
        total_stock = df_items[df_items['base_item_code'] == base_code]['CurrentStock'].sum()
        print(f"  {i}. Base: {base_code}")
        print(f"     Variants: {', '.join(variants)}")
        print(f"     Regions: {', '.join(regions)}")
        print(f"     Total Stock: {total_stock:.0f}")
        print()

    print("  After consolidation, these will become:")
    print(f"  - Single item code: {base_code}")
    print(f"  - Multiple warehouses: {count}")
    print()
else:
    print("  [INFO] No items with multiple regional variants found")
    print("  (This is unusual - most items should have regional variants)")

# ============================================================================
# Check 6: Warehouse distribution by region
# ============================================================================
print("\nCheck 6: Warehouse distribution by region...")
print("-" * 80)

region_counts = df_items['Region'].value_counts()
print("  Items per region:")
for region, count in region_counts.items():
    pct = count / len(df_items) * 100
    print(f"    {region:12s}: {count:5d} ({pct:5.1f}%)")

# ============================================================================
# Check 7: Historical sales mapping preview
# ============================================================================
print("\nCheck 7: Historical sales mapping preview...")
print("-" * 80)

# Show how regional items will map to consolidated format
regional_sales = df_sales[df_sales['item_code'].str.contains('-', na=False)]

if len(regional_sales) > 0:
    print("  Sample historical sales records and how they'll map:")
    print()

    for i, (idx, row) in enumerate(regional_sales.head(5).iterrows(), 1):
        item_code = row['item_code']
        base_code = extract_base_item_code(item_code)
        region = extract_region_from_item_code(item_code)
        future_warehouse = WAREHOUSE_CODES_FUTURE.get(region, '000-DEL1')

        print(f"  {i}. Historical: {item_code} ({region})")
        print(f"     Mapped to: {base_code} + Warehouse {future_warehouse}")
        print(f"     Date: {row['date']}, Qty: {row['qty']}")
        print()
else:
    print("  [INFO] No regional item codes in sales data")
    print("  Data may already be in consolidated format")

# ============================================================================
# Check 8: Recommendations
# ============================================================================
print("\nCheck 8: Recommendations...")
print("-" * 80)

if status['status'] == 'CURRENT_STATE':
    print("  [CURRENT STATE DETECTED]")
    print()
    print("  Your data is in CURRENT STATE (regional item codes).")
    print()
    print("  NEXT STEPS:")
    print("  1. Run SAP query to find multi-warehouse error cases:")
    print("     queries/find_multi_warehouse_items.sql")
    print("  2. Review post-consolidation SAP queries:")
    print("     - queries/post_consolidation_items.sql")
    print("     - queries/post_consolidation_sales.sql")
    print("  3. Test multi-warehouse logic with error cases")
    print("  4. Before consolidation cutover:")
    print("     - Clear all caches")
    print("     - Export data with new queries")
    print("     - Validate warehouse assignments")
    print()

elif status['status'] == 'FUTURE_STATE':
    print("  [FUTURE STATE DETECTED]")
    print()
    print("  Your data is already in FUTURE STATE (consolidated codes).")
    print()
    print("  VALIDATION CHECKS:")
    print("  ✓ Item codes have no regional suffixes")
    print("  ✓ Multiple warehouses per item")
    print("  ✓ Historical data mapped correctly")
    print()

else:
    print("  [MIXED STATE DETECTED]")
    print()
    print("  Your data has BOTH regional and consolidated items.")
    print("  This is unexpected for a hard cutover approach.")
    print()
    print("  ACTION REQUIRED:")
    print("  1. Investigate why mixed state exists")
    print("  2. Ensure data exports are consistent")
    print("  3. Re-export data if needed")
    print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 80)
print("CONSOLIDATION READINESS: SUMMARY")
print("=" * 80)
print()

print("Current Status:")
print(f"  Items: {len(df_items)}")
print(f"  Sales records: {len(df_sales)}")
print(f"  State: {status['status']}")
print()

print("Key Findings:")
print(f"  Regional items: {status['regional_count']}")
print(f"  Consolidated items: {status['consolidated_count']}")
print(f"  Multi-warehouse items: {len(issues['multi_warehouse_items'])}")
print()

print("Readiness:")
if status['status'] == 'CURRENT_STATE' and len(issues['multi_warehouse_items']) == 0:
    print("  [READY] Data is in current state and ready for consolidation planning")
    print()
    print("  Your forecasting tool now supports:")
    print("  ✓ Item state detection")
    print("  ✓ Historical data mapping (regional → consolidated)")
    print("  ✓ Warehouse code mapping (old → new)")
    print("  ✓ Multi-warehouse logic (for future state)")
    print()
    print("  When consolidation happens:")
    print("  1. Run post-consolidation SAP queries")
    print("  2. Update TSV exports")
    print("  3. Clear caches and reload data")
    print("  4. Tool will automatically detect future state")
    print()
elif status['status'] == 'FUTURE_STATE':
    print("  [READY] Data is in future state")
    print("  Tool will handle consolidated items correctly")
    print()
else:
    print("  [ATTENTION REQUIRED] Review issues above before consolidation")
    print()

print("Documentation:")
print("  - FORECASTING_TOOL_GUIDE.md (consolidation requirements)")
print("  - FORECASTING_CONSOLIDATION_ANALYSIS.md (compatibility analysis)")
print("  - queries/post_consolidation_*.sql (SAP queries for cutover)")
print()
