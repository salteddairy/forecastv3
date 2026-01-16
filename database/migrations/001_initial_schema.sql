-- ============================================================================
-- Railway PostgreSQL Migration: 001_initial_schema.sql
-- SAP B1 Inventory & Forecast Analyzer
-- Version: 1.0
-- Date: 2026-01-15
--
-- Description: Initial database schema with core tables for items, inventory,
--              sales, purchases, costs, pricing, and forecasts.
--
-- Estimated Storage: ~30 MB (well within Railway free tier of 1 GB)
-- ============================================================================

-- ============================================================================
-- TABLE: warehouses
-- ============================================================================
CREATE TABLE warehouses (
    warehouse_code         VARCHAR(20) PRIMARY KEY,
    warehouse_name         VARCHAR(200) NOT NULL,
    region                 VARCHAR(100),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE warehouses IS 'Warehouse and location definitions';
COMMENT ON COLUMN warehouses.warehouse_code IS 'SAP B1 warehouse code (OBWH.WhsCode)';

-- ============================================================================
-- TABLE: vendors
-- ============================================================================
CREATE TABLE vendors (
    vendor_code            VARCHAR(50) PRIMARY KEY,
    vendor_name            VARCHAR(500) NOT NULL,
    contact_name           VARCHAR(200),
    email                  VARCHAR(255),
    phone                  VARCHAR(50),
    reliability_score      NUMERIC(3,2),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE vendors IS 'Supplier master data from SAP B1 (OCRD)';
COMMENT ON COLUMN vendors.reliability_score IS 'Vendor performance metric (0-1), higher is better';

-- ============================================================================
-- TABLE: items
-- ============================================================================
CREATE TABLE items (
    item_code              VARCHAR(50) PRIMARY KEY,
    item_description       VARCHAR(500) NOT NULL,
    item_group             VARCHAR(100),
    region                 VARCHAR(50) NOT NULL DEFAULT 'Delta',
    base_uom               VARCHAR(20) NOT NULL,
    purch_uom              VARCHAR(20),
    qty_per_purch_uom      NUMERIC(10,3),
    sales_uom              VARCHAR(20),
    qty_per_sales_uom      NUMERIC(10,3),
    preferred_vendor_code  VARCHAR(50) REFERENCES vendors(vendor_code),
    last_vendor_code       VARCHAR(50) REFERENCES vendors(vendor_code),
    last_purchase_date     DATE,
    moq                    NUMERIC(12,3) DEFAULT 0,
    order_multiple         NUMERIC(12,3) DEFAULT 1,
    last_sale_date         DATE,
    is_active              BOOLEAN DEFAULT TRUE,
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_moq_positive CHECK (moq >= 0),
    CONSTRAINT chk_order_multiple_positive CHECK (order_multiple > 0)
);

CREATE INDEX idx_items_region ON items(region);
CREATE INDEX idx_items_item_group ON items(item_group);
CREATE INDEX idx_items_vendor ON items(preferred_vendor_code);
CREATE INDEX idx_items_last_sale ON items(last_sale_date DESC) WHERE last_sale_date IS NOT NULL;
CREATE INDEX idx_items_active ON items(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE items IS 'Master product catalog from SAP B1';
COMMENT ON COLUMN items.region IS 'Extracted from item code suffix (-CGY=Calgary, -DEL=Delta, etc.)';
COMMENT ON COLUMN items.moq IS 'Minimum Order Quantity from SAP B1';
COMMENT ON COLUMN items.order_multiple IS 'Order in multiples of this quantity';

-- ============================================================================
-- TABLE: inventory_current
-- ============================================================================
CREATE TABLE inventory_current (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    warehouse_code         VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_code),
    on_hand_qty            NUMERIC(12,3) NOT NULL DEFAULT 0,
    on_order_qty           NUMERIC(12,3) NOT NULL DEFAULT 0,
    committed_qty          NUMERIC(12,3) NOT NULL DEFAULT 0,
    available_qty          NUMERIC(12,3) GENERATED ALWAYS AS (
        on_hand_qty + on_order_qty - committed_qty
    ) STORED,
    uom                    VARCHAR(20) NOT NULL,
    unit_cost              NUMERIC(12,4),
    last_stock_movement    TIMESTAMPTZ,
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, warehouse_code),
    CONSTRAINT chk_inventory_non_negative CHECK (on_hand_qty >= 0)
);

CREATE INDEX idx_inventory_current_available ON inventory_current(available_qty)
    WHERE available_qty > 0;
CREATE INDEX idx_inventory_current_shortage ON inventory_current(available_qty)
    WHERE available_qty < 100;
CREATE INDEX idx_inventory_current_warehouse ON inventory_current(warehouse_code);

COMMENT ON TABLE inventory_current IS 'Current inventory levels from SAP B1 (OITW)';
COMMENT ON COLUMN inventory_current.on_order_qty IS 'Quantity on open purchase orders';
COMMENT ON COLUMN inventory_current.committed_qty IS 'Quantity allocated to sales orders';
COMMENT ON COLUMN inventory_current.available_qty IS 'Available for sale (on_hand + on_order - committed)';

-- ============================================================================
-- TABLE: costs
-- ============================================================================
CREATE TABLE costs (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    effective_date         DATE NOT NULL,
    vendor_code            VARCHAR(50) REFERENCES vendors(vendor_code),
    vendor_code_key        VARCHAR(50) GENERATED ALWAYS AS (COALESCE(vendor_code, '')) STORED,
    unit_cost              NUMERIC(12,4) NOT NULL,
    currency               VARCHAR(3) DEFAULT 'CAD',
    freight_per_unit       NUMERIC(12,4),
    duty_per_unit          NUMERIC(12,4),
    total_landed_cost      NUMERIC(12,4) GENERATED ALWAYS AS (
        unit_cost + COALESCE(freight_per_unit, 0) + COALESCE(duty_per_unit, 0)
    ) STORED,
    cost_source            VARCHAR(50),
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, effective_date, vendor_code_key),
    CONSTRAINT chk_costs_positive CHECK (unit_cost >= 0)
);

