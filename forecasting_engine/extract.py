"""
Data extraction module for retrieving sales data from PostgreSQL or local files.
Supports both database queries and local .tsv files for testing.
"""
import logging
import pandas as pd
from pathlib import Path
from sqlalchemy import text
from typing import List, Optional, Literal
from datetime import datetime, timedelta

from forecasting_engine.db import get_session
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


# Column name mappings for local files
COLUMN_MAPPINGS = {
    # Sales columns
    'Posting Date': 'date',
    'Item No.': 'item_code',
    'ItemCode': 'item_code',
    'OrderedQty': 'qty',
    'Quantity': 'qty',
    'Warehouse': 'warehouse_code',
    'WhsCode': 'warehouse_code',
    'Linked_SpecialOrder_Num': 'linked_special_order_num',
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names from SAP format to snake_case.

    Parameters:
    -----------
    df : pd.DataFrame
        Input DataFrame with SAP column names

    Returns:
    --------
    pd.DataFrame
        DataFrame with normalized column names
    """
    return df.rename(columns=COLUMN_MAPPINGS)


def extract_sales_data(
    item_codes: Optional[List[str]] = None,
    warehouse: Optional[str] = None,
    months_history: int = 24,
    source: Literal["database", "local"] = "database",
    data_dir: Path = None
) -> pd.DataFrame:
    """
    Extract sales data for forecasting.

    Parameters:
    -----------
    item_codes : List[str], optional
        List of item codes to extract (None = all items)
    warehouse : str, optional
        Filter by warehouse code (None = all warehouses)
    months_history : int
        Number of months of historical data to extract (default: 24)
    source : str
        Data source: "database" (default) or "local"
    data_dir : Path, optional
        Directory containing local data files (required if source="local")

    Returns:
    --------
    pd.DataFrame
        Sales data with columns: [date, item_code, qty, warehouse_code]
    """
    if source == "local":
        return _extract_sales_from_local(item_codes, warehouse, months_history, data_dir)
    else:
        return _extract_sales_from_database(item_codes, warehouse, months_history)


def _extract_sales_from_database(
    item_codes: Optional[List[str]],
    warehouse: Optional[str],
    months_history: int
) -> pd.DataFrame:
    """Extract sales data from PostgreSQL database."""
    query = text("""
        SELECT
            so.posting_date as date,
            so.item_code,
            so.ordered_qty as qty,
            so.warehouse_code
        FROM sales_orders so
        WHERE so.posting_date >= CURRENT_DATE - INTERVAL ':months months'
          AND so.ordered_qty > 0
          AND NOT so.is_linked_special_order  -- Exclude back-to-back orders
    """)

    # Build filters
    params = {"months": months_history}

    if item_codes:
        query = text(query.text + " AND so.item_code = ANY(:item_codes)")
        params["item_codes"] = item_codes

    if warehouse:
        query = text(query.text + " AND so.warehouse_code = :warehouse")
        params["warehouse"] = warehouse

    query = text(query.text + " ORDER BY so.item_code, so.posting_date")

    # Execute query
    with get_session() as session:
        result = session.execute(query, params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    if df.empty:
        logger.warning(f"No sales data found for the given criteria")
        return df

    # Convert date column
    df["date"] = pd.to_datetime(df["date"])

    logger.info(
        f"Extracted {len(df)} sales records for "
        f"{df['item_code'].nunique()} items "
        f"from {df['date'].min()} to {df['date'].max()}"
    )

    return df


def _extract_sales_from_local(
    item_codes: Optional[List[str]],
    warehouse: Optional[str],
    months_history: int,
    data_dir: Path
) -> pd.DataFrame:
    """
    Extract sales data from local .tsv file.

    Parameters:
    -----------
    item_codes : List[str], optional
        Filter by item codes
    warehouse : str, optional
        Filter by warehouse code
    months_history : int
        Only return data from last N months
    data_dir : Path
        Directory containing sales.tsv

    Returns:
    --------
    pd.DataFrame
        Sales data
    """
    if data_dir is None:
        data_dir = Path("data/raw")

    sales_file = data_dir / "sales.tsv"

    if not sales_file.exists():
        raise FileNotFoundError(f"Sales file not found: {sales_file}")

    logger.info(f"Loading sales data from {sales_file}")

    # Load data
    df = pd.read_csv(sales_file, sep='\t', encoding='utf-8', thousands=',')

    # Normalize column names
    df = normalize_columns(df)

    # Convert date
    df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y', errors='coerce')

    # Clean quantity
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce')

    # Drop rows with missing data
    df = df.dropna(subset=['date', 'item_code', 'qty'])

    # Filter out linked special orders (back-to-back orders)
    if 'linked_special_order_num' in df.columns:
        df = df[df['linked_special_order_num'].isna() | (df['linked_special_order_num'] == '')]
        logger.info("Filtered out back-to-back orders (linked special orders)")

    # Filter by date range
    cutoff_date = datetime.now() - timedelta(days=months_history * 30)
    df = df[df['date'] >= cutoff_date]
    logger.info(f"Filtered to last {months_history} months (since {cutoff_date.date()})")

    # Filter by item codes if specified
    if item_codes:
        df = df[df['item_code'].isin(item_codes)]
        logger.info(f"Filtered to {len(item_codes)} specific items")

    # Filter by warehouse if specified
    if warehouse:
        df = df[df['warehouse_code'] == str(warehouse)]
        logger.info(f"Filtered to warehouse: {warehouse}")

    # Select required columns
    df = df[['date', 'item_code', 'qty', 'warehouse_code']].copy()

    logger.info(
        f"Loaded {len(df)} sales records for "
        f"{df['item_code'].nunique()} items "
        f"from {df['date'].min()} to {df['date'].max()}"
    )

    return df


def extract_items_with_sufficient_history(
    min_months: int = None,
    min_orders: int = None,
    source: Literal["database", "local"] = "database",
    data_dir: Path = None,
    df_sales: pd.DataFrame = None
) -> List[str]:
    """
    Get list of items that have sufficient sales history for forecasting.

    Parameters:
    -----------
    min_months : int, optional
        Minimum number of months with sales (default: from settings)
    min_orders : int, optional
        Minimum total number of orders (default: from settings)
    source : str
        Data source: "database" (default) or "local"
    data_dir : Path, optional
        Directory for local data (if source="local")
    df_sales : pd.DataFrame, optional
        Pre-loaded sales data (if available, skips loading)

    Returns:
    --------
    List[str]
        List of item codes with sufficient history
    """
    min_months = min_months or settings.min_months_history
    min_orders = min_orders or settings.min_orders

    if df_sales is not None:
        # Use provided sales data
        df = df_sales
    elif source == "local":
        # Load from local file
        df = extract_sales_data(source="local", data_dir=data_dir)
    else:
        # Query database
        return _extract_items_from_database(min_months, min_orders)

    # Calculate from DataFrame
    df['year_month'] = df['date'].dt.to_period('M')

    item_stats = df.groupby('item_code').agg({
        'year_month': 'nunique',  # Number of months with sales
        'date': 'count'           # Total number of orders
    }).rename(columns={'year_month': 'months', 'date': 'orders'})

    # Filter by criteria
    eligible_items = item_stats[
        (item_stats['months'] >= min_months) &
        (item_stats['orders'] >= min_orders)
    ].index.tolist()

    logger.info(
        f"Found {len(eligible_items)} items with sufficient history "
        f"(min {min_months} months, {min_orders} orders) "
        f"out of {len(item_stats)} total items"
    )

    return eligible_items


def _extract_items_from_database(min_months: int, min_orders: int) -> List[str]:
    """Query database for items with sufficient history."""
    query = text("""
        SELECT
            so.item_code
        FROM sales_orders so
        WHERE so.posting_date >= CURRENT_DATE - INTERVAL '2 years'
          AND NOT so.is_linked_special_order
          AND so.ordered_qty > 0
        GROUP BY so.item_code
        HAVING COUNT(DISTINCT DATE_TRUNC('month', so.posting_date)) >= :min_months
           AND COUNT(*) >= :min_orders
        ORDER BY so.item_code
    """)

    with get_session() as session:
        result = session.execute(query, {
            "min_months": min_months,
            "min_orders": min_orders
        })
        item_codes = [row[0] for row in result]

    logger.info(
        f"Found {len(item_codes)} items with sufficient history "
        f"(min {min_months} months, {min_orders} orders)"
    )

    return item_codes


def get_sales_summary(df_sales: pd.DataFrame) -> dict:
    """
    Get summary statistics for sales data.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales data from extract_sales_data()

    Returns:
    --------
    dict
        Summary statistics
    """
    if df_sales.empty:
        return {
            "total_records": 0,
            "unique_items": 0,
            "date_range": None,
            "total_quantity": 0
        }

    return {
        "total_records": len(df_sales),
        "unique_items": df_sales["item_code"].nunique(),
        "date_range": {
            "start": df_sales["date"].min().isoformat(),
            "end": df_sales["date"].max().isoformat(),
            "days": (df_sales["date"].max() - df_sales["date"].min()).days
        },
        "total_quantity": float(df_sales["qty"].sum()),
        "avg_quantity": float(df_sales["qty"].mean()),
        "warehouses": df_sales["warehouse_code"].nunique() if "warehouse_code" in df_sales.columns else 0
    }


def compare_sources(
    item_codes: List[str] = None,
    data_dir: Path = Path("data/raw"),
    months_history: int = 24
) -> dict:
    """
    Compare database vs local file data for verification.

    Parameters:
    -----------
    item_codes : List[str], optional
        Items to compare (None = compare all items)
    data_dir : Path
        Directory for local data files
    months_history : int
        Months of history to compare

    Returns:
    --------
    dict
        Comparison results
    """
    logger.info("Comparing database vs local file data...")

    # Load from both sources
    try:
        df_db = extract_sales_data(
            item_codes=item_codes,
            months_history=months_history,
            source="database"
        )
    except Exception as e:
        logger.warning(f"Could not load from database: {e}")
        df_db = pd.DataFrame()

    try:
        df_local = extract_sales_data(
            item_codes=item_codes,
            months_history=months_history,
            source="local",
            data_dir=data_dir
        )
    except Exception as e:
        logger.warning(f"Could not load from local file: {e}")
        df_local = pd.DataFrame()

    if df_db.empty and df_local.empty:
        return {"error": "No data available from either source"}

    comparison = {
        "database": {
            "available": not df_db.empty,
            "records": len(df_db) if not df_db.empty else 0,
            "items": df_db["item_code"].nunique() if not df_db.empty else 0,
            "date_range": {
                "start": df_db["date"].min().isoformat() if not df_db.empty else None,
                "end": df_db["date"].max().isoformat() if not df_db.empty else None
            }
        },
        "local": {
            "available": not df_local.empty,
            "records": len(df_local) if not df_local.empty else 0,
            "items": df_local["item_code"].nunique() if not df_local.empty else 0,
            "date_range": {
                "start": df_local["date"].min().isoformat() if not df_local.empty else None,
                "end": df_local["date"].max().isoformat() if not df_local.empty else None
            }
        }
    }

    # Find items in database but not in local
    if not df_db.empty and not df_local.empty:
        db_items = set(df_db["item_code"].unique())
        local_items = set(df_local["item_code"].unique())
        comparison["items_only_in_database"] = list(db_items - local_items)
        comparison["items_only_in_local"] = list(local_items - db_items)
        comparison["common_items"] = list(db_items & local_items)

    logger.info(f"Comparison complete: Database={comparison['database']['records']} records, "
                f"Local={comparison['local']['records']} records")

    return comparison
