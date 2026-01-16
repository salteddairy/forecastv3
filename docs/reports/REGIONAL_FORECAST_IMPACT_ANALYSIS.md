# Regional Forecasting Accuracy After Item Master Consolidation

**Date:** 2026-01-16
**Status:** ⚠️ **CRITICAL ISSUE FOUND**
**Impact:** HIGH - Forecasting will lose regional granularity after consolidation

---

## Executive Summary

**Answer: NO** - Forecasting will **NOT** be regionally accurate after item master changeover without code changes.

**The Problem:**
- Current forecasting aggregates by `item_code` only
- After consolidation, BX010155-EDM + BX010155-CGY → BX010155 (single item code)
- All regional demand will be **mixed into one forecast**
- Edmonton and Calgary demand will be combined, losing regional accuracy

**Impact Severity:** HIGH - Will cause incorrect purchase recommendations per region

---

## Current State (What Works Now)

### Data Structure
```
Item Code         | Warehouse | Demand (monthly)
------------------|-----------|-----------------
BX010155-EDM      | 40        | 10 units (Edmonton only)
BX010155-CGY      | 30        | 5 units (Calgary only)
```

### Forecasting Behavior
```python
# From src/forecasting.py:67-100
def prepare_monthly_data(df_sales: pd.DataFrame, item_code: str) -> pd.Series:
    # Filter for specific item
    item_data = df_sales[df_sales['item_code'] == item_code].copy()

    # Aggregate by month
    item_data['year_month'] = item_data['date'].dt.to_period('M')
    monthly_demand = item_data.groupby('year_month')['qty'].sum()
```

**Result:**
- BX010155-EDM → forecast based on Edmonton demand only ✅
- BX010155-CGY → forecast based on Calgary demand only ✅
- Regional accuracy maintained ✅

---

## Future State (After Consolidation)

### Data Structure
```
Item Code    | Warehouse   | Demand (monthly)
-------------|-------------|-----------------
BX010155     | 040-EDM1    | 10 units (Edmonton)
BX010155     | 030-CGY1    | 5 units (Calgary)
```

### Current Forecasting Behavior (BROKEN)
```python
# Same function - still filters by item_code only
item_data = df_sales[df_sales['item_code'] == 'BX010155'].copy()

# Aggregates BOTH warehouses together:
# 10 + 5 = 15 units (mixed Edmonton + Calgary)
monthly_demand = item_data.groupby('year_month')['qty'].sum()
```

**Result:**
- BX010155 → forecast based on 15 units (Edmonton + Calgary combined)
- **Cannot determine** how much to stock in Edmonton vs Calgary ❌
- Purchase recommendations will be wrong ❌

---

## The Fix: Warehouse-Aware Forecasting

### Required Code Changes

**Option 1: Forecast by Item + Warehouse (Recommended)**

Modify `prepare_monthly_data()` to accept warehouse parameter:

```python
def prepare_monthly_data(df_sales: pd.DataFrame, item_code: str,
                        warehouse: str = None) -> pd.Series:
    """
    Prepare monthly time series data for a specific item/warehouse combination.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe
    item_code : str
        Item code to prepare data for
    warehouse : str, optional
        Warehouse code. If provided, filter by warehouse.
        If None, aggregates all warehouses (current behavior).
    """
    # Filter for specific item
    item_data = df_sales[df_sales['item_code'] == item_code].copy()

    # NEW: Filter by warehouse if specified
    if warehouse is not None:
        item_data = item_data[item_data['warehouse'] == warehouse]

    # Aggregate by month
    item_data['year_month'] = item_data['date'].dt.to_period('M')
    monthly_demand = item_data.groupby('year_month')['qty'].sum()

    return monthly_demand
```

**Option 2: Forecast by Item + Region (Alternative)**

Use region instead of warehouse code:

```python
def prepare_monthly_data_by_region(df_sales: pd.DataFrame, item_code: str,
                                   region: str = None) -> pd.Series:
    """Prepare monthly data filtered by region."""
    # Filter for specific item
    item_data = df_sales[df_sales['item_code'] == item_code].copy()

    # Filter by region if specified
    if region is not None:
        item_data = item_data[item_data['region'] == region]

    # Aggregate by month
    item_data['year_month'] = item_data['date'].dt.to_period('M')
    monthly_demand = item_data.groupby('year_month')['qty'].sum()

    return monthly_demand
```

---

## Implementation Strategy

### Phase 1: Add Warehouse to Sales Data (CRITICAL)

**File:** `src/ingestion.py`

```python
def load_sales(filepath: Path) -> pd.DataFrame:
    """Load sales orders with warehouse information."""
    df = pd.read_csv(filepath, sep='\t')

    # Add warehouse column from item code suffix (current state)
    df['warehouse'] = df['item_code'].apply(extract_warehouse_from_item_code)

    # Add region column for easier filtering
    df['region'] = df['item_code'].apply(parse_region)

    return df
```

### Phase 2: Update Forecasting Functions

**File:** `src/forecasting.py`

**Changes needed:**
1. Update `prepare_monthly_data()` to accept `warehouse` parameter
2. Update `_process_single_item()` to pass warehouse
3. Update `forecast_items()` to generate item+warehouse combinations