CREATE INDEX idx_costs_item_code_latest ON costs(item_code, effective_date DESC);

CREATE MATERIALIZED VIEW mv_latest_costs AS
SELECT DISTINCT ON (item_code)
    item_code,
    unit_cost,
    freight_per_unit,
    duty_per_unit,
    total_landed_cost,
    currency,
    effective_date,
    cost_source
FROM costs
ORDER BY item_code, effective_date DESC;

CREATE UNIQUE INDEX idx_mv_latest_costs_item ON mv_latest_costs(item_code);

COMMENT ON TABLE costs IS 'Purchase cost history for margin calculations';
COMMENT ON COLUMN costs.total_landed_cost IS 'Includes unit cost + freight + duty';
COMMENT ON MATERIALIZED VIEW mv_latest_costs IS 'Latest cost per item for real-time margin calculations';

-- ============================================================================
-- TABLE: pricing
-- ============================================================================
CREATE TABLE pricing (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    price_level            VARCHAR(20) NOT NULL,
    region                 VARCHAR(50),
    region_key             VARCHAR(50) GENERATED ALWAYS AS (COALESCE(region, '')) STORED,
    unit_price             NUMERIC(12,4) NOT NULL,
    currency               VARCHAR(3) DEFAULT 'CAD',
    effective_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date            DATE,
    price_source           VARCHAR(50),
    sap_sync_timestamp     TIMESTAMPTZ,
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, price_level, region_key, effective_date),
    CONSTRAINT chk_pricing_dates CHECK (expiry_date IS NULL OR expiry_date >= effective_date)
);

CREATE INDEX idx_pricing_item_code ON pricing(item_code, effective_date DESC);
CREATE INDEX idx_pricing_active ON pricing(is_active) WHERE is_active = TRUE;

CREATE MATERIALIZED VIEW mv_latest_pricing AS
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

CREATE UNIQUE INDEX idx_mv_latest_pricing_key ON mv_latest_pricing(item_code, price_level, region_key);

COMMENT ON TABLE pricing IS 'Sales price history from SAP B1 (ITM1, OPLN)';
COMMENT ON COLUMN pricing.price_level IS 'Price list code from SAP B1';
COMMENT ON MATERIALIZED VIEW mv_latest_pricing IS 'Latest active prices per item and price level';

