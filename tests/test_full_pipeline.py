"""
Full Pipeline Test - End-to-End Verification
Tests the complete data pipeline before launching Streamlit
"""
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

print("\n" + "=" * 70)
print(" FULL PIPELINE TEST - End-to-End Verification")
print("=" * 70)

# Step 1: Ingestion
print("\n[1/5] INGESTION - Loading Data...")
from src.ingestion import load_sales_orders, load_supply_chain, load_items

data_dir = Path("data/raw")
df_sales = load_sales_orders(data_dir / "sales.tsv")
df_history, df_schedule = load_supply_chain(data_dir / "supply.tsv")
df_items = load_items(data_dir / "items.tsv")

print(f"  [OK] Sales: {len(df_sales):,} rows")
print(f"  [OK] Supply History: {len(df_history):,} rows")
print(f"  [OK] Supply Schedule: {len(df_schedule):,} rows")
print(f"  [OK] Items: {len(df_items):,} rows")

# Step 2: Cleaning
print("\n[2/5] CLEANING - Removing Outliers & Segmenting Items...")
from src.cleaning import clean_supply_data, classify_items

df_history_clean, df_schedule_clean = clean_supply_data(df_history, df_schedule)
df_classified = classify_items(df_sales)

print(f"  [OK] Cleaned History: {len(df_history_clean):,} rows")
print(f"  [OK] Cleaned Schedule: {len(df_schedule_clean):,} rows")
print(f"  [OK] Items Classified: {len(df_classified):,} items")
print(f"    - Smooth: {(df_classified['classification']=='Smooth').sum():,}")
print(f"    - Intermittent: {(df_classified['classification']=='Intermittent').sum():,}")
print(f"    - Lumpy: {(df_classified['classification']=='Lumpy').sum():,}")

# Step 3: Forecasting
print("\n[3/5] FORECASTING - Running Tournament...")
from src.forecasting import forecast_items

# Forecast first 50 items for testing
df_forecasts = forecast_items(df_sales, n_samples=50)
df_forecasts_valid = df_forecasts[df_forecasts['winning_model'].notna()]

print(f"  [OK] Total forecasts generated: {len(df_forecasts)}")
print(f"  [OK] Valid forecasts: {len(df_forecasts_valid)}")
print(f"     - SMA Wins: {(df_forecasts_valid['winning_model']=='SMA').sum()}")
print(f"     - Holt-Winters Wins: {(df_forecasts_valid['winning_model']=='Holt-Winters').sum()}")
print(f"     - Prophet Wins: {(df_forecasts_valid['winning_model']=='Prophet').sum()}")

# Step 4: Optimization
print("\n[4/5] OPTIMIZATION - Calculating TCO & Stock Recommendations...")
from src.optimization import optimize_inventory, load_config

config = load_config()
df_stockout, df_tco = optimize_inventory(
    df_items,
    df_forecasts,
    df_schedule_clean,
    config
)

print(f"  [OK] Stockout Analysis: {len(df_stockout)} items analyzed")
stockouts = df_stockout['will_stockout'].sum()
print(f"     - Items at risk of stockout: {stockouts:,}")
critical = (df_stockout['urgency'] == 'CRITICAL (<30 days)').sum()
print(f"     - Critical stockouts (<30 days): {critical:,}")

print(f"  [OK] TCO Analysis: {len(df_tco)} items analyzed")
should_switch = df_tco['should_switch'].sum()
print(f"     - Items recommended to switch: {should_switch:,}")
total_savings = df_tco['annual_savings'].sum()
print(f"     - Total annual savings: ${total_savings:,.2f}")

# Step 5: Summary
print("\n[5/5] PIPELINE SUMMARY")
print("-" * 70)

print("\n[DATA FLOW]:")
print(f"  Raw Data -> Cleaned Data -> Forecasts -> Optimization")
print(f"  {len(df_sales):,} sales -> {len(df_history_clean):,} history -> {len(df_forecasts_valid)} forecasts -> {len(df_tco)} optimized")

print("\n[KEY INSIGHTS]:")
print(f"  1. Supply Chain:")
print(f"     • {len(df_history_clean)} historical records ready for forecasting")
print(f"     • Exchange rate normalized (CAD)")

print(f"\n  2. Demand Patterns:")
print(f"     • {(df_classified['classification']=='Smooth').sum():,} smooth demand items")
print(f"     • {(df_classified['classification']=='Intermittent').sum():,} intermittent demand items")

print(f"\n  3. Forecasting Performance:")
print(f"     • Best model: {df_forecasts_valid['winning_model'].mode()[0] if len(df_forecasts_valid) > 0 else 'N/A'}")
print(f"     • Average RMSE: {df_forecasts_valid[[f'rmse_{m}' for m in ['SMA', 'Holt-Winters', 'Prophet'] if f'rmse_{m}' in df_forecasts_valid.columns]].min(axis=1).mean():.2f}")

print(f"\n  4. Inventory Risks:")
print(f"     • {stockouts:,} items at risk of stockout")
print(f"     • ${total_savings:,.2f} potential annual savings from optimization")

print("\n[SUCCESS] PIPELINE TEST COMPLETE - All components working!")
print("=" * 70)

print("\n[READY] Next: Launch Streamlit app")
print("   Command: streamlit run app.py")
