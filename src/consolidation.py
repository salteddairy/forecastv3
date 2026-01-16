"""
Item Master Consolidation Support Module

Handles the transition from current state (regional item codes) to
future state (consolidated item codes with multiple warehouses).

Current State:
  - Item codes: 30027C-TOR, 30027C-CGY (regional suffixes)
  - One warehouse per item (embedded in suffix)

Future State:
  - Item codes: 30027C (consolidated)
  - Multiple warehouses per item (separate rows)
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# WAREHOUSE CODE MAPPINGS
# ============================================================================

# Current warehouse codes (before consolidation)
WAREHOUSE_CODES_CURRENT = {
    'Toronto': '50',
    'Calgary': '30',
    'Delta': ['1', '3', '4', '5', '7', '9', '11', '12', '15', '21', '23', '25'],
    'Edmonton': '40',
    'Regina': '60',
    'Saskatoon': '20',
    'Winnipeg': '10',
    'Vaughan': 'VGH',
    'Montreal': 'MTL'
}

# Future warehouse codes (after consolidation)
WAREHOUSE_CODES_FUTURE = {
    'Toronto': '050-TOR1',
    'Calgary': '030-CGY1',
    'Delta': '000-DEL1',
    'Edmonton': '040-EDM1',
    'Regina': '060-REG1',
    'Saskatoon': '020-SAS1',
    'Winnipeg': '010-WPG1',
    'Vaughan': 'VGH-VGH1',
    'Montreal': 'MTL-MTL1'
}

# Regional suffix mapping
REGIONAL_SUFFIXES = {
    '-TOR': 'Toronto',
    '-CGY': 'Calgary',
    '-EDM': 'Edmonton',
    '-REG': 'Regina',
    '-SAS': 'Saskatoon',
    '-WPG': 'Winnipeg',
    '-DEL': 'Delta',
    '-VGH': 'Vaughan',
    '-MTL': 'Montreal'
}

# Reverse mapping
REGION_TO_SUFFIX = {v: k for k, v in REGIONAL_SUFFIXES.items()}


# ============================================================================
# ITEM STATE DETECTION
# ============================================================================

def get_item_state(item_code: str) -> str:
    """
    Detect if item is in current state (regional) or future state (consolidated).

    Parameters:
    -----------
    item_code : str
        Item code to check

    Returns:
    --------
    str
        'CURRENT' if item has regional suffix (e.g., 30027C-TOR)
        'FUTURE' if item is consolidated (e.g., 30027C)
        'UNKNOWN' if item_code is invalid

    Examples:
    ---------
    >>> get_item_state("30027C-TOR")
    'CURRENT'
    >>> get_item_state("30027C")
    'FUTURE'
    """
    if not isinstance(item_code, str) or not item_code:
        return 'UNKNOWN'

    # Check for regional suffix pattern (XXX-REG where REG is 3 chars)
    if '-' in item_code:
        parts = item_code.split('-')
        if len(parts) == 2 and len(parts[1]) == 3:
            suffix = f"-{parts[1].upper()}"
            if suffix in REGIONAL_SUFFIXES:
                return 'CURRENT'

    return 'FUTURE'


def extract_region_from_item_code(item_code: str) -> str:
    """
    Extract region from item code suffix.

    Parameters:
    -----------
    item_code : str
        Item code (current state with suffix)

    Returns:
    --------
    str
        Region name (e.g., 'Toronto', 'Calgary')

    Examples:
    ---------
    >>> extract_region_from_item_code("30027C-TOR")
    'Toronto'
    >>> extract_region_from_item_code("30027C-CGY")
    'Calgary'
    """
    if not isinstance(item_code, str):
        return 'Delta'

    # Check suffixes
    for suffix, region in REGIONAL_SUFFIXES.items():
        if item_code.upper().endswith(suffix):
            return region

    # Default fallback
    return 'Delta'


def extract_base_item_code(item_code: str) -> str:
    """
    Extract base item code by removing regional suffix.

    Parameters:
    -----------
    item_code : str
        Item code (may or may not have suffix)

    Returns:
    --------
    str
        Base item code without regional suffix

    Examples:
    ---------
    >>> extract_base_item_code("30027C-TOR")
    '30027C'
    >>> extract_base_item_code("30027C")
    '30027C'
    """
    if not isinstance(item_code, str):
        return item_code

    if '-' in item_code:
        parts = item_code.split('-')
        if len(parts) == 2 and len(parts[1]) == 3:
            return parts[0]

    return item_code


# ============================================================================
# HISTORICAL DATA MAPPING
# ============================================================================

def map_historical_item_code(item_code: str, warehouse: str = None) -> Tuple[str, str]:
    """
    Map historical regional item code to consolidated item code with warehouse.

    This function handles the mapping from:
      Current: 30555C-DEL → Future: 30555C + Warehouse 000-DEL1

    Parameters:
    -----------
    item_code : str
        Historical item code (may have regional suffix)
    warehouse : str, optional
        Warehouse code (if not provided, derived from item code suffix)

    Returns:
    --------
    Tuple[str, str]
        (consolidated_item_code, warehouse_code)

    Examples:
    ---------
    >>> map_historical_item_code("30555C-DEL")
    ('30555C', '000-DEL1')
    >>> map_historical_item_code("30555C")
    ('30555C', None)
    """
    item_state = get_item_state(item_code)

    if item_state == 'CURRENT':
        # Extract base item code and region
        base_code = extract_base_item_code(item_code)
        region = extract_region_from_item_code(item_code)

        # Map region to future warehouse code
        warehouse = WAREHOUSE_CODES_FUTURE.get(region, '000-DEL1')

        return base_code, warehouse

    else:
        # Already consolidated - return as-is
        return item_code, warehouse


def map_historical_sales_data(df_sales: pd.DataFrame) -> pd.DataFrame:
    """
    Map historical sales data from regional item codes to consolidated format.

    Transforms data from:
      Item Code: 30555C-DEL, Warehouse: 1
    To:
      Item Code: 30555C, Warehouse: 000-DEL1

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Historical sales data with columns: item_code, warehouse, date, qty

    Returns:
    --------
    pd.DataFrame
        Sales data with consolidated item codes and mapped warehouses

    Examples:
    ---------
    >>> df = pd.DataFrame({
    ...     'item_code': ['30555C-DEL', '30555C-REG'],
    ...     'qty': [100, 50],
    ...     'warehouse': ['1', '60']
    ... })
    >>> mapped = map_historical_sales_data(df)
    >>> mapped[['item_code', 'warehouse', 'qty']].values
    array([['30555C', '000-DEL1', 100],
           ['30555C', '060-REG1', 50]])
    """
    df_result = df_sales.copy()

    # Add columns for consolidated format
    df_result['item_state'] = df_result['item_code'].apply(get_item_state)
    df_result['base_item_code'] = df_result['item_code'].apply(extract_base_item_code)
    df_result['region'] = df_result['item_code'].apply(extract_region_from_item_code)

    # Map current state items to consolidated format
    current_mask = df_result['item_state'] == 'CURRENT'
    if current_mask.any():
        logger.info(f"Mapping {current_mask.sum()} historical sales records to consolidated format...")

        # Update item code to base (remove suffix)
        df_result.loc[current_mask, 'item_code_consolidated'] = \
            df_result.loc[current_mask, 'base_item_code']

        # Map warehouse code
        def map_warehouse(row):
            if row['item_state'] == 'CURRENT':
                region = row['region']
                return WAREHOUSE_CODES_FUTURE.get(region, row['warehouse'])
            return row['warehouse']

        df_result['warehouse_consolidated'] = df_result.apply(map_warehouse, axis=1)

    # For future state items, no mapping needed
    future_mask = df_result['item_state'] == 'FUTURE'
    if future_mask.any():
        df_result.loc[future_mask, 'item_code_consolidated'] = \
            df_result.loc[future_mask, 'item_code']
        df_result.loc[future_mask, 'warehouse_consolidated'] = \
            df_result.loc[future_mask, 'warehouse']

    return df_result


# ============================================================================
# MULTI-WAREHOUSE HANDLING
# ============================================================================

def get_warehouses_for_item(item_code: str, df_items: pd.DataFrame = None) -> List[str]:
    """
    Get all warehouses for an item (handles both current and future state).

    Parameters:
    -----------
    item_code : str
        Item code
    df_items : pd.DataFrame, optional
        Items dataframe (to look up warehouses for future state)

    Returns:
    --------
    List[str]
        List of warehouse codes

    Examples:
    ---------
    >>> # Current state: single warehouse from suffix
    >>> get_warehouses_for_item("30555C-TOR")
    ['050-TOR1']

    >>> # Future state: multiple warehouses from dataframe
    >>> get_warehouses_for_item("30555C", df_items)
    ['050-TOR1', '030-CGY1', '000-DEL1']
    """
    item_state = get_item_state(item_code)

    if item_state == 'CURRENT':
        # Extract from suffix
        region = extract_region_from_item_code(item_code)
        warehouse = WAREHOUSE_CODES_FUTURE.get(region, '000-DEL1')
        return [warehouse]

    elif item_state == 'FUTURE':
        # Look up from dataframe
        if df_items is not None and 'Item No.' in df_items.columns and 'Warehouse' in df_items.columns:
            warehouses = df_items[
                df_items['Item No.'] == item_code
            ]['Warehouse'].dropna().unique().tolist()
            return warehouses if warehouses else ['000-DEL1']
        else:
            # Default to Delta if no data available
            return ['000-DEL1']

    return []


def expand_items_to_warehouses(df_items: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure each item has a row for each warehouse it exists in.

    For current state (regional items): warehouse embedded in suffix
    For future state (consolidated items): multiple rows per item

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe

    Returns:
    --------
    pd.DataFrame
        Items with one row per item/warehouse combination
    """
    df_result = df_items.copy()

    # Add item state detection
    df_result['item_state'] = df_result['Item No.'].apply(get_item_state)

    # For current state, extract warehouse from suffix
    current_mask = df_result['item_state'] == 'CURRENT'
    if current_mask.any():
        df_result.loc[current_mask, 'Warehouse'] = \
            df_result.loc[current_mask, 'Item No.'].apply(
                lambda x: extract_region_from_item_code(x)
            )

    # For future state, warehouse should already be in column
    # (one row per warehouse combination)

    # Validate multi-warehouse items
    future_mask = df_result['item_state'] == 'FUTURE'
    if future_mask.any():
        item_warehouse_counts = df_result[future_mask].groupby('Item No.').size()
        multi_warehouse = item_warehouse_counts[item_warehouse_counts > 1]

        if len(multi_warehouse) > 0:
            logger.info(f"Found {len(multi_warehouse)} consolidated items with multiple warehouses:")
            for item_code, count in multi_warehouse.head(10).items():
                warehouses = df_result[df_result['Item No.'] == item_code]['Warehouse'].tolist()
                logger.info(f"  {item_code}: {warehouses}")

    return df_result


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_consolidation_readiness(df_items: pd.DataFrame,
                                      df_sales: pd.DataFrame) -> Dict:
    """
    Validate data is ready for consolidation and identify potential issues.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe
    df_sales : pd.DataFrame
        Sales dataframe

    Returns:
    --------
    Dict
        Validation results with issues found
    """
    issues = {
        'regional_items_found': [],
        'multi_warehouse_items': [],
        'missing_warehouse': [],
        'warehouse_mismatch': [],
        'conversion_factors_missing': []
    }

    # Check 1: Identify regional items (current state)
    if 'Item No.' in df_items.columns:
        regional_items = df_items[
            df_items['Item No.'].str.contains('-', na=False)
        ]['Item No.'].unique()

        if len(regional_items) > 0:
            issues['regional_items_found'] = regional_items[:10].tolist()  # First 10
            logger.warning(f"Found {len(regional_items)} items with regional suffixes (current state)")

    # Check 2: Identify multi-warehouse items
    if 'Item No.' in df_items.columns and 'Warehouse' in df_items.columns:
        item_warehouse_counts = df_items.groupby('Item No.')['Warehouse'].nunique()
        multi_warehouse = item_warehouse_counts[item_warehouse_counts > 1]

        if len(multi_warehouse) > 0:
            issues['multi_warehouse_items'] = multi_warehouse.index[:10].tolist()
            logger.info(f"Found {len(multi_warehouse)} items with multiple warehouses")

    # Check 3: Missing warehouse assignments
    if 'Warehouse' in df_items.columns:
        missing_warehouse = df_items[df_items['Warehouse'].isna()]['Item No.'].unique()
        if len(missing_warehouse) > 0:
            issues['missing_warehouse'] = missing_warehouse[:10].tolist()
            logger.error(f"Found {len(missing_warehouse)} items without warehouse assignment")

    # Check 4: Conversion factors
    if 'QtyPerSalesUoM' in df_items.columns:
        # Convert to numeric, handling string values
        qty_per_uom = pd.to_numeric(df_items['QtyPerSalesUoM'], errors='coerce')

        missing_factors = df_items[
            (df_items.get('SalesUoM', '') != df_items.get('BaseUoM', '')) &
            (qty_per_uom.isna() | (qty_per_uom <= 0))
        ]['Item No.'].unique()

        if len(missing_factors) > 0:
            issues['conversion_factors_missing'] = missing_factors[:10].tolist()
            logger.error(f"Found {len(missing_factors)} items missing conversion factors")

    return issues