-- ============================================================================
-- TABLE: sales_orders
-- ============================================================================
CREATE TABLE sales_orders (
    order_number           VARCHAR(50) NOT NULL,
    line_number            INTEGER NOT NULL,
    posting_date           DATE NOT NULL,
    promise_date           DATE,
    customer_code          VARCHAR(50),
    customer_name          VARCHAR(500),
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    item_description       VARCHAR(500),
    ordered_qty            NUMERIC(12,3) NOT NULL,
    shipped_qty            NUMERIC(12,3) DEFAULT 0,
    backlog_qty            NUMERIC(12,3) GENERATED ALWAYS AS (
        ordered_qty - shipped_qty
    ) STORED,
    row_value              NUMERIC(15,2),
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code),
    linked_special_order_num VARCHAR(50),
    is_linked_special_order BOOLEAN GENERATED ALWAYS AS (
        linked_special_order_num IS NOT NULL
    ) STORED,
    document_type          VARCHAR(20),
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (order_number, line_number),
    CONSTRAINT chk_sales_qty_positive CHECK (ordered_qty > 0)
);

CREATE INDEX idx_sales_orders_item_date ON sales_orders(item_code, posting_date DESC)
    WHERE NOT is_linked_special_order;
CREATE INDEX idx_sales_orders_date ON sales_orders(posting_date DESC);
CREATE INDEX idx_sales_orders_customer ON sales_orders(customer_code, posting_date DESC);
CREATE INDEX idx_sales_orders_backlog ON sales_orders(backlog_qty)
    WHERE backlog_qty > 0;

COMMENT ON TABLE sales_orders IS 'Sales order history from SAP B1 (ORDR, RDR1)';
COMMENT ON COLUMN sales_orders.is_linked_special_order IS 'TRUE = back-to-back order, exclude from demand forecast';
COMMENT ON COLUMN sales_orders.backlog_qty IS 'Unfulfilled quantity (open orders)';

-- ============================================================================
-- TABLE: purchase_orders
-- ============================================================================
CREATE TABLE purchase_orders (
    po_number              VARCHAR(50) NOT NULL,
    line_number            INTEGER NOT NULL,
    po_date                DATE NOT NULL,
    event_date             DATE,
    vendor_code            VARCHAR(50) NOT NULL REFERENCES vendors(vendor_code),
    vendor_name            VARCHAR(500),
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    ordered_qty            NUMERIC(12,3) NOT NULL,
    received_qty           NUMERIC(12,3) DEFAULT 0,
    open_qty               NUMERIC(12,3) GENERATED ALWAYS AS (
        ordered_qty - received_qty
    ) STORED,
    row_value              NUMERIC(15,2),
    currency               VARCHAR(3) DEFAULT 'CAD',
    exchange_rate          NUMERIC(10,6) DEFAULT 1.0,
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code),
    freight_terms          VARCHAR(20),
    fob                    VARCHAR(20),
    lead_time_days         INTEGER,
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (po_number, line_number),
    CONSTRAINT chk_po_qty_positive CHECK (ordered_qty > 0)
);

CREATE INDEX idx_purchase_orders_item_date ON purchase_orders(item_code, po_date DESC);
CREATE INDEX idx_purchase_orders_vendor_date ON purchase_orders(vendor_code, po_date DESC);
CREATE INDEX idx_purchase_orders_open ON purchase_orders(open_qty) WHERE open_qty > 0;

CREATE MATERIALIZED VIEW mv_vendor_lead_times AS
SELECT
    vendor_code,
    item_code,
    AVG(lead_time_days) as avg_lead_time_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lead_time_days) as median_lead_time_days,
    COUNT(*) as order_count
FROM purchase_orders
WHERE lead_time_days IS NOT NULL
GROUP BY vendor_code, item_code;

CREATE UNIQUE INDEX idx_mv_vendor_lead_times_key ON mv_vendor_lead_times(vendor_code, item_code);

COMMENT ON TABLE purchase_orders IS 'Purchase order history from SAP B1 (OPOR, POR1)';
COMMENT ON COLUMN purchase_orders.lead_time_days IS 'Actual days from PO to receipt (for forecasting)';
COMMENT ON MATERIALIZED VIEW mv_vendor_lead_times IS 'Vendor lead time statistics for safety stock calculations';

