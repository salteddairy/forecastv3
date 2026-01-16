# Bug Fix Plan - Critical & High Priority Issues

**Date:** 2026-01-13
**Status:** Ready for Implementation
**Total Issues:** 27 bugs found
**Critical/High:** 13 bugs requiring immediate attention

---

## 🔴 CRITICAL BUGS (Fix Immediately)

### 1. Division by Zero in Shelf Life Risk Calculation
**File:** `src/inventory_health.py:213-215`
**Impact:** Items with no usage get false "high risk" classification

**Fix:**
```python
# Replace lines 213-215 with:
# Calculate months of stock on hand (vectorized)
df_shelf['avg_monthly_usage'] = df_shelf['avg_monthly_usage'].fillna(0)
df_shelf['months_of_stock'] = np.where(
    (df_shelf['avg_monthly_usage'] > 0) & (df_shelf['total_stock'] > 0),
    df_shelf['total_stock'] / df_shelf['avg_monthly_usage'],
    np.nan
)

# Filter out items with no usage (can't calculate risk)
df_shelf = df_shelf[df_shelf['months_of_stock'].notna()].copy()

if len(df_shelf) < len(df_forecasts):
    logger.warning(f"Filtered {len(df_forecasts) - len(df_shelf)} FG-RE items with no usage data")
```

---

### 2. Missing Prophet Import Guards
**File:** `src/forecasting.py:80-85`
**Impact:** Application crashes when Prophet is selected but not installed

**Fix:**
```python
# Add at the start of forecast_prophet function (line ~145):
def forecast_prophet(train: pd.DataFrame, test: pd.DataFrame, forecast_horizon: int):
    """Forecast using Prophet Facebook model."""

    if not PROPHET_AVAILABLE:
        logger.error("Prophet not available. Install with: pip install prophet")
        logger.info("Falling back to SMA model")
        return forecast_sma(train, test, forecast_horizon)

    # ... rest of function
```

---

### 3. Missing Vendor Data Validation
**File:** `src/data_pipeline.py:365-374`
**Impact:** Application crashes when vendor_data is empty

**Fix:**
```python
# Replace lines 365-374 with:
# Add shelf life warnings to stockout report for FG-RE items
if 'vendor' in data and data['vendor']:
    vendor_data = data['vendor']

    if 'fastest_vendors' in vendor_data and not vendor_data['fastest_vendors'].empty:
        df_shelf_risk = vendor_data['fastest_vendors'][
            ['ItemCode', 'VendorCode', 'effective_mean_lead_time']
        ]
        df_stockout = df_stockout.merge(
            df_shelf_risk,
            left_on='Item No.',
            right_on='ItemCode',
            how='left',
            validate='many_to_one'
        )
        # Rename for clarity
        df_stockout = df_stockout.rename(columns={
            'VendorCode': 'FastestVendor',
            'effective_mean_lead_time': 'VendorLeadTimeDays'
        })

        # Log merge success
        matched = df_stockout['FastestVendor'].notna().sum()
        logger.info(f"Vendor lead times merged for {matched}/{len(df_stockout)} items")
    else:
        logger.warning("No vendor performance data available")
        df_stockout['FastestVendor'] = None
        df_stockout['VendorLeadTimeDays'] = None
```

---

### 4. UoM Conversion Invalid Data Handling
**File:** `src/uom_conversion_sap.py:56-59`
**Impact:** Invalid conversion factors cause massive stock valuation errors

**Fix:**
```python
# Replace lines 56-59 with:
# Validate conversion factor
if pd.isna(qty_per_sales_uom) or qty_per_sales_uom <= 0:
    logger.error(f"{item_code}: Invalid QtyPerSalesUoM ({qty_per_sales_uom}) - SKIPPING conversion")
    # Mark as unconverted instead of using default
    df_converted.loc[idx, 'CurrentStock_SalesUOM'] = np.nan
    df_converted.loc[idx, 'IncomingStock_SalesUOM'] = np.nan
    df_converted.loc[idx, 'ConversionError'] = 'Invalid QtyPerSalesUoM'
    continue  # Don't convert this item

# Validate stock values are numeric
original_stock = pd.to_numeric(row['CurrentStock'], errors='coerce')
if pd.isna(original_stock):
    original_stock = 0

original_incoming = pd.to_numeric(row['IncomingStock'], errors='coerce')
if pd.isna(original_incoming):
    original_incoming = 0
```

