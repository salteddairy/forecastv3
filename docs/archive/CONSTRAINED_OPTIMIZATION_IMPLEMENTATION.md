# Constrained Inventory Optimization - Implementation Summary

## What Was Implemented

A **hybrid approach to shortage calculation** using **constrained Economic Order Quantity (EOQ) optimization** that considers:

1. **Warehouse Capacity Constraints** - Physical space limitations
2. **Carrying Cost vs Transportation Cost** - Optimal trade-off
3. **Lead Time Variability** - Safety stock calculations

---

## New Files Created

### 1. `src/inventory_optimization.py`
**Core optimization engine** with the `InventoryOptimizer` class.

**Key Features:**
- Calculates constrained EOQ considering warehouse space, transportation costs, and order cycles
- Determines optimal reorder points based on lead time demand and safety stock
- Provides cost breakdown (ordering, transportation, carrying)
- Configurable via YAML file or Python dict

**Key Methods:**
- `calculate_constrained_eoq()` - Optimal order quantity with constraints
- `calculate_reorder_point()` - When to place an order
- `optimize_inventory_multi_item()` - Batch optimization for all items

### 2. `config_inventory_optimization.yaml`
**Configuration template** for the optimizer.

**Key Parameters:**
```yaml
carrying_cost:
  total_carrying_cost_percent: 0.25  # 25% annually

transportation:
  ordering_cost_per_order: 50.0
  ftl_minimum_units: 500
  ftl_fixed_cost: 1500.0
  ltl_cost_per_unit: 2.50
  ltl_fixed_cost: 150.0

warehouse:
  total_capacity_sqft: 50000
  max_utilization_pct: 0.85  # Use 85% max

service_level:
  target_fill_rate: 0.95  # 95% service level
  lead_time_buffer_days: 7

constraints:
  max_order_quantity_months: 6
  min_order_value: 100.0
```

### 3. `INVENTORY_OPTIMIZATION_GUIDE.md`
**Comprehensive documentation** including:
- Formulas and calculations
- Step-by-step algorithm
- Example calculations
- Configuration guide
- FAQ

---

## Modified Files

### 1. `src/optimization.py`
**Added:** `calculate_constrained_stockout_predictions()` function

**New Function:**
```python
def calculate_constrained_stockout_predictions(
    df_items: pd.DataFrame,
    df_forecasts: pd.DataFrame,
    df_vendor_lead_times: pd.DataFrame,
    config_path: str = None,
    config: dict = None
) -> pd.DataFrame
```

This function:
1. Initializes the `InventoryOptimizer`
2. Runs constrained optimization for all items
3. Calculates reorder points and order quantities
4. Determines shortage status based on **reorder point** (not 12-month forecast)
5. Returns enriched dataframe with optimization columns

### 2. `app.py`
**Updated:** Shortage Report tab with optimization method selection

**New UI Elements:**
- **Optimization Settings expander** - Choose between Standard and Constrained EOQ
- **Radio button** - Toggle between methods
- **Info messages** - Shows which method is active

**New Columns (when using Constrained EOQ):**
- `Reorder Point` - When to place an order
- `Optimal Order Qty` - EOQ with constraints
- `Current Position` - Current Stock + On Order - Committed
- `Order Qty Needed` - Actual quantity to order
- `Days Until Reorder` - When will we hit the reorder point

**New Summary Section:**
- Items to Order count
- Total Order Quantity
- Space Required (sq ft)
- Estimated Annual Cost
- Average Lead Time
- Annual Cost Breakdown chart

---

## How to Use

### Method 1: Via Streamlit App (Interactive)

1. **Start the app:**
   ```bash
   streamlit run app.py
   ```

2. **Navigate to "📦 Shortage Report" tab**

3. **Open "⚙️ Optimization Settings" expander**

4. **Select "Constrained EOQ"**

5. **Review the results:**
   - Shortage report now shows **reorder point-based shortages**
   - Additional columns: Reorder Point, Optimal Order Qty, Current Position
   - Summary metrics: Space required, annual cost breakdown

### Method 2: Via Python Script (Batch)