def check_consolidation_status(df_items: pd.DataFrame) -> Dict:
    """
    Check if data is in current state, future state, or mixed.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe

    Returns:
    --------
    Dict
        Status information
    """
    if 'Item No.' not in df_items.columns:
        return {'status': 'UNKNOWN', 'error': 'Missing Item No. column'}

    # Add item state
    df_items['item_state'] = df_items['Item No.'].apply(get_item_state)

    state_counts = df_items['item_state'].value_counts()

    # Determine overall status
    if 'CURRENT' in state_counts and 'FUTURE' not in state_counts:
        status = 'CURRENT_STATE'
        message = f"All {len(df_items)} items are in current state (regional suffixes)"
    elif 'FUTURE' in state_counts and 'CURRENT' not in state_counts:
        status = 'FUTURE_STATE'
        message = f"All {len(df_items)} items are in future state (consolidated)"
    else:
        status = 'MIXED_STATE'
        message = f"Mixed state: {state_counts.get('CURRENT', 0)} current, {state_counts.get('FUTURE', 0)} future"

    return {
        'status': status,
        'message': message,
        'state_counts': state_counts.to_dict(),
        'regional_count': state_counts.get('CURRENT', 0),
        'consolidated_count': state_counts.get('FUTURE', 0)
    }


# ============================================================================
# MIGRATION HELPERS
# ============================================================================

