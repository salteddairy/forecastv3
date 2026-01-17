-- ============================================================================
-- Railway PostgreSQL Migration: Part 1 - Tables Only
-- SAP B1 Inventory & Forecast Analyzer
-- ============================================================================

-- ============================================================================
-- TABLE: warehouses
-- ============================================================================
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_code         VARCHAR(20) PRIMARY KEY,
    warehouse_name         VARCHAR(200) NOT NULL,
    region                 VARCHAR(100),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- TABLE: vendors
-- ============================================================================
CREATE TABLE IF NOT EXISTS vendors (
    vendor_code            VARCHAR(50) PRIMARY KEY,
    vendor_name            VARCHAR(500) NOT NULL,
    contact_name           VARCHAR(200),
    email                  VARCHAR(255),
    phone                  VARCHAR(50),
    reliability_score      NUMERIC(3,2),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- TABLE: items
-- ============================================================================
CREATE TABLE IF NOT EXISTS items (
    item_code              VARCHAR(50) PRIMARY KEY,
    item_description       VARCHAR(500) NOT NULL,
    item_group             VARCHAR(100),
    region                 VARCHAR(100),
    base_uom               VARCHAR(10) DEFAULT 'EA',
    purch_uom              VARCHAR(10) DEFAULT 'EA',
    qty_per_purch_uom      NUMERIC(10,3) DEFAULT 1,
    sales_uom              VARCHAR(10) DEFAULT 'EA',
    qty_per_sales_uom      NUMERIC(10,3) DEFAULT 1,
    preferred_vendor_code  VARCHAR(50) REFERENCES vendors(vendor_code),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- TABLE: inventory_current
-- ============================================================================
CREATE TABLE IF NOT EXISTS inventory_current (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    warehouse_code         VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_code) ON DELETE CASCADE,
    on_hand_qty            NUMERIC(12,3) NOT NULL DEFAULT 0,
    on_order_qty           NUMERIC(12,3) DEFAULT 0,
    committed_qty          NUMERIC(12,3) DEFAULT 0,
    available_qty          NUMERIC(12,3) NOT NULL DEFAULT 0,
    uom                    VARCHAR(10) DEFAULT 'EA',
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, warehouse_code)
);

-- ============================================================================
-- TABLE: sales_orders
-- ============================================================================
CREATE TABLE IF NOT EXISTS sales_orders (
    order_number           VARCHAR(50) NOT NULL,
    order_line_id          INTEGER NOT NULL,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    order_date             DATE NOT NULL,
    quantity               NUMERIC(12,3) NOT NULL,
    uom                    VARCHAR(10) DEFAULT 'EA',
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code) ON DELETE SET NULL,
    customer_code          VARCHAR(50),
    region                 VARCHAR(100),
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (order_number, order_line_id)
);

CREATE INDEX IF NOT EXISTS idx_sales_orders_item_date ON sales_orders(item_code, order_date DESC);

-- ============================================================================
-- TABLE: purchase_orders
-- ============================================================================
CREATE TABLE IF NOT EXISTS purchase_orders (
    order_number           VARCHAR(50) NOT NULL,
    order_line_id          INTEGER NOT NULL,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    order_date             DATE NOT NULL,
    quantity               NUMERIC(12,3) NOT NULL,
    uom                    VARCHAR(10) DEFAULT 'EA',
    vendor_code            VARCHAR(50) REFERENCES vendors(vendor_code) ON DELETE SET NULL,
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code) ON DELETE SET NULL,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (order_number, order_line_id)
);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_item_date ON purchase_orders(item_code, order_date DESC);

-- ============================================================================
-- TABLE: costs
-- ============================================================================
CREATE TABLE IF NOT EXISTS costs (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    effective_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    unit_cost              NUMERIC(12,4) NOT NULL,
    freight                NUMERIC(12,4) DEFAULT 0,
    duty                   NUMERIC(12,4) DEFAULT 0,
    total_landed_cost      NUMERIC(12,4) NOT NULL,
    currency               VARCHAR(3) DEFAULT 'CAD',
    vendor_code            VARCHAR(50) REFERENCES vendors(vendor_code) ON DELETE SET NULL,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, effective_date, vendor_code)
);

CREATE INDEX IF NOT EXISTS idx_costs_item_date ON costs(item_code, effective_date DESC);

-- ============================================================================
-- TABLE: pricing (without GENERATED column for compatibility)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pricing (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    price_level            VARCHAR(20) NOT NULL,
    region                 VARCHAR(50),
    region_key             VARCHAR(50) DEFAULT '',  -- Regular column instead of GENERATED
    unit_price             NUMERIC(12,4) NOT NULL,
    currency               VARCHAR(3) DEFAULT 'CAD',
    effective_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date            DATE,
    price_source           VARCHAR(50),
    sap_sync_timestamp     TIMESTAMPTZ,
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, price_level, region_key, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_pricing_item_code ON pricing(item_code, effective_date DESC);
CREATE INDEX IF NOT EXISTS idx_pricing_active ON pricing(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- TABLE: forecasts
-- ============================================================================
CREATE TABLE IF NOT EXISTS forecasts (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    forecast_generated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    forecast_horizon       INTEGER NOT NULL DEFAULT 3,
    winning_model          VARCHAR(50) NOT NULL,
    forecast_confidence_pct NUMERIC(5,2),
    status                 VARCHAR(20) DEFAULT 'Active',
    forecast_month_1       NUMERIC(12,3),
    forecast_month_2       NUMERIC(12,3),
    forecast_month_3       NUMERIC(12,3),
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, forecast_generated_at)
);

CREATE INDEX IF NOT EXISTS idx_forecasts_item ON forecasts(item_code, forecast_generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_status ON forecasts(status) WHERE status = 'Active';

-- ============================================================================
-- TABLE: forecast_accuracy
-- ============================================================================
CREATE TABLE IF NOT EXISTS forecast_accuracy (
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
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (item_code, forecast_generated_at, winning_model)
);

CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_item ON forecast_accuracy(item_code, forecast_generated_at DESC);

-- ============================================================================
-- TABLE: margin_alerts
-- ============================================================================
CREATE TABLE IF NOT EXISTS margin_alerts (
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    alert_type             VARCHAR(20) NOT NULL,
    current_margin_pct     NUMERIC(5,2),
    threshold_margin_pct   NUMERIC(5,2),
    price_level            VARCHAR(50),
    region                 VARCHAR(50),
    is_resolved            BOOLEAN DEFAULT FALSE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    resolved_at            TIMESTAMPTZ,
    PRIMARY KEY (item_code, alert_type, created_at)
);

CREATE INDEX IF NOT EXISTS idx_margin_alerts_resolved ON margin_alerts(is_resolved, created_at) WHERE is_resolved = FALSE;

PRINT 'Tables created successfully.';
