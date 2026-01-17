-- ============================================================================
-- Railway PostgreSQL Migration: Part 2 - Materialized Views
-- ============================================================================

-- Refresh materialized view: mv_latest_costs
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_costs AS
SELECT
    item_code,
    unit_cost,
    freight,
    duty,
    total_landed_cost,
    currency,
    vendor_code,
    effective_date
FROM costs c
WHERE effective_date = (
    SELECT MAX(effective_date)
    FROM costs
    WHERE item_code = c.item_code
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_costs_key ON mv_latest_costs(item_code);

-- Refresh materialized view: mv_latest_pricing
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_pricing AS
SELECT DISTINCT ON (item_code, price_level, region_key)
    item_code,
    price_level,
    region,
    unit_price,
    currency,
    effective_date,
    price_source
FROM pricing
WHERE is_active = TRUE
ORDER BY item_code, price_level, region_key, effective_date DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_pricing_key ON mv_latest_pricing(item_code, price_level, region_key);

-- Refresh materialized view: mv_vendor_lead_times
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_vendor_lead_times AS
SELECT
    v.vendor_code,
    v.vendor_name,
    COUNT(po.order_number) as total_orders,
    AVG(EXTRACT(DAY FROM (CURRENT_DATE - po.order_date))) as avg_lead_time_days,
    MAX(po.order_date) as last_order_date
FROM vendors v
LEFT JOIN purchase_orders po ON v.vendor_code = po.vendor_code
GROUP BY v.vendor_code, v.vendor_name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_vendor_lead_times_key ON mv_vendor_lead_times(vendor_code);

-- Refresh materialized view: mv_forecast_summary
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
WHERE f.status = 'Active';

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_forecast_summary_key ON mv_forecast_summary(item_code);

-- Refresh materialized view: mv_forecast_accuracy_summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_accuracy_summary AS
SELECT
    winning_model,
    COUNT(*) as item_count,
    AVG(mape) as avg_mape,
    AVG(rmse) as avg_rmse,
    AVG(bias) as avg_bias
FROM forecast_accuracy
GROUP BY winning_model;

PRINT 'Materialized views created successfully.';