def prepare_for_consolidation(df_items: pd.DataFrame,
                                df_sales: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Prepare data for consolidation by:
    1. Detecting item state
    2. Adding warehouse information
    3. Validating data structure

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe
    df_sales : pd.DataFrame
        Sales dataframe

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        (prepared_items, prepared_sales)
    """
    logger.info("Preparing data for consolidation...")

    # Prepare items
    df_items_prep = expand_items_to_warehouses(df_items)

    # Prepare sales (map historical regional codes)
    df_sales_prep = map_historical_sales_data(df_sales)

    # Use consolidated columns if mapping was done
    if 'item_code_consolidated' in df_sales_prep.columns:
        df_sales_prep['item_code'] = df_sales_prep['item_code_consolidated']
    if 'warehouse_consolidated' in df_sales_prep.columns:
        df_sales_prep['warehouse'] = df_sales_prep['warehouse_consolidated']

    # Validate
    validation = validate_consolidation_readiness(df_items_prep, df_sales_prep)

    logger.info(f"Preparation complete:")
    logger.info(f"  Items: {len(df_items_prep)}")
    logger.info(f"  Sales: {len(df_sales_prep)}")
    logger.info(f"  Issues: {sum(len(v) if isinstance(v, list) else 0 for v in validation.values())}")

    return df_items_prep, df_sales_prep


if __name__ == "__main__":
    # Test the module
    print("Testing consolidation module...")

    # Test item state detection
    test_codes = ["30555C-TOR", "30555C-REG", "30555C", "INVALID"]
    for code in test_codes:
        state = get_item_state(code)
        base = extract_base_item_code(code)
        region = extract_region_from_item_code(code)
        print(f"{code}: State={state}, Base={base}, Region={region}")

    # Test mapping
    mapped = map_historical_item_code("30555C-DEL")
    print(f"\nMap '30555C-DEL': {mapped}")