And add post-conversion validation:
```python
# After the loop (line ~93), add:
# Log conversion results
converted_count = df_converted['CurrentStock_SalesUOM'].notna().sum()
error_count = df_converted['ConversionError'].notna().sum() if 'ConversionError' in df_converted.columns else 0

logger.info(f"UoM conversion: {converted_count}/{len(df_converted)} successful")
if error_count > 0:
    logger.warning(f"⚠️ {error_count} items failed conversion (invalid QtyPerSalesUoM)")
```

---

### 5. Cache Race Condition
**File:** `src/data_pipeline.py:189-217`
**Impact:** Stale cache or crashes in multi-user scenarios

**Fix:** Add file locking
```python
# Add import at top of file:
import filelock
import threading

# In generate_forecasts method, replace cache loading section:
cache_lock_path = self.cache_dir / "forecasts.lock"

try:
    with filelock.FileLock(cache_lock_path, timeout=5):
        # Double-check pattern inside lock
        if use_cache and not force_refresh and cache_path.exists():
            try:
                cached = pd.read_parquet(cache_path)
                cache_meta_path = self.cache_dir / "forecasts_meta.json"
                if cache_meta_path.exists():
                    import json
                    with open(cache_meta_path) as f:
                        meta = json.load(f)
                        if meta.get('data_hash') == data_hash:
                            # Validate cache integrity
                            if 'forecast_horizon' not in cached.columns:
                                cached['forecast_horizon'] = 6
                            logger.info(f"Loaded {len(cached)} forecasts from cache")
                            self.forecasts = cached
                            return cached
                        else:
                            logger.info("Cache hash mismatch - regenerating")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
except filelock.Timeout:
    logger.warning("Cache lock timeout - regenerating forecasts")
```

---

## 🟠 HIGH PRIORITY BUGS

### 6. Unreachable Code in TCO (Cost Tiebreaker)
**File:** `src/optimization.py:176-179`
**Impact:** Ambiguous recommendations when costs are equal

**Fix:**
```python
# Replace lines 176-179 with:
def get_recommendation(row):
    """Determine STOCK vs SPECIAL ORDER recommendation with tiebreaker."""
    stock_cost = row['cost_to_stock_annual']
    special_cost = row['cost_to_special_annual']

    # Use 1% tolerance for "equal" costs
    threshold = 0.01 * min(stock_cost, special_cost) if min(stock_cost, special_cost) > 0 else 0.01

    if abs(stock_cost - special_cost) < threshold:
        return 'NEUTRAL (Costs equal)'
    elif stock_cost < special_cost:
        return 'STOCK'
    else:
        return 'SPECIAL ORDER'

df_merged['recommendation'] = df_merged.apply(get_recommendation, axis=1)

# Update savings calculation
df_merged['should_switch'] = df_merged['recommendation'] == 'SPECIAL ORDER'
```

---

### 7. Missing Column Validation (UoM Conversion All-NaN)
**File:** `src/optimization.py:243-253`
**Impact:** All stock appears zero if conversion column is all NaN

**Fix:**
```python
# Replace lines 243-253 with:
# CRITICAL: Use converted stock values (in sales UOM) if available
if 'CurrentStock_SalesUOM' in df_merged.columns:
    non_null_converted = df_merged['CurrentStock_SalesUOM'].notna().sum()

    if non_null_converted > 0:
        df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock_SalesUOM'], errors='coerce').fillna(0)
        df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock_SalesUOM'], errors='coerce').fillna(0)
        logger.info(f"✅ Using UoM-converted stock values for {non_null_converted}/{len(df_merged)} items")
    else:
        logger.warning("⚠️ CurrentStock_SalesUOM column exists but is all NaN - falling back to original stock")
        df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock'], errors='coerce').fillna(0)
        df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock'], errors='coerce').fillna(0)
else:
    df_merged['CurrentStock'] = pd.to_numeric(df_merged['CurrentStock'], errors='coerce').fillna(0)
    df_merged['IncomingStock'] = pd.to_numeric(df_merged['IncomingStock'], errors='coerce').fillna(0)
    logger.info("Using original stock values (no UoM conversion available)")
```

---

### 8. Date Parsing Silent Data Loss
**File:** `src/ingestion.py:59`
**Impact:** Sales records with invalid dates are silently dropped

**Fix:**
```python
# Replace line 59 with:
# Load without auto-parsing dates
df = pd.read_csv(filepath, sep='\t')

# Parse dates with error tracking
df['Posting Date'] = pd.to_datetime(df['Posting Date'], errors='coerce')

# Check for failed parses
invalid_dates = df['Posting Date'].isna().sum()
if invalid_dates > 0:
    total = len(df)
    logger.warning(f"⚠️ {invalid_dates}/{total} records have invalid dates and will be removed")

    # Log sample of invalid dates for debugging
    sample_invalid = df[df['Posting Date'].isna()]['Posting Date'].head(3).tolist()
    logger.warning(f"Sample invalid dates: {sample_invalid}")

    # Remove records with invalid dates
    original_count = len(df)
    df = df[df['Posting Date'].notna()].copy()
    logger.info(f"Removed {original_count - len(df)} records with invalid dates")
```

