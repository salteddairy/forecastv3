-- ============================================================================
-- Railway PostgreSQL Migration: Part 3 - Views
-- ============================================================================

-- View: v_inventory_status_with_forecast
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
) c ON true;

-- View: v_item_margins
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
WHERE i.is_active = TRUE;

PRINT 'Views created successfully.';
