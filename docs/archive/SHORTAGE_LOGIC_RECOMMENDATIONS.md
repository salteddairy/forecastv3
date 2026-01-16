# Shortage Report Logic Analysis & Recommendations

## Current Logic (PROBLEMATIC)

### Formula Used:
```python
total_available = CurrentStock + IncomingStock
forecast_period_demand = sum(forecast_month_1 through forecast_month_12)

will_stockout = total_available < forecast_period_demand
shortage_qty = forecast_period_demand - total_available
days_until_stockout = (total_available / avg_monthly_demand) * 30
```

### Problems:

1. **Overestimates Shortages**
   - Compares current stock against **entire 12-month forecast**
   - Example: You need 100 units for the year, you have 80 → Shortage = 20
   - But you only need 100 over 12 months, not 100 today!
   - You can order multiple times throughout the year

2. **Ignores Lead Time**
   - Doesn't consider when the item will actually run out
   - Doesn't account for supplier lead time
   - May show shortages for items that won't run out for months

3. **Ignores Reorder Cycles**
   - Assumes you order once per year
   - In reality, you order monthly/quarterly
   - Should use "Reorder Point" logic instead

4. **Static Month Names**
   - Shows "Month 1", "Month 2", etc.
   - Should show actual month names (January, February, etc.)

---

## Recommended Logic (INDUSTRY STANDARD)

### Option A: Lead Time Based Shortage (Recommended)

**Trigger:** Will we run out before we can get more stock?

```python
# When will we run out?
current_position = CurrentStock + OnOrder - Committed
burn_rate = avg_monthly_demand / 30  # daily demand
days_of_stock = current_position / burn_rate

# Can we get more in time?
will_stockout_before_replenishment = days_of_stock < lead_time_days

# If yes, calculate shortage
shortage_qty = (lead_time_demand + safety_stock) - current_position
```

**Benefits:**
- Only shows shortages if you can't reorder in time
- Accounts for lead time
- Uses safety stock buffer
- Industry standard approach

---

### Option B: Reorder Point Based (Best Practice)

**Trigger:** Are we below the reorder point?

```python
# When should we order?
lead_time_demand = avg_monthly_demand * (lead_time_days / 30)
safety_stock = Z_score * demand_std * sqrt(lead_time_months) + buffer
reorder_point = lead_time_demand + safety_stock

# Should we order now?
should_order = current_position < reorder_point

# How much are we short (if ordering now)?
shortage_qty = order_up_to_level - current_position
```

**Benefits:**
- Proactive ordering (order before you run out)
- Incorporates demand variability
- Statistical safety stock
- Works well with automated ordering

---

### Option C: Month-by-Month Shortage (Detailed)

**Trigger:** Which specific months will have shortages?

```python
# Check each month cumulatively
cumulative_stock = current_position
cumulative_demand = 0
shortage_by_month = []

for month in 1..12:
    monthly_demand = forecast_month_X
    cumulative_demand += monthly_demand
    cumulative_stock -= monthly_demand

    if cumulative_stock < 0:
        shortage_qty = abs(cumulative_stock)
        shortage_by_month.append({
            'month': month_X,
            'shortage_qty': shortage_qty,
            'will_stockout': True
        })
```

**Benefits:**
- Shows exactly which months are affected
- More granular visibility
- Helps with planning

---

## Recommended Changes

### 1. **Hybrid Approach** (Best for Your Needs)

Combine the best of all approaches:

```python
# Primary Logic: Reorder Point (for proactive ordering)
should_order = current_position < reorder_point

# Secondary Logic: Lead Time Shortage (for immediate concerns)
will_stockout_soon = days_of_stock < lead_time_days

# Tertiary Logic: Month-by-Month (for planning)
# Shows which months are affected
```

### 2. **Column Display Changes**

| Column | Current | Recommended |
|--------|---------|-------------|
| Month 1 | "Month 1" | Dynamic: "January 2025" |
| Month 2 | "Month 2" | Dynamic: "February 2025" |
| Month 3 | "Month 3" | Dynamic: "March 2025" |
| Month 4 | "Month 4" | Dynamic: "April 2025" |
| Item Description | Missing | **Add this column** |

### 3. **New Columns to Add**

- **Lead Time (Days)** - Supplier lead time
- **Days Until Reorder** - When will we hit the reorder point
- **Reorder Point** - When should we order
- **Order Urgency** - How urgent is the order
- **Stock Status** - Current position classification

---

## Implementation Priority

### Phase 1: Quick Fixes (Current Session)
1. ✅ Add Item Description column
2. ✅ Add Lead Time column
3. ✅ Show actual month names (January, February, etc.)

### Phase 2: Logic Improvement
4. Implement better shortage calculation (Reorder Point based)
5. Add "Days Until Reorder" instead of "Days Until Stockout"
6. Use lead time in shortage determination

### Phase 3: Advanced Features
7. Month-by-month shortage breakdown
8. Configurable shortage logic (user can choose approach)
9. Integration with automated ordering

---

## Configuration Options

Add these settings to allow customization:

```python
shortage_config = {
    'method': 'reorder_point',  # or 'lead_time', or 'month_by_month'
    'lead_time_buffer_days': 7,  # Extra buffer before lead time
    'safety_stock_z_score': 1.65,  # 95% service level
    'show_months': 4,  # Number of forecast months to display
    'include_on_order_in_available': True,  # Count POs as available
    'include_committed_as_reserved': True,  # Count SOs as reserved
}
```

---

## Visual Example

### Current Display:
```
Item Code | Item Desc | Lead Time | Current | Month 1 | Month 2 | Month 3 | Month 4 | Shortage
----------|-----------|-----------|---------|---------|---------|---------|---------|---------
ABC001    | Product A | 21 days   | 100     | 10      | 10      | 10      | 10      | 50
```
Problem: Shows 50 shortage but that's for the full year, not immediate

### Recommended Display:
```
Item Code | Item Desc | Lead Time | Reorder Pt | Current | Days Until Reorder | Jan 2025 | Feb 2025 | Mar 2025 | Apr 2025 | Order Qty | Urgency
----------|-----------|-----------|------------|---------|-------------------|----------|----------|----------|----------|----------|--------
ABC001    | Product A | 21 days   | 25        | 100     | 225               | 10       | 10       | 10       | 10       | 0        | OK
ABC002    | Product B | 45 days   | 65        | 30      | 12                | 15       | 15       | 15       | 15       | 40       | HIGH
```
Benefits: Shows when to order, how much, urgency based on lead time

---

Let me know which approach you prefer and I'll implement it!