```python
def forecast_items_by_warehouse(df_sales: pd.DataFrame,
                                item_codes: List[str] = None,
                                n_samples: int = None,
                                n_jobs: int = -1) -> pd.DataFrame:
    """
    Run tournament for item+warehouse combinations.

    After consolidation, each item can have multiple warehouses.
    We need to forecast each combination separately.
    """
    # Get unique item+warehouse combinations
    if 'warehouse' in df_sales.columns:
        combinations = df_sales[['item_code', 'warehouse']].drop_duplicates().values
    else:
        # Fallback: just item codes
        combinations = df_sales['item_code'].unique()

    logger.info(f"Running tournament for {len(combinations)} item/warehouse combos...")

    results = []
    for item_code, warehouse in combinations:
        result = _process_single_item_with_warehouse(
            df_sales, item_code, warehouse
        )
        results.append(result)

    return pd.DataFrame(results)
```

### Phase 3: Update Purchase Ordering Logic

**File:** `src/automated_ordering.py` (if exists)

**Changes needed:**
- Use item+warehouse forecast for purchase recommendations
- Generate separate POs per warehouse

```python
def generate_purchase_orders(df_forecasts: pd.DataFrame,
                            df_items: pd.DataFrame) -> pd.DataFrame:
    """
    Generate purchase recommendations by warehouse.

    After consolidation:
      BX010155 @ 040-EDM1 → forecast 10 units → PO to Edmonton warehouse
      BX010155 @ 030-CGY1 → forecast 5 units → PO to Calgary warehouse
    """
    # Join forecasts with item+warehouse data
    recommendations = []

    for _, forecast in df_forecasts.iterrows():
        item_code = forecast['item_code']
        warehouse = forecast['warehouse']
        forecast_qty = forecast['forecast_next_month']

        # Generate PO for this warehouse
        po = create_purchase_order(item_code, warehouse, forecast_qty)
        recommendations.append(po)

    return pd.DataFrame(recommendations)
```

---

## Testing Strategy

### Test Case 1: Current State (Before Consolidation)

```python
# Input
item_codes = ['BX010155-EDM', 'BX010155-CGY']

# Expected Output
forecasts = {
    'BX010155-EDM': {'forecast': 10, 'warehouse': '40'},
    'BX010155-CGY': {'forecast': 5, 'warehouse': '30'}
}
```

### Test Case 2: Future State (After Consolidation)

```python
# Input
item_code = 'BX010155'
warehouses = ['040-EDM1', '030-CGY1']

# Expected Output
forecasts = {
    'BX010155@040-EDM1': {'forecast': 10, 'warehouse': '040-EDM1'},
    'BX010155@030-CGY1': {'forecast': 5, 'warehouse': '030-CGY1'}
}
```

### Test Case 3: Mixed State (Transition Period)

```python
# Input
items = [
    {'item_code': 'BX010155-EDM', 'warehouse': '40'},  # Current state
    {'item_code': 'BX010155', 'warehouse': '030-CGY1'}  # Future state
]

# Expected Output
# Should handle both formats correctly
```

---

## Risk Assessment

### HIGH RISK

**Risk:** Forecasting loses regional granularity
**Impact:**
- Purchase orders go to wrong warehouse
- Stockouts in some regions, overstock in others
- Incorrect safety stock calculations
- Poor customer service due to misallocated inventory

**Mitigation:**
- Implement warehouse-aware forecasting BEFORE consolidation
- Test thoroughly with BX010155 test case
- Validate forecast accuracy per warehouse

---

## Recommendations

### Immediate Actions (Before Consolidation)

1. ✅ **Add warehouse column** to sales data ingestion
2. ✅ **Update `prepare_monthly_data()`** to filter by warehouse
3. ✅ **Update `forecast_items()`** to process item+warehouse combos
4. ✅ **Test with BX010155** (Edmonton + Calgary variants)
5. ✅ **Validate forecast accuracy** per warehouse is maintained

### Implementation Timeline

- **Phase 1:** Add warehouse to sales data (2 hours)
- **Phase 2:** Update forecasting functions (4 hours)
- **Phase 3:** Update purchase ordering logic (3 hours)
- **Phase 4:** Testing and validation (4 hours)

**Total: 13 hours (2 days)**

---

## Backward Compatibility

### Current State Items (Regional Suffixes)

```python
# Current items will continue to work
BX010155-EDM → warehouse derived from suffix → forecast for Edmonton only ✅
```

### Future State Items (Consolidated)

```python
# New consolidated items work correctly
BX010155 → warehouse from OITW table → forecast per warehouse ✅
```

### Mixed State (Transition Period)

```python
# Both can coexist during transition
BX010155-EDM (old) + BX010155 (new) → both forecast correctly ✅
```

---

## Conclusion

**Current Status:** ⚠️ **FORECASTING WILL BREAK** after consolidation

**Fix Required:** Implement warehouse-aware forecasting

**Priority:** **HIGH** - Must be completed before consolidation date

**Good News:**
- ✅ Consolidation module already has warehouse mappings
- ✅ Item state detection working
- ✅ Historical data mapping functions ready
- ❌ Only forecasting needs to be updated

**Next Steps:**
1. Review this analysis with team
2. Confirm warehouse-aware forecasting is required
3. Implement Phase 1-4 before consolidation
4. Test with BX010155 test case
5. Validate accuracy maintained

---

## Questions for Team

1. **Is warehouse-level forecasting required?** Or is aggregate forecasting acceptable?
2. **Should we forecast by warehouse code or region?**
3. **When is the consolidation date?** We need to implement this before then.
4. **Can we get test data with future state items?** For validation.

---

**Document Version:** 1.0
**Author:** Claude (AI Assistant)
**Last Updated:** 2026-01-16