-- ============================================================================
-- TABLE: forecasts
-- ============================================================================
CREATE TABLE forecasts (
    forecast_id            BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    forecast_generated_at  TIMESTAMPTZ NOT NULL,
    winning_model          VARCHAR(50) NOT NULL,
    forecast_horizon       INTEGER NOT NULL,
    forecast_confidence_pct NUMERIC(5,2),
    history_months         INTEGER,
    train_months           INTEGER,
    test_months            INTEGER,
    avg_monthly_demand     NUMERIC(12,3),
    demand_cv              NUMERIC(10,2),
    forecast_month_1       NUMERIC(12,3),
    forecast_month_2       NUMERIC(12,3),
    forecast_month_3       NUMERIC(12,3),
    forecast_month_4       NUMERIC(12,3),
    forecast_month_5       NUMERIC(12,3),
    forecast_month_6       NUMERIC(12,3),
    forecast_month_7       NUMERIC(12,3),
    forecast_month_8       NUMERIC(12,3),
    forecast_month_9       NUMERIC(12,3),
    forecast_month_10      NUMERIC(12,3),
    forecast_month_11      NUMERIC(12,3),
    forecast_month_12      NUMERIC(12,3),
    rmse_sma               NUMERIC(10,2),
    rmse_holt_winters      NUMERIC(10,2),
    rmse_prophet           NUMERIC(10,2),
    rmse_arima             NUMERIC(10,2),
    rmse_sarimax           NUMERIC(10,2),
    rmse_theta             NUMERIC(10,2),
    forecast_period_start  DATE NOT NULL,
    status                 VARCHAR(20) DEFAULT 'Active',
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_forecast_horizon CHECK (forecast_horizon = 12),
    CONSTRAINT chk_forecast_status CHECK (status IN ('Active', 'Superseded'))
);

CREATE INDEX idx_forecasts_item_date ON forecasts(item_code, forecast_generated_at DESC);
CREATE INDEX idx_forecasts_status ON forecasts(status) WHERE status = 'Active';
CREATE UNIQUE INDEX idx_forecasts_active_item ON forecasts(item_code)
    WHERE status = 'Active';

CREATE MATERIALIZED VIEW mv_forecast_summary AS
SELECT
    item_code,
    forecast_generated_at,
    winning_model,
    forecast_confidence_pct,
    forecast_month_1,
    forecast_month_2,
    forecast_month_3,
    (forecast_month_1 + forecast_month_2 + forecast_month_3) as forecast_3month_total,
    avg_monthly_demand,
    demand_cv,
    forecast_period_start
FROM forecasts
WHERE status = 'Active';

CREATE UNIQUE INDEX idx_mv_forecast_summary_item ON mv_forecast_summary(item_code);

COMMENT ON TABLE forecasts IS '12-month demand forecast results from ML tournament';
COMMENT ON COLUMN forecasts.demand_cv IS 'Coefficient of variation (stddev/mean), higher = more volatile';
COMMENT ON COLUMN forecasts.rmse_prophet IS 'Root Mean Square Error for Prophet model during testing';
COMMENT ON MATERIALIZED VIEW mv_forecast_summary IS 'Latest active forecast per item for dashboard';

-- ============================================================================
-- TABLE: forecast_accuracy
-- ============================================================================
CREATE TABLE forecast_accuracy (
    accuracy_id            BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    forecast_generated_at  TIMESTAMPTZ NOT NULL,
    winning_model          VARCHAR(50) NOT NULL,
    forecast_confidence_pct NUMERIC(5,2),
    months_compared        INTEGER NOT NULL,
    forecast_horizon       INTEGER NOT NULL,
    mape                   NUMERIC(10,2),
    rmse                   NUMERIC(10,2),
    bias                   NUMERIC(12,3),
    mae                    NUMERIC(12,3),
    total_forecast         NUMERIC(12,3),
    total_actual           NUMERIC(12,3),
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_forecast_accuracy_item ON forecast_accuracy(item_code, forecast_generated_at DESC);

CREATE MATERIALIZED VIEW mv_forecast_accuracy_summary AS
SELECT
    winning_model,
    COUNT(*) as item_count,
    AVG(mape) as avg_mape,
    AVG(rmse) as avg_rmse,
    AVG(bias) as avg_bias
FROM forecast_accuracy
GROUP BY winning_model;

COMMENT ON TABLE forecast_accuracy IS 'Forecast vs actual comparison for model tuning';
COMMENT ON COLUMN forecast_accuracy.mape IS 'Mean Absolute Percentage Error (MAPE)';
COMMENT ON MATERIALIZED VIEW mv_forecast_accuracy_summary IS 'Per-item and per-model accuracy statistics';

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: v_inventory_status_with_forecast
CREATE VIEW v_inventory_status_with_forecast AS
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
    f.created_at as forecast_generated
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

COMMENT ON VIEW v_inventory_status_with_forecast IS 'Main dashboard view combining inventory, forecast, and margin data';

-- View: v_item_margins
CREATE VIEW v_item_margins AS
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

COMMENT ON VIEW v_item_margins IS 'Margin analysis by item (uses latest prices and costs)';
