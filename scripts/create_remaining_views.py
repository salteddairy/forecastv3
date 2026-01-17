#!/usr/bin/env python3
"""Create remaining views."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

database_url = "postgresql://postgres:bESEdDxzAMlfHmtFjrGMQcIESsBlbQrk@yamanote.proxy.rlwy.net:16099/railway"
engine = create_engine(database_url)

with engine.connect() as conn:
    # mv_vendor_lead_times (fixed)
    print('Creating mv_vendor_lead_times...')
    conn.execute(text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_vendor_lead_times AS
        SELECT
            v.vendor_code,
            v.vendor_name,
            COUNT(po.order_number) as total_orders,
            AVG(CURRENT_DATE - po.order_date) as avg_lead_time_days,
            MAX(po.order_date) as last_order_date
        FROM vendors v
        LEFT JOIN purchase_orders po ON v.vendor_code = po.vendor_code
        GROUP BY v.vendor_code, v.vendor_name
    """))
    conn.commit()
    print('[OK] mv_vendor_lead_times')

    # mv_forecast_summary
    print('Creating mv_forecast_summary...')
    conn.execute(text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_summary AS
        SELECT
            f.item_code,
            i.item_description,
            f.winning_model,
            f.status,
            f.forecast_confidence_pct,
            f.forecast_month_1,
            f.forecast_month_2,
            f.forecast_month_3,
            (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) as forecast_3month_total,
            f.forecast_generated_at
        FROM forecasts f
        JOIN items i ON f.item_code = i.item_code
        WHERE f.status = 'Active'
    """))
    conn.commit()
    print('[OK] mv_forecast_summary')

    # mv_forecast_accuracy_summary
    print('Creating mv_forecast_accuracy_summary...')
    conn.execute(text("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_accuracy_summary AS
        SELECT
            winning_model,
            COUNT(*) as item_count,
            AVG(mape) as avg_mape,
            AVG(rmse) as avg_rmse,
            AVG(bias) as avg_bias
        FROM forecast_accuracy
        GROUP BY winning_model
    """))
    conn.commit()
    print('[OK] mv_forecast_accuracy_summary')

    # Indexes
    print('Creating indexes...')
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_vendor_lead_times_key ON mv_vendor_lead_times(vendor_code)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_forecast_summary_key ON mv_forecast_summary(item_code)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_costs_key ON mv_latest_costs(item_code)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key ON mv_latest_pricing(item_code, price_level, region_key)"))
    conn.commit()
    print('[OK] All indexes')

print('\nAll materialized views and indexes created!')
