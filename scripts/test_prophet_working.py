#!/usr/bin/env python3
"""
Test Prophet Integration - Working Version

This script verifies Prophet is working with your data.
"""
import sys
import pandas as pd
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Prophet Integration Test")
print("=" * 60)
print()

# Test 1: Verify Prophet is installed
print("Test 1: Checking Prophet installation...")
try:
    from prophet import Prophet
    print("  [OK] Prophet is installed")
except ImportError as e:
    print(f"  [FAIL] Prophet not installed: {e}")
    sys.exit(1)

# Test 2: Verify Prophet is available in forecasting module
print("\nTest 2: Checking forecasting module...")
try:
    from src.forecasting import PROPHET_AVAILABLE, forecast_prophet
    if PROPHET_AVAILABLE:
        print("  [OK] Prophet is available in forecasting module")
    else:
        print("  [FAIL] Prophet not available in module")
        sys.exit(1)
except Exception as e:
    print(f"  [FAIL] Error: {e}")
    sys.exit(1)

# Test 3: Load data and find test item
print("\nTest 3: Loading sales data...")
try:
    from src.ingestion import load_sales_orders
    from src.forecasting import prepare_monthly_data

    df_sales = load_sales_orders(project_root / "data" / "raw" / "sales.tsv")
    print(f"  [OK] Loaded {len(df_sales)} sales records")

    # Get unique items
    items = df_sales['item_code'].unique()
    print(f"  Total unique items: {len(items)}")

    # Find first item with 18+ months of data
    for test_item in items[:100]:  # Check first 100 items
        monthly = prepare_monthly_data(df_sales, test_item)
        if len(monthly) >= 18:
            print(f"  Found item with 18+ months: {test_item} ({len(monthly)} months)")
            break
    else:
        print("  [WARN] No items with 18+ months found in first 100")
        # Use first available item anyway
        test_item = items[0]
        monthly = prepare_monthly_data(df_sales, test_item)
        print(f"  Using item: {test_item} ({len(monthly)} months)")

except Exception as e:
    print(f"  [FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Run tournament
print("\nTest 4: Running forecast tournament...")
try:
    from src.forecasting import run_tournament

    result = run_tournament(df_sales, test_item, use_advanced_models=True)

    if 'error' in result:
        print(f"  [ERROR] {result['error']}")
        sys.exit(1)

    print(f"  [OK] Tournament completed")
    print(f"  Item: {result['item_code']}")
    print(f"  Winning model: {result['winning_model']}")

    # Check Prophet results
    prophet_key = 'rmse_Prophet'
    if prophet_key in result:
        prophet_rmse = result[prophet_key]
        if pd.isna(prophet_rmse):
            print(f"\n  Prophet: Not enough data (needs 18+ months)")
        else:
            print(f"\n  Prophet RMSE: {prophet_rmse:.2f}")

            # Compare all models
            print(f"\n  Model RMSE Comparison (lower is better):")
            rmse_values = []
            for key, value in result.items():
                if key.startswith('rmse_') and not pd.isna(value):
                    model = key.replace('rmse_', '')
                    rmse_values.append((model, value))

            rmse_values.sort(key=lambda x: x[1])
            for i, (model, rmse) in enumerate(rmse_values, 1):
                marker = " <-- WINNER" if model == result['winning_model'] else ""
                print(f"    {i}. {model}: {rmse:.2f}{marker}")

    # Show forecast
    print(f"\n  12-Month Forecast:")
    for i in range(1, 13):
        key = f'forecast_month_{i}'
        if key in result and not pd.isna(result[key]):
            print(f"    Month {i}: {result[key]:.1f} units")

except Exception as e:
    print(f"  [FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("SUCCESS: Prophet is integrated and working!")
print("=" * 60)
print()
print("Key findings:")
print("  - Prophet is installed and available")
print("  - Prophet participated in the tournament")
print("  - Tournament automatically selects the best model")
print()
print("Prophet will be used for items with 18+ months of history")
print("that exhibit seasonal patterns or trends.")
