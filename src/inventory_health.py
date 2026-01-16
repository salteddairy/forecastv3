"""
Inventory Health Module - Dead Stock Detection and Shelf Life Warnings
Identifies slow-moving/obsolete stock and items with shelf life constraints
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def detect_dead_stock(df_items: pd.DataFrame,
                     df_sales: pd.DataFrame,
                     df_history: pd.DataFrame = None,
                     inactive_months: int = 24) -> pd.DataFrame:
    """
    Identify items that haven't had any movement (sales or purchases) in X months.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with CurrentStock, Item No.
    df_sales : pd.DataFrame
        Sales order history with Posting Date, Item No.
    df_history : pd.DataFrame, optional
        Purchase history (OPDN) with EventDate, ItemCode
    inactive_months : int
        Months of inactivity to consider as "dead stock" (default: 24)

    Returns:
    --------
    pd.DataFrame
        Dead stock analysis with last sale date, last purchase date, days inactive
    """
    logger.info(f"Detecting dead stock (inactive for {inactive_months}+ months)...")

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=inactive_months * 30)

    # Find last sale date per item
    # Note: Sales data has 'date' column (Posting Date was renamed during ingestion)
    if 'date' in df_sales.columns:
        date_col = 'date'
        item_col = 'item_code'
    else:
        # Fallback to original column names
        date_col = 'Posting Date'
        item_col = 'Item No.'

    df_sales[date_col] = pd.to_datetime(df_sales[date_col], errors='coerce')
    last_sales = df_sales.groupby(item_col)[date_col].max().reset_index()
    last_sales.columns = ['Item No.', 'last_sale_date']

    # Find last purchase/receipt date per item (if history provided)
    if df_history is not None and len(df_history) > 0:
        df_history['EventDate'] = pd.to_datetime(df_history['EventDate'], errors='coerce')
        last_purchases = df_history.groupby('ItemCode')['EventDate'].max().reset_index()
        last_purchases.columns = ['Item No.', 'last_purchase_date']
    else:
        last_purchases = pd.DataFrame(columns=['Item No.', 'last_purchase_date'])

    # Merge with items
    df_dead = df_items[['Item No.', 'Item Description', 'ItemGroup',
                        'CurrentStock', 'UnitCost', 'Warehouse']].copy()

    df_dead = df_dead.merge(last_sales, on='Item No.', how='left')
    df_dead = df_dead.merge(last_purchases, on='Item No.', how='left')

    # Calculate last movement date (max of last sale or last purchase)
    df_dead['last_movement_date'] = df_dead[['last_sale_date', 'last_purchase_date']].max(axis=1)

    # Calculate days inactive
    today = pd.Timestamp.now()
    df_dead['days_since_sale'] = (today - df_dead['last_sale_date']).dt.days
    df_dead['days_since_purchase'] = (today - df_dead['last_purchase_date']).dt.days
    df_dead['days_inactive'] = (today - df_dead['last_movement_date']).dt.days

    # Calculate inventory value at risk
    df_dead['inventory_value'] = df_dead['CurrentStock'] * df_dead['UnitCost']

    # Categorize dead stock
    df_dead['is_dead_stock'] = df_dead['last_movement_date'] < cutoff_date

    # Count items with stock but no movement ever
    never_moved = df_dead['last_movement_date'].isna() & (df_dead['CurrentStock'] > 0)
    df_dead['never_moved'] = never_moved

    # Categorize urgency
    df_dead['urgency'] = pd.cut(
        df_dead['days_inactive'].fillna(999),
        bins=[-np.inf, 365, 730, np.inf],
        labels=['ACTIVE (<1 year)', 'SLOW MOVING (1-2 years)', 'DEAD STOCK (2+ years)']
    )

    # Only return items with stock
    df_dead = df_dead[df_dead['CurrentStock'] > 0].copy()

    dead_count = df_dead['is_dead_stock'].sum()
    dead_value = df_dead[df_dead['is_dead_stock']]['inventory_value'].sum()

    logger.info(f"Found {dead_count} dead stock items valued at ${dead_value:,.2f}")

    return df_dead


def identify_shelf_life_items(df_items: pd.DataFrame,
                              shelf_life_groups: list = ['FG-RE'],
                              shelf_life_months: int = 6) -> pd.DataFrame:
    """
    Identify items with shelf life constraints and flag ordering risks.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with ItemGroup, CurrentStock, IncomingStock
    shelf_life_groups : list
        Item groups with shelf life (default: ['FG-RE'])
    shelf_life_months : int
        Shelf life in months (default: 6 for FG-RE)

    Returns:
    --------
    pd.DataFrame
        Shelf life items with current stock age risk and ordering recommendations
    """
    logger.info(f"Identifying shelf life items (groups: {shelf_life_groups})...")

    # Filter to shelf life item groups
    df_shelf = df_items[df_items['ItemGroup'].isin(shelf_life_groups)].copy()

    if len(df_shelf) == 0:
        logger.warning(f"No items found in shelf life groups: {shelf_life_groups}")
        return pd.DataFrame()

    # Calculate total stock (current + incoming)
    df_shelf['total_stock'] = df_shelf['CurrentStock'] + df_shelf['IncomingStock']

    # Estimate stock age risk (simplified - assumes FIFO, oldest stock sells first)
    # Without actual expiry dates, we flag high stock levels as risk
    df_shelf['months_of_stock'] = df_shelf['total_stock'] / (
        df_shelf.get('avg_monthly_usage', 1)  # Will be filled in by caller
    )

    # Calculate annual usage to determine if current stock is excessive
    # This will be filled in when merged with forecast data

    # Flag items with excessive stock (> 6 months supply)
    df_shelf['excess_stock_flag'] = df_shelf['months_of_stock'] > shelf_life_months

    # Risk category
    df_shelf['expiry_risk'] = pd.cut(
        df_shelf['months_of_stock'],
        bins=[0, 3, shelf_life_months, np.inf],
        labels=['LOW (<3 months)', 'MEDIUM (3-6 months)', 'HIGH (>6 months)']
    )

    logger.info(f"Found {len(df_shelf)} shelf life items")

    return df_shelf


def calculate_shelf_life_risk(df_items: pd.DataFrame,
                              df_forecasts: pd.DataFrame,
                              df_sales: pd.DataFrame,
                              shelf_life_groups: list = ['FG-RE'],
                              shelf_life_months: int = 6) -> pd.DataFrame:
    """
    Calculate shelf life risk using forecast data to estimate usage rate.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data
    df_forecasts : pd.DataFrame
        Forecast data with forecast_month_1 through 6
    df_sales : pd.DataFrame
        Sales data (for historical usage)
    shelf_life_groups : list
        Item groups with shelf life
    shelf_life_months : int
        Shelf life in months

    Returns:
    --------
    pd.DataFrame
        Shelf life risk analysis with ordering recommendations
    """
    logger.info("Calculating shelf life risk with forecast data...")

    # Identify shelf life items
    df_shelf = df_items[df_items['ItemGroup'].isin(shelf_life_groups)].copy()

    if len(df_shelf) == 0:
        logger.warning(f"No items found in shelf life groups: {shelf_life_groups}")
        return pd.DataFrame()

    # Merge with forecasts (12 months)
    forecast_cols_all = [f'forecast_month_{i}' for i in range(1, 13)]
    # Only select columns that exist in forecasts (handles both 6-month and 12-month cached data)
    forecast_cols_to_select = ['item_code'] + [col for col in forecast_cols_all if col in df_forecasts.columns]
    df_shelf = df_shelf.merge(
        df_forecasts[forecast_cols_to_select],
        left_on='Item No.',
        right_on='item_code',
        how='left'
    )

    # Calculate forecast horizon and monthly usage
    df_shelf['forecast_horizon'] = df_shelf.get('forecast_horizon', 12).fillna(12)
    # Only use forecast columns that exist in the merged dataframe
    forecast_cols = [col for col in forecast_cols_all if col in df_shelf.columns]
    df_shelf['total_forecast_demand'] = df_shelf[forecast_cols].fillna(0).sum(axis=1)

    # Calculate average monthly usage (VECTORIZED)
    df_shelf['avg_monthly_usage'] = np.where(
        df_shelf['forecast_horizon'] > 0,
        df_shelf['total_forecast_demand'] / df_shelf['forecast_horizon'],
        0
    )

    # Calculate current stock position
    df_shelf['total_stock'] = df_shelf['CurrentStock'] + df_shelf['IncomingStock']

    # Calculate months of stock on hand (vectorized, with division by zero protection)
    df_shelf['avg_monthly_usage'] = df_shelf['avg_monthly_usage'].fillna(0)
    df_shelf['months_of_stock'] = np.where(
        (df_shelf['avg_monthly_usage'] > 0) & (df_shelf['total_stock'] > 0),
        df_shelf['total_stock'] / df_shelf['avg_monthly_usage'],
        np.nan
    )

    # Filter out items with no usage (can't calculate risk)
    initial_count = len(df_shelf)
    df_shelf = df_shelf[df_shelf['months_of_stock'].notna()].copy()
    filtered_count = initial_count - len(df_shelf)

    if filtered_count > 0:
        logger.warning(f"Filtered {filtered_count} FG-RE items with no usage data")

    # Estimate stock age (assuming FIFO, current stock is average age)
    # Without actual batch dates, estimate based on months of stock
    df_shelf['estimated_stock_age_months'] = df_shelf['months_of_stock'] / 2  # Rough approximation

    # Calculate expiry risk
    df_shelf['months_until_expiry'] = shelf_life_months - df_shelf['estimated_stock_age_months']
    df_shelf['expiry_risk'] = pd.cut(
        df_shelf['months_until_expiry'],
        bins=[-np.inf, 0, 2, np.inf],
        labels=['EXPIRED (>6 months old)', 'HIGH RISK (<2 months)', 'LOW RISK (2+ months)']
    )

    # Ordering recommendations (VECTORIZED)
    df_shelf['ordering_recommendation'] = np.select(
        [
            df_shelf['months_of_stock'] > shelf_life_months,
            df_shelf['months_of_stock'] > shelf_life_months * 0.7
        ],
        [
            'DO NOT ORDER - EXPIRY RISK',
            'ORDER CAUTIOUSLY - MONITOR STOCK AGE'
        ],
        default='OK TO ORDER'
    )

    # Flag items needing immediate attention
    df_shelf['action_required'] = df_shelf['months_of_stock'] > shelf_life_months * 0.7

    # Calculate value at risk (VECTORIZED)
    df_shelf['stock_value'] = df_shelf['total_stock'] * df_shelf['UnitCost']
    df_shelf['expiry_risk_value'] = np.where(
        df_shelf['months_of_stock'] > shelf_life_months,
        df_shelf['stock_value'],
        0
    )

    logger.info(f"Shelf life analysis complete for {len(df_shelf)} items")
    logger.info(f"  - High risk items: {(df_shelf['action_required']).sum()}")
    logger.info(f"  - Value at risk: ${df_shelf['expiry_risk_value'].sum():,.2f}")

    return df_shelf


def generate_inventory_health_report(df_items: pd.DataFrame,
                                    df_sales: pd.DataFrame,
                                    df_forecasts: pd.DataFrame,
                                    df_history: pd.DataFrame = None) -> dict:
    """
    Generate complete inventory health report.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data
    df_sales : pd.DataFrame
        Sales history
    df_forecasts : pd.DataFrame
        Forecast data
    df_history : pd.DataFrame, optional
        Purchase history

    Returns:
    --------
    dict
        Dictionary with dead_stock, shelf_life_risk, and summary metrics
    """
    logger.info("Generating inventory health report...")

    # Detect dead stock
    df_dead = detect_dead_stock(df_items, df_sales, df_history, inactive_months=24)

    # Calculate shelf life risk
    df_shelf = calculate_shelf_life_risk(
        df_items,
        df_forecasts,
        df_sales,
        shelf_life_groups=['FG-RE'],
        shelf_life_months=6
    )

    # Summary metrics
    summary = {
        'dead_stock': {
            'count': int(df_dead['is_dead_stock'].sum()) if len(df_dead) > 0 else 0,
            'value': float(df_dead[df_dead['is_dead_stock']]['inventory_value'].sum()) if len(df_dead) > 0 else 0,
            'items_with_stock': len(df_dead),
        },
        'shelf_life_risk': {
            'high_risk_count': int(df_shelf['action_required'].sum()) if len(df_shelf) > 0 else 0,
            'total_count': len(df_shelf),
            'value_at_risk': float(df_shelf['expiry_risk_value'].sum()) if len(df_shelf) > 0 else 0,
        },
        'total_items_analyzed': len(df_items),
        'report_generated_at': datetime.now().isoformat()
    }

    logger.info("=" * 60)
    logger.info("INVENTORY HEALTH REPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Dead Stock Items: {summary['dead_stock']['count']} (${summary['dead_stock']['value']:,.2f})")
    logger.info(f"Shelf Life Risk Items: {summary['shelf_life_risk']['high_risk_count']} (${summary['shelf_life_risk']['value_at_risk']:,.2f})")
    logger.info(f"Total Items Analyzed: {summary['total_items_analyzed']}")
    logger.info("=" * 60)

    return {
        'dead_stock': df_dead,
        'shelf_life_risk': df_shelf,
        'summary': summary
    }


def save_inventory_health_report(health_report: dict,
                                 output_dir: Path = Path("data/cache")) -> None:
    """
    Save inventory health report to cache.

    Parameters:
    -----------
    health_report : dict
        Report from generate_inventory_health_report()
    output_dir : Path
        Directory to save reports
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Saving inventory health report...")

    try:
        # Save dead stock
        if not health_report['dead_stock'].empty:
            health_report['dead_stock'].to_parquet(
                output_dir / "dead_stock.parquet",
                index=False
            )

        # Save shelf life risk
        if not health_report['shelf_life_risk'].empty:
            health_report['shelf_life_risk'].to_parquet(
                output_dir / "shelf_life_risk.parquet",
                index=False
            )

        # Save summary as JSON
        import json
        with open(output_dir / "inventory_health_summary.json", 'w') as f:
            json.dump(health_report['summary'], f, indent=2)

        logger.info("[OK] Inventory health report saved")
    except Exception as e:
        logger.error(f"Failed to save inventory health report: {e}")


def load_inventory_health_report(cache_dir: Path = Path("data/cache")) -> dict:
    """
    Load inventory health report from cache.

    Parameters:
    -----------
    cache_dir : Path
        Directory containing cached reports

    Returns:
    --------
    dict or None
        Report data or None if not found
    """
    logger.info("Loading inventory health report from cache...")

    try:
        df_dead = pd.read_parquet(cache_dir / "dead_stock.parquet")
        df_shelf = pd.read_parquet(cache_dir / "shelf_life_risk.parquet")

        import json
        with open(cache_dir / "inventory_health_summary.json", 'r') as f:
            summary = json.load(f)

        logger.info("[OK] Inventory health report loaded from cache")
        return {
            'dead_stock': df_dead,
            'shelf_life_risk': df_shelf,
            'summary': summary
        }
    except Exception as e:
        logger.warning(f"Failed to load inventory health cache: {e}")
        return None
