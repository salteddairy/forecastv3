"""
Advanced Inventory Optimization Module

Implements constrained multi-objective optimization for reorder points and order quantities
considering:
1. Warehouse capacity constraints
2. Carrying cost vs transportation cost trade-offs
3. Lead time variability
4. Service level requirements

Best Practices:
- Modified Economic Order Quantity (EOQ) with constraints
- Cycle stock vs safety stock optimization
- Transportation cost minimization (FTL vs LTL breakpoints)
- Warehouse space allocation by ABC classification
"""
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from typing import Dict, Tuple, Optional
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class InventoryOptimizer:
    """
    Advanced inventory optimization system that calculates optimal reorder points
    and order quantities considering warehouse capacity, carrying costs, and
    transportation costs.
    """

    def __init__(self, config: dict = None, config_path: Path = None):
        """
        Initialize the inventory optimizer.

        Parameters:
        -----------
        config : dict, optional
            Configuration parameters
        config_path : Path, optional
            Path to config.yaml file
        """
        if config_path and Path(config_path).exists():
            self.config = self._load_config(config_path)
        else:
            self.config = config or self._default_config()

        logger.info("Initialized Inventory Optimizer with constrained optimization")

    def _load_config(self, config_path: Path) -> dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _default_config(self) -> dict:
        """
        Default configuration for inventory optimization.

        Key Parameters:
        - carrying_cost: Annual cost to hold inventory (as % of unit cost)
        - transportation: Shipping cost structure
        - warehouse: Capacity constraints
        - service_level: Target fill rate
        """
        return {
            # Carrying Cost Components (Annual % of unit cost)
            'carrying_cost': {
                'cost_of_capital_percent': 0.08,      # Cost of capital (8%)
                'storage_percent': 0.10,               # Warehousing, rent, utilities (10%)
                'service_percent': 0.02,               # Insurance, taxes (2%)
                'risk_percent': 0.05,                  # Obsolescence, shrinkage, damage (5%)
                'total_carrying_cost_percent': 0.25,   # Total = 25% annually
            },

            # Transportation Cost Structure
            'transportation': {
                # Fixed ordering costs (admin, receiving, etc.)
                'ordering_cost_per_order': 50.0,

                # Freight cost structure (per shipment)
                'ftl_minimum_units': 500,              # Full truckload threshold (units)
                'ftl_fixed_cost': 1500.0,              # FTL flat rate
                'ltl_cost_per_unit': 2.50,             # Less-than-truckload per-unit rate
                'ltl_fixed_cost': 150.0,               # LTL fixed charge

                # Volume discount breakpoints
                'volume_discount_tiers': [
                    {'min_units': 0, 'discount_pct': 0.00},
                    {'min_units': 100, 'discount_pct': 0.05},   # 5% discount for 100+ units
                    {'min_units': 500, 'discount_pct': 0.10},   # 10% discount for 500+ units
                    {'min_units': 1000, 'discount_pct': 0.15},  # 15% discount for 1000+ units
                ]
            },

            # Warehouse Capacity Constraints
            'warehouse': {
                # Total warehouse capacity (square feet or cubic meters)
                'total_capacity_sqft': 50000,

                # Capacity utilization target (don't exceed 85% to allow for operations)
                'max_utilization_pct': 0.85,

                # Space requirements per unit (adjust by item category)
                'space_per_unit_sqft': {
                    'default': 1.0,                    # Default: 1 sq ft per unit
                    'FG-RE': 0.5,                      # Finished goods - Refrigerated: 0.5 sq ft
                    'FG-FZ': 0.3,                      # Frozen goods: 0.3 sq ft
                    'RM-BULK': 2.0,                    # Raw materials bulk: 2 sq ft
                },

                # ABC classification for space allocation priority
                # A items: High turnover, get priority space (80% of space)
                # B items: Medium turnover (15% of space)
                # C items: Low turnover (5% of space)
                'abc_space_allocation': {
                    'A': 0.80,
                    'B': 0.15,
                    'C': 0.05
                }
            },

            # Service Level & Lead Time
            'service_level': {
                'target_fill_rate': 0.95,              # 95% service level (Z = 1.65)
                'lead_time_buffer_days': 7,            # Extra safety buffer
                'max_order_cycle_days': 90,            # Maximum time between orders (3 months)
            },

            # Optimization Constraints
            'constraints': {
                'max_order_quantity_months': 6,        # Don't order more than 6 months supply
                'min_order_value': 100.0,              # Minimum order value in dollars
                'min_order_quantity': 1,               # Minimum order quantity (units)
                'round_to_nearest': 1,                 # Round order quantities to nearest unit
            }
        }

    def calculate_carrying_cost_per_unit_per_year(
        self,
        unit_cost: float
    ) -> float:
        """
        Calculate annual carrying cost per unit.

        Formula:
        Carrying Cost = Unit Cost × (Capital + Storage + Service + Risk) %

        Parameters:
        -----------
        unit_cost : float
            Cost per unit

        Returns:
        --------
        float
            Annual carrying cost per unit
        """
        cc = self.config['carrying_cost']
        carrying_cost_pct = (
            cc['cost_of_capital_percent'] +
            cc['storage_percent'] +
            cc['service_percent'] +
            cc['risk_percent']
        )
        return unit_cost * carrying_cost_pct

    def calculate_transportation_cost(
        self,
        order_quantity: int,
        unit_cost: float
    ) -> float:
        """
        Calculate total transportation cost for an order.

        Considers:
        - Fixed ordering cost (admin, receiving)
        - Freight cost (FTL vs LTL optimization)
        - Volume discounts

        Parameters:
        -----------
        order_quantity : int
            Quantity being ordered
        unit_cost : float
            Cost per unit (for volume discount calc)

        Returns:
        --------
        float
            Total transportation cost
        """
        trans = self.config['transportation']

        # Base fixed ordering cost
        total_cost = trans['ordering_cost_per_order']

        # Determine freight structure (FTL vs LTL)
        if order_quantity >= trans['ftl_minimum_units']:
            # Full truckload - flat rate
            freight_cost = trans['ftl_fixed_cost']
        else:
            # Less-than-truckload - per-unit rate + fixed charge
            freight_cost = (order_quantity * trans['ltl_cost_per_unit']) + trans['ltl_fixed_cost']

        total_cost += freight_cost

        # Apply volume discount to unit cost portion
        # (discount applies to merchandise value, not freight)
        discount_pct = 0.0
        for tier in trans['volume_discount_tiers']:
            if order_quantity >= tier['min_units']:
                discount_pct = tier['discount_pct']

        # Discount savings = Order Quantity × Unit Cost × Discount %
        discount_savings = order_quantity * unit_cost * discount_pct
        total_cost -= discount_savings

        return max(0, total_cost)  # Don't allow negative costs

    def calculate_eoq(
        self,
        annual_demand: float,
        unit_cost: float,
        ordering_cost: float = None,
        carrying_cost_pct: float = None
    ) -> float:
        """
        Calculate Economic Order Quantity (EOQ).

        Formula: EOQ = √((2 × D × S) / H)

        Where:
        - D = Annual demand
        - S = Ordering cost per order
        - H = Holding cost per unit per year

        Parameters:
        -----------
        annual_demand : float
            Annual demand in units
        unit_cost : float
            Cost per unit
        ordering_cost : float, optional
            Fixed cost per order (default from config)
        carrying_cost_pct : float, optional
            Annual holding cost as % of unit cost (default from config)

        Returns:
        --------
        float
            Optimal order quantity
        """
        if annual_demand <= 0 or unit_cost <= 0:
            return 0

        # Use config defaults if not provided
        if ordering_cost is None:
            ordering_cost = self.config['transportation']['ordering_cost_per_order']

        if carrying_cost_pct is None:
            carrying_cost_pct = self.config['carrying_cost']['total_carrying_cost_percent']

        # Holding cost per unit per year
        holding_cost_per_unit = unit_cost * carrying_cost_pct

        # Classic EOQ formula
        eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)

        return eoq

    def calculate_constrained_eoq(
        self,
        item_code: str,
        annual_demand: float,
        unit_cost: float,
        item_group: str = None,
        abc_classification: str = 'C',
        available_warehouse_space: float = None
    ) -> Tuple[float, Dict]:
        """
        Calculate EOQ with warehouse capacity and transportation constraints.

        This is the CORE optimization function that considers:
        1. Classic EOQ (optimal from pure cost perspective)
        2. Warehouse space constraints
        3. Transportation cost breakpoints (FTL vs LTL)
        4. Maximum order cycle (don't order too much at once)

        Parameters:
        -----------
        item_code : str
            Item identifier
        annual_demand : float
            Annual demand in units
        unit_cost : float
            Cost per unit
        item_group : str, optional
            Item group for space calculation
        abc_classification : str
            ABC class (A, B, or C) for space priority
        available_warehouse_space : float, optional
            Available warehouse space in sq ft

        Returns:
        --------
        Tuple[float, Dict]
            (optimal_order_quantity, optimization_details)
        """
        details = {}

        # 1. Calculate unconstrained EOQ
        unconstrained_eoq = self.calculate_eoq(annual_demand, unit_cost)
        details['unconstrained_eoq'] = unconstrained_eoq

        # 2. Apply warehouse capacity constraint
        if available_warehouse_space is not None:
            # Get space requirements per unit
            space_per_unit = self._get_space_per_unit(item_group)

            # Maximum quantity we can store given space constraint
            max_by_space = available_warehouse_space / space_per_unit
            details['max_by_space'] = max_by_space

            # Don't exceed space capacity
            eoq_space_constrained = min(unconstrained_eoq, max_by_space)
        else:
            eoq_space_constrained = unconstrained_eoq
            details['max_by_space'] = None

        # 3. Apply maximum order cycle constraint
        # Don't order more than X months of supply
        max_order_months = self.config['constraints']['max_order_quantity_months']
        monthly_demand = annual_demand / 12
        max_by_cycle = monthly_demand * max_order_months
        details['max_by_cycle'] = max_by_cycle

        eoq_cycle_constrained = min(eoq_space_constrained, max_by_cycle)

        # 4. Optimize for transportation cost (FTL vs LTL breakpoints)
        # Test ordering quantities around FTL threshold to find true optimal
        optimal_qty = self._optimize_for_transportation(
            eoq_cycle_constrained,
            annual_demand,
            unit_cost,
            monthly_demand
        )
        details['optimized_for_transportation'] = optimal_qty

        # 5. Apply minimum order quantity
        min_order_qty = self.config['constraints']['min_order_quantity']
        final_order_qty = max(optimal_qty, min_order_qty)
        details['final_order_quantity'] = final_order_qty

        # 6. Calculate cost comparison
        details['cost_analysis'] = self._analyze_order_costs(
            final_order_qty,
            annual_demand,
            unit_cost
        )

        return final_order_qty, details

    def _get_space_per_unit(self, item_group: str = None) -> float:
        """Get warehouse space required per unit (in sq ft)."""
        space_reqs = self.config['warehouse']['space_per_unit_sqft']
        return space_reqs.get(item_group, space_reqs.get('default', 1.0))

    def _optimize_for_transportation(
        self,
        base_eoq: float,
        annual_demand: float,
        unit_cost: float,
        monthly_demand: float
    ) -> float:
        """
        Optimize order quantity considering transportation cost breakpoints.

        Tests quantities around the FTL threshold to find the true optimum
        considering both carrying costs and transportation costs.

        Parameters:
        -----------
        base_eoq : float
            EOQ before transportation optimization
        annual_demand : float
            Annual demand
        unit_cost : float
            Unit cost
        monthly_demand : float
            Monthly demand

        Returns:
        --------
        float
            Optimal order quantity
        """
        ftl_threshold = self.config['transportation']['ftl_minimum_units']

        # Candidate quantities to test
        candidates = [
            base_eoq,
            ftl_threshold * 0.9,  # Just below FTL
            ftl_threshold,        # Exactly at FTL threshold
            ftl_threshold * 1.1,  # Just above FTL (to test cost impact)
        ]

        # Calculate total annual cost for each candidate
        best_quantity = base_eoq
        lowest_cost = float('inf')

        for qty in candidates:
            if qty <= 0:
                continue

            # Number of orders per year
            num_orders = annual_demand / qty

            # Annual ordering + transportation cost
            annual_transport_cost = num_orders * self.calculate_transportation_cost(qty, unit_cost)

            # Annual carrying cost (average inventory = qty / 2)
            avg_inventory = qty / 2
            annual_carrying_cost = avg_inventory * self.calculate_carrying_cost_per_unit_per_year(unit_cost)

            # Total annual cost
            total_cost = annual_transport_cost + annual_carrying_cost

            if total_cost < lowest_cost:
                lowest_cost = total_cost
                best_quantity = qty

        return best_quantity

    def _analyze_order_costs(
        self,
        order_quantity: float,
        annual_demand: float,
        unit_cost: float
    ) -> Dict:
        """
        Analyze the cost components of the optimal order quantity.

        Returns breakdown of:
        - Ordering costs
        - Transportation costs
        - Carrying costs
        - Total annual cost

        Parameters:
        -----------
        order_quantity : float
            Order quantity
        annual_demand : float
            Annual demand
        unit_cost : float
            Unit cost

        Returns:
        --------
        Dict
            Cost breakdown
        """
        num_orders_per_year = annual_demand / order_quantity
        avg_inventory = order_quantity / 2

        # Ordering cost (admin, receiving)
        ordering_cost = num_orders_per_year * self.config['transportation']['ordering_cost_per_order']

        # Transportation cost
        transport_cost_per_order = self.calculate_transportation_cost(order_quantity, unit_cost)
        annual_transport_cost = num_orders_per_year * transport_cost_per_order

        # Carrying cost (holding inventory)
        carrying_cost_per_unit = self.calculate_carrying_cost_per_unit_per_year(unit_cost)
        annual_carrying_cost = avg_inventory * carrying_cost_per_unit

        # Total cost
        total_annual_cost = ordering_cost + annual_transport_cost + annual_carrying_cost

        return {
            'order_quantity': order_quantity,
            'orders_per_year': num_orders_per_year,
            'ordering_cost_annual': ordering_cost,
            'transportation_cost_annual': annual_transport_cost,
            'carrying_cost_annual': annual_carrying_cost,
            'total_annual_cost': total_annual_cost,
            'annual_demand': annual_demand
        }

    def calculate_reorder_point(
        self,
        item_code: str,
        df_forecasts: pd.DataFrame,
        df_vendor_lead_times: pd.DataFrame,
        df_items: pd.DataFrame = None
    ) -> Tuple[float, Dict]:
        """
        Calculate reorder point using lead time demand + safety stock.

        Formula: Reorder Point = Lead Time Demand + Safety Stock

        Where:
        - Lead Time Demand = Average Daily Demand × Lead Time Days
        - Safety Stock = Z-score × Demand_STD × √(Lead Time) + Buffer Days × Daily Demand

        Parameters:
        -----------
        item_code : str
            Item identifier
        df_forecasts : pd.DataFrame
            Forecast data with item_code and forecast_month_1-12
        df_vendor_lead_times : pd.DataFrame
            Lead time data with item_code, vendor_code, lead_time_days
        df_items : pd.DataFrame, optional
            Item master data (for unit cost, item group, etc.)

        Returns:
        --------
        Tuple[float, Dict]
            (reorder_point, calculation_details)
        """
        # Get forecast data for this item
        item_forecast = df_forecasts[df_forecasts['item_code'] == item_code]

        if len(item_forecast) == 0:
            logger.warning(f"No forecast data found for {item_code}")
            return 0, {}

        # Get forecast values (12 months)
        forecast_cols = [f'forecast_month_{i}' for i in range(1, 13)]
        forecast_values = item_forecast[forecast_cols].values[0]

        # Calculate demand statistics
        avg_monthly_demand = np.nanmean(forecast_values)
        demand_std = np.nanstd(forecast_values)
        avg_daily_demand = avg_monthly_demand / 30

        # Get lead time
        item_lead_times = df_vendor_lead_times[
            df_vendor_lead_times['item_code'] == item_code
        ]

        if len(item_lead_times) == 0:
            # Use default lead time
            lead_time_days = 21  # 3 weeks
            logger.warning(f"No lead time data for {item_code}, using default 21 days")
        else:
            # Use average lead time across vendors
            lead_time_days = item_lead_times['lead_time_days'].mean()

        # Calculate lead time in months
        lead_time_months = lead_time_days / 30

        # Calculate service level Z-score
        target_fill_rate = self.config['service_level']['target_fill_rate']
        from scipy.stats import norm
        z_score = norm.ppf(target_fill_rate)  # 95% → Z = 1.65

        # Calculate Safety Stock
        # Statistical safety stock = Z × σ × √(Lead Time)
        safety_stock_statistical = z_score * demand_std * np.sqrt(lead_time_months)

        # Buffer safety stock = Buffer Days × Daily Demand
        buffer_days = self.config['service_level']['lead_time_buffer_days']
        safety_stock_buffer = buffer_days * avg_daily_demand

        total_safety_stock = safety_stock_statistical + safety_stock_buffer

        # Calculate Lead Time Demand
        lead_time_demand = avg_daily_demand * lead_time_days

        # Calculate Reorder Point
        reorder_point = lead_time_demand + total_safety_stock

        details = {
            'avg_monthly_demand': avg_monthly_demand,
            'avg_daily_demand': avg_daily_demand,
            'demand_std': demand_std,
            'lead_time_days': lead_time_days,
            'lead_time_months': lead_time_months,
            'z_score': z_score,
            'service_level': target_fill_rate,
            'safety_stock_statistical': safety_stock_statistical,
            'safety_stock_buffer': safety_stock_buffer,
            'total_safety_stock': total_safety_stock,
            'lead_time_demand': lead_time_demand,
            'reorder_point': reorder_point
        }

        return reorder_point, details

    def calculate_order_up_to_level(
        self,
        reorder_point: float,
        optimal_order_quantity: float
    ) -> float:
        """
        Calculate the Order-Up-To Level (target stock level after ordering).

        Formula: Order-Up-To = Reorder Point + Order Quantity

        Or alternatively: Order-Up-To = (Lead Time Demand + Safety Stock) + EOQ

        Parameters:
        -----------
        reorder_point : float
            Calculated reorder point
        optimal_order_quantity : float
            Constrained EOQ

        Returns:
        --------
        float
            Order-up-to level
        """
        return reorder_point + optimal_order_quantity

    def optimize_inventory_multi_item(
        self,
        df_items: pd.DataFrame,
        df_forecasts: pd.DataFrame,
        df_vendor_lead_times: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Run complete constrained optimization for all items.

        For each item, calculates:
        1. Reorder point (when to order)
        2. Optimal order quantity (how much to order)
        3. Order-up-to level (target stock level)
        4. Space requirements
        5. Cost analysis

        Parameters:
        -----------
        df_items : pd.DataFrame
            Item master with Item No., ItemGroup, UnitCost, etc.
        df_forecasts : pd.DataFrame
            Forecast data with item_code, forecast_month_1-12
        df_vendor_lead_times : pd.DataFrame
            Lead time data

        Returns:
        --------
        pd.DataFrame
            Items with all optimization calculations
        """
        logger.info("Running constrained inventory optimization for all items...")

        results = []

        # Calculate total warehouse space available
        total_capacity = self.config['warehouse']['total_capacity_sqft']
        max_utilization = self.config['warehouse']['max_utilization_pct']
        available_space = total_capacity * max_utilization

        for _, item in df_items.iterrows():
            item_code = item['Item No.']

            # Skip items without forecasts
            item_forecast = df_forecasts[df_forecasts['item_code'] == item_code]
            if len(item_forecast) == 0:
                continue

            # Calculate annual demand from forecast
            forecast_cols = [f'forecast_month_{i}' for i in range(1, 13)]
            forecast_values = item_forecast[forecast_cols].values[0]
            annual_demand = np.nansum(forecast_values)

            if annual_demand <= 0:
                continue

            # Get item details
            unit_cost = pd.to_numeric(item.get('UnitCost', 0), errors='coerce')
            item_group = item.get('ItemGroup', 'default')
            abc_class = item.get('ABC_Class', 'C')  # Assuming ABC classification exists

            # 1. Calculate constrained EOQ
            optimal_order_qty, eoq_details = self.calculate_constrained_eoq(
                item_code=item_code,
                annual_demand=annual_demand,
                unit_cost=unit_cost,
                item_group=item_group,
                abc_classification=abc_class,
                available_warehouse_space=available_space / len(df_items)  # Pro-rata space
            )

            # 2. Calculate reorder point
            reorder_point, rp_details = self.calculate_reorder_point(
                item_code=item_code,
                df_forecasts=df_forecasts,
                df_vendor_lead_times=df_vendor_lead_times,
                df_items=df_items
            )

            # 3. Calculate order-up-to level
            order_up_to_level = self.calculate_order_up_to_level(
                reorder_point,
                optimal_order_qty
            )

            # 4. Calculate current position
            current_stock = pd.to_numeric(item.get('CurrentStock', 0), errors='coerce').fillna(0)
            on_order = pd.to_numeric(item.get('OnOrder', 0), errors='coerce').fillna(0)
            committed = pd.to_numeric(item.get('Committed', 0), errors='coerce').fillna(0)

            current_position = current_stock + on_order - committed

            # 5. Calculate order quantity needed
            order_quantity = max(0, order_up_to_level - current_position)

            # 6. Determine if ordering is needed
            should_order = current_position < reorder_point

            # 7. Calculate space requirements
            space_per_unit = self._get_space_per_unit(item_group)
            space_required = optimal_order_qty * space_per_unit

            # 8. Calculate days until reorder
            daily_demand = rp_details.get('avg_daily_demand', 0)
            if daily_demand > 0:
                days_until_reorder = max(0, (current_position - reorder_point) / daily_demand)
            else:
                days_until_reorder = 999

            # Compile results
            result = {
                'item_code': item_code,
                'Item No.': item.get('Item No.'),
                'Item Description': item.get('Item Description', ''),
                'ItemGroup': item_group,
                'ABC_Class': abc_class,

                # Demand
                'annual_demand': annual_demand,
                'avg_monthly_demand': rp_details.get('avg_monthly_demand', 0),
                'avg_daily_demand': daily_demand,
                'demand_std': rp_details.get('demand_std', 0),

                # Lead Time
                'lead_time_days': rp_details.get('lead_time_days', 0),
                'lead_time_months': rp_details.get('lead_time_months', 0),

                # Reorder Point
                'reorder_point': reorder_point,
                'safety_stock': rp_details.get('total_safety_stock', 0),
                'safety_stock_statistical': rp_details.get('safety_stock_statistical', 0),
                'safety_stock_buffer': rp_details.get('safety_stock_buffer', 0),
                'lead_time_demand': rp_details.get('lead_time_demand', 0),

                # Order Quantity
                'optimal_order_quantity': optimal_order_qty,
                'order_up_to_level': order_up_to_level,
                'current_position': current_position,
                'order_quantity': order_quantity,
                'should_order': should_order,
                'days_until_reorder': days_until_reorder,

                # Warehouse Space
                'space_per_unit_sqft': space_per_unit,
                'space_required_sqft': space_required,

                # Cost Analysis
                'ordering_cost_annual': eoq_details['cost_analysis']['ordering_cost_annual'],
                'transportation_cost_annual': eoq_details['cost_analysis']['transportation_cost_annual'],
                'carrying_cost_annual': eoq_details['cost_analysis']['carrying_cost_annual'],
                'total_annual_cost': eoq_details['cost_analysis']['total_annual_cost'],

                # Current Stock
                'CurrentStock': current_stock,
                'OnOrder': on_order,
                'Committed': committed,
                'UnitCost': unit_cost,
            }

            results.append(result)

        df_results = pd.DataFrame(results)

        logger.info(f"Optimization complete for {len(df_results)} items")
        logger.info(f"  Items requiring orders: {df_results['should_order'].sum()}")

        return df_results


def calculate_warehouse_space_allocation(
    df_items: pd.DataFrame,
    total_capacity_sqft: float,
    max_utilization_pct: float = 0.85,
    abc_space_allocation: dict = None
) -> Dict[str, float]:
    """
    Calculate available warehouse space by ABC classification.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master with ABC_Class and CurrentStock
    total_capacity_sqft : float
        Total warehouse capacity
    max_utilization_pct : float
        Maximum utilization percentage (default 85%)
    abc_space_allocation : dict
        Space allocation by ABC class (default: A=80%, B=15%, C=5%)

    Returns:
    --------
    Dict[str, float]
        Available space per ABC class
    """
    if abc_space_allocation is None:
        abc_space_allocation = {'A': 0.80, 'B': 0.15, 'C': 0.05}

    available_space = total_capacity_sqft * max_utilization_pct

    space_by_class = {}
    for abc_class, allocation_pct in abc_space_allocation.items():
        space_by_class[abc_class] = available_space * allocation_pct

    return space_by_class
