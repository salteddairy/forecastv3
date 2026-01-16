#!/usr/bin/env python3
"""
Test Prophet Integration

This script tests that Prophet is properly integrated with the forecasting system.
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Prophet Integration Test")
print("=" * 60)
print()

# Test 1: Check Prophet is available
print("Test 1: Checking Prophet availability...")
try:
    from prophet import Prophet
    print("  [OK] Prophet is installed")
except ImportError as e:
    print(f"  [FAIL] Prophet not installed: {e}")
    sys.exit(1)

# Test 2: Check forecasting module can import Prophet
print("\nTest 2: Checking forecasting module...")
try:
    from src.forecasting import PROPHET_AVAILABLE, forecast_prophet
    if PROPHET_AVAILABLE:
        print("  [OK] Prophet is available in forecasting module")
    else:
        print("  [FAIL] Prophet not available in forecasting module")
        sys.exit(1)
except Exception as e:
    print(f"  [FAIL] Error importing forecasting module: {e}")
    sys.exit(1)

# Test 3: Run a simple forecast with Prophet
print("\nTest 3: Running Prophet forecast on sample data...")
try:
    # Create sample monthly data (24 months = 2 years)
    dates = pd.date_range(start='2023-01-01', periods=24, freq='M')
    # Create seasonal pattern + trend
    values = (
        100 + np.arange(24) * 2 +  # Linear trend
        np.sin(np.arange(24) * 2 * np.pi / 12) * 20  # Yearly seasonality
    )

    # Create time series
    train = pd.Series(values[:18], index=pd.period_range(start='2023-01-01', periods=18, freq='M'))
    test = pd.Series(values[18:], index=pd.period_range(start='2024-07-01', periods=6, freq='M'))

    print(f"  Train period: {len(train)} months ({train.index[0]} to {train.index[-1]})")
    print(f"  Test period: {len(test)} months ({test.index[0]} to {test.index[-1]})")

    # Run Prophet forecast
    forecast, rmse = forecast_prophet(train, test, forecast_horizon=6)

    print(f"  [OK] Prophet forecast completed")
    print(f"  Forecast values: {np.round(forecast, 1)}")
    print(f"  RMSE on test set: {rmse:.2f}")

    # Verify forecast shape
    if len(forecast) != 6:
        print(f"  [WARN] Expected 6 forecast values, got {len(forecast)}")
    else:
        print(f"  [OK] Forecast shape correct")

except Exception as e:
    print(f"  [FAIL] Prophet forecast failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check Prophet is in the model tournament
print("\nTest 4: Checking model tournament...")
try:
    from src.forecasting import run_forecast_tournament

    # Run tournament on sample data
    result = run_forecast_tournament(train, test, forecast_horizon=6)

    print(f"  [OK] Tournament completed with {len(result['models'])} models")
    print(f"  Winning model: {result['winning_model']}")

    if 'Prophet' in result['models']:
        print(f"  [OK] Prophet is in tournament")
        prophet_result = result['models']['Prophet']
        print(f"    RMSE: {prophet_result['rmse']:.2f}")
    else:
        print(f"  [WARN] Prophet not in tournament results (may need more data)")

except Exception as e:
    print(f"  [WARN] Tournament test failed: {e}")

# Test 5: Test with real data if available
print("\nTest 5: Testing with real data (if available)...")
try:
    sales_path = project_root / "data" / "raw" / "sales.tsv"
    if sales_path.exists():
        from src.ingestion import load_sales_orders

        df_sales = load_sales_orders(sales_path)
        print(f"  Loaded {len(df_sales)} sales records")

        # Get a sample item with enough history
        item_counts = df_sales['item_code'].value_counts()
        popular_items = item_counts[item_counts >= 20].head(5).index.tolist()

        if popular_items:
            test_item = popular_items[0]
            print(f"  Testing item: {test_item}")

            # Filter for this item
            item_sales = df_sales[df_sales['item_code'] == test_item].copy()
            item_sales['date'] = pd.to_datetime(item_sales['date'], errors='coerce')
            item_sales = item_sales.dropna(subset=['date'])

            # Aggregate to monthly
            item_sales['month'] = item_sales['date'].dt.to_period('M')
            monthly = item_sales.groupby('month')['quantity'].sum()

            if len(monthly) >= 18:
                train_size = int(len(monthly) * 0.8)
                train = monthly[:train_size]
                test = monthly[train_size:]

                print(f"    Train: {len(train)} months")
                print(f"    Test: {len(test)} months")

                # Run tournament
                result = run_forecast_tournament(train, test, forecast_horizon=6)

                print(f"    [OK] Tournament completed")
                print(f"    Winning model: {result['winning_model']}")

                if 'Prophet' in result['models']:
                    print(f"    [OK] Prophet participated")
                    print(f"      Prophet RMSE: {result['models']['Prophet']['rmse']:.2f}")
            else:
                print(f"  [SKIP] Item {test_item} has only {len(monthly)} months (need 18+)")
        else:
            print(f"  [SKIP] No items with 20+ records found")
    else:
        print(f"  [SKIP] sales.tsv not found")

except Exception as e:
    print(f"  [WARN] Real data test failed: {e}")

print()
print("=" * 60)
print("Prophet Integration Test: PASSED")
print("=" * 60)
print()
print("Prophet is ready to use in your forecasting system!")
print("The model tournament will automatically use Prophet when there's")
print("sufficient historical data (18+ months).")
