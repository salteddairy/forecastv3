# Constrained Inventory Optimization - Implementation Guide

## Overview

This implementation uses a **modified Economic Order Quantity (EOQ) model with constraints** to calculate optimal reorder points and order quantities based on:

1. **Warehouse Capacity Constraints** - Physical space limitations
2. **Carrying Cost vs Transportation Cost Trade-offs** - Optimal order size
3. **Lead Time Variability** - Safety stock calculations

---

## Core Formulas

### 1. Economic Order Quantity (EOQ)

The classic EOQ formula minimizes total inventory costs:

```
EOQ = √((2 × D × S) / H)
```

Where:
- **D** = Annual demand (units/year)
- **S** = Ordering cost per order ($/order)
- **H** = Holding cost per unit per year ($/unit/year)

**Holding Cost (H)** = Unit Cost × Carrying Cost %

**Carrying Cost %** = Cost of Capital + Storage + Service + Risk

Example:
- Unit Cost = $10
- Annual Demand = 1,000 units
- Ordering Cost = $50 per order
- Carrying Cost = 25% annually

```
H = $10 × 0.25 = $2.50 per unit per year
EOQ = √((2 × 1000 × 50) / 2.50) = √(40,000) = 200 units
```

---

### 2. Constrained EOQ

The basic EOQ is then adjusted for real-world constraints:

#### Constraint A: Warehouse Capacity
```
Max Quantity (Space) = Available Warehouse Space / Space per Unit
EOQ(space constrained) = min(EOQ, Max Quantity)
```

#### Constraint B: Maximum Order Cycle
```
Max Quantity (Time) = Monthly Demand × Max Order Cycle (months)
EOQ(cycle constrained) = min(EOQ(space constrained), Max Quantity)
```

#### Constraint C: Transportation Cost Optimization
The algorithm tests order quantities around transportation breakpoints (FTL vs LTL) to find the true optimal quantity considering both carrying and transportation costs.

**Test Candidates:**
1. Base EOQ
2. 90% of FTL threshold (just below full truckload)
3. FTL threshold (exactly at breakpoint)
4. 110% of FTL threshold (just above full truckload)

Select the quantity with the **lowest total annual cost** (ordering + transportation + carrying).

---

### 3. Reorder Point Calculation

```
Reorder Point = Lead Time Demand + Safety Stock
```

#### Lead Time Demand
```
Lead Time Demand = Average Daily Demand × Lead Time Days
```

#### Safety Stock
```
Safety Stock = (Z × σ × √(LT)) + (Buffer Days × Daily Demand)
```

Where:
- **Z** = Z-score for service level (1.65 for 95%, 2.33 for 99%)
- **σ** = Demand standard deviation (volatility)
- **LT** = Lead time in months
- **Buffer Days** = Extra safety buffer (default 7 days)

---

### 4. Order-Up-To Level

```
Order-Up-To Level = Reorder Point + Optimal Order Quantity
```

This is the target stock level after placing an order.

---

### 5. Order Quantity to Place

```
Order Quantity = max(0, Order-Up-To - Current Position)
```

Where:
```
Current Position = Current Stock + On Order - Committed
```

---

## How the Algorithm Works

### Step 1: Calculate Unconstrained EOQ
```
EOQ = √((2 × Annual Demand × Ordering Cost) / Holding Cost)
```
This is the theoretical optimal quantity from a pure cost perspective.

### Step 2: Apply Warehouse Space Constraint
```
Max by Space = Available Space / Space per Unit
EOQ₁ = min(EOQ, Max by Space)
```
Don't order more than you can store.

### Step 3: Apply Maximum Order Cycle Constraint
```
Max by Cycle = Monthly Demand × Max Order Cycle (e.g., 6 months)
EOQ₂ = min(EOQ₁, Max by Cycle)
```
Don't order more than X months of supply.

