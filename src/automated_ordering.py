"""
Automated Ordering Module

Calculates reorder points, order quantities, and generates vendor-grouped purchase orders
ready for SAP B1 import.

Best Practices Implemented:
1. Reorder Point = (Lead Time Demand) + (Safety Stock)
2. Safety Stock = Z-score × σdemand × √(Lead Time) + Safety Buffer
3. Order Up-To Level = Reorder Point + (Order Cycle × Monthly Demand)
4. Order Quantity = Order Up-To - (Current Stock + On Order - Committed)
"""
import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class AutomatedOrderingSystem:
    """
    Automated ordering system that calculates:
    - Reorder points (when to order)
    - Order quantities (how much to order)
    - Groups orders by vendor
    - Outputs SAP-ready purchase orders
    """

    def __init__(self, config: dict = None):
        """
        Initialize the ordering system.

        Parameters:
        -----------
        config : dict, optional
            Configuration parameters
        """
        self.config = config or self._default_config()

    def _default_config(self) -> dict:
        """Default configuration for ordering calculations."""
        return {
            # Service Level (Z-score for safety stock)
            'service_level_z_score': 1.65,  # 95% service level

            # Order Cycle (how often you review/place orders)
            'order_cycle_days': 30,  # Monthly reviews

            # Safety Buffer (extra days of stock for uncertainty)
            'safety_buffer_days': 7,  # 1 week buffer

            # Minimum Order Thresholds
            'minimum_order_value': 50.00,  # Don't order if value < $50
            'round_to_nearest': 1,  # Round order quantities to nearest whole unit

            # Vendor Grouping
            'consolidate_by_vendor': True,
        }

    def calculate_reorder_points(
        self,
        df_forecasts: pd.DataFrame,
        df_inventory: pd.DataFrame,
        df_vendor_lead_times: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate reorder points for all items using industry best practices.

        Formula:
        ┌─────────────────────────────────────────────────────────────┐
        │ Reorder Point = Lead Time Demand + Safety Stock             │
        ├─────────────────────────────────────────────────────────────┤
        │ Lead Time Demand = Avg Monthly Demand × (Lead Time / 30)    │
        │ Safety Stock = (Z × σ × √(LT/30)) + (Buffer Days × Daily Dem)│
        └─────────────────────────────────────────────────────────────┘

        Parameters:
        -----------
        df_forecasts : pd.DataFrame
            Forecast data with item_code, forecast_month_1-12, winning_model
        df_inventory : pd.DataFrame
            Current inventory with item_code, CurrentStock, OnOrder, Committed
        df_vendor_lead_times : pd.DataFrame
            Lead times per item per vendor

        Returns:
        --------
        pd.DataFrame
            Items with calculated reorder points and order quantities
        """
        logger.info("Calculating reorder points using industry best practices...")

        # Validate required columns exist
        required_forecast_cols = ['forecast_month_1', 'forecast_month_2', 'forecast_month_3']
        missing_cols = [col for col in required_forecast_cols if col not in df_forecasts.columns]
        if missing_cols:
            logger.error(f"Missing required forecast columns: {missing_cols}")
            return pd.DataFrame()

        # Merge data
        df = df_forecasts.merge(df_inventory, on='item_code', how='left')
        df = df.merge(df_vendor_lead_times, on='item_code', how='left')

        # Calculate demand statistics from 12-month forecast
        forecast_cols = [col for col in df.columns if col.startswith('forecast_month_') and col in df.columns]

        if not forecast_cols:
            logger.error("No forecast columns found in data")
            return pd.DataFrame()

        # Average monthly demand
        df['avg_monthly_demand'] = df[forecast_cols].mean(axis=1)

        # Demand standard deviation (volatility)
        df['demand_std'] = df[forecast_cols].std(axis=1)

        # Coefficient of variation - use safe_divide to handle zero demand
        from src.utils import safe_divide
        df['demand_cv'] = safe_divide(df['demand_std'], df['avg_monthly_demand'], 0.0)

        # Lead time in months (handle missing)
        if 'lead_time_days' not in df.columns:
            logger.warning("lead_time_days column not found, using default 21 days")
            df['lead_time_days'] = 21
        else:
            df['lead_time_days'] = df['lead_time_days'].fillna(21)  # Default 3 weeks

        df['lead_time_months'] = safe_divide(df['lead_time_days'], 30, 0.7)  # Default ~3 weeks

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 1. LEAD TIME DEMAND                                         │
        # │    Demand during the lead time period                       │
        # └─────────────────────────────────────────────────────────────┘
        df['lead_time_demand'] = df['avg_monthly_demand'] * df['lead_time_months']

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 2. SAFETY STOCK                                             │
        # │    Statistical safety stock + manual buffer                │
        # │                                                             │
        # │    Statistical = Z × σ × √(Lead Time)                      │
        # │    Buffer = Safety Buffer Days × Daily Demand               │
        # └─────────────────────────────────────────────────────────────┘
        df['daily_demand'] = df['avg_monthly_demand'] / 30

        # Statistical safety stock
        df['safety_stock_statistical'] = (
            self.config['service_level_z_score'] *
            df['demand_std'] *
            np.sqrt(df['lead_time_months'])
        )

        # Manual safety buffer (for uncertainty)
        df['safety_stock_buffer'] = df['daily_demand'] * self.config['safety_buffer_days']

        # Total safety stock
        df['safety_stock'] = df['safety_stock_statistical'] + df['safety_stock_buffer']

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 3. REORDER POINT                                            │
        # │    When to place an order                                   │
        # └─────────────────────────────────────────────────────────────┘
        df['reorder_point'] = df['lead_time_demand'] + df['safety_stock']

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 4. ORDER UP-TO LEVEL                                        │
        # │    Target stock level after ordering                       │
        # │                                                             │
        # │    Order-Up-To = Reorder Point + (Order Cycle × Demand)    │
        # └─────────────────────────────────────────────────────────────┘
        order_cycle_months = self.config['order_cycle_days'] / 30
        df['order_up_to_level'] = df['reorder_point'] + (df['avg_monthly_demand'] * order_cycle_months)

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 5. CURRENT POSITION                                        │
        # │    Where we are now                                        │
        # └─────────────────────────────────────────────────────────────┘
        # Get columns safely (handle both normalized and original names)
        def safe_get_column(col_name, normalized_name, default=0):
            """Get column value, checking both normalized and original names"""
            if normalized_name in df.columns:
                return df[normalized_name].fillna(default)
            elif col_name in df.columns:
                return df[col_name].fillna(default)
            else:
                return default

        current_stock = safe_get_column('CurrentStock', 'current_stock', 0)
        on_order = safe_get_column('OnOrder', 'on_order', 0)
        committed = safe_get_column('Committed', 'committed_stock', 0)

        df['current_position'] = current_stock + on_order - committed

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 6. ORDER QUANTITY                                          │
        # │    How much to order                                       │
        # │                                                             │
        # │    Order Qty = Order-Up-To - Current Position               │
        # └─────────────────────────────────────────────────────────────┘
        df['order_quantity'] = np.maximum(
            0,
            df['order_up_to_level'] - df['current_position']
        )

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 7. SHOULD ORDER?                                           │
        # │    Decision logic                                           │
        # └─────────────────────────────────────────────────────────────┘
        df['should_order'] = df['current_position'] < df['reorder_point']

        # Apply minimum order value threshold
        # Handle both normalized (unit_cost) and original (UnitCost) column names
        if 'unit_cost' in df.columns or 'UnitCost' in df.columns:
            unit_cost = safe_get_column('UnitCost', 'unit_cost', 0)
            df['order_value'] = df['order_quantity'] * unit_cost
            df['should_order'] = df['should_order'] & (df['order_value'] >= self.config['minimum_order_value'])

        # Round order quantities
        df['order_quantity_rounded'] = np.round(
            df['order_quantity'] / self.config['round_to_nearest']
        ) * self.config['round_to_nearest']

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 8. STOCK STATUS CLASSIFICATION                             │
        # └─────────────────────────────────────────────────────────────┘
        def classify_stock_status(row):
            """Classify current stock status."""
            position = row['current_position']
            reorder = row['reorder_point']
            up_to = row['order_up_to_level']

            if position <= reorder * 0.5:
                return 'CRITICAL - Below 50% of Reorder Point'
            elif position < reorder:
                return 'LOW - Below Reorder Point'
            elif position < up_to:
                return 'OK - Within Target Range'
            else:
                return 'OVERSTOCKED - Above Target'

        df['stock_status'] = df.apply(classify_stock_status, axis=1)

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 9. DAYS UNTIL REORDER                                      │
        # │    When will we hit the reorder point?                      │
        # └─────────────────────────────────────────────────────────────┘
        df['days_until_reorder'] = df.apply(
            lambda row: max(0, ((row['current_position'] - row['reorder_point']) / row['daily_demand']))
            if row['daily_demand'] > 0 else 999,
            axis=1
        )

        # ┌─────────────────────────────────────────────────────────────┐
        # │ 10. ORDER URGENCY                                          │
        # └─────────────────────────────────────────────────────────────┘
        def classify_order_urgency(row):
            """Classify order urgency based on stock position."""
            days = row['days_until_reorder']
            should = row['should_order']

            if not should:
                return 'NO ORDER NEEDED'
            elif days <= 0:
                return 'URGENT - Past Due'
            elif days <= 7:
                return 'CRITICAL - Order Now'
            elif days <= 14:
                return 'HIGH - Order Within 1 Week'
            elif days <= 30:
                return 'MEDIUM - Order Within Month'
            else:
                return 'LOW - Plan for Next Cycle'

        df['order_urgency'] = df.apply(classify_order_urgency, axis=1)

        # Select and order columns for output
        result_cols = [
            'item_code',
            'Item No.',
            'Item Description',
            'vendor_code',
            'TargetVendor',
            'lead_time_days',
            'avg_monthly_demand',
            'demand_cv',
            'demand_std',
            'lead_time_demand',
            'safety_stock',
            'safety_stock_statistical',
            'safety_stock_buffer',
            'reorder_point',
            'order_up_to_level',
            'CurrentStock',
            'OnOrder',
            'Committed',
            'current_position',
            'order_quantity',
            'order_quantity_rounded',
            'order_value',
            'should_order',
            'days_until_reorder',
            'order_urgency',
            'stock_status',
            'UnitCost',
            'winning_model',
            'forecast_confidence_pct'
        ]

        # Only include columns that exist
        result_cols = [col for col in result_cols if col in df.columns]

        logger.info(f"Calculated reorder points for {len(df)} items")
        logger.info(f"  - Items requiring orders: {df['should_order'].sum()}")
        logger.info(f"  - Critical items: {((df['order_urgency'] == 'CRITICAL - Order Now') | (df['order_urgency'] == 'URGENT - Past Due')).sum()}")

        return df[result_cols]

    def generate_vendor_purchase_orders(
        self,
        df_ordering: pd.DataFrame,
        include_non_critical: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Group orders by vendor for SAP B1 purchase order creation.

        Output is ready to copy-paste into SAP B1.

        Parameters:
        -----------
        df_ordering : pd.DataFrame
            Output from calculate_reorder_points()
        include_non_critical : bool
            Include items that don't need immediate ordering

        Returns:
        --------
        Dict[str, pd.DataFrame]
            Dictionary keyed by vendor_code with PO line items
        """
        logger.info("Generating vendor-grouped purchase orders...")

        # Filter for items that need ordering
        if not include_non_critical:
            df_to_order = df_ordering[df_ordering['should_order'] == True].copy()
        else:
            df_to_order = df_ordering.copy()

        if len(df_to_order) == 0:
            logger.warning("No items require ordering")
            return {}

        # Group by vendor
        vendor_orders = {}

        for vendor_code in df_to_order['vendor_code'].dropna().unique():
            vendor_items = df_to_order[df_to_order['vendor_code'] == vendor_code].copy()

            # Sort by urgency (critical first)
            urgency_order = {
                'URGENT - Past Due': 1,
                'CRITICAL - Order Now': 2,
                'HIGH - Order Within 1 Week': 3,
                'MEDIUM - Order Within Month': 4,
                'LOW - Plan for Next Cycle': 5,
                'NO ORDER NEEDED': 6
            }
            vendor_items['urgency_rank'] = vendor_items['order_urgency'].map(urgency_order)
            vendor_items['urgency_rank'] = vendor_items['urgency_rank'].fillna(99)
            vendor_items = vendor_items.sort_values('urgency_rank')

            # Select PO columns
            po_columns = [
                'item_code',
                'Item No.',
                'Item Description',
                'order_quantity_rounded',
                'UoM',
                'UnitCost',
                'order_value',
                'lead_time_days',
                'order_urgency',
                'days_until_reorder'
            ]

            # Only include columns that exist
            po_columns = [col for col in po_columns if col in vendor_items.columns]

            vendor_orders[vendor_code] = vendor_items[po_columns]

        logger.info(f"Generated purchase orders for {len(vendor_orders)} vendors")

        # Log summary
        for vendor_code, po_items in vendor_orders.items():
            total_value = po_items['order_value'].sum() if 'order_value' in po_columns else 0
            item_count = len(po_items)
            logger.info(f"  Vendor {vendor_code}: {item_count} items, ${total_value:,.2f} total")

        return vendor_orders

    def format_for_sap_import(
        self,
        vendor_orders: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Format vendor orders for SAP B1 import.

        Creates a flat format ready for SAP B1 PO entry or DTW import.

        Parameters:
        -----------
        vendor_orders : Dict[str, pd.DataFrame]
            Output from generate_vendor_purchase_orders()

        Returns:
        --------
        pd.DataFrame
            Flattened PO data with vendor grouping
        """
        all_po_lines = []

        for vendor_code, po_items in vendor_orders.items():
            po_items_copy = po_items.copy()
            po_items_copy['vendor_code'] = vendor_code
            all_po_lines.append(po_items_copy)

        if not all_po_lines:
            return pd.DataFrame()

        df_sap = pd.concat(all_po_lines, ignore_index=True)

        # Reorder columns for SAP format
        sap_columns = [
            'vendor_code',
            'Item No.',
            'Item Description',
            'order_quantity_rounded',
            'UoM',
            'UnitCost',
            'order_value',
            'lead_time_days',
            'order_urgency'
        ]

        sap_columns = [col for col in sap_columns if col in df_sap.columns]

        return df_sap[sap_columns]

    def export_to_excel(
        self,
        vendor_orders: Dict[str, pd.DataFrame],
        output_path: str = "purchase_orders.xlsx"
    ) -> None:
        """
        Export vendor orders to Excel with one sheet per vendor.

        Parameters:
        -----------
        vendor_orders : Dict[str, pd.DataFrame]
            Output from generate_vendor_purchase_orders()
        output_path : str
            Path to save Excel file
        """
        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Summary sheet
                summary_data = []
                for vendor_code, po_items in vendor_orders.items():
                    total_value = po_items['order_value'].sum() if 'order_value' in po_items.columns else 0
                    item_count = len(po_items)
                    summary_data.append({
                        'Vendor': vendor_code,
                        'Item Count': item_count,
                        'Total Value': total_value,
                        'Average Lead Time': po_items['lead_time_days'].mean() if 'lead_time_days' in po_items.columns else 0
                    })

                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Summary', index=False)

                # One sheet per vendor
                for vendor_code, po_items in vendor_orders.items():
                    # Sanitize sheet name (Excel max 31 chars)
                    sheet_name = str(vendor_code)[:31]
                    po_items.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"Exported purchase orders to {output_path}")

        except ImportError:
            logger.warning("openpyxl not installed - Excel export unavailable")
            logger.info("Install with: pip install openpyxl")

    def calculate_eoq(
        self,
        annual_demand: float,
        unit_cost: float,
        ordering_cost: float = 50.00,
        holding_cost_pct: float = 0.25
    ) -> float:
        """
        Calculate Economic Order Quantity (EOQ).

        Formula: EOQ = √((2 × D × S) / H)

        Where:
        - D = Annual demand
        - S = Ordering cost per order
        - H = Holding cost per unit per year (Unit Cost × Holding %)

        Parameters:
        -----------
        annual_demand : float
            Annual demand in units
        unit_cost : float
            Cost per unit
        ordering_cost : float
            Fixed cost per order (admin, receiving, etc.)
        holding_cost_pct : float
            Annual holding cost as % of unit cost

        Returns:
        --------
        float
            Optimal order quantity
        """
        if annual_demand <= 0 or unit_cost <= 0:
            return 0

        holding_cost = unit_cost * holding_cost_pct
        eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost)

        return eoq


def get_vendor_lead_times(
    df_supply: pd.DataFrame,
    df_items: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate lead times per item per vendor from supply chain data.

    Parameters:
    -----------
    df_supply : pd.DataFrame
        Supply chain history with lead_time_days
    df_items : pd.DataFrame
        Item master with vendor information

    Returns:
    --------
    pd.DataFrame
        Lead times by item and vendor
    """
    # Import normalization function
    from src.ingestion import normalize_column_names

    # Normalize supply data columns
    df_supply = normalize_column_names(df_supply)

    # Normalize items data columns
    df_items_normalized = normalize_column_names(df_items)

    # Ensure required columns exist
    if 'item_code' not in df_supply.columns:
        raise ValueError(f"df_supply missing 'item_code' column. Has: {df_supply.columns.tolist()}")

    if 'vendor_code' not in df_supply.columns:
        # Try to get vendor from items
        if 'vendor_code' in df_items_normalized.columns:
            # Merge vendor info
            item_vendor_map = df_items_normalized[['item_code', 'vendor_code']].drop_duplicates()
            df_supply = df_supply.merge(
                item_vendor_map,
                on='item_code',
                how='left'
            )
        else:
            # Add default vendor
            df_supply['vendor_code'] = 'DEFAULT'

    # Check for lead_time_days column
    if 'lead_time_days' not in df_supply.columns:
        raise ValueError(f"df_supply missing 'lead_time_days' column. Has: {df_supply.columns.tolist()}")

    # Remove rows with missing/invalid lead times
    df_supply = df_supply.dropna(subset=['lead_time_days', 'item_code', 'vendor_code'])
    df_supply = df_supply[df_supply['lead_time_days'] >= 0]

    # Group by item and vendor
    lead_times = df_supply.groupby(['item_code', 'vendor_code'])['lead_time_days'].agg([
        ('lead_time_days', 'mean'),
        ('lead_time_std', 'std'),
        ('lead_time_min', 'min'),
        ('lead_time_max', 'max'),
        ('sample_count', 'count')
    ]).reset_index()

    # Flatten column names - handle MultiIndex properly
    if isinstance(lead_times.columns, pd.MultiIndex):
        lead_times.columns = ['_'.join(col).strip('_') for col in lead_times.columns.values]
    else:
        # Already flat
        pass

    # Verify expected columns exist
    expected_cols = ['item_code', 'vendor_code', 'lead_time_days', 'sample_count']
    missing_cols = [col for col in expected_cols if col not in lead_times.columns]
    if missing_cols:
        raise ValueError(f"lead_times missing columns: {missing_cols}. Has: {lead_times.columns.tolist()}")

    return lead_times
