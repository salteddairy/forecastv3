"""
Comprehensive Bug Check Script
Tests all data loading and column name handling before migration
"""
import sys
from pathlib import Path
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_column_normalization():
    """Test 1: Column normalization"""
    print("\n" + "="*60)
    print("TEST 1: Column Normalization")
    print("="*60)

    from src.ingestion import normalize_column_names

    test_data = pd.DataFrame({
        'Item No.': ['A', 'B'],
        'VendorCode': ['V1', 'V2'],
        'Posting Date': ['2023-01-01', '2023-01-02'],
        'Quantity': [10, 20],
        'ItemCode': ['C', 'D'],
    })

    result = normalize_column_names(test_data)

    print(f"Original columns: {list(test_data.columns)}")
    print(f"Normalized columns: {list(result.columns)}")

    # Check expected columns
    expected_cols = ['item_code', 'vendor_code', 'date', 'qty']
    missing = [col for col in expected_cols if col not in result.columns]

    if missing:
        print(f"[FAIL] FAIL: Missing columns: {missing}")
        return False
    else:
        print("[OK] PASS: All expected columns present")
        return True


def test_load_sales():
    """Test 2: Load sales data"""
    print("\n" + "="*60)
    print("TEST 2: Load Sales Data")
    print("="*60)

    try:
        from src.ingestion import load_sales_orders

        df_sales = load_sales_orders(Path('data/raw/sales.tsv'))

        print(f"[OK] Sales loaded: {len(df_sales)} rows")
        print(f"   Columns: {list(df_sales.columns[:10])}")

        # Check for expected columns
        required_cols = ['item_code', 'date', 'qty']
        missing = [col for col in required_cols if col not in df_sales.columns]

        if missing:
            print(f"[FAIL] FAIL: Missing required columns: {missing}")
            return False
        else:
            print(f"[OK] PASS: Has required columns {required_cols}")
            return True

    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_supply():
    """Test 3: Load supply data"""
    print("\n" + "="*60)
    print("TEST 3: Load Supply Data")
    print("="*60)

    try:
        from src.ingestion import load_supply_chain

        df_history, df_schedule = load_supply_chain(Path('data/raw/supply.tsv'))

        print(f"[OK] Supply loaded:")
        print(f"   History: {len(df_history)} rows")
        print(f"   Schedule: {len(df_schedule)} rows")
        print(f"   History columns: {list(df_history.columns[:10])}")

        # Check for expected columns
        required_cols = ['item_code', 'lead_time_days']
        missing = [col for col in required_cols if col not in df_history.columns]

        if missing:
            print(f"[FAIL] FAIL: Missing required columns: {missing}")
            return False
        else:
            print(f"[OK] PASS: Has required columns {required_cols}")
            return True

    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vendor_lead_times():
    """Test 4: Vendor lead times calculation"""
    print("\n" + "="*60)
    print("TEST 4: Vendor Lead Times Calculation")
    print("="*60)

    try:
        from src.ingestion import load_supply_chain, load_items
        from src.automated_ordering import get_vendor_lead_times

        df_supply, _ = load_supply_chain(Path('data/raw/supply.tsv'))
        df_items = load_items(Path('data/raw/items.tsv'))

        df_lead_times = get_vendor_lead_times(df_supply, df_items)

        print(f"[OK] Lead times calculated: {len(df_lead_times)} rows")
        print(f"   Columns: {list(df_lead_times.columns)}")

        # Check for expected columns
        required_cols = ['item_code', 'vendor_code', 'lead_time_days', 'sample_count']
        missing = [col for col in required_cols if col not in df_lead_times.columns]

        if missing:
            print(f"[FAIL] FAIL: Missing required columns: {missing}")
            return False
        else:
            print(f"[OK] PASS: Has required columns {required_cols}")
            return True

    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_forecasting_with_correct_columns():
    """Test 5: Forecasting with normalized columns"""
    print("\n" + "="*60)
    print("TEST 5: Forecasting with Normalized Columns")
    print("="*60)

    try:
        from src.ingestion import load_sales_orders
        from src.forecasting import prepare_monthly_data

        df_sales = load_sales_orders(Path('data/raw/sales.tsv'))

        # Get first item
        first_item = df_sales['item_code'].iloc[0]

        # Prepare monthly data
        monthly_data = prepare_monthly_data(df_sales, first_item)

        print(f"[OK] Monthly data prepared for {first_item}")
        print(f"   Data points: {len(monthly_data)}")

        if len(monthly_data) > 0:
            print(f"   Sample: {monthly_data.head().tolist()}")
            print("[OK] PASS: Forecasting preparation works")
            return True
        else:
            print("[FAIL] FAIL: No monthly data generated")
            return False

    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_pipeline():
    """Test 6: Full data pipeline"""
    print("\n" + "="*60)
    print("TEST 6: Full Data Pipeline")
    print("="*60)

    try:
        from src.data_pipeline import DataPipeline

        pipeline = DataPipeline()

        # Load raw data
        print("Loading raw data...")
        raw_data = pipeline.load_raw_data(Path('data/raw'))

        print(f"[OK] Raw data loaded:")
        for key, df in raw_data.items():
            print(f"   {key}: {len(df)} rows")

        # Check for required columns in sales
        if 'sales' in raw_data:
            required_cols = ['item_code', 'date', 'qty']
            missing = [col for col in required_cols if col not in raw_data['sales'].columns]

            if missing:
                print(f"[FAIL] FAIL: Sales missing columns: {missing}")
                return False

        print("[OK] PASS: Data pipeline works")
        return True

    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("COMPREHENSIVE BUG CHECK")
    print("Testing all data loading and column handling")
    print("="*60)

    tests = [
        ("Column Normalization", test_column_normalization),
        ("Load Sales Data", test_load_sales),
        ("Load Supply Data", test_load_supply),
        ("Vendor Lead Times", test_vendor_lead_times),
        ("Forecasting Preparation", test_forecasting_with_correct_columns),
        ("Full Data Pipeline", test_data_pipeline),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[FAIL] {name} CRASHED: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n*** ALL TESTS PASSED - Ready for migration! ***")
        return 0
    else:
        print(f"\n*** {total - passed} test(s) failed - Fix before migrating ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