### Step 4: Optimize for Transportation Cost
Test multiple order quantities around the FTL threshold. Calculate total annual cost for each candidate:

```
Total Annual Cost = Ordering Cost + Transportation Cost + Carrying Cost

Where:
- Ordering Cost = (Annual Demand / Order Quantity) × Fixed Cost per Order
- Transportation Cost = (Annual Demand / Order Quantity) × Freight Cost per Order
- Carrying Cost = (Order Quantity / 2) × Holding Cost per Unit per Year
```

Select the quantity with minimum total cost.

### Step 5: Calculate Reorder Point
```
Reorder Point = Lead Time Demand + Safety Stock
```

### Step 6: Calculate Order-Up-To Level
```
Order-Up-To = Reorder Point + Optimal Order Quantity
```

### Step 7: Determine Order Quantity
```
If Current Position < Reorder Point:
    Order Quantity = Order-Up-To - Current Position
Else:
    Order Quantity = 0 (Don't order)
```

---

## Configuration Parameters

### Carrying Cost Components

| Component | Default | Description |
|-----------|---------|-------------|
| Cost of Capital | 8% | Interest rate, opportunity cost |
| Storage | 10% | Warehousing, rent, utilities |
| Service | 2% | Insurance, taxes |
| Risk | 5% | Obsolescence, spoilage, damage |
| **Total** | **25%** | **Annual carrying cost** |

**Adjustments:**
- High-value items → Increase cost of capital
- Perishable goods → Increase risk %
- Climate-controlled storage → Increase storage %

---

### Transportation Costs

| Parameter | Default | Description |
|-----------|---------|-------------|
| Ordering Cost | $50 | Fixed cost per order (admin, receiving) |
| FTL Minimum | 500 units | Full truckload threshold |
| FTL Cost | $1,500 | Flat rate for full truckload |
| LTL Cost | $2.50/unit | Per-unit rate for LTL |
| LTL Fixed | $150 | LTL fixed charge |

**Transportation Cost Calculation:**
```
If Order Qty ≥ FTL Minimum:
    Freight Cost = FTL Fixed Cost
Else:
    Freight Cost = (Order Qty × LTL per-unit) + LTL Fixed Cost
```

**Volume Discounts:**
Apply to merchandise value (not freight):
- 100+ units: 5% discount
- 500+ units: 10% discount
- 1,000+ units: 15% discount

---

### Warehouse Capacity

| Parameter | Default | Description |
|-----------|---------|-------------|
| Total Capacity | 50,000 sq ft | Total warehouse space |
| Max Utilization | 85% | Keep 15% free for operations |
| Space per Unit | Varies | By item group (see config) |

**Space Requirements (per unit):**
- Default: 1.0 sq ft
- FG-RE (Refrigerated): 0.5 sq ft
- FG-FZ (Frozen): 0.3 sq ft
- RM-BULK (Bulk): 2.0 sq ft
- SMALL: 0.2 sq ft
- LARGE: 3.0 sq ft

**ABC Space Allocation:**
- Class A (high turnover): 80% of space
- Class B (medium turnover): 15% of space
- Class C (low turnover): 5% of space

---

### Service Level

| Parameter | Default | Description |
|-----------|---------|-------------|
| Target Fill Rate | 95% | Probability of not stocking out |
| Z-Score | 1.65 | Corresponds to 95% service level |
| Buffer Days | 7 days | Extra safety stock |

**Service Level Options:**
- 95% (Z=1.65) - Standard
- 99% (Z=2.33) - Critical items
- 90% (Z=1.28) - Non-critical items

---

### Constraints

| Parameter | Default | Description |
|-----------|---------|-------------|
| Max Order Cycle | 6 months | Don't order >6 months supply |
| Min Order Value | $100 | Minimum order value |
| Min Order Qty | 1 unit | Minimum units to order |

---

## Example Calculation

