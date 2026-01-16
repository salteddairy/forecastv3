import pandas as pd
import yaml
from pathlib import Path
import numpy as np
import logging

# Handle both relative and absolute imports for compatibility
try:
    from .utils import validate_file_exists, validate_file_format, validate_dataframe_columns
    from .consolidation import (
        get_item_state,
        extract_base_item_code,
        extract_region_from_item_code,
        map_historical_sales_data,
        WAREHOUSE_CODES_FUTURE
    )
except ImportError:
    from src.utils import validate_file_exists, validate_file_format, validate_dataframe_columns
    from src.consolidation import (
        get_item_state,
        extract_base_item_code,
        extract_region_from_item_code,
        map_historical_sales_data,
        WAREHOUSE_CODES_FUTURE
    )

logger = logging.getLogger(__name__)

# Load Config
CONFIG_PATH = Path("config.yaml")
try:
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print("Warning: config.yaml not found, using defaults.")
    CONFIG = {}

def normalize_column_names(df: pd.DataFrame, mapping: dict = None) -> pd.DataFrame:
    """
    Normalize column names from SAP format to snake_case.

    Common mappings:
    - 'Item No.' / 'ItemCode' / 'Item Code' -> 'item_code'
    - 'VendorCode' / 'Vendor Code' -> 'vendor_code'
    - 'Posting Date' / 'DocDate' -> 'date'
    - 'Quantity' / 'Qty' -> 'qty'
    - etc.
    """
    if mapping is None:
        mapping = {
            # Item columns
            'Item No.': 'item_code',
            'ItemCode': 'item_code',
            'Item Code': 'item_code',
            'ItemName': 'item_name',
            'Item Name': 'item_name',

            # Vendor columns
            'VendorCode': 'vendor_code',
            'Vendor Code': 'vendor_code',
            'VendorName': 'vendor_name',
            'Vendor Name': 'vendor_name',
            'CardCode': 'vendor_code',
            'CardName': 'vendor_name',

            # Date columns
            'Posting Date': 'date',
            'DocDate': 'date',
            'PO_Date': 'po_date',
            'EventDate': 'event_date',

            # Quantity columns
            'Quantity': 'qty',
            'OrderedQty': 'qty',
            'DelivrdQty': 'shipped_qty',
            'OpenQty': 'open_qty',
            'OnHand': 'on_hand',
            'OnOrder': 'on_order',
            'IsCommited': 'committed',
            'CurrentStock': 'current_stock',
            'IncomingStock': 'incoming_stock',
            'CommittedStock': 'committed_stock',

            # Warehouse columns
            'WhsCode': 'warehouse',
            'Warehouse': 'warehouse',

            # Value columns
            'RowTotal': 'line_total',
            'LineTotal': 'line_total',
            'UnitCost': 'unit_cost',
        }

    # Rename columns based on mapping
    df_renamed = df.rename(columns=mapping)

    return df_renamed


def parse_region(item_code: str) -> str:
    """
    Parses the ItemCode suffix to determine the Region.
    Defaults to 'Delta' if no suffix matches or input is invalid.
    """
    suffix_map = {
        '-DEL': 'Delta',
        '-CGY': 'Calgary',
        '-EDM': 'Edmonton',
        '-SAS': 'Saskatoon',
        '-REG': 'Regina',
        '-WPG': 'Winnipeg',
        '-TOR': 'Toronto',
        '-VGH': 'Vaughan',
        '-MTL': 'Montreal'
    }

    if not isinstance(item_code, str):
        return 'Delta'

    # Check suffixes
    for suffix, region in suffix_map.items():
        if item_code.endswith(suffix):
            return region

    # Default fallback for equipment/no-suffix
    return 'Delta'