```python
from src.inventory_optimization import InventoryOptimizer
from src.data_pipeline import ForecastDataPipeline

# Load data
pipeline = ForecastDataPipeline()
df_items = pipeline.raw_data.get('items')
df_forecasts = pipeline.forecasts

# Prepare vendor lead times
df_vendor_lead_times = df_forecasts[['item_code', 'lead_time_days']].copy()
df_vendor_lead_times['vendor_code'] = 'DEFAULT'

# Initialize optimizer with config
optimizer = InventoryOptimizer(config_path='config_inventory_optimization.yaml')

# Run optimization
df_optimized = optimizer.optimize_inventory_multi_item(
    df_items=df_items,
    df_forecasts=df_forecasts,
    df_vendor_lead_times=df_vendor_lead_times
)

# Review results
print(df_optimized[['Item No.', 'reorder_point', 'optimal_order_quantity', 'order_quantity', 'should_order']])

# Export
df_optimized.to_parquet('data/cache/constrained_optimization_results.parquet')
```

---

## Configuration

### Step 1: Customize `config_inventory_optimization.yaml`

Edit the values based on your business:

#### Carrying Cost
```yaml
carrying_cost:
  cost_of_capital_percent: 0.08   # Adjust based on your interest rate
  storage_percent: 0.10            # Adjust based on warehousing costs
  service_percent: 0.02            # Insurance, taxes
  risk_percent: 0.05               # Obsolescence, spoilage
```

#### Transportation
```yaml
transportation:
  ordering_cost_per_order: 50.0    # Admin, receiving cost
  ftl_minimum_units: 500           # Your truckload threshold
  ftl_fixed_cost: 1500.0           # Your carrier's FTL rate
  ltl_cost_per_unit: 2.50          # Your LTL per-unit rate
```

#### Warehouse
```yaml
warehouse:
  total_capacity_sqft: 50000       # Your warehouse size
  max_utilization_pct: 0.85        # Keep 15% free
  space_per_unit_sqft:
    default: 1.0
    FG-RE: 0.5                     # Adjust based on your products
    RM-BULK: 2.0
```

### Step 2: Validate Configuration

Test with a small subset first:

```python
# Test on Class A items only
df_items_a = df_items[df_items['ABC_Class'] == 'A']

df_test = optimizer.optimize_inventory_multi_item(
    df_items=df_items_a,
    df_forecasts=df_forecasts,
    df_vendor_lead_times=df_vendor_lead_times
)

# Compare to historical orders
print("Recommended Order Quantities:")
print(df_test[['Item No.', 'optimal_order_quantity', 'order_quantity']])
```

### Step 3: Roll Out to All Items

Once validated, run for all items and integrate into purchasing workflow.

---

## Key Differences: Standard vs Constrained EOQ

| Aspect | Standard (12-month) | Constrained EOQ |
|--------|---------------------|-----------------|
| **Shortage Threshold** | 12-month forecast total | Reorder point (lead time + safety stock) |
| **Order Quantity** | N/A (just shows shortage) | Optimal order quantity (EOQ) |
| **Warehouse Space** | Not considered | Constrained by capacity |
| **Transportation Costs** | Not considered | Optimizes FTL vs LTL |
| **Carrying Costs** | Not considered | Minimizes holding cost |
| **Lead Time** | Only for urgency | Used for reorder point calculation |
| **Shortage Definition** | Will run out in 12 months | Below reorder point (order now) |

### Example Comparison

**Item:** Product A
- Current Stock: 80 units
- On Order: 0
- Committed: 20
- Current Position: 60 units
- Monthly Demand: 10 units
- Lead Time: 21 days

**Standard Method:**
- 12-month forecast: 120 units
- Shortage = 120 - 60 = 60 units
- **Result:** Shows 60 unit shortage