### Input Data
```
Item: Product A
Unit Cost: $10
Annual Demand: 1,200 units (100/month)
Daily Demand: 4 units
Demand Std Dev: 15 units
Lead Time: 21 days
Item Group: FG-RE
ABC Class: A
```

### Step 1: Calculate Unconstrained EOQ
```
Holding Cost per Unit = $10 × 0.25 = $2.50/year
EOQ = √((2 × 1200 × 50) / 2.50) = √(48,000) = 219 units
```

### Step 2: Apply Warehouse Constraint
```
Available Space = 50,000 sq ft × 85% × 80% (Class A) / 1000 items = 34 sq ft per item
Space per Unit = 0.5 sq ft (FG-RE)
Max by Space = 34 / 0.5 = 68 units
EOQ₁ = min(219, 68) = 68 units
```

### Step 3: Apply Max Order Cycle
```
Max by Cycle = 100 units/month × 6 months = 600 units
EOQ₂ = min(68, 600) = 68 units (space constrained)
```

### Step 4: Transportation Optimization
Test candidates: 68, 450 (90% FTL), 500 (FTL), 550 (110% FTL)

Calculate total annual cost for each (example for 68 units):
```
Orders per Year = 1200 / 68 = 17.6 orders
Ordering Cost = 17.6 × $50 = $880
Freight Cost = 17.6 × [(68 × $2.50) + $150] = 17.6 × $320 = $5,632
Carrying Cost = (68 / 2) × $2.50 = $85
Total Cost = $880 + $5,632 + $85 = $6,597
```

After testing all candidates, assume 500 units (FTL) is optimal due to lower freight costs.

```
Optimal Order Quantity = 500 units
```

### Step 5: Calculate Reorder Point
```
Lead Time Demand = 4 units/day × 21 days = 84 units

Safety Stock:
  Statistical = 1.65 × 15 × √(21/30) = 1.65 × 15 × 0.84 = 20.8 units
  Buffer = 7 days × 4 units/day = 28 units
  Total Safety Stock = 20.8 + 28 = 48.8 units

Reorder Point = 84 + 48.8 = 132.8 ≈ 133 units
```

### Step 6: Order-Up-To Level
```
Order-Up-To = 133 + 500 = 633 units
```

### Step 7: Determine Order Quantity
```
Current Position = Current Stock (100) + On Order (0) - Committed (20) = 80 units

Should Order? 80 < 133 → YES

Order Quantity = 633 - 80 = 553 units
```

---

## Integration with Shortage Report

### Current Shortage Logic (Problematic)
```python
shortage_qty = sum(forecast_month_1 through forecast_month_12) - total_available
```
**Problem:** Compares current stock against entire 12-month forecast → Overestimates shortages.

### New Shortage Logic (Recommended)
```python
# Using reorder point as threshold
will_have_shortage = current_position < reorder_point
shortage_qty = order_up_to_level - current_position
```
**Benefits:**
- Only shows shortage if below reorder point
- Considers lead time and safety stock
- Accounts for warehouse capacity
- Optimizes for transportation costs

---

## Implementation Steps

### 1. Install Required Dependencies
```bash
pip install scipy pyyaml
```

### 2. Configure Parameters
Edit `config_inventory_optimization.yaml`:
- Set warehouse capacity (sq ft)
- Update transportation costs
- Adjust carrying cost percentages
- Set service level target

### 3. Run Optimization
```python
from src.inventory_optimization import InventoryOptimizer
from src.data_pipeline import ForecastDataPipeline

# Load data
pipeline = ForecastDataPipeline()
df_items = pipeline.load_data('items')
df_forecasts = pipeline.load_data('forecasts')
df_vendor_lead_times = pipeline.load_data('vendor_lead_times')

# Initialize optimizer
optimizer = InventoryOptimizer(config_path='config_inventory_optimization.yaml')

# Run optimization
df_optimized = optimizer.optimize_inventory_multi_item(
    df_items,
    df_forecasts,
    df_vendor_lead_times
)

# Save results
df_optimized.to_parquet('data/cache/optimized_orders.parquet')
```

