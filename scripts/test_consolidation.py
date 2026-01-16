"""
Test Consolidation Module with Existing TSV Data

Tests the consolidation.py module against current TSV data to verify:
1. Item state detection works
2. Warehouse mapping is correct
3. Multi-warehouse items are identified
4. Data is ready for future consolidation
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import logging

from consolidation import (
    get_item_state,
    extract_region_from_item_code,
    extract_base_item_code,
    map_historical_item_code,
    get_warehouses_for_item,
    validate_consolidation_readiness,
    check_consolidation_status,
    WAREHOUSE_CODES_FUTURE,
    REGIONAL_SUFFIXES
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_tsv_data():
    """Load TSV data files"""
    data_dir = Path(__file__).parent.parent / "data" / "raw"

    logger.info(f"Loading data from {data_dir}...")

    # Load items
    items_path = data_dir / "items.tsv"
    if items_path.exists():
        df_items = pd.read_csv(items_path, sep='\t')
        logger.info(f"  Loaded {len(df_items)} items from {items_path.name}")
    else:
        logger.error(f"  Items file not found: {items_path}")
        return None, None

    # Load sales
    sales_path = data_dir / "sales.tsv"
    if sales_path.exists():
        df_sales = pd.read_csv(sales_path, sep='\t')
        logger.info(f"  Loaded {len(df_sales)} sales records from {sales_path.name}")
    else:
        logger.warning(f"  Sales file not found: {sales_path}")
        df_sales = None

    # Load supply
    supply_path = data_dir / "supply.tsv"
    if supply_path.exists():
        df_supply = pd.read_csv(supply_path, sep='\t')
        logger.info(f"  Loaded {len(df_supply)} supply records from {supply_path.name}")
    else:
        logger.warning(f"  Supply file not found: {supply_path}")
        df_supply = None

    return df_items, df_sales


def test_item_state_detection(df_items):
    """Test item state detection on real data"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Item State Detection")
    logger.info("="*70)

    # Add item state column
    df_items['item_state'] = df_items['Item No.'].apply(get_item_state)

    # Count states
    state_counts = df_items['item_state'].value_counts()
    logger.info(f"\nItem State Distribution:")
    for state, count in state_counts.items():
        pct = (count / len(df_items)) * 100
        logger.info(f"  {state}: {count} ({pct:.1f}%)")

    # Show examples
    logger.info(f"\nSample Items by State:")
    for state in ['CURRENT', 'FUTURE', 'UNKNOWN']:
        if state in state_counts.index:
            samples = df_items[df_items['item_state'] == state]['Item No.'].head(5).tolist()
            logger.info(f"  {state} examples: {samples}")

    return df_items


def test_regional_variants(df_items, base_code='BX010155'):
    """Test finding all regional variants of a base item"""
    logger.info("\n" + "="*70)
    logger.info(f"TEST 2: Regional Variants Analysis (Base: {base_code})")
    logger.info("="*70)

    # Find all variants
    variants = df_items[df_items['Item No.'].str.startswith(base_code, na=False)]

    if len(variants) == 0:
        logger.warning(f"No variants found for base code: {base_code}")
        return None

    logger.info(f"\nFound {len(variants)} variants:")

    for _, row in variants.iterrows():
        item_code = row['Item No.']
        state = get_item_state(item_code)
        region = extract_region_from_item_code(item_code)
        base = extract_base_item_code(item_code)

        # Get warehouse info
        if 'WhsCode' in row and pd.notna(row['WhsCode']):
            warehouse = row['WhsCode']
        else:
            # Try to get from suffix
            if state == 'CURRENT':
                warehouse = WAREHOUSE_CODES_FUTURE.get(region, 'UNKNOWN')
            else:
                warehouse = 'UNKNOWN'

        logger.info(f"  {item_code:20s} | State: {state:7s} | Region: {region:10s} | Whs: {warehouse}")

    return variants