**Constrained EOQ Method:**
- Reorder Point: 35 units (lead time demand + safety stock)
- Current Position: 60 units
- Is 60 < 35? No
- **Result:** No shortage (don't order yet)

**Key Insight:** Standard overestimates shortages. Constrained is more actionable.

---

## Output Columns

### When Using Standard Method
```
Item Code | Item Description | Current Stock | Incoming Stock | Total Available | Shortage Qty | Days Until Stockout | Urgency
```

### When Using Constrained EOQ Method
```
Item Code | Item Description | Reorder Point | Optimal Order Qty | Current Position | Order Qty Needed | Days Until Reorder | Urgency
```

**Additional Columns Available (for export):**
- `reorder_point` - When to order
- `optimal_order_quantity` - EOQ with constraints
- `order_up_to_level` - Target stock level
- `safety_stock` - Safety stock buffer
- `lead_time_demand` - Demand during lead time
- `space_required_sqft` - Warehouse space for order
- `ordering_cost_annual` - Annual ordering cost ($)
- `transportation_cost_annual` - Annual freight cost ($)
- `carrying_cost_annual` - Annual holding cost ($)
- `total_annual_cost` - Sum of all costs ($)

---

## Cost Analysis

### Components of Total Annual Cost

1. **Ordering Cost**
   ```
   Ordering Cost = (Annual Demand / Order Quantity) × Fixed Cost per Order
   ```
   - Admin time
   - Receiving costs
   - Inspection costs

2. **Transportation Cost**
   ```
   Transportation Cost = (Annual Demand / Order Quantity) × Freight Cost per Order
   ```
   - FTL: Flat rate ($1,500 per truckload)
   - LTL: Per-unit rate ($2.50/unit) + fixed charge ($150)
   - Volume discounts applied

3. **Carrying Cost**
   ```
   Carrying Cost = (Order Quantity / 2) × Holding Cost per Unit per Year
   ```
   - Cost of capital (8%)
   - Storage (10%)
   - Service (2%)
   - Risk (5%)

### Optimization Goal

**Minimize Total Annual Cost:**
```
Total Cost = Ordering + Transportation + Carrying
```

The algorithm finds the order quantity that minimizes this total while respecting:
- Warehouse space constraints
- Maximum order cycle (don't order too far ahead)
- Minimum order value thresholds

---

## Troubleshooting

### Issue: "No optimization results generated"

**Cause:** Empty or missing forecast data

**Solution:**
1. Verify forecasts have been generated
2. Check that forecast columns exist (`forecast_month_1` through `forecast_month_12`)
3. Ensure `item_code` column matches between forecasts and items

### Issue: ImportError for scipy or yaml

**Solution:**
```bash
pip install scipy pyyaml
```

### Issue: "Warehouse capacity exceeded"

**Cause:** Order quantities exceed available space

**Solution:**
1. Increase `warehouse.total_capacity_sqft` in config
2. Increase `warehouse.max_utilization_pct` (max 0.95)
3. Decrease `constraints.max_order_quantity_months` to reduce order sizes
4. Adjust `abc_space_allocation` to give more space to high-turn items

### Issue: "Order quantities seem too high"

**Cause:** EOQ may be recommending large orders to minimize ordering costs

**Solution:**
1. Decrease `max_order_quantity_months` (try 3 instead of 6)
2. Increase `ordering_cost_per_order` (if true cost is higher)
3. Increase `carrying_cost.total_carrying_cost_percent` (if holding cost is higher)

### Issue: "Order quantities seem too low"

**Cause:** High carrying costs or low ordering costs

**Solution:**
1. Increase `max_order_quantity_months` (try 9 or 12)
2. Decrease `ordering_cost_per_order`
3. Decrease `carrying_cost.total_carrying_cost_percent`

---

## Next Steps

1. **Review Configuration**
   - Edit `config_inventory_optimization.yaml` with your actual costs and constraints

2. **Test on Subset**
   - Run optimization on Class A items only
   - Compare recommended order quantities to historical orders
   - Adjust config if needed

3. **Run Full Optimization**
   - Execute for all items
   - Review summary metrics
   - Validate space requirements

4. **Integrate into Workflow**
   - Use reorder points to trigger purchase orders
   - Export optimized order quantities by vendor
   - Upload to SAP as purchase orders

5. **Monitor and Tune**
   - Track actual costs vs predicted costs
   - Adjust config parameters quarterly
   - Refine based on actual warehouse utilization

---

## References

- **Theory:** Economic Order Quantity (EOQ) Model
- **Safety Stock:** Service level and Z-score calculations
- **Transportation:** FTL vs LTL cost optimization
- **Constraints:** Warehouse capacity and order cycle limits

For detailed formulas and examples, see `INVENTORY_OPTIMIZATION_GUIDE.md`.

---

## Support

For issues or questions:
1. Check `INVENTORY_OPTIMIZATION_GUIDE.md` for detailed documentation
2. Review example calculations in the guide
3. Validate configuration parameters
4. Test with small subset before full rollout