### 4. Update Shortage Report
Replace current shortage logic with reorder-point-based detection.

---

## Column Descriptions

| Column | Description |
|--------|-------------|
| `reorder_point` | When to place an order (units) |
| `optimal_order_quantity` | How much to order (EOQ constrained) |
| `order_up_to_level` | Target stock level after ordering |
| `current_position` | Current stock + On Order - Committed |
| `order_quantity` | Actual quantity to order now |
| `should_order` | Boolean: is ordering needed? |
| `days_until_reorder` | Days until hitting reorder point |
| `safety_stock` | Statistical + buffer safety stock |
| `lead_time_demand` | Demand during lead time period |
| `space_required_sqft` | Warehouse space needed for order |
| `ordering_cost_annual` | Annual ordering cost ($/year) |
| `transportation_cost_annual` | Annual freight cost ($/year) |
| `carrying_cost_annual` | Annual holding cost ($/year) |
| `total_annual_cost` | Sum of all costs ($/year) |

---

## Key Benefits

### 1. **Warehouse Capacity Awareness**
- Prevents over-ordering beyond space constraints
- Allocates space by ABC classification priority
- Maintains 15% buffer for operations

### 2. **Transportation Cost Optimization**
- Balances carrying cost vs freight cost
- Identifies FTL vs LTL breakpoints
- Accounts for volume discounts

### 3. **Accurate Reorder Points**
- Uses lead time demand + safety stock
- Accounts for demand variability
- Configurable service levels

### 4. **Cost Visibility**
- Breakdown of ordering, transportation, carrying costs
- Identify cost drivers by item
- Optimize order quantities for minimum total cost

### 5. **Practical Constraints**
- Maximum order cycle (don't order 1 year at once)
- Minimum order value thresholds
- Rounding to practical units

---

## FAQ

### Q: How do I adjust for perishable items?
**A:** Lower the `max_order_quantity_months` constraint (e.g., 1-2 months) and increase the `risk_percent` in carrying cost.

### Q: How do I prioritize space for high-turnover items?
**A:** Adjust `abc_space_allocation` to give Class A items more space (e.g., A=90%, B=8%, C=2%).

### Q: What if I don't know my carrying cost percentage?
**A:** Start with 25% (industry average). Adjust based on:
- High-value items → 30-35%
- Low-value/bulky items → 15-20%
- Perishables → 30-40%

### Q: How do I handle supplier minimum order quantities (MOQ)?
**A:** Add supplier MOQ as a constraint in Step 5:
```python
order_quantity = max(
    calculated_order_quantity,
    supplier_moq
)
```

### Q: Should I use this for all items?
**A:**
- **Use for:** A and B items (high/medium turnover), significant carrying costs
- **Consider for:** C items if they have high transportation costs
- **Don't use for:** Intermittent/special-order-only items (use TCO analysis instead)

---

## Next Steps

1. **Review and customize** `config_inventory_optimization.yaml` for your business
2. **Test on subset** of items first (e.g., Class A only)
3. **Validate results** - compare recommended order quantities to historical orders
4. **Tune parameters** - adjust carrying costs, transportation costs until realistic
5. **Roll out** to all items once validated
6. **Monitor** - track actual costs vs predicted costs, adjust quarterly

---

## References

- **EOQ Model:** https://en.wikipedia.org/wiki/Economic_order_quantity
- **Safety Stock:** https://www.inventoryops.com/safety_stock.htm
- **Warehouse Optimization:** https://www logisticsmgmt.com/dc-management/warehouse-capacity-planning

---

## Support

For questions or issues, refer to:
- Main documentation: `README.md`
- Automated ordering: `src/automated_ordering.py`
- Shortage report: `app.py` (Shortage Report tab)
