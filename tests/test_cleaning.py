"""
Test script to verify cleaning.py functionality
Tests outlier detection and lead time imputation
"""
from pathlib import Path
import pandas as pd
from src.ingestion import load_supply_chain
from src.cleaning import clean_supply_data


def main():
    print("=" * 60)
    print("CLEANING TEST - Outlier Detection & Imputation")
    print("=" * 60)

    # Define paths
    data_dir = Path("data/raw")

    # 1. Load Supply Data
    print("\n[1/2] Loading Supply Chain data...")
    try:
        df_history, df_schedule = load_supply_chain(data_dir / "supply.tsv")
        print(f"   SUCCESS:")
        print(f"   - History: {len(df_history)} rows")
        print(f"   - Schedule: {len(df_schedule)} rows")
    except Exception as e:
        print(f"   X ERROR: {e}")
        return

    # 2. Run Cleaning Pipeline
    print("\n" + "=" * 60)
    print("[2/2] Running Cleaning Pipeline...")
    print("=" * 60)

    try:
        df_history_clean, df_schedule_clean = clean_supply_data(
            df_history, df_schedule, max_lead_time_days=365
        )

        print("\n[Cleaned Data Summary]")
        print(f"History:")
        print(f"  - Total rows: {len(df_history_clean)}")
        print(f"  - Lead time stats:")
        print(f"    * Min: {df_history_clean['lead_time_days'].min():.1f} days")
        print(f"    * Max: {df_history_clean['lead_time_days'].max():.1f} days")
        print(f"    * Mean: {df_history_clean['lead_time_days'].mean():.1f} days")
        print(f"    * Median: {df_history_clean['lead_time_days'].median():.1f} days")
        print(f"  - Missing lead times: {df_history_clean['lead_time_days'].isna().sum()}")

        print(f"\nSchedule:")
        print(f"  - Total rows: {len(df_schedule_clean)}")
        print(f"  - Lead time stats:")
        print(f"    * Min: {df_schedule_clean['lead_time_days'].min():.1f} days")
        print(f"    * Max: {df_schedule_clean['lead_time_days'].max():.1f} days")
        print(f"    * Mean: {df_schedule_clean['lead_time_days'].mean():.1f} days")
        print(f"    * Median: {df_schedule_clean['lead_time_days'].median():.1f} days")
        print(f"  - Missing lead times: {df_schedule_clean['lead_time_days'].isna().sum()}")

        print("\n[Sample Cleaned History Data]")
        print(df_history_clean.head(3).to_string())

        print("\n" + "=" * 60)
        print("SUCCESS - CLEANING TEST COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"   X ERROR: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
