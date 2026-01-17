#!/usr/bin/env python3
"""
Apply remaining materialized views and views one at a time.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

def apply_remaining_objects(database_url: str):
    """Apply remaining materialized views and views."""

    statements = [
        # mv_vendor_lead_times
        ("mv_vendor_lead_times", """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_vendor_lead_times AS
            SELECT
                v.vendor_code,
                v.vendor_name,
                COUNT(po.order_number) as total_orders,
                AVG(EXTRACT(DAY FROM (CURRENT_DATE - po.order_date))) as avg_lead_time_days,
                MAX(po.order_date) as last_order_date
            FROM vendors v
            LEFT JOIN purchase_orders po ON v.vendor_code = po.vendor_code
            GROUP BY v.vendor_code, v.vendor_name
        """),

        # Index for mv_vendor_lead_times
        ("idx_mv_vendor_lead_times", """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_vendor_lead_times_key
            ON mv_vendor_lead_times(vendor_code)
        """),

        # mv_forecast_summary
        ("mv_forecast_summary", """
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
        """),

        # Index for mv_forecast_summary
        ("idx_mv_forecast_summary", """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_forecast_summary_key
            ON mv_forecast_summary(item_code)
        """),

        # mv_forecast_accuracy_summary
        ("mv_forecast_accuracy_summary", """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_accuracy_summary AS
            SELECT
                winning_model,
                COUNT(*) as item_count,
                AVG(mape) as avg_mape,
                AVG(rmse) as avg_rmse,
                AVG(bias) as avg_bias
            FROM forecast_accuracy
            GROUP BY winning_model
        """),

        # Index for mv_latest_costs
        ("idx_mv_latest_costs", """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_costs_key
            ON mv_latest_costs(item_code)
        """),

        # Index for mv_latest_pricing
        ("idx_mv_latest_pricing", """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key
            ON mv_latest_pricing(item_code, price_level, region_key)
        """),

        # v_inventory_status_with_forecast
        ("v_inventory_status_with_forecast", """
            CREATE OR REPLACE VIEW v_inventory_status_with_forecast AS
            SELECT
                ic.item_code,
                i.item_description,
                i.item_group,
                ic.warehouse_code,
                i.region,
                ic.on_hand_qty,
                ic.on_order_qty,
                ic.committed_qty,
                ic.available_qty,
                ic.uom,
                f.winning_model,
                f.forecast_confidence_pct,
                f.forecast_month_1,
                f.forecast_month_2,
                f.forecast_month_3,
                (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) AS forecast_3month_total,
                CASE
                    WHEN ic.available_qty < f.forecast_month_1 THEN 'Critical'
                    WHEN ic.available_qty < (f.forecast_month_1 + f.forecast_month_2) THEN 'High'
                    WHEN ic.available_qty < (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) THEN 'Medium'
                    ELSE 'Low'
                END AS shortage_urgency,
                p.unit_price as latest_list_price,
                c.total_landed_cost as latest_cost,
                (p.unit_price - c.total_landed_cost) as gross_margin_amt,
                CASE WHEN p.unit_price > 0
                    THEN ((p.unit_price - c.total_landed_cost) / p.unit_price) * 100
                    ELSE NULL
                END as gross_margin_pct,
                ic.updated_at as inventory_updated,
                f.forecast_generated_at as forecast_generated
            FROM inventory_current ic
            JOIN items i ON ic.item_code = i.item_code
            LEFT JOIN LATERAL (
                SELECT * FROM forecasts
                WHERE forecasts.item_code = ic.item_code
                AND forecasts.status = 'Active'
                ORDER BY forecast_generated_at DESC
                LIMIT 1
            ) f ON true
            LEFT JOIN LATERAL (
                SELECT * FROM mv_latest_pricing
                WHERE mv_latest_pricing.item_code = ic.item_code
                AND price_level = 'List'
                LIMIT 1
            ) p ON true
            LEFT JOIN LATERAL (
                SELECT * FROM mv_latest_costs
                WHERE mv_latest_costs.item_code = ic.item_code
                LIMIT 1
            ) c ON true
        """),

        # v_item_margins
        ("v_item_margins", """
            CREATE OR REPLACE VIEW v_item_margins AS
            SELECT
                i.item_code,
                i.item_description,
                i.item_group,
                p.price_level,
                p.region,
                p.unit_price as selling_price,
                c.unit_cost as purchase_price,
                c.total_landed_cost,
                (p.unit_price - c.total_landed_cost) as gross_margin_amt,
                CASE WHEN p.unit_price > 0
                    THEN ((p.unit_price - c.total_landed_cost) / p.unit_price) * 100
                    ELSE NULL
                END as gross_margin_pct,
                CASE WHEN c.total_landed_cost > 0
                    THEN ((p.unit_price - c.total_landed_cost) / c.total_landed_cost) * 100
                    ELSE NULL
                END as markup_pct,
                CASE
                    WHEN p.unit_price IS NULL THEN 'No Price'
                    WHEN c.total_landed_cost IS NULL THEN 'No Cost'
                    WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.40 THEN 'High (>=40%)'
                    WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.20 THEN 'Medium (20-40%)'
                    WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.00 THEN 'Low (0-20%)'
                    ELSE 'Negative (<0%)'
                END as margin_category,
                p.effective_date as price_effective_date,
                c.effective_date as cost_effective_date
            FROM items i
            LEFT JOIN LATERAL (
                SELECT * FROM mv_latest_pricing
                WHERE mv_latest_pricing.item_code = i.item_code
                AND price_level = 'List'
                LIMIT 1
            ) p ON true
            LEFT JOIN LATERAL (
                SELECT * FROM mv_latest_costs
                WHERE mv_latest_costs.item_code = i.item_code
                LIMIT 1
            ) c ON true
            WHERE i.is_active = TRUE
        """),
    ]

    engine = create_engine(database_url)

    for name, sql in statements:
        print(f"Creating {name}...")
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAILED] {name}: {e}")
            return False

    return True

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python apply_remaining_views.py <DATABASE_URL>")
        sys.exit(1)

    database_url = sys.argv[1]

    print("Applying remaining views...")
    success = apply_remaining_objects(database_url)

    if success:
        print("\n[SUCCESS] All views created successfully!")
    else:
        print("\n[FAILED] Some views failed")
        sys.exit(1)