def test_bx010155_analysis(df_items, df_sales):
    """Analyze BX010155-EDM specifically"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: BX010155-EDM Multi-Warehouse Analysis")
    logger.info("="*70)

    # Find BX010155-EDM
    target_item = 'BX010155-EDM'

    if target_item not in df_items['Item No.'].values:
        logger.warning(f"Item {target_item} not found in items.tsv")
        return

    # Get item data
    item_data = df_items[df_items['Item No.'] == target_item].iloc[0]

    logger.info(f"\nItem: {target_item}")
    logger.info(f"  Description: {item_data.get('Item Name', 'N/A')}")
    logger.info(f"  State: {get_item_state(target_item)}")
    logger.info(f"  Region: {extract_region_from_item_code(target_item)}")
    logger.info(f"  Base Code: {extract_base_item_code(target_item)}")

    # Check UoM
    if 'InvntryUom' in item_data:
        logger.info(f"  Base UoM: {item_data['InvntryUom']}")
    if 'SalUnitMsr' in item_data:
        logger.info(f"  Sales UoM: {item_data['SalUnitMsr']}")
    if 'BuyUnitMsr' in item_data:
        logger.info(f"  Purchasing UoM: {item_data['BuyUnitMsr']}")

    # Check warehouse
    if 'WhsCode' in item_data and pd.notna(item_data['WhsCode']):
        logger.info(f"  Warehouse: {item_data['WhsCode']}")
    else:
        # Derive from region
        region = extract_region_from_item_code(target_item)
        future_whs = WAREHOUSE_CODES_FUTURE.get(region, 'UNKNOWN')
        logger.info(f"  Warehouse (derived): {future_whs}")

    # Find all variants
    logger.info(f"\nAll BX010155 Variants:")
    base_code = extract_base_item_code(target_item)
    variants = df_items[df_items['Item No.'].str.startswith(base_code, na=False)]

    for _, variant in variants.iterrows():
        code = variant['Item no.'] if 'Item no.' in variant else variant['Item No.']
        state = get_item_state(code)
        region = extract_region_from_item_code(code)

        stock = variant.get('OnHand', variant.get('InStock', 'N/A'))
        whs = variant.get('WhsCode', variant.get('Warehouse', 'N/A'))

        logger.info(f"  {code:20s} | Stock: {stock:8s} | Whs: {whs:10s} | Region: {region}")

    # Check sales data if available
    if df_sales is not None:
        sales_for_item = df_sales[df_sales['Item no.'] == target_item] if 'Item no.' in df_sales.columns else df_sales[df_sales['Item No.'] == target_item]
        if len(sales_for_item) > 0:
            recent_sales = None
            logger.info(f"\nSales History for {target_item}:")
            logger.info(f"  Total Sales Records: {len(sales_for_item)}")

            # Show recent sales (convert date column first)
            date_col = None
            for col in ['DocDate', 'Date', 'Posting Date']:
                if col in sales_for_item.columns:
                    date_col = col
                    try:
                        sales_for_item = sales_for_item.copy()
                        sales_for_item['_parsed_date'] = pd.to_datetime(sales_for_item[col], errors='coerce')
                        recent_sales = sales_for_item.nlargest(5, '_parsed_date')
                        break
                    except Exception:
                        pass

            if recent_sales is not None and len(recent_sales) > 0:
                for _, sale in recent_sales.iterrows():
                    date = sale.get(date_col, 'N/A')
                    qty = sale.get('Quantity', sale.get('Qty', 'N/A'))
                    logger.info(f"    {date} | Qty: {qty}")
            else:
                # Fallback: just show first 5 rows
                for _, sale in sales_for_item.head(5).iterrows():
                    qty = sale.get('Quantity', sale.get('Qty', 'N/A'))
                    logger.info(f"    Qty: {qty}")


def test_warehouse_mapping():
    """Test warehouse code mappings"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Warehouse Code Mappings")
    logger.info("="*70)

    logger.info(f"\nFuture Warehouse Codes:")
    for region, code in sorted(WAREHOUSE_CODES_FUTURE.items()):
        logger.info(f"  {region:15s} -> {code}")


def test_validation(df_items, df_sales):
    """Run consolidation readiness validation"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Consolidation Readiness Validation")
    logger.info("="*70)

    issues = validate_consolidation_readiness(df_items, df_sales if df_sales is not None else df_items.head(0))

    logger.info(f"\nValidation Results:")
    logger.info(f"  Regional items found: {len(issues['regional_items_found'])}")
    if issues['regional_items_found']:
        logger.info(f"    Examples: {issues['regional_items_found'][:5]}")

    logger.info(f"  Multi-warehouse items: {len(issues['multi_warehouse_items'])}")
    if issues['multi_warehouse_items']:
        logger.info(f"    Examples: {issues['multi_warehouse_items'][:5]}")

    logger.info(f"  Missing warehouse: {len(issues['missing_warehouse'])}")
    if issues['missing_warehouse']:
        logger.info(f"    Examples: {issues['missing_warehouse'][:5]}")

    logger.info(f"  Missing conversion factors: {len(issues['conversion_factors_missing'])}")
    if issues['conversion_factors_missing']:
        logger.info(f"    Examples: {issues['conversion_factors_missing'][:5]}")


def test_consolidation_status(df_items):
    """Check overall consolidation status"""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Consolidation Status")
    logger.info("="*70)

    status = check_consolidation_status(df_items)

    logger.info(f"\nStatus: {status['status']}")
    logger.info(f"Message: {status['message']}")
    logger.info(f"\nState Counts:")
    for state, count in status['state_counts'].items():
        logger.info(f"  {state}: {count}")


def main():
    """Run all tests"""
    logger.info("\n" + "="*70)
    logger.info("CONSOLIDATION MODULE TEST")
    logger.info("Testing with existing TSV data")
    logger.info("="*70)

    # Load data
    df_items, df_sales = load_tsv_data()

    if df_items is None:
        logger.error("Failed to load items data. Exiting.")
        return

    # Run tests
    df_items = test_item_state_detection(df_items)
    test_regional_variants(df_items, base_code='BX010155')
    test_bx010155_analysis(df_items, df_sales)
    test_warehouse_mapping()
    test_validation(df_items, df_sales)
    test_consolidation_status(df_items)

    logger.info("\n" + "="*70)
    logger.info("TEST COMPLETE")
    logger.info("="*70)


if __name__ == "__main__":
    main()
