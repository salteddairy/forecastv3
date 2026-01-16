"""
Optimization Module - TCO Calculation and Stock vs Special Order Analysis
Implements Total Cost of Ownership analysis for inventory decisions
"""
import pandas as pd
import numpy as np
import yaml
import logging
from pathlib import Path
from typing import Tuple
from src.utils import safe_divide

logger = logging.getLogger(__name__)


def load_config(config_path: Path = Path("config.yaml")) -> dict:
    """
    Load configuration from YAML file.

    Parameters:
    -----------
    config_path : Path
        Path to config.yaml

    Returns:
    --------
    dict
        Configuration parameters
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        # Return default configuration
        return {
            'carrying_cost': {
                'cost_of_capital_percent': 0.08,
                'storage_percent': 0.10,
                'service_percent': 0.02,
                'risk_percent': 0.05
            },
            'shipping': {
                'standard_freight_percent': 0.05,
                'special_order_freight_percent': 0.15,
                'special_order_fixed_surcharge': 50.0
            },
            'defaults': {
                'fallback_lead_time_days': 21,
                'target_service_level': 0.95
            }
        }


def calculate_carrying_cost_percentage(config: dict) -> float:
    """
    Calculate total carrying cost percentage from config components.

    Parameters:
    -----------
    config : dict
        Configuration dictionary

    Returns:
    --------
    float
        Total carrying cost as a percentage (e.g., 0.25 for 25%)
    """
    cc = config.get('carrying_cost', {})
    return (
        cc.get('cost_of_capital_percent', 0.08) +
        cc.get('storage_percent', 0.10) +
        cc.get('service_percent', 0.02) +
        cc.get('risk_percent', 0.05)
    )


def calculate_annual_selling_price(unit_cost: float, markup_percent: float = 0.30) -> float:
    """
    Calculate annual selling price from unit cost.

    Parameters:
    -----------
    unit_cost : float
        Unit cost
    markup_percent : float
        Standard markup percentage (default: 30%)

    Returns:
    --------
    float
        Selling price
    """
    return unit_cost * (1 + markup_percent)


def calculate_tco_metrics(df_items: pd.DataFrame,
                           df_forecasts: pd.DataFrame,
                           config: dict = None) -> pd.DataFrame:
    """
    Calculate TCO metrics and Stock vs Special Order recommendations.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with UnitCost
    df_forecasts : pd.DataFrame
        Forecast data with item_code and forecast_month_1 through 6
    config : dict, optional
        Configuration dictionary (loads from file if not provided)

    Returns:
    --------
    pd.DataFrame
        Items with TCO metrics and recommendations
    """
    if config is None:
        config = load_config()

    # Ensure forecast_horizon column exists in forecasts (for backward compatibility)
    if 'forecast_horizon' not in df_forecasts.columns:
        logger.warning("Forecasts missing forecast_horizon column - adding default value")
        df_forecasts = df_forecasts.copy()
        df_forecasts['forecast_horizon'] = 12  # Default to 12 months

    # Merge items with forecasts (12 months)
    forecast_cols_to_select = ['item_code', 'winning_model', 'forecast_horizon'] + [f'forecast_month_{i}' for i in range(1, 13)]
    df_merged = df_items.merge(
        df_forecasts[[col for col in forecast_cols_to_select if col in df_forecasts.columns]],
        left_on='Item No.',
        right_on='item_code',
        how='left'
    )

    # Calculate carrying cost percentage
    carrying_cost_pct = calculate_carrying_cost_percentage(config)

    # Get shipping parameters
    shipping = config.get('shipping', {})
    standard_freight_pct = shipping.get('standard_freight_percent', 0.05)
    special_freight_pct = shipping.get('special_order_freight_percent', 0.15)
    special_surcharge = shipping.get('special_order_fixed_surcharge', 50.0)

    # Ensure UnitCost is numeric
    df_merged['UnitCost'] = pd.to_numeric(df_merged['UnitCost'], errors='coerce')

    # Get forecast horizon and calculate forecast demand (fill NaN with 0)
    forecast_cols_all = [f'forecast_month_{i}' for i in range(1, 13)]
    # Only use forecast columns that exist in the dataframe (handles both 6-month and 12-month cached data)
    forecast_cols = [col for col in forecast_cols_all if col in df_merged.columns]
    df_merged['forecast_horizon'] = df_merged['forecast_horizon'].fillna(12)  # Default to 12 if missing

    # Sum only the forecasted months (fill NaN with 0 for unforecasted months)
    df_merged['forecast_period_demand'] = df_merged[forecast_cols].fillna(0).sum(axis=1)

    # Calculate annual demand based on actual forecast horizon (extrapolate)
    # For 3-month horizon: multiply by 4, for 6-month: multiply by 2
    df_merged['annualization_factor'] = df_merged['forecast_horizon'].apply(
        lambda x: round(12 / x, 2) if x > 0 else 2.0  # Default to 6-month horizon if invalid
    )
    df_merged['annual_demand'] = df_merged['forecast_period_demand'] * df_merged['annualization_factor']

    # Calculate Cost to Stock
    # Cost = (Carrying Cost % * Unit Cost) + (Standard Freight % * Unit Cost)
    df_merged['cost_to_stock_annual'] = (
        (carrying_cost_pct * df_merged['UnitCost']) +
        (standard_freight_pct * df_merged['UnitCost'])
    ) * df_merged['annual_demand']

    # Calculate Cost to Special Order
    # Cost = (Special Order Surcharge + Special Freight % * Unit Cost) * Annual Demand
    df_merged['cost_to_special_annual'] = (
        special_surcharge +
        (special_freight_pct * df_merged['UnitCost'])
    ) * df_merged['annual_demand']

    # Make recommendation with tiebreaker logic
    def get_recommendation(row):
        """Determine STOCK vs SPECIAL ORDER recommendation with tiebreaker."""
        stock_cost = row['cost_to_stock_annual']
        special_cost = row['cost_to_special_annual']

        # Use 1% tolerance for "equal" costs (handles floating point precision)
        threshold = 0.01 * min(stock_cost, special_cost) if min(stock_cost, special_cost) > 0 else 0.01

        if abs(stock_cost - special_cost) < threshold:
            return 'NEUTRAL (Costs equal)'
        elif stock_cost < special_cost:
            return 'STOCK'
        else:
            return 'SPECIAL ORDER'

    df_merged['recommendation'] = df_merged.apply(get_recommendation, axis=1)

    # Calculate annual savings if we switch to the recommended approach
    # Current approach: Assume everything is currently STOCKED
    df_merged['current_approach'] = 'STOCK'
    df_merged['current_cost_annual'] = df_merged['cost_to_stock_annual']

    # Calculate cost if we follow recommendation
    df_merged['recommended_cost_annual'] = df_merged.apply(
        lambda row: row['cost_to_stock_annual'] if row['recommendation'] == 'STOCK' else row['cost_to_special_annual'],
        axis=1
    )

    # Calculate savings
    df_merged['annual_savings'] = df_merged['current_cost_annual'] - df_merged['recommended_cost_annual']

    # Calculate potential annual savings percentage (with division by zero protection)
    df_merged['savings_percent'] = df_merged.apply(
        lambda row: safe_divide(row['annual_savings'], row['current_cost_annual'], 0.0) * 100,
        axis=1
    )

    # Flag items that should switch from Stock to Special Order
    # Exclude NEUTRAL cases from switching
    df_merged['should_switch'] = df_merged['recommendation'] == 'SPECIAL ORDER'

    return df_merged


def calculate_stockout_predictions(df_items: pd.DataFrame,
                                    df_forecasts: pd.DataFrame,
                                    df_supply_schedule: pd.DataFrame = None) -> pd.DataFrame:
    """
    Calculate stockout predictions for items.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with CurrentStock, IncomingStock
    df_forecasts : pd.DataFrame
        Forecast data
    df_supply_schedule : pd.DataFrame, optional
        Supply schedule with incoming stock dates

    Returns:
    --------
    pd.DataFrame
        Items with stockout predictions
    """
    # Ensure forecast_horizon column exists in forecasts (for backward compatibility)
    if 'forecast_horizon' not in df_forecasts.columns:
        logger.warning("Forecasts missing forecast_horizon column - adding default value")
        df_forecasts = df_forecasts.copy()
        df_forecasts['forecast_horizon'] = 6  # Default to 6 months

    # Ensure forecast_confidence_pct column exists (for backward compatibility)
    if 'forecast_confidence_pct' not in df_forecasts.columns:
        df_forecasts = df_forecasts.copy()
        df_forecasts['forecast_confidence_pct'] = 50.0  # Default confidence

    # Merge items with forecasts (12 months)
    forecast_cols_to_select = ['item_code'] + [f'forecast_month_{i}' for i in range(1, 13)] + ['forecast_horizon', 'forecast_confidence_pct']
    df_merged = df_items.merge(
        df_forecasts[[col for col in forecast_cols_to_select if col in df_forecasts.columns]],
        left_on='Item No.',
        right_on='item_code',
        how='left'
    )

    # CRITICAL: Use converted stock values (in sales UOM) if available
    # Fall back to original stock values if conversion not applied
    if 'CurrentStock_SalesUOM' in df_merged.columns:
        non_null_converted = df_merged['CurrentStock_SalesUOM'].notna().sum()

        if non_null_converted > 0:
            df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock_SalesUOM'], errors='coerce').fillna(0)
            df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock_SalesUOM'], errors='coerce').fillna(0)
            logger.info(f"[OK] Using UoM-converted stock values for {non_null_converted}/{len(df_merged)} items")
        else:
            logger.warning("[WARNING] CurrentStock_SalesUOM column exists but is all NaN - falling back to original stock")
            df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock'], errors='coerce').fillna(0)
            df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock'], errors='coerce').fillna(0)
    else:
        df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock'], errors='coerce').fillna(0)
        df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock'], errors='coerce').fillna(0)
        logger.warning("[WARNING] CurrentStock_SalesUOM column not found - using original stock values (may be in Base UoM)")

    # Calculate total available stock
    df_merged['total_available'] = df_merged['CurrentStock'] + df_merged['IncomingStock']

    # Fill missing forecast horizon with default (12 months)
    df_merged['forecast_horizon'] = df_merged['forecast_horizon'].fillna(12)

    # Calculate forecast demand (only sum forecasted months, fill NaN with 0)
    forecast_cols_all = [f'forecast_month_{i}' for i in range(1, 13)]
    # Only use forecast columns that exist in the dataframe (handles both 6-month and 12-month cached data)
    forecast_cols = [col for col in forecast_cols_all if col in df_merged.columns]
    df_merged['forecast_period_demand'] = df_merged[forecast_cols].fillna(0).sum(axis=1)

    # For display/analysis, also calculate annualized 12-month equivalent
    df_merged['forecast_annualized_demand'] = df_merged.apply(
        lambda row: row['forecast_period_demand'] * safe_divide(12, row['forecast_horizon'], 1.0),
        axis=1
    )

    # Calculate stockout status
    df_merged['will_stockout'] = df_merged['total_available'] < df_merged['forecast_period_demand']

    # Calculate shortage quantity
    df_merged['shortage_qty'] = np.maximum(
        0,
        df_merged['forecast_period_demand'] - df_merged['total_available']
    )

    # Calculate days until stockout (simplified - assumes constant demand rate)
    # Use actual forecast horizon for average monthly calculation
    df_merged['avg_monthly_demand'] = df_merged.apply(
        lambda row: safe_divide(row['forecast_period_demand'], row['forecast_horizon'], 0.0),
        axis=1
    )
    df_merged['days_until_stockout'] = df_merged.apply(
        lambda row: (row['total_available'] / row['avg_monthly_demand']) * 30
                    if row['avg_monthly_demand'] > 0 and row['will_stockout']
                    else 999,  # No stockout expected
        axis=1
    )

    # Categorize urgency with correct boundary conditions
    def classify_urgency(days):
        """Classify stockout urgency with correct boundary conditions."""
        if pd.isna(days) or days < 0:
            return 'UNKNOWN'
        elif days <= 30:
            return 'CRITICAL (<30 days)'
        elif days <= 60:
            return 'HIGH (30-60 days)'
        elif days <= 90:
            return 'MEDIUM (60-90 days)'
        else:
            return 'LOW (>90 days)'

    df_merged['urgency'] = df_merged['days_until_stockout'].apply(classify_urgency)

    # Identify intermittent items (very long periods between purchases)
    # These should be special order only, not stocked
    # Criteria: Low demand (< 5 units/month) AND low forecast confidence (< 60%)
    df_merged['is_intermittent'] = (
        (df_merged['avg_monthly_demand'] < 5) &
        (df_merged['forecast_confidence_pct'] < 60)
    )

    # For intermittent items: recommend special order, allow stock to go to 0
    df_merged['inventory_strategy'] = df_merged.apply(
        lambda row: 'SPECIAL ORDER ONLY' if row['is_intermittent'] else 'STOCK ITEM',
        axis=1
    )

    # Log intermittent items for review
    intermittent_count = df_merged['is_intermittent'].sum()
    if intermittent_count > 0:
        logger.info(f"Identified {intermittent_count} intermittent items (special order only)")
        logger.info("These items should be allowed to go to 0 inventory and ordered on-demand")

    # Ensure all forecast month columns are preserved and numeric for display
    # These will be used in the shortage report for monthly usage projections
    for i in range(1, 7):
        if f'forecast_month_{i}' in df_merged.columns:
            df_merged[f'forecast_month_{i}'] = pd.to_numeric(
                df_merged[f'forecast_month_{i}'], errors='coerce'
            ).fillna(0)

    return df_merged


def calculate_constrained_stockout_predictions(
    df_items: pd.DataFrame,
    df_forecasts: pd.DataFrame,
    df_vendor_lead_times: pd.DataFrame,
    config_path: str = None,
    config: dict = None
) -> pd.DataFrame:
    """
    Calculate stockout predictions using constrained EOQ optimization.

    This function uses the advanced InventoryOptimizer which considers:
    - Warehouse capacity constraints
    - Carrying cost vs transportation cost trade-offs
    - Lead time variability
    - Service level requirements

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with Item No., ItemGroup, UnitCost, CurrentStock, OnOrder, Committed
    df_forecasts : pd.DataFrame
        Forecast data with item_code, forecast_month_1-12
    df_vendor_lead_times : pd.DataFrame
        Lead time data with item_code, vendor_code, lead_time_days
    config_path : str, optional
        Path to config_inventory_optimization.yaml
    config : dict, optional
        Configuration dictionary (overrides config file)

    Returns:
    --------
    pd.DataFrame
        Items with constrained optimization results including reorder points,
        order quantities, and shortage predictions
    """
    logger.info("Running constrained EOQ optimization...")

    # Import here to avoid circular imports
    from src.inventory_optimization import InventoryOptimizer

    # Initialize optimizer
    optimizer = InventoryOptimizer(config=config, config_path=Path(config_path) if config_path else None)

    # Run optimization for all items
    df_optimized = optimizer.optimize_inventory_multi_item(
        df_items=df_items,
        df_forecasts=df_forecasts,
        df_vendor_lead_times=df_vendor_lead_times
    )

    if len(df_optimized) == 0:
        logger.warning("No optimization results generated")
        return pd.DataFrame()

    # Merge with original item data for display
    df_result = df_items.merge(
        df_optimized,
        on='Item No.',
        how='left',
        suffixes=('', '_optimized')
    )

    # Determine shortage status based on reorder point (NOT 12-month forecast)
    df_result['will_stockout'] = df_result['current_position'] < df_result['reorder_point']
    df_result['shortage_qty'] = np.maximum(
        0,
        df_result['order_quantity']
    )

    # Calculate urgency based on days until reorder
    def classify_urgency_constrained(days):
        """Classify order urgency based on days until reorder point."""
        if pd.isna(days) or days < 0:
            return 'UNKNOWN'
        elif days == 0:
            return 'CRITICAL - At Reorder Point'
        elif days <= 7:
            return 'CRITICAL (<7 days to reorder)'
        elif days <= 14:
            return 'HIGH (7-14 days to reorder)'
        elif days <= 30:
            return 'MEDIUM (14-30 days to reorder)'
        else:
            return 'LOW (>30 days to reorder)'

    df_result['urgency'] = df_result['days_until_reorder'].apply(classify_urgency_constrained)

    # Add forecast month columns for display
    forecast_cols = [f'forecast_month_{i}' for i in range(1, 13)]
    df_forecasts_display = df_forecasts[['item_code'] + [col for col in forecast_cols if col in df_forecasts.columns]].copy()
    df_result = df_result.merge(
        df_forecasts_display,
        left_on='Item No.',
        right_on='item_code',
        how='left'
    )

    # Ensure all forecast columns are numeric
    for col in forecast_cols:
        if col in df_result.columns:
            df_result[col] = pd.to_numeric(df_result[col], errors='coerce').fillna(0)

    logger.info(f"Constrained optimization complete: {len(df_result)} items")
    logger.info(f"  Items below reorder point: {df_result['will_stockout'].sum()}")
    logger.info(f"  Total order quantity needed: {df_result['shortage_qty'].sum():,.0f} units")

    return df_result


def optimize_inventory(df_items: pd.DataFrame,
                       df_forecasts: pd.DataFrame,
                       df_supply_schedule: pd.DataFrame = None,
                       config: dict = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run complete optimization analysis.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data
    df_forecasts : pd.DataFrame
        Forecast data
    df_supply_schedule : pd.DataFrame, optional
        Supply schedule data
    config : dict, optional
        Configuration dictionary

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        (stockout_predictions, tco_analysis)
    """
    # Calculate stockout predictions
    df_stockout = calculate_stockout_predictions(df_items, df_forecasts, df_supply_schedule)

    # Calculate TCO analysis
    df_tco = calculate_tco_metrics(df_items, df_forecasts, config)

    return df_stockout, df_tco