def load_sales_orders(filepath: Path) -> pd.DataFrame:
    """
    Loads Sales Order History (ORDR) - Unconstrained Demand.
    - Flags Linked Special Orders (U_SORDNUM)
    - Adds Region Column based on Suffix
    """
    # Validate file exists
    validate_file_exists(filepath, "Sales orders file")
    validate_file_format(filepath, ('.tsv', '.csv'))

    # Load without auto-parsing dates (to catch invalid dates)
    try:
        df = pd.read_csv(filepath, sep='\t')
    except Exception as e:
        logger.error(f"Error loading sales orders from {filepath}: {e}")
        raise ValueError(f"Failed to load sales orders: {e}")

    # IMPORTANT: Normalize column names FIRST before any other operations
    df = normalize_column_names(df)

    # Validate required columns exist (check for both original and normalized names)
    required_cols = ['date', 'item_code']  # Use normalized names
    # Also check for original names if normalized names not found
    original_cols = ['Posting Date', 'Item No.']

    # Check if we have normalized or original columns
    has_normalized = all(col in df.columns for col in required_cols)
    has_original = all(col in df.columns for col in original_cols)

    if not has_normalized and not has_original:
        raise ValueError(f"Missing required columns. Need either {required_cols} or {original_cols}. File may be malformed or have incorrect format.")

    # Parse dates with error tracking
    date_col = 'date' if 'date' in df.columns else 'Posting Date'
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    # Check for failed parses
    date_col = 'date' if 'date' in df.columns else 'Posting Date'
    invalid_dates = df[date_col].isna().sum()
    if invalid_dates > 0:
        total = len(df)
        logger.warning(f"[WARNING] {invalid_dates}/{total} records have invalid dates and will be removed")

        # Log sample of invalid dates for debugging
        if invalid_dates > 0:
            item_col = 'item_code' if 'item_code' in df.columns else 'Item No.'
            sample_invalid = df[df[date_col].isna()][item_col].head(3).tolist() if item_col in df.columns else []
            if sample_invalid:
                logger.warning(f"Sample items with invalid dates: {sample_invalid}")

        # Remove records with invalid dates
        original_count = len(df)
        df = df[df[date_col].notna()].copy()
        logger.info(f"Removed {original_count - len(df)} records with invalid dates")

    # Create the special order flag (exclusion logic)
    # If Linked_SpecialOrder_Num is not null, it's a back-to-back order
    special_order_col = 'Linked_SpecialOrder_Num' if 'Linked_SpecialOrder_Num' in df.columns else 'U_SORDNUM'
    df['is_linked_special_order'] = df[special_order_col].notna()

    # Apply region mapping
    item_col = 'item_code' if 'item_code' in df.columns else 'Item No.'
    df['Region'] = df[item_col].apply(parse_region)

    # No need to normalize again - already done at top

    # ============================================================================
    # CONSOLIDATION SUPPORT: Add warehouse column and handle historical mapping
    # ============================================================================

    # Detect item state (current vs future)
    df['item_state'] = df['item_code'].apply(get_item_state)

    # For current state items, warehouse is derived from suffix (for future compatibility)
    # For future state items, warehouse should already be in the data
    if 'Warehouse' not in df.columns:
        # No warehouse column - derive from item code suffix
        def derive_warehouse_from_item_code(item_code: str) -> str:
            """Derive warehouse code from item code suffix."""
            state = get_item_state(item_code)
            if state == 'CURRENT':
                # Map region to future warehouse code
                region = extract_region_from_item_code(item_code)
                return WAREHOUSE_CODES_FUTURE.get(region, '000-DEL1')
            return '000-DEL1'  # Default for consolidated items

        df['Warehouse'] = df['item_code'].apply(derive_warehouse_from_item_code)
    else:
        # Warehouse column exists - validate and standardize
        logger.info("Warehouse column found in sales data")

        # Check for historical data mapping needs
        current_state_count = (df['item_state'] == 'CURRENT').sum()
        if current_state_count > 0:
            logger.info(f"Found {current_state_count} historical sales records with regional item codes")
            logger.info("Historical data will maintain warehouse context for forecast continuity")

    # Note: Columns already normalized earlier in function
    # This section is kept for backwards compatibility but columns should already be normalized
    # Columns after normalization: date, item_code, qty (from OrderedQty if present)

    # Log consolidation status
    state_counts = df['item_state'].value_counts()
    logger.info(f"Sales data state distribution: {state_counts.to_dict()}")

    return df

