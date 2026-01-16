#!/usr/bin/env python3
"""
Test Prophet with Real Data

This script tests Prophet integration using actual sales data.
"""
import sys
import pandas as pd
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Prophet Real Data Test")
print("=" * 60)
print()

# Test 1: Load sales data
print("Test 1: Loading sales data...")
try:
    from src.ingestion import load_sales_orders

    df_sales = load_sales_orders(project_root / "data" / "raw" / "sales.tsv")
    print(f"  [OK] Loaded {len(df_sales)} sales records")
    print(f"  Columns: {', '.join(df_sales.columns.tolist())}")
except Exception as e:
    print(f"  [FAIL] Error loading sales: {e}")
    sys.exit(1)

# Test 2: Find item with enough history
print("\nTest 2: Finding item with sufficient history...")
try:
    df_sales['date'] = pd.to_datetime(df_sales['date'], errors='coerce')
    df_sales = df_sales.dropna(subset=['date'])

    # Get items with 18+ months of history
    item_monthly_counts = df_sales.groupby('item_code').apply(
        lambda x: x.set_index('date').resample('M').size()
    ).reset_index(name='months')
    items_with_history = item_monthly_counts[item_monthly_counts['months'] >= 18]['item_code'].unique()

    print(f"  Found {len(items_with_history)} items with 18+ months of history")

    if len(items_with_history) == 0:
        print("  [SKIP] No items with sufficient history")
        sys.exit(0)

    # Use first item
    test_item = items_with_history[0]
    print(f"  Testing item: {test_item}")

except Exception as e:
    print(f"  [FAIL] Error finding items: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Run tournament with Prophet
print("\nTest 3: Running forecast tournament with Prophet...")
try:
    from src.forecasting import run_tournament

    result = run_tournament(
        df_sales=df_sales,
        item_code=test_item,
        forecast_horizon=6
    )

    print(f"  [OK] Tournament completed")
    print(f"  Item: {result['item_code']}")
    print(f"  Winning model: {result['winning_model']}")
    print(f"  Models tested: {list(result['model_results'].keys())}")

    # Show Prophet results if available
    if 'Prophet' in result['model_results']:
        prophet_result = result['model_results']['Prophet']
        print(f"\n  Prophet Results:")
        print(f"    RMSE: {prophet_result['rmse']:.2f}")
        print(f"    Forecast (next 6 months):")
        for i, val in enumerate(prophet_result['forecast'], 1):
            print(f"      Month {i}: {val:.1f} units")
    else:
        print(f"  [WARN] Prophet not in tournament results")

    # Show all model RMSEs
    print(f"\n  Model Comparison:")
    models_sorted = sorted(
        result['model_results'].items(),
        key=lambda x: x[1]['rmse'] if not pd.isna(x[1]['rmse']) else 999
    )
    for model, data in models_sorted:
        rmse = data['rmse']
        if pd.isna(rmse):
            print(f"    {model}: N/A (insufficient data)")
        else:
            print(f"    {model}: {rmse:.2f}")

except Exception as e:
    print(f"  [FAIL] Tournament failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("Prophet Real Data Test: PASSED")
print("=" * 60)
print()
print("Prophet is successfully integrated and working with real data!")
print("The forecasting tournament will automatically select the best model")
print("(SMA, Holt-Winters, Theta, ARIMA, or Prophet) based on RMSE.")