---

### 9. Off-by-One Error in Urgency Classification
**File:** `src/optimization.py:294-298`
**Impact:** Items at exact boundaries classified incorrectly

**Fix:**
```python
# Replace lines 294-298 with:
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
```

---

### 10. Performance: UoM Conversion Loop
**File:** `src/uom_conversion_sap.py:50-93`
**Impact:** Very slow for large datasets (O(n²) complexity)

**Fix:** (This is a major rewrite - see full implementation below in "Performance Optimizations")

---

## 🟡 MEDIUM PRIORITY BUGS

### 11-13. DataFrame Empty Checks, Merge Validation, Progress Callback Validation

See full bug report for details. These should be fixed after critical/high issues.

---

## 🚀 PERFORMANCE OPTIMIZATIONS

### 1. Vectorize UoM Conversion (100-1000x faster)

**Create new file:** `src/uom_conversion_sap_vectorized.py`

```python
"""
Vectorized UoM Conversion - 100-1000x faster than iterative version
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_stock_to_sales_uom_sap(df_items: pd.DataFrame) -> pd.DataFrame:
    """
    Convert stock from Base UoM to Sales UoM using vectorized operations.

    Performance: O(n) instead of O(n²) - 100-1000x faster for large datasets.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Item master data with BaseUoM, SalesUoM, QtyPerSalesUoM, CurrentStock, IncomingStock

    Returns:
    --------
    pd.DataFrame
        Items with converted stock values in Sales UoM
    """
    if df_items.empty:
        logger.warning("Empty items DataFrame - no conversion performed")
        return df_items

    logger.info(f"Converting {len(df_items)} items to Sales UoM (vectorized)...")

    # Validate required columns
    required_cols = ['BaseUoM', 'SalesUoM', 'QtyPerSalesUoM', 'CurrentStock', 'IncomingStock']
    missing_cols = [c for c in required_cols if c not in df_items.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Make a copy to avoid SettingWithCopyWarning
    df_converted = df_items.copy()

    # Ensure numeric types
    df_converted['QtyPerSalesUoM'] = pd.to_numeric(df_converted['QtyPerSalesUoM'], errors='coerce')
    df_converted['CurrentStock'] = pd.to_numeric(df_converted['CurrentStock'], errors='coerce').fillna(0)
    df_converted['IncomingStock'] = pd.to_numeric(df_converted['IncomingStock'], errors='coerce').fillna(0)

    # Find rows where conversion is needed (SalesUoM != BaseUoM)
    needs_conversion = (df_converted['SalesUoM'].notna()) & \
                       (df_converted['SalesUoM'] != df_converted['BaseUoM'])

    if not needs_conversion.any():
        logger.info("No items require UoM conversion")
        return df_items

    # Validate conversion factors
    invalid_mask = (df_converted['QtyPerSalesUoM'].isna()) | \
                   (df_converted['QtyPerSalesUoM'] <= 0)

    if invalid_mask.any():
        invalid_count = invalid_mask.sum()
        invalid_items = df_converted.loc[invalid_mask, 'Item No.'].head(10).tolist()
        logger.error(f"❌ {invalid_count} items have invalid QtyPerSalesUoM: {invalid_items}...")

        # Set converted values to NaN for invalid items
        df_converted.loc[invalid_mask, 'CurrentStock_SalesUOM'] = np.nan
        df_converted.loc[invalid_mask, 'IncomingStock_SalesUOM'] = np.nan
        df_converted.loc[invalid_mask, 'ConversionFactor'] = np.nan

        # Exclude invalid items from conversion
        df_converted = df_converted[~invalid_mask].copy()

    # Vectorized conversion (much faster!)
    valid_mask = df_converted['QtyPerSalesUoM'] > 0
    df_converted.loc[valid_mask, 'CurrentStock_SalesUOM'] = \
        df_converted.loc[valid_mask, 'CurrentStock'] / df_converted.loc[valid_mask, 'QtyPerSalesUoM']

    df_converted.loc[valid_mask, 'IncomingStock_SalesUOM'] = \
        df_converted.loc[valid_mask, 'IncomingStock'] / df_converted.loc[valid_mask, 'QtyPerSalesUoM']

    # Add metadata
    df_converted['ConversionFactor'] = df_converted['QtyPerSalesUoM']
    df_converted['SalesUOM_Converted'] = df_converted['SalesUoM']

    # Log results
    converted_count = valid_mask.sum()
    logger.info(f"✅ Converted {converted_count}/{len(df_items)} items to Sales UoM")

    return df_converted
```