def load_supply_chain(filepath: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads unified supply.tsv and splits it into:
    1. History (OPDN) -> For Lead Time Training
    2. Schedule (OPOR) -> For Availability Extrapolation

    Handles Currency Normalization (USD -> CAD).
    """
    # Validate file exists and format
    validate_file_exists(filepath, "Supply chain file")
    validate_file_format(filepath, ('.tsv', '.csv'))

    # Load with error handling
    try:
        df = pd.read_csv(filepath, sep='\t', parse_dates=['PO_Date', 'EventDate'], low_memory=False)
    except Exception as e:
        logger.error(f"Error loading supply chain from {filepath}: {e}")
        raise ValueError(f"Failed to load supply chain data: {e}")

    # 1. Currency Normalization
    # Convert RowValue_SourceCurrency to numeric (it's stored as strings)
    df['RowValue_SourceCurrency'] = pd.to_numeric(df['RowValue_SourceCurrency'], errors='coerce')
    # Calculate Total Cost in CAD. If currency is missing, assume rate 1.0
    df['ExchangeRate'] = df['ExchangeRate'].fillna(1.0)
    df['RowValue_CAD'] = df['RowValue_SourceCurrency'] * df['ExchangeRate']

    # 2. Use existing LeadTimeDays if available, otherwise calculate
    if 'LeadTimeDays' in df.columns:
        df['lead_time_days'] = pd.to_numeric(df['LeadTimeDays'], errors='coerce')
    else:
        df['lead_time_days'] = (df['EventDate'] - df['PO_Date']).dt.days

    # 3. Split Data
    df_history = df[df['DataType'] == 'History'].copy()
    df_schedule = df[df['DataType'] == 'OpenPO'].copy()

    # 4. Remove negative lead times (data entry errors)
    df_history = df_history[df_history['lead_time_days'] >= 0]

    # 5. Normalize column names
    df_history = normalize_column_names(df_history)
    df_schedule = normalize_column_names(df_schedule)

    return df_history, df_schedule

def load_items(filepath: Path) -> pd.DataFrame:
    """
    Loads Item Master snapshots (Stock by Warehouse).
    - Cleans 'nvarchar' Price UDFs
    - Cleans comma separators from numeric columns
    - Sets up Vendor Hierarchy
    """
    # Validate file exists and format
    validate_file_exists(filepath, "Items file")
    validate_file_format(filepath, ('.tsv', '.csv'))

    # Load with error handling
    try:
        df = pd.read_csv(filepath, sep='\t')
    except Exception as e:
        logger.error(f"Error loading items from {filepath}: {e}")
        raise ValueError(f"Failed to load items data: {e}")

    # IMPORTANT: Normalize column names FIRST before any other operations
    df = normalize_column_names(df)

    # 1. Clean comma separators from numeric columns
    # SAP B1 sometimes exports numbers with commas (e.g., "1,852.20")
    numeric_cols = ['CurrentStock', 'IncomingStock', 'CommittedStock',
                    'UnitCost', 'MOQ', 'OrderMultiple', 'QtyPerSalesUoM',
                    'QtyPerPurchUoM', 'LastPurchasePrice_Fallback']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. Clean Last Purchase Price (Handling nvarchar schema: '$12.50')
    # This is now handled above, but keep $ symbol removal for safety
    if 'LastPurchasePrice_Fallback' in df.columns:
        df['LastPurchasePrice_Fallback'] = (
            df['LastPurchasePrice_Fallback']
            .astype(str)
            .str.replace('$', '', regex=False)
        )
        df['LastPurchasePrice_Fallback'] = pd.to_numeric(
            df['LastPurchasePrice_Fallback'], errors='coerce'
        )

    # 2. Parse Last Purchase Date
    if 'LastPurchaseDate_Fallback' in df.columns:
        df['LastPurchaseDate_Fallback'] = pd.to_datetime(
            df['LastPurchaseDate_Fallback'], errors='coerce'
        )

    # 3. Vendor Consolidation Logic
    # Priority: Last Vendor UDF > Preferred Vendor
    # Note: 'LastVendorCode_Fallback' corresponds to U_LPVENDC
    if 'LastVendorCode_Fallback' in df.columns:
        df['TargetVendor'] = df['LastVendorCode_Fallback'].fillna(df['PreferredVendor'])
        df['TargetVendorName'] = df['LastVendorName_Fallback'] # For UI Display
    else:
        df['TargetVendor'] = df['PreferredVendor']

    # 4. Apply Region Logic to Inventory
    df['Region'] = df['item_code'].apply(parse_region)

    # ============================================================================
    # CONSOLIDATION SUPPORT: Add warehouse handling and state detection
    # ============================================================================

    # Detect item state (current vs future)
    df['item_state'] = df['item_code'].apply(get_item_state)

    # Handle warehouse column for multi-warehouse items
    if 'Warehouse' not in df.columns:
        # No warehouse column - derive from item code suffix (current state)
        def derive_warehouse_from_item_code(item_code: str) -> str:
            """Derive warehouse code from item code suffix."""
            state = get_item_state(item_code)
            if state == 'CURRENT':
                # Map region to future warehouse code
                region = extract_region_from_item_code(item_code)
                return WAREHOUSE_CODES_FUTURE.get(region, '000-DEL1')
            return '000-DEL1'  # Default for consolidated items

        df['Warehouse'] = df['item_code'].apply(derive_warehouse_from_item_code)
    else:
        # Warehouse column exists - this could be:
        # 1. Future state (consolidated items with multiple warehouses)
        # 2. Current state error cases (items in multiple warehouses)
        logger.info("Warehouse column found in items data")

        # Check for multi-warehouse items
        item_warehouse_counts = df.groupby('item_code')['Warehouse'].nunique()
        multi_warehouse = item_warehouse_counts[item_warehouse_counts > 1]

        if len(multi_warehouse) > 0:
            logger.info(f"Found {len(multi_warehouse)} items with multiple warehouses:")
            for item_code in multi_warehouse.head(10).index:
                warehouses = df[df['item_code'] == item_code]['Warehouse'].tolist()
                logger.info(f"  {item_code}: {warehouses}")

    # Log consolidation status
    state_counts = df['item_state'].value_counts()
    logger.info(f"Items state distribution: {state_counts.to_dict()}")

    return df

if __name__ == "__main__":
    print("Ingestion Module Test:")
    print("1. Ensure 'sales.tsv', 'supply.tsv', 'items.tsv' are in data/raw/")
    print("2. Run this script via other modules or pytest.")