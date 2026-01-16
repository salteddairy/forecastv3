"""
Test script to verify ingestion.py functionality
Loads all 3 TSV files and prints summaries
"""
from pathlib import Path
import pandas as pd
from src.ingestion import load_sales_orders, load_supply_chain, load_items

def main():
    print("=" * 60)
    print("INGESTION TEST - Loading TSV Files")
    print("=" * 60)

    # Define paths
    data_dir = Path("data/raw")

    # 1. Load Sales Orders
    print("\n[1/3] Loading Sales Orders (sales.tsv)...")
    try:
        df_sales = load_sales_orders(data_dir / "sales.tsv")
        print(f"   SUCCESS: Loaded {len(df_sales)} rows")
        print(f"   Columns: {list(df_sales.columns)}")
        print(f"   Date range: {df_sales['date'].min()} to {df_sales['date'].max()}")
        print(f"   Regions: {df_sales['Region'].unique().tolist()}")
        print(f"   Special orders flagged: {df_sales['is_linked_special_order'].sum()}")
        print("\n   Sample data (head):")
        print(df_sales.head(3).to_string())
    except Exception as e:
        print(f"   X ERROR: {e}")
        return

    # 2. Load Supply Chain
    print("\n" + "=" * 60)
    print("[2/3] Loading Supply Chain (supply.tsv)...")
    try:
        df_history, df_schedule = load_supply_chain(data_dir / "supply.tsv")
        print(f"   SUCCESS:")
        print(f"   - History: {len(df_history)} rows")
        print(f"   - Schedule: {len(df_schedule)} rows")
        print(f"\n   History columns: {list(df_history.columns)}")
        print(f"   Schedule columns: {list(df_schedule.columns)}")

        if len(df_history) > 0:
            print(f"\n   History Lead Time stats:")
            print(f"   - Min: {df_history['lead_time_days'].min()} days")
            print(f"   - Max: {df_history['lead_time_days'].max()} days")
            print(f"   - Mean: {df_history['lead_time_days'].mean():.1f} days")
            print(f"   - Median: {df_history['lead_time_days'].median():.1f} days")
            print(f"   - Outliers (>365 days): {(df_history['lead_time_days'] > 365).sum()}")

        print(f"\n   Currency normalization check:")
        print(f"   - RowValue_CAD created: {'RowValue_CAD' in df_history.columns}")
        print(f"   - ExchangeRate mean: {df_history['ExchangeRate'].mean():.4f}")

        print("\n   Sample History data (head):")
        print(df_history.head(2).to_string())
    except Exception as e:
        print(f"   X ERROR: {e}")
        return

    # 3. Load Items
    print("\n" + "=" * 60)
    print("[3/3] Loading Item Master (items.tsv)...")
    try:
        df_items = load_items(data_dir / "items.tsv")
        print(f"   SUCCESS: Loaded {len(df_items)} rows")
        print(f"   Columns: {list(df_items.columns)}")
        print(f"   Regions: {df_items['Region'].unique().tolist()}")
        print(f"   Vendors assigned: {df_items['TargetVendor'].notna().sum()} / {len(df_items)}")

        if 'UnitCost' in df_items.columns:
            # Convert to numeric for stats
            unit_cost_numeric = pd.to_numeric(df_items['UnitCost'], errors='coerce')
            print(f"\n   Cost stats:")
            print(f"   - Mean UnitCost: ${unit_cost_numeric.mean():.2f}")
            print(f"   - Zero/Null costs: {(unit_cost_numeric.isna() | (unit_cost_numeric == 0)).sum()}")

        print("\n   Sample data (head):")
        print(df_items.head(3).to_string())
    except Exception as e:
        print(f"   X ERROR: {e}")
        return

    print("\n" + "=" * 60)
    print("SUCCESS - INGESTION TEST COMPLETE - All files loaded successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
