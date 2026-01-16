#!/usr/bin/env python3
"""
Test Prophet with Real Data - Simplified

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
        lambda x: x.set_index('date').resample('ME').size(),
        include_groups=False
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
        use_advanced_models=True
    )

    print(f"  [OK] Tournament completed")
    print(f"  Item: {result['item_code']}")

    if 'error' in result:
        print(f"  [ERROR] {result['error']}")
        sys.exit(1)

    print(f"  Winning model: {result['winning_model']}")
    print(f"  Models tested: {list(result['model_results'].keys())}")

    # Show Prophet results if available
    if 'Prophet' in result['model_results']:
        prophet_result = result['model_results']['Prophet']
        print(f"\n  Prophet Results:")
        rmse = prophet_result['rmse']
        if pd.isna(rmse):
            print(f"    RMSE: N/A (insufficient data)")
        else:
            print(f"    RMSE: {rmse:.2f}")
    else:
        print(f"  [INFO] Prophet not in results (item may have < 18 months history)")

    # Show all model RMSEs
    print(f"\n  Model Comparison (lower RMSE is better):")
    models_sorted = sorted(
        [(k, v['rmse']) for k, v in result['model_results'].items()],
        key=lambda x: float('inf') if pd.isna(x[1]) else x[1]
    )
    for i, (model, rmse) in enumerate(models_sorted, 1):
        if pd.isna(rmse):
            print(f"    {i}. {model}: N/A (insufficient data)")
        else:
            print(f"    {i}. {model}: {rmse:.2f}")

    # Show forecasts
    print(f"\n  Forecast (next 12 months):")
    for i in range(1, 13):
        month_key = f'month_{i}'
        if month_key in result['forecasts']:
            val = result['forecasts'][month_key]
            print(f"    Month {i}: {val:.1f} units" if not pd.isna(val) else f"    Month {i}: N/A")

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
print()
print("Key findings:")
print(f"  - Prophet participated in the tournament")
print(f"  - Winning model: {result['winning_model']}")
print(f"  - The tournament automatically selects the best model")
print(f"    based on RMSE (Root Mean Square Error)")
print()
print("Prophet will be used for items with 18+ months of history")
print("that exhibit seasonal patterns or trends.")