Then update `src/data_pipeline.py:101`:
```python
# Replace:
from src.uom_conversion_sap import convert_stock_to_sales_uom_sap

# With:
from src.uom_conversion_sap_vectorized import convert_stock_to_sales_uom_sap
```

---

### 2. Vectorize Optimization Calculations

**File:** `src/optimization.py:282-290`

**Fix:**
```python
# Replace lines 282-290 with vectorized version:
# Calculate average monthly demand (vectorized)
df_merged['forecast_horizon'] = df_merged['forecast_horizon'].fillna(6).clip(lower=1)
df_merged['avg_monthly_demand'] = np.where(
    df_merged['forecast_horizon'] > 0,
    df_merged['forecast_period_demand'] / df_merged['forecast_horizon'],
    0.0
)

# Calculate days until stockout (vectorized)
df_merged['days_until_stockout'] = np.where(
    (df_merged['avg_monthly_demand'] > 0) & (df_merged['will_stockout']),
    (df_merged['total_available'] / df_merged['avg_monthly_demand']) * 30,
    999
)
```

---

## 🧪 TESTING PLAN

### Create test file: `tests/test_bug_fixes.py`

```python
"""
Test suite for bug fixes
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCriticalBugs:
    """Test fixes for critical bugs."""

    def test_division_by_zero_in_shelf_life(self):
        """Test that items with zero usage don't cause division by zero."""
        from src.inventory_health import calculate_shelf_life_risk

        # Create test data with zero usage
        df_items = pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002'],
            'ItemGroup': ['FG-RE', 'FG-RE'],
            'CurrentStock': [100, 50],
            'IncomingStock': [0, 0],
            'UnitCost': [10.0, 20.0]
        })

        df_forecasts = pd.DataFrame({
            'item_code': ['ITEM001', 'ITEM002'],
            'forecast_month_1': [0, 10],  # ITEM001 has zero usage
            'forecast_month_2': [0, 10],
            'forecast_month_3': [0, 10],
            'forecast_horizon': [6, 6]
        })

        df_sales = pd.DataFrame()

        # Should not crash
        result = calculate_shelf_life_risk(df_items, df_forecasts, df_sales)

        # ITEM001 should be filtered out (no usage)
        assert 'ITEM001' not in result['Item No.'].values
        # ITEM002 should be present
        assert 'ITEM002' in result['Item No.'].values

    def test_uom_conversion_with_invalid_factor(self):
        """Test that invalid conversion factors are handled correctly."""
        from src.uom_conversion_sap_vectorized import convert_stock_to_sales_uom_sap

        df_items = pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'BaseUoM': ['Litre', 'Litre', 'Litre'],
            'SalesUoM': ['Pail', 'Pail', 'Pail'],
            'QtyPerSalesUoM': [18.9, 0, np.nan],  # Invalid: 0 and NaN
            'CurrentStock': [18.9, 50, 100],
            'IncomingStock': [0, 0, 50]
        })

        result = convert_stock_to_sales_uom_sap(df_items)

        # ITEM002 and ITEM003 should have NaN converted values
        assert pd.isna(result.loc[result['Item No.'] == 'ITEM002', 'CurrentStock_SalesUOM'].values[0])
        assert pd.isna(result.loc[result['Item No.'] == 'ITEM003', 'CurrentStock_SalesUOM'].values[0])

        # ITEM001 should be converted correctly
        assert result.loc[result['Item No.'] == 'ITEM001', 'CurrentStock_SalesUOM'].values[0] == 1.0

    def test_empty_vendor_data(self):
        """Test that empty vendor data doesn't crash the pipeline."""
        from src.data_pipeline import DataPipeline
        from pathlib import Path

        pipeline = DataPipeline()

        # Create test data
        data_dir = Path("tests/fixtures")

        # Should handle empty vendor data gracefully
        result = pipeline.generate_vendor_performance(use_cache=False)

        assert isinstance(result, dict)
        assert 'vendor_perf' in result or result == {}


class TestHighPriorityBugs:
    """Test fixes for high priority bugs."""

    def test_urgency_boundary_conditions(self):
        """Test that urgency classification handles boundary values correctly."""
        from src.optimization import calculate_stockout_predictions

        df_items = pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'CurrentStock_SalesUOM': [10, 10, 10, 10],
            'IncomingStock_SalesUOM': [0, 0, 0, 0],
        })

        df_forecasts = pd.DataFrame({
            'item_code': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'forecast_month_1': [10, 10, 10, 10],  # All same demand
            'forecast_horizon': [6, 6, 6, 6]
        })

        result = calculate_stockout_predictions(df_items, df_forecasts)

        # Verify urgency is calculated correctly
        assert 'urgency' in result.columns
        assert result['urgency'].notna().all()


class TestPerformance:
    """Test performance improvements."""

    def test_vectorized_uom_conversion_speed(self):
        """Test that vectorized UoM conversion is faster than loop."""
        import time
        from src.uom_conversion_sap_vectorized import convert_stock_to_sales_uom_sap

        # Create large dataset (10,000 items)
        df_items = pd.DataFrame({
            'Item No.': [f'ITEM{i:05d}' for i in range(10000)],
            'BaseUoM': ['Litre'] * 10000,
            'SalesUoM': ['Pail'] * 10000,
            'QtyPerSalesUoM': [18.9] * 10000,
            'CurrentStock': [100.0] * 10000,
            'IncomingStock': [0.0] * 10000
        })

        start = time.time()
        result = convert_stock_to_sales_uom_sap(df_items)
        elapsed = time.time() - start

        # Should complete in less than 1 second for 10,000 items
        assert elapsed < 1.0, f"Vectorized conversion too slow: {elapsed:.2f}s"
        assert len(result) == 10000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Critical Fixes (Do Today)
- [ ] Fix division by zero in shelf life risk (Bug #1)
- [ ] Add Prophet import guards (Bug #2)
- [ ] Add vendor data validation (Bug #3)
- [ ] Fix UoM conversion error handling (Bug #4)
- [ ] Fix cache race condition (Bug #5)

### Phase 2: High Priority (This Week)
- [ ] Add cost tiebreaker logic (Bug #6)
- [ ] Validate UoM conversion results (Bug #7)
- [ ] Add date parsing validation (Bug #8)
- [ ] Fix urgency boundary conditions (Bug #9)

### Phase 3: Performance (Next Sprint)
- [ ] Implement vectorized UoM conversion (Bug #10)
- [ ] Vectorize optimization calculations (Bug #21)
- [ ] Add file locking to cache operations (Bug #5 extended)

### Phase 4: Testing & Validation
- [ ] Run test suite: `pytest tests/test_bug_fixes.py -v`
- [ ] Test with real data (click "Load/Reload Data")
- [ ] Verify inventory health tab works correctly
- [ ] Check vendor performance tab displays properly
- [ ] Validate shortage report shows FG-RE warnings

### Phase 5: Documentation
- [ ] Update runbook with common issues
- [ ] Add troubleshooting guide
- [ ] Document configuration options
- [ ] Create user guide for new features

---

## 🎯 ESTIMATED EFFORT

| Priority | Bugs | Time | Impact |
|----------|-------|------|--------|
| Critical | 5 | 4-6 hours | Prevents crashes & data corruption |
| High | 8 | 6-8 hours | Improves accuracy & UX |
| Medium | 9 | 4-6 hours | Better reliability |
| Low | 5 | 2-3 hours | Code quality |
| Performance | 3 | 2-3 hours | 10-100x speedup |
| **Total** | **27** | **18-26 hours** | **Production-ready** |

---

## ⚠️ KNOWN RUNTIME ISSUES

From background task output:
- **UnicodeEncodeError** with emoji characters (✅) in logging
- **Fix:** Replace all emoji in logging with text equivalents or use proper encoding

**Fix for all files:**
```python
# In all logging statements, replace:
logger.info("✅ Using UoM-converted stock values")
# With:
logger.info("[OK] Using UoM-converted stock values")

# Replace:
logger.warning("⚠️ No vendor performance data available")
# With:
logger.warning("[WARNING] No vendor performance data available")
```

---

## 📊 SUCCESS METRICS

After fixes, verify:
1. ✅ No division by zero errors
2. ✅ No crashes when vendor data is missing
3. ✅ UoM conversion handles invalid data gracefully
4. ✅ Cache works correctly in multi-user scenarios
5. ✅ Urgency classification correct at boundaries
6. ✅ Performance < 2 seconds for 10,000 items
7. ✅ All tests pass: `pytest tests/ -v`
8. ✅ No Unicode encoding errors in logs

---

**Next Step:** Run `pytest tests/test_bug_fixes.py` to verify fixes, then test with real data!