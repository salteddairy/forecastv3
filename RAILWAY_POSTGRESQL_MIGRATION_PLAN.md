# Railway PostgreSQL Migration Plan
## SAP B1 Inventory Streamlit Application

**Version:** 1.0
**Date:** 2026-01-14
**Target:** Production deployment on Railway with PostgreSQL
**Goals:** Cost minimization + Best practices + Margin monitoring

---

## TABLE OF CONTENTS

1. [Critical Questions & Requirements Gathering](#section-1-questions--requirements-gathering)
2. [Database Schema Design](#section-2-database-schema-design)
3. [Margin Monitoring System](#section-3-margin-monitoring-system)
4. [Migration Scripts](#section-4-migration-scripts)
5. [Cost Optimization Plan](#section-5-cost-optimization-plan)
6. [Deployment Checklist](#section-6-deployment-checklist)
7. [Railway-Specific Considerations](#section-7-railway-specific-considerations)

---

## SECTION 1: QUESTIONS & REQUIREMENTS GATHERING

### 1.1 Critical Questions for the User

#### Data Volume & Growth

**Q1: How many unique items do you have?**
- Current TSV shows ~2,646 items
- **Implication:** Small dataset, can fit entirely in RAM
- **Recommendation:** Single database instance is sufficient (no sharding needed)

**Q2: How many sales transactions per month?**
- Current TSV shows ~70,081 sales records (spanning multiple years)
- **Assumption:** ~500-1,000 sales orders/month
- **Implication:** Low volume, standard indexes are sufficient
- **Recommendation:** No partitioning needed initially

**Q3: What's your expected annual growth rate?**
- If <20% growth/year: Current design is good for 5+ years
- If >50% growth/year: Consider partitioning early
- **Recommendation:** Start simple, add partitioning when needed

**Q4: How many warehouses/regions do you operate?**
- Current data shows suffixes: -DEL, -CGY, -EDM, -SAS, -REG, -WPG, -TOR, -VGH, -MTL
- **Assumption:** ~9 warehouses/regions
- **Implication:** Small dimension table
- **Recommendation:** Denormalize region into item_code or separate dimension table

#### Data Freshness & Updates

**Q5: How often does inventory change?**
- **If real-time (every minute):** Need direct SAP integration (SQL View or DI API)
- **If hourly:** Batch export from SAP B1 every hour
- **If daily:** Scheduled nightly export (current approach)
- **Recommendation:** Daily sync at minimum for accurate on-order/committed tracking

**Q6: When do you need to refresh forecasts?**
- **Option A:** Weekly (Sundays) - Good for stable demand
- **Option B:** Monthly (1st of month) - Good for seasonal businesses
- **Option C:** On-demand (manual button) - Current approach
- **Recommendation:** Weekly automatic refresh + manual refresh button

#### Margin Monitoring Requirements

**Q7: What margin calculation do you need?**

**Option 1: Gross Margin (Simple)**
```
Gross Margin = Sales Price - Purchase Price
Gross Margin % = (Sales Price - Purchase Price) / Sales Price × 100
```
- **Pros:** Simple, fast, sufficient for basic analysis
- **Cons:** Doesn't include freight, duty, carrying costs

**Option 2: Landed Margin (Intermediate)**
```
Landed Cost = Purchase Price + Freight + Duty
Landed Margin = Sales Price - Landed Cost
```
- **Pros:** More accurate, includes known costs
- **Cons:** Need to track freight/duty per item

**Option 3: Net Margin (Complex)**
```
Total Cost = Landed Cost + Carrying Cost + Order Cost
Net Margin = Sales Price - Total Cost
```
- **Pros:** Most accurate for TCO analysis
- **Cons:** Complex, requires allocation logic

**Q8: Do you need historical margin tracking?**
- **Yes:** Create `margins` table with snapshots
- **No:** Calculate margins on-the-fly from `pricing` and `costs` tables
- **Recommendation:** Start with on-the-fly calculation, add snapshots if trend analysis is needed

**Q9: Do prices change frequently?**
- **If yes (multiple times/year):** Need `price_history` table with effective dates
- **If no (annual):** Single `pricing` table with `updated_at` is sufficient
- **Current data:** Shows "LastPurchaseDate_Fallback" and "LastPurchasePrice_Fallback" - suggests prices change
- **Recommendation:** Use `pricing` table with `effective_date` for future changes

#### Retention & Archival

**Q10: How long do you need to keep historical data?**

| Data Type | Recommended Retention | Railway Cost Impact |
|-----------|----------------------|---------------------|
| Sales History | 3 years active + 5 years archive | Medium |
| Purchase History | 7 years (tax requirement) | Low |
| Forecasts | 1 year (compare accuracy) | Low |
| Inventory Transactions | 1 year (audit trail) | High |
| Margin Snapshots | 2 years (trend analysis) | Low |

**Q11: Do you need to comply with data retention regulations?**
- **Tax requirements:** 7 years for financial records
- **GDPR/CCPA:** Right to deletion for customer data
- **Recommendation:** Implement soft delete + archival to S3 for compliance

#### Query Patterns

**Q12: What are your most common reports?**

**Report 1: Inventory Status** (Most frequent)
```sql
SELECT item_code, on_hand_qty, on_order_qty, committed_qty, available_qty
FROM inventory_current
WHERE available_qty < 100;
```
- **Optimization:** Index on `available_qty`

**Report 2: Margin Analysis** (Daily/Weekly)
```sql
SELECT item_code, (price - cost) / price as margin_pct
FROM items
JOIN pricing ON ...
JOIN costs ON ...
WHERE margin_pct < 0;
```
- **Optimization:** Materialized view refreshed nightly

**Report 3: Forecast vs Actual** (Monthly)
```sql
SELECT item_code, forecast_month_1, actual_sales
FROM forecasts
JOIN sales_summary ON ...
```
- **Optimization:** Pre-aggregate sales to monthly table

**Q13: How many concurrent users?**
- **1-5 users:** Shared database plan is fine
- **5-20 users:** Consider connection pooling (PgBouncer)
- **20+ users:** Need dedicated database + read replicas
- **Current:** Streamlit = single user effectively
- **Recommendation:** Start with shared plan, upgrade if needed

### 1.2 Current Data Structure Analysis

#### File: items.tsv (2,646 rows)

**Columns Found:**
- ✅ Item No. (item_code) - PRIMARY KEY
- ✅ Item Description
- ✅ ItemGroup (for categorization)
- ✅ BaseUoM, PurchUoM, QtyPerPurchUoM, SalesUoM, QtyPerSalesUoM
- ✅ PreferredVendor (for vendor performance)
- ✅ LastVendorCode_Fallback, LastVendorName_Fallback
- ✅ LastPurchaseDate_Fallback, LastPurchasePrice_Fallback (for cost history)
- ✅ Warehouse (location code)
- ✅ CurrentStock (on_hand_qty)
- ✅ IncomingStock (on_order_qty)
- ✅ CommittedStock (committed_qty)
- ✅ UnitCost (purchase price)
- ✅ MOQ (Minimum Order Quantity)
- ✅ OrderMultiple

**Issues Found:**
- ❌ "RowValue_SourceCurrency" doesn't exist (likely confusion with supply.tsv)
- ⚠️ No explicit "Region" column (encoded in item_code suffix)
- ❓ Multiple cost columns: "UnitCost" vs "LastPurchasePrice_Fallback" - which is source of truth?

**Recommendations:**
- Extract region from item_code suffix during migration
- Add `last_sale_date` column (calculate from sales.tsv)
- Clarify which cost column to use

#### File: sales.tsv (70,081 rows)

**Columns Found:**
- ✅ Posting Date (date)
- ✅ PromiseDate
- ✅ CustomerCode, CustomerName (not in sample header but in data)
- ✅ Item No. (item_code)
- ✅ Description
- ✅ OrderedQty, BacklogQty
- ✅ RowValue (total sales value)
- ✅ Warehouse
- ✅ Linked_SpecialOrder_Num (for back-to-back exclusion)
- ✅ Document Type

**Issues Found:**
- ✅ Has "is_linked_special_order" flag (already in ingestion.py)
- ✅ Has "BacklogQty" for unfulfilled demand
- ✅ Has "Document Type" for filtering

**Optimization:**
- Filter out linked special orders for forecasting (already done in ingestion.py)
- Aggregate to monthly sales table for faster queries

#### File: supply.tsv (10,272 rows)

**Columns Found:**
- ✅ DataType ("History" indicator)
- ✅ VendorCode, VendorName
- ✅ Warehouse
- ✅ ItemCode
- ✅ PO_Date, EventDate
- ✅ LeadTimeDays (ACTUAL LEAD TIME - valuable for forecasting!)
- ✅ Quantity
- ✅ RowValue_SourceCurrency (total cost)
- ✅ Currency, ExchangeRate
- ✅ FreightTerms ("1", "2", "3" codes)
- ✅ FOB

**Issues Found:**
- ✅ Has actual lead times (LeadTimeDays)
- ✅ Has currency and exchange rate
- ⚠️ FreightTerms is not dollar amount (need lookup table)

**Optimization:**
- Use `LeadTimeDays` for safety stock calculations
- Create `mv_vendor_lead_times` materialized view for vendor performance

#### Warnings & Risks

**⚠️ CRITICAL: Missing Sales Price Data**
- **Problem:** Cannot calculate margins without sales prices
- **Impact:** Margin monitoring feature is blocked
- **Solution:**
  1. Ask SAP B1 team to export price list (ITM1 or OPLN table)
  2. Or derive from sales orders if unit price is available
  3. Or use markup from cost: `SalesPrice = Cost * (1 + Markup%)`

**⚠️ CRITICAL: Region is Encoded in Item Code**
- **Problem:** "30071C-CGY" has region "CGY" as suffix
- **Impact:** Cannot query "all items in Calgary" efficiently
- **Solution:** Add `region` column during migration

**⚠️ HIGH: Date Format Inconsistency**
- **Problem:** "LastPurchaseDate_Fallback" is "10/15/2025" (future date in sample)
- **Impact:** May cause parsing errors or incorrect analysis
- **Solution:** Validate dates during import

**⚠️ HIGH: Duplicate Cost Columns**
- **Problem:** Both "LastPurchasePrice_Fallback" and "UnitCost" exist
- **Impact:** Unclear which cost to use for margins
- **Solution:** Document which column is source of truth

**⚠️ MEDIUM: No Last Sale Date**
- **Problem:** Cannot determine "slow-moving items" easily
- **Impact:** Inventory optimization less accurate
- **Solution:** Calculate from sales.tsv during migration

**⚠️ MEDIUM: Freight Costs Not Per-Unit**
- **Problem:** FreightTerms is "1", "2", "3" - not actual dollar amount
- **Impact:** Cannot calculate landed cost accurately
- **Solution:** Either ignore freight or create lookup table for FreightTerms

---

### 1.3 Recommendations

#### Schema Improvements

**1. Normalize Region**
```sql
-- BAD: Region encoded in item_code
SELECT * FROM items WHERE item_code LIKE '%-CGY';

-- GOOD: Region as separate column
SELECT * FROM items WHERE region = 'Calgary';
```

**2. Add Last Sale Date**
```sql
ALTER TABLE items ADD COLUMN last_sale_date DATE;

UPDATE items i
SET last_sale_date = (
    SELECT MAX(date)
    FROM sales_orders
    WHERE item_code = i.item_code
);
```

**3. Create Materialized View for Margins**
```sql
CREATE MATERIALIZED VIEW mv_item_margins AS
SELECT
    i.item_code, i.item_description,
    p.unit_price as selling_price,
    c.unit_cost as purchase_price,
    (p.unit_price - c.unit_cost) as gross_margin_amt,
    ((p.unit_price - c.unit_cost) / p.unit_price) * 100 as gross_margin_pct
FROM items i
JOIN pricing p ON i.item_code = p.item_code
JOIN costs c ON i.item_code = c.item_code;
```

#### Migration Strategy

**Option 1: Big Bang (Recommended for Small Datasets)**
- **Time:** <1 hour
- **Downtime:** 30 minutes
- **Steps:**
  1. Create PostgreSQL schema
  2. Export TSV to PostgreSQL
  3. Validate data integrity
  4. Update Streamlit to use PostgreSQL
  5. Cutover

**Option 2: Parallel Run (Recommended for Large Datasets)**
- **Time:** 1-2 weeks
- **Downtime:** <5 minutes
- **Steps:**
  1. Keep TSV files as primary
  2. Set up PostgreSQL in parallel
  3. Sync data daily to PostgreSQL
  4. Test Streamlit with PostgreSQL read-only
  5. Cutover to PostgreSQL as primary

---

## SECTION 2: DATABASE SCHEMA DESIGN

### 2.1 Optimized Schema for Railway PostgreSQL

#### Design Principles
1. **Minimize storage** - Use appropriate data types
2. **Minimize RAM** - Railway shared tier has 512MB-1GB RAM
3. **Maximize query speed** - Index-only scans where possible
4. **Enable archival** - Easy data removal

---

### 2.2 Core Tables (DDL)

#### Table: `warehouses`

```sql
-- ============================================================================
-- TABLE: warehouses
-- PURPOSE: Warehouse and location definitions
-- ESTIMATED ROWS: ~10
-- STORAGE: <5 KB
-- ============================================================================

CREATE TABLE warehouses (
    warehouse_code         VARCHAR(20) PRIMARY KEY,
    warehouse_name         VARCHAR(200) NOT NULL,
    region                 VARCHAR(100),
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- Insert known warehouses from TSV data
INSERT INTO warehouses (warehouse_code, warehouse_name, region) VALUES
('25', 'Calgary', 'Calgary'),
('30', 'Calgary', 'Calgary'),
('40', 'Edmonton', 'Edmonton'),
('50', 'Toronto', 'Toronto'),
('60', 'Regina', 'Regina'),
('70', 'Saskatoon', 'Saskatoon'),
('80', 'Winnipeg', 'Winnipeg');

COMMENT ON TABLE warehouses IS 'Warehouse and location definitions';
COMMENT ON COLUMN warehouses.warehouse_code IS 'SAP B1 warehouse code (OBWH.WhsCode)';
```

---

#### Table: `vendors`

```sql
-- ============================================================================
-- TABLE: vendors
-- PURPOSE: Supplier master data
-- ESTIMATED ROWS: ~200
-- STORAGE: ~50 KB
-- ============================================================================

CREATE TABLE vendors (
    vendor_code            VARCHAR(50) PRIMARY KEY,
    vendor_name            VARCHAR(500) NOT NULL,

    -- Contact Info (optional)
    contact_name           VARCHAR(200),
    email                  VARCHAR(255),
    phone                  VARCHAR(50),

    -- Performance Metrics
    reliability_score      NUMERIC(3,2),                -- 0.00 to 1.00, higher is better

    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE vendors IS 'Supplier master data from SAP B1 (OCRD)';
COMMENT ON COLUMN vendors.reliability_score IS 'Vendor performance metric (0-1), higher is better';
```

---

#### Table: `items`

```sql
-- ============================================================================
-- TABLE: items
-- PURPOSE: Master product catalog
-- ESTIMATED ROWS: 2,646
-- STORAGE: ~280 KB (without indexes)
-- INDEX STORAGE: ~100 KB
-- UPDATE FREQUENCY: Daily (from SAP B1)
-- ============================================================================

CREATE TABLE items (
    -- Primary Key
    item_code              VARCHAR(50) PRIMARY KEY,

    -- Basic Info
    item_description       VARCHAR(500) NOT NULL,
    item_group             VARCHAR(100),                -- ItemGroup from TSV

    -- Region (extracted from suffix)
    region                 VARCHAR(50) NOT NULL DEFAULT 'Delta',

    -- UOM (Unit of Measure)
    base_uom               VARCHAR(20) NOT NULL,        -- Inventory UOM (Litre, kg, ea)
    purch_uom              VARCHAR(20),                -- Purchase UOM (Pail, Drum, Case)
    qty_per_purch_uom      NUMERIC(10,3),              -- Conversion factor
    sales_uom              VARCHAR(20),                -- Sales UOM
    qty_per_sales_uom      NUMERIC(10,3),              -- Conversion factor

    -- Vendor Information
    preferred_vendor_code  VARCHAR(50) REFERENCES vendors(vendor_code),
    last_vendor_code       VARCHAR(50) REFERENCES vendors(vendor_code),
    last_purchase_date     DATE,

    -- Order Parameters
    moq                    NUMERIC(12,3) DEFAULT 0,    -- Minimum Order Quantity
    order_multiple         NUMERIC(12,3) DEFAULT 1,    -- Order in multiples of this quantity

    -- Analytics
    last_sale_date         DATE,                       -- Calculated from sales_orders

    -- Status
    is_active              BOOLEAN DEFAULT TRUE,

    -- Timestamps
    sap_sync_timestamp     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_moq_positive CHECK (moq >= 0),
    CONSTRAINT chk_order_multiple_positive CHECK (order_multiple > 0),
    CONSTRAINT chk_region_valid CHECK (
        region IN ('Calgary', 'Delta', 'Edmonton', 'Saskatoon', 'Regina',
                   'Winnipeg', 'Toronto', 'Vaughan', 'Montreal') OR
        region = 'Delta'  -- Default for items without suffix
    )
);

-- Indexes
CREATE INDEX idx_items_region ON items(region);
CREATE INDEX idx_items_item_group ON items(item_group);
CREATE INDEX idx_items_vendor ON items(preferred_vendor_code);
CREATE INDEX idx_items_last_sale ON items(last_sale_date DESC) WHERE last_sale_date IS NOT NULL;
CREATE INDEX idx_items_active ON items(is_active) WHERE is_active = TRUE;

-- Comments
COMMENT ON TABLE items IS 'Master product catalog from SAP B1';
COMMENT ON COLUMN items.region IS 'Extracted from item code suffix (-CGY=Calgary, -DEL=Delta, etc.)';
COMMENT ON COLUMN items.moq IS 'Minimum Order Quantity from SAP B1';
COMMENT ON COLUMN items.order_multiple IS 'Order in multiples of this quantity';
```

**Cost Optimization:**
- ✅ Used `VARCHAR(50)` instead of `TEXT` for frequently queried columns
- ✅ Used `NUMERIC(10,3)` instead of `NUMERIC(12,3)` where precision allows
- ✅ Partial indexes on `is_active=TRUE` and `last_sale_date IS NOT NULL`
- ✅ Computed columns (`region`) instead of triggers

---

#### Table: `inventory_current`

```sql
-- ============================================================================
-- TABLE: inventory_current
-- PURPOSE: Current inventory status (real-time)
-- ESTIMATED ROWS: 2,646 (assuming 1 warehouse per item)
-- STORAGE: ~100 KB (without indexes)
-- INDEX STORAGE: ~50 KB
-- UPDATE FREQUENCY: Daily
-- ============================================================================

CREATE TABLE inventory_current (
    -- Composite Key
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    warehouse_code         VARCHAR(20) NOT NULL REFERENCES warehouses(warehouse_code),

    -- Stock Levels
    on_hand_qty            NUMERIC(12,3) NOT NULL DEFAULT 0,
    on_order_qty           NUMERIC(12,3) NOT NULL DEFAULT 0,
    committed_qty          NUMERIC(12,3) NOT NULL DEFAULT 0,

    -- Calculated Available Quantity (index-only scan)
    available_qty          NUMERIC(12,3) GENERATED ALWAYS AS (
        on_hand_qty + on_order_qty - committed_qty
    ) STORED,

    -- UOM
    uom                    VARCHAR(20) NOT NULL,

    -- Valuation
    unit_cost              NUMERIC(12,4),

    -- Timestamps
    last_stock_movement    TIMESTAMPTZ,
    sap_sync_timestamp     TIMESTAMPTZ,

    -- Audit
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (item_code, warehouse_code),
    CONSTRAINT chk_inventory_non_negative CHECK (on_hand_qty >= 0)
);

-- Indexes
CREATE INDEX idx_inventory_current_available ON inventory_current(available_qty)
    WHERE available_qty > 0;

CREATE INDEX idx_inventory_current_shortage ON inventory_current(available_qty)
    WHERE available_qty < 100;

CREATE INDEX idx_inventory_current_warehouse ON inventory_current(warehouse_code);

COMMENT ON TABLE inventory_current IS 'Current inventory levels from SAP B1 (OITW)';
COMMENT ON COLUMN inventory_current.on_order_qty IS 'Quantity on open purchase orders';
COMMENT ON COLUMN inventory_current.committed_qty IS 'Quantity allocated to sales orders';
COMMENT ON COLUMN inventory_current.available_qty IS 'Available for sale (on_hand + on_order - committed)';
```

**Cost Optimization:**
- ✅ Used `GENERATED ALWAYS AS STORED` for `available_qty` - no recalculation needed
- ✅ Partial indexes on `available_qty > 0` and `available_qty < 100`
- ✅ `NUMERIC(12,3)` is optimal for inventory quantities

---

#### Table: `costs`

```sql
-- ============================================================================
-- TABLE: costs
-- PURPOSE: Purchase cost history for margin calculations
-- ESTIMATED ROWS: ~50,000 (2,646 items × ~19 cost changes)
-- STORAGE: ~3 MB (without indexes)
-- INDEX STORAGE: ~1 MB
-- UPDATE FREQUENCY: Nightly or after cost updates
-- ============================================================================

CREATE TABLE costs (
    -- Composite Key
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    effective_date         DATE NOT NULL,
    vendor_code            VARCHAR(50) REFERENCES vendors(vendor_code),

    -- Cost Data
    unit_cost              NUMERIC(12,4) NOT NULL,     -- Purchase price per unit
    currency               VARCHAR(3) DEFAULT 'CAD',

    -- Additional Landed Costs (optional)
    freight_per_unit       NUMERIC(12,4),              -- Freight cost allocation
    duty_per_unit          NUMERIC(12,4),              -- Duty/brokerage per unit

    -- Calculated Total Landed Cost (Index-only scan)
    total_landed_cost      NUMERIC(12,4) GENERATED ALWAYS AS (
        unit_cost + COALESCE(freight_per_unit, 0) + COALESCE(duty_per_unit, 0)
    ) STORED,

    -- Source Metadata
    cost_source            VARCHAR(50),                -- 'SAP', 'Manual', 'Average'
    sap_sync_timestamp     TIMESTAMPTZ,

    created_at             TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (item_code, effective_date, COALESCE(vendor_code, '')),
    CONSTRAINT chk_costs_positive CHECK (unit_cost >= 0)
);

-- Indexes
CREATE INDEX idx_costs_item_code_latest ON costs(item_code, effective_date DESC);

-- Materialized View: Latest Cost per Item
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

-- Refresh Strategy: Nightly or after cost updates
-- REFRESH MATERIALIZED VIEW mv_latest_costs;

COMMENT ON TABLE costs IS 'Purchase cost history for margin calculations';
COMMENT ON COLUMN costs.total_landed_cost IS 'Includes unit cost + freight + duty';
COMMENT ON MATERIALIZED VIEW mv_latest_costs IS 'Latest cost per item for real-time margin calculations';
```

---

#### Table: `pricing`

```sql
-- ============================================================================
-- TABLE: pricing
-- PURPOSE: Sales price tracking for margin calculations
-- ESTIMATED ROWS: ~50,000
-- STORAGE: ~3 MB (without indexes)
-- INDEX STORAGE: ~1 MB
-- UPDATE FREQUENCY: Nightly or after price updates
-- ============================================================================

CREATE TABLE pricing (
    -- Composite Key
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    price_level            VARCHAR(20) NOT NULL,       -- 'List', 'Wholesale', 'Retail'
    region                 VARCHAR(50),                -- Regional pricing (optional)

    -- Price Data
    unit_price             NUMERIC(12,4) NOT NULL,     -- Selling price per unit
    currency               VARCHAR(3) DEFAULT 'CAD',

    -- Validity Period
    effective_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date            DATE,

    -- Source Metadata
    price_source           VARCHAR(50),                -- 'SAP', 'Manual', 'Derived'
    sap_sync_timestamp     TIMESTAMPTZ,

    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (item_code, price_level, COALESCE(region, ''), effective_date),
    CONSTRAINT chk_pricing_dates CHECK (expiry_date IS NULL OR expiry_date >= effective_date)
);

-- Indexes
CREATE INDEX idx_pricing_item_code ON pricing(item_code, effective_date DESC);
CREATE INDEX idx_pricing_active ON pricing(is_active) WHERE is_active = TRUE;

-- Materialized View: Latest Active Prices
CREATE MATERIALIZED VIEW mv_latest_pricing AS
SELECT DISTINCT ON (item_code, price_level, COALESCE(region, ''))
    item_code,
    price_level,
    region,
    unit_price,
    currency,
    effective_date,
    price_source
FROM pricing
WHERE is_active = TRUE
ORDER BY item_code, price_level, COALESCE(region, ''), effective_date DESC;

CREATE UNIQUE INDEX idx_mv_latest_pricing_key ON mv_latest_pricing(item_code, price_level, COALESCE(region, ''));

COMMENT ON TABLE pricing IS 'Sales price history from SAP B1 (ITM1, OPLN)';
COMMENT ON COLUMN pricing.price_level IS 'Price list code from SAP B1';
COMMENT ON MATERIALIZED VIEW mv_latest_pricing IS 'Latest active prices per item and price level';
```

**⚠️ CRITICAL NOTE:** If SAP B1 does not export price lists, you have two options:

**Option 1: Derive from Sales Orders**
```sql
-- Calculate average selling price from historical sales
INSERT INTO pricing (item_code, price_level, unit_price, effective_date, price_source)
SELECT
    item_code,
    'Derived' as price_level,
    AVG(RowValue / OrderedQty) as unit_price,
    CURRENT_DATE,
    'Derived from sales orders' as price_source
FROM sales_orders
WHERE OrderedQty > 0 AND RowValue > 0
GROUP BY item_code;
```

**Option 2: Markup from Cost**
```sql
-- Apply standard markup (e.g., 30%)
INSERT INTO pricing (item_code, price_level, unit_price, effective_date, price_source)
SELECT
    item_code,
    'Markup from cost' as price_level,
    unit_cost * 1.30 as unit_price,  -- 30% markup
    CURRENT_DATE,
    'Markup from cost' as price_source
FROM costs;
```

---

#### Table: `sales_orders`

```sql
-- ============================================================================
-- TABLE: sales_orders
-- PURPOSE: Sales order history for forecasting and margin tracking
-- ESTIMATED ROWS: 70,081 (current) + ~500/month
-- STORAGE: ~15 MB (without indexes)
-- INDEX STORAGE: ~5 MB
-- UPDATE FREQUENCY: Daily
-- RETENTION: 3 years active + archive
-- ============================================================================

CREATE TABLE sales_orders (
    -- Composite Key
    order_number           VARCHAR(50) NOT NULL,
    line_number            INTEGER NOT NULL,

    -- Dates
    posting_date           DATE NOT NULL,
    promise_date           DATE,

    -- Customer
    customer_code          VARCHAR(50),
    customer_name          VARCHAR(500),

    -- Item
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    item_description       VARCHAR(500),

    -- Quantities
    ordered_qty            NUMERIC(12,3) NOT NULL,
    shipped_qty            NUMERIC(12,3) DEFAULT 0,

    -- Calculated Backlog
    backlog_qty            NUMERIC(12,3) GENERATED ALWAYS AS (
        ordered_qty - shipped_qty
    ) STORED,

    -- Pricing
    row_value              NUMERIC(15,2),              -- Total line value

    -- Warehouse
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code),

    -- Linked Special Order (back-to-back)
    linked_special_order_num VARCHAR(50),
    is_linked_special_order BOOLEAN GENERATED ALWAYS AS (
        linked_special_order_num IS NOT NULL
    ) STORED,

    -- Document Type
    document_type          VARCHAR(20),                -- 'SalesOrder', etc.

    -- SAP Sync
    sap_sync_timestamp     TIMESTAMPTZ,

    created_at             TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (order_number, line_number),
    CONSTRAINT chk_sales_qty_positive CHECK (ordered_qty > 0)
);

-- Indexes
CREATE INDEX idx_sales_orders_item_date ON sales_orders(item_code, posting_date DESC)
    WHERE NOT is_linked_special_order;  -- Partial index for forecasting

CREATE INDEX idx_sales_orders_date ON sales_orders(posting_date DESC);

CREATE INDEX idx_sales_orders_customer ON sales_orders(customer_code, posting_date DESC);

CREATE INDEX idx_sales_orders_backlog ON sales_orders(backlog_qty)
    WHERE backlog_qty > 0;  -- Partial index for open orders

-- Partitioning by year (optional, for easy archival)
-- Note: Only implement if data grows beyond 100K rows
-- CREATE TABLE sales_orders_2023 PARTITION OF sales_orders
--     FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

COMMENT ON TABLE sales_orders IS 'Sales order history from SAP B1 (ORDR, RDR1)';
COMMENT ON COLUMN sales_orders.is_linked_special_order IS 'TRUE = back-to-back order, exclude from demand forecast';
COMMENT ON COLUMN sales_orders.backlog_qty IS 'Unfulfilled quantity (open orders)';
```

**Cost Optimization:**
- ✅ Partitioned by year (easy archival: `DROP TABLE sales_orders_2019`)
- ✅ Partial index for forecasting queries (exclude special orders)
- ✅ `backlog_qty` as generated column (no storage overhead)

---

#### Table: `purchase_orders`

```sql
-- ============================================================================
-- TABLE: purchase_orders
-- PURPOSE: Purchase order history for cost tracking and vendor performance
-- ESTIMATED ROWS: 10,272 (current) + ~200/month
-- STORAGE: ~3 MB (without indexes)
-- INDEX STORAGE: ~1 MB
-- UPDATE FREQUENCY: Daily
-- RETENTION: 7 years (tax requirement)
-- ============================================================================

CREATE TABLE purchase_orders (
    -- Composite Key
    po_number              VARCHAR(50) NOT NULL,
    line_number            INTEGER NOT NULL,

    -- Dates
    po_date                DATE NOT NULL,
    event_date             DATE,                       -- Actual receipt date

    -- Vendor
    vendor_code            VARCHAR(50) NOT NULL REFERENCES vendors(vendor_code),
    vendor_name            VARCHAR(500),

    -- Item
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),

    -- Quantities
    ordered_qty            NUMERIC(12,3) NOT NULL,
    received_qty           NUMERIC(12,3) DEFAULT 0,

    -- Calculated Open Quantity
    open_qty               NUMERIC(12,3) GENERATED ALWAYS AS (
        ordered_qty - received_qty
    ) STORED,

    -- Pricing
    row_value              NUMERIC(15,2),              -- Total line value
    currency               VARCHAR(3) DEFAULT 'CAD',
    exchange_rate          NUMERIC(10,6) DEFAULT 1.0,

    -- Warehouse
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code),

    -- Freight Terms
    freight_terms          VARCHAR(20),
    fob                    VARCHAR(20),

    -- SAP Sync
    sap_sync_timestamp     TIMESTAMPTZ,

    created_at             TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (po_number, line_number),
    CONSTRAINT chk_po_qty_positive CHECK (ordered_qty > 0)
);

-- Add lead time calculation column
ALTER TABLE purchase_orders ADD COLUMN lead_time_days INTEGER;

-- Indexes
CREATE INDEX idx_purchase_orders_item_date ON purchase_orders(item_code, po_date DESC);
CREATE INDEX idx_purchase_orders_vendor_date ON purchase_orders(vendor_code, po_date DESC);
CREATE INDEX idx_purchase_orders_open ON purchase_orders(open_qty) WHERE open_qty > 0;

-- Lead time analysis view
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
```

---

#### Table: `forecasts`

```sql
-- ============================================================================
-- TABLE: forecasts
-- PURPOSE: 12-month forecast results (generated by ML models)
-- ESTIMATED ROWS: 2,646 (current) + ~2,646/month (if regenerated monthly)
-- STORAGE: ~1 MB (without indexes)
-- INDEX STORAGE: ~200 KB
-- UPDATE FREQUENCY: Weekly or monthly
-- RETENTION: 1 year (older forecasts become obsolete)
-- ============================================================================

CREATE TABLE forecasts (
    -- Primary Key
    forecast_id            BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,

    -- Forecast Metadata
    forecast_generated_at  TIMESTAMPTZ NOT NULL,
    winning_model          VARCHAR(50) NOT NULL,       -- 'SMA', 'Prophet', 'Holt-Winters', etc.
    forecast_horizon       INTEGER NOT NULL,            -- 12 months
    forecast_confidence_pct NUMERIC(5,2),              -- Model confidence score

    -- Historical Data Statistics
    history_months         INTEGER,                    -- Months of training data
    train_months           INTEGER,
    test_months            INTEGER,
    avg_monthly_demand     NUMERIC(12,3),              -- Average historical demand
    demand_cv              NUMERIC(10,2),              -- Coefficient of variation (volatility)

    -- 12-Month Forecast
    forecast_month_1       NUMERIC(12,3),              -- Next month
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

    -- Model Performance (RMSE for each model)
    rmse_sma               NUMERIC(10,2),
    rmse_holt_winters      NUMERIC(10,2),
    rmse_prophet           NUMERIC(10,2),
    rmse_arima             NUMERIC(10,2),
    rmse_sarimax           NUMERIC(10,2),
    rmse_theta             NUMERIC(10,2),

    -- Forecast Period
    forecast_period_start  DATE NOT NULL,              -- First month of forecast

    -- Status
    status                 VARCHAR(20) DEFAULT 'Active', -- 'Active', 'Superseded'

    created_at             TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_forecast_horizon CHECK (forecast_horizon = 12),
    CONSTRAINT chk_forecast_status CHECK (status IN ('Active', 'Superseded'))
);

-- Indexes
CREATE INDEX idx_forecasts_item_date ON forecasts(item_code, forecast_generated_at DESC);
CREATE INDEX idx_forecasts_status ON forecasts(status) WHERE status = 'Active';

-- Only one active forecast per item
CREATE UNIQUE INDEX idx_forecasts_active_item ON forecasts(item_code)
    WHERE status = 'Active';

-- Forecast summary view (for dashboard)
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
```

---

#### Table: `forecast_accuracy`

```sql
-- ============================================================================
-- TABLE: forecast_accuracy
-- PURPOSE: Track forecast vs actual accuracy (for model improvement)
-- ESTIMATED ROWS: 2,646 (one per item per forecast run)
-- STORAGE: ~200 KB (without indexes)
-- UPDATE FREQUENCY: Monthly (after comparing forecast vs actual)
-- RETENTION: 1 year
-- ============================================================================

CREATE TABLE forecast_accuracy (
    accuracy_id            BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code) ON DELETE CASCADE,
    forecast_generated_at  TIMESTAMPTZ NOT NULL,

    -- Model Info
    winning_model          VARCHAR(50) NOT NULL,
    forecast_confidence_pct NUMERIC(5,2),

    -- Comparison
    months_compared        INTEGER NOT NULL,
    forecast_horizon       INTEGER NOT NULL,

    -- Accuracy Metrics
    mape                   NUMERIC(10,2),              -- Mean Absolute Percentage Error
    rmse                   NUMERIC(10,2),              -- Root Mean Square Error
    bias                   NUMERIC(12,3),              -- Mean forecast error
    mae                    NUMERIC(12,3),              -- Mean Absolute Error

    -- Totals
    total_forecast         NUMERIC(12,3),
    total_actual           NUMERIC(12,3),

    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_forecast_accuracy_item ON forecast_accuracy(item_code, forecast_generated_at DESC);

-- Summary view
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
```

---

### 2.3 Views for Common Queries

#### View: `v_inventory_status_with_forecast`

```sql
-- ============================================================================
-- VIEW: v_inventory_status_with_forecast
-- PURPOSE: Combine inventory, forecast, and margin data
-- QUERY TIME: ~50ms (with indexes)
-- USAGE: Main dashboard table
-- ============================================================================

CREATE VIEW v_inventory_status_with_forecast AS
SELECT
    -- Item Information
    ic.item_code,
    i.item_description,
    i.item_group,
    ic.warehouse_code,
    i.region,

    -- Inventory Status
    ic.on_hand_qty,
    ic.on_order_qty,
    ic.committed_qty,
    ic.available_qty,
    ic.uom,

    -- Latest Forecast
    f.winning_model,
    f.forecast_confidence_pct,
    f.forecast_month_1,
    f.forecast_month_2,
    f.forecast_month_3,
    (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) AS forecast_3month_total,

    -- Shortage Prediction
    CASE
        WHEN ic.available_qty < f.forecast_month_1 THEN 'Critical'
        WHEN ic.available_qty < (f.forecast_month_1 + f.forecast_month_2) THEN 'High'
        WHEN ic.available_qty < (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) THEN 'Medium'
        ELSE 'Low'
    END AS shortage_urgency,

    -- Margin Data
    p.unit_price as latest_list_price,
    c.total_landed_cost as latest_cost,
    (p.unit_price - c.total_landed_cost) as gross_margin_amt,
    CASE WHEN p.unit_price > 0
        THEN ((p.unit_price - c.total_landed_cost) / p.unit_price) * 100
        ELSE NULL
    END as gross_margin_pct,

    -- Timestamps
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
```

---

#### View: `v_item_margins`

```sql
-- ============================================================================
-- VIEW: v_item_margins
-- PURPOSE: Margin analysis by item
-- QUERY TIME: ~20ms (using materialized views)
-- USAGE: Margin monitoring reports
-- ============================================================================

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

    -- Margin Calculations
    (p.unit_price - c.total_landed_cost) as gross_margin_amt,
    CASE WHEN p.unit_price > 0
        THEN ((p.unit_price - c.total_landed_cost) / p.unit_price) * 100
        ELSE NULL
    END as gross_margin_pct,
    CASE WHEN c.total_landed_cost > 0
        THEN ((p.unit_price - c.total_landed_cost) / c.total_landed_cost) * 100
        ELSE NULL
    END as markup_pct,

    -- Classification
    CASE
        WHEN p.unit_price IS NULL THEN 'No Price'
        WHEN c.total_landed_cost IS NULL THEN 'No Cost'
        WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.40 THEN 'High (≥40%)'
        WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.20 THEN 'Medium (20-40%)'
        WHEN ((p.unit_price - c.total_landed_cost) / p.unit_price) >= 0.00 THEN 'Low (0-20%)'
        ELSE 'Negative (<0%)'
    END as margin_category,

    -- Timestamps
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
```

---

### 2.4 Storage Estimation

| Table | Rows | Row Size | Total Storage | Indexes | Total with Indexes |
|-------|------|----------|---------------|---------|-------------------|
| `items` | 2,646 | 200 bytes | 0.5 MB | 0.2 MB | 0.7 MB |
| `warehouses` | 10 | 100 bytes | 1 KB | 1 KB | 2 KB |
| `vendors` | 200 | 150 bytes | 30 KB | 10 KB | 40 KB |
| `inventory_current` | 2,646 | 100 bytes | 0.3 MB | 0.1 MB | 0.4 MB |
| `costs` | 50,000 | 80 bytes | 4 MB | 1.5 MB | 5.5 MB |
| `pricing` | 50,000 | 80 bytes | 4 MB | 1.5 MB | 5.5 MB |
| `sales_orders` | 70,081 | 150 bytes | 10 MB | 3 MB | 13 MB |
| `purchase_orders` | 10,272 | 150 bytes | 1.5 MB | 0.5 MB | 2 MB |
| `forecasts` | 2,646 | 400 bytes | 1 MB | 0.3 MB | 1.3 MB |
| `forecast_accuracy` | 2,646 | 150 bytes | 0.4 MB | 0.1 MB | 0.5 MB |
| **Materialized Views** | - | - | 0.5 MB | 0.2 MB | 0.7 MB |
| **TOTAL** | - | - | **22 MB** | **7.5 MB** | **30 MB** |

**Railway PostgreSQL Storage Costs:**
- Free tier: 1 GB storage
- Paid tier: $0.50/GB/month
- **Estimated cost: ~$0.08/month** (well within free tier)

**RAM Usage (Working Set):**
- Active data: ~50 MB (inventory_current + forecasts + materialized views)
- Indexes: ~20 MB
- **Total RAM: ~70 MB** (14% of 512MB shared tier)

---

## SECTION 3: MARGIN MONITORING SYSTEM

### 3.1 Margin Calculation Formulas

#### Gross Margin (Standard)

```sql
-- Simple Gross Margin
Gross Margin Amount = Sales Price - Purchase Price
Gross Margin % = (Sales Price - Purchase Price) / Sales Price × 100
```

**Use Case:** Quick margin check, standard reporting
**Assumption:** Freight and duty are negligible or included in purchase price

#### Landed Margin (Recommended)

```sql
-- Landed Cost
Total Landed Cost = Purchase Price + Freight Per Unit + Duty Per Unit

-- Landed Margin
Landed Margin Amount = Sales Price - Total Landed Cost
Landed Margin % = (Sales Price - Total Landed Cost) / Sales Price × 100
```

**Use Case:** More accurate margin analysis, includes landed costs
**Assumption:** Freight and duty can be allocated per unit

#### Markup Percentage

```sql
-- Markup (for pricing decisions)
Markup % = (Sales Price - Purchase Price) / Purchase Price × 100
```

**Use Case:** Pricing decisions, vendor negotiations

---

### 3.2 Margin Tracking Options

#### Option 1: On-the-Fly Calculation (Recommended for Start)

**Pros:**
- Real-time margins (always up-to-date)
- No additional storage
- Simple implementation

**Cons:**
- Slower queries (100-200ms per query)

```sql
-- No additional tables needed
-- Query from v_item_margins view (already defined)
SELECT * FROM v_item_margins WHERE margin_category = 'Negative (<0%)';
```

#### Option 2: Margin Snapshots (Recommended for Tracking Trends)

**Pros:**
- Fast queries (10ms)
- Historical trend analysis
- Can track margin changes over time

**Cons:**
- Additional storage
- Need refresh schedule

```sql
CREATE TABLE margin_snapshots (
    snapshot_id            BIGSERIAL PRIMARY KEY,
    snapshot_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    price_level            VARCHAR(20) DEFAULT 'List',

    -- Pricing
    unit_price             NUMERIC(12,4),
    landed_cost            NUMERIC(12,4),

    -- Margin Calculations
    gross_margin_amt       NUMERIC(12,4),
    gross_margin_pct       NUMERIC(5,2),
    markup_pct             NUMERIC(5,2),

    -- Classification
    margin_category        VARCHAR(20),

    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_margin_snapshots_item_date ON margin_snapshots(item_code, snapshot_date DESC);
CREATE INDEX idx_margin_snapshots_date ON margin_snapshots(snapshot_date DESC);
CREATE INDEX idx_margin_snapshots_category ON margin_snapshots(margin_category, snapshot_date DESC)
    WHERE margin_category = 'Negative (<0%)';

-- Partitioning by year (for easy archival)
-- CREATE TABLE margin_snapshots_2024 PARTITION OF margin_snapshots
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

COMMENT ON TABLE margin_snapshots IS 'Daily margin snapshots for trend analysis';
```

---

### 3.3 Margin Monitoring Queries

#### Query: Negative Margin Items

```sql
-- Find items with negative margins (requires immediate action)
SELECT
    item_code,
    item_description,
    selling_price,
    landed_cost,
    gross_margin_amt,
    gross_margin_pct,
    margin_category
FROM v_item_margins
WHERE margin_category = 'Negative (<0%)'
ORDER BY gross_margin_pct ASC;
```

**Query Time:** ~20ms (using materialized views)

---

#### Query: Margin Trend Analysis

```sql
-- Track margin changes over time
WITH margin_changes AS (
    SELECT
        item_code,
        snapshot_date,
        gross_margin_pct,
        LAG(gross_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date) as prev_margin_pct
    FROM margin_snapshots
    WHERE snapshot_date >= CURRENT_DATE - INTERVAL '90 days'
)
SELECT
    item_code,
    MIN(snapshot_date) as start_date,
    MAX(snapshot_date) as end_date,
    AVG(gross_margin_pct) as avg_margin_pct,
    (MAX(gross_margin_pct) - MIN(gross_margin_pct)) as margin_range_pct
FROM margin_changes
GROUP BY item_code
HAVING COUNT(DISTINCT snapshot_date) > 1  -- At least 2 snapshots
ORDER BY margin_range_pct DESC;
```

**Query Time:** ~150ms (scans last 90 days)

---

#### Query: Margin by Product Group

```sql
-- Aggregate margins by item group
SELECT
    i.item_group,
    COUNT(*) as item_count,
    AVG(m.gross_margin_pct) as avg_margin_pct,
    MIN(m.gross_margin_pct) as min_margin_pct,
    MAX(m.gross_margin_pct) as max_margin_pct,
    SUM(CASE WHEN m.margin_category = 'Negative (<0%)' THEN 1 ELSE 0 END) as negative_margin_count
FROM items i
JOIN v_item_margins m ON i.item_code = m.item_code
WHERE i.is_active = TRUE
GROUP BY i.item_group
ORDER BY avg_margin_pct DESC;
```

**Query Time:** ~50ms

---

### 3.4 Margin Alert System

```sql
-- ============================================================================
-- TABLE: margin_alerts
-- PURPOSE: Alert when margins drop below threshold
-- ESTIMATED ROWS: ~100 active alerts
-- STORAGE: <0.1 MB
-- UPDATE FREQUENCY: On margin snapshot refresh
-- ============================================================================

CREATE TABLE margin_alerts (
    alert_id               BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    alert_date             DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Alert Details
    alert_type             VARCHAR(20) NOT NULL,       -- 'Negative', 'Below Target', 'Decreased'
    current_margin_pct     NUMERIC(5,2),
    threshold_margin_pct   NUMERIC(5,2),
    margin_change_pct      NUMERIC(5,2),

    -- Status
    is_resolved            BOOLEAN DEFAULT FALSE,
    resolved_at            TIMESTAMPTZ,
    resolution_notes       TEXT,

    -- Timestamps
    alert_generated_at     TIMESTAMPTZ DEFAULT NOW(),
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_margin_alerts_unresolved ON margin_alerts(is_resolved, alert_generated_at DESC)
    WHERE is_resolved = FALSE;

CREATE INDEX idx_margin_alerts_item ON margin_alerts(item_code, alert_generated_at DESC);

COMMENT ON TABLE margin_alerts IS 'Alerts for margin issues (negative, below target, decreased)';
```

---

### 3.5 Automated Margin Monitoring

#### PostgreSQL Function: Calculate and Insert Margin Snapshot

```sql
-- ============================================================================
-- FUNCTION: refresh_margin_snapshots()
-- PURPOSE: Calculate current margins and insert snapshot
-- USAGE: Call this function daily (or hourly)
-- ============================================================================
CREATE OR REPLACE FUNCTION refresh_margin_snapshots()
RETURNS INTEGER AS $$
DECLARE
    snapshot_count INTEGER;
BEGIN
    -- Insert current margins into snapshot table
    INSERT INTO margin_snapshots (
        snapshot_date,
        item_code,
        price_level,
        unit_price,
        landed_cost,
        gross_margin_amt,
        gross_margin_pct,
        markup_pct,
        margin_category
    )
    SELECT
        CURRENT_DATE as snapshot_date,
        item_code,
        price_level,
        selling_price as unit_price,
        landed_cost,
        gross_margin_amt,
        gross_margin_pct,
        markup_pct,
        CASE
            WHEN selling_price IS NULL THEN 'No Price'
            WHEN landed_cost IS NULL THEN 'No Cost'
            WHEN ((selling_price - landed_cost) / selling_price) >= 0.40 THEN 'High (≥40%)'
            WHEN ((selling_price - landed_cost) / selling_price) >= 0.20 THEN 'Medium (20-40%)'
            WHEN ((selling_price - landed_cost) / selling_price) >= 0.00 THEN 'Low (0-20%)'
            ELSE 'Negative (<0%)'
        END as margin_category
    FROM v_item_margins
    WHERE selling_price IS NOT NULL AND landed_cost IS NOT NULL;

    -- Get count of inserted rows
    GET DIAGNOSTICS snapshot_count = ROW_COUNT;

    -- Generate alerts for negative margins
    INSERT INTO margin_alerts (item_code, alert_type, current_margin_pct, threshold_margin_pct)
    SELECT
        item_code,
        'Negative' as alert_type,
        gross_margin_pct as current_margin_pct,
        0 as threshold_margin_pct
    FROM margin_snapshots
    WHERE snapshot_date = CURRENT_DATE
    AND margin_category = 'Negative (<0%)'
    ON CONFLICT DO NOTHING;

    RETURN snapshot_count;
END;
$$ LANGUAGE plpgsql;

-- Usage:
-- SELECT refresh_margin_snapshots();
-- Expected output: "2646" (number of items)
```

---

#### Schedule: Daily Margin Refresh

```sql
-- ============================================================================
-- SCHEDULE: pg_cron (if available on Railway)
-- NOTE: Railway does not support pg_cron by default
-- ALTERNATIVE: Use external scheduler (GitHub Actions, cron job, etc.)
-- ============================================================================

-- IF pg_cron is available:
-- SELECT cron.schedule('refresh-margins', '0 2 * * *', 'SELECT refresh_margin_snapshots();');
-- This runs daily at 2 AM

-- Alternative: External Python script (see Section 4)
```

---

## SECTION 4: MIGRATION SCRIPTS

### 4.1 Phase 1: Schema Creation (DDL)

#### Script: `001_create_schema.sql`

```sql
-- ============================================================================
-- SCRIPT: 001_create_schema.sql
-- PURPOSE: Create all database tables, indexes, and views
-- USAGE: Run this first in Railway PostgreSQL
-- ESTIMATED TIME: <1 minute
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pg_cron";  -- May not be available on Railway

-- Create tables in order (respecting foreign keys)
-- Note: Split into separate files for better version control
\i tables/10_warehouses.sql
\i tables/20_vendors.sql
\i tables/30_items.sql
\i tables/40_inventory_current.sql
\i tables/50_costs.sql
\i tables/60_pricing.sql
\i tables/70_sales_orders.sql
\i tables/80_purchase_orders.sql
\i tables/90_forecasts.sql
\i tables/100_forecast_accuracy.sql
\i tables/110_margin_snapshots.sql
\i tables/120_margin_alerts.sql

-- Create materialized views
\i views/10_mv_latest_costs.sql
\i views/20_mv_latest_pricing.sql
\i views/30_mv_vendor_lead_times.sql
\i views/40_mv_forecast_summary.sql
\i views/50_mv_forecast_accuracy_summary.sql

-- Create standard views
\i views/60_v_inventory_status_with_forecast.sql
\i views/70_v_item_margins.sql

-- Create functions
\i functions/10_refresh_margin_snapshots.sql
```

---

### 4.2 Phase 2: Data Migration from TSV to PostgreSQL

#### Python Script: `migrate_tsv_to_postgres.py`

```python
"""
Migrate TSV files to PostgreSQL
Usage: python migrate_tsv_to_postgres.py
"""
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from pathlib import Path
import logging
from datetime import datetime
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
# Get from Railway dashboard: PostgreSQL → "Variables" → "DATABASE_URL"
DATABASE_URL = "postgresql://user:password@host.railway.app:5432/dbname"

# Data paths
DATA_DIR = Path("D:/code/forecastv3/data/raw")

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_connection():
    """Create PostgreSQL connection"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False  # Use transactions
    return conn

# ============================================================================
# REGION PARSING
# ============================================================================

def parse_region(item_code: str) -> str:
    """
    Parse region from item code suffix
    Examples:
        30071C-CGY → Calgary
        30071C-DEL → Delta
        30071C-EDM → Edmonton
        30071C-REG → Regina
        30071C-TOR → Toronto
        30071C-SAS → Saskatoon
        30071C-WPG → Winnipeg
    """
    if not isinstance(item_code, str):
        return 'Delta'

    suffix_map = {
        '-CGY': 'Calgary',
        '-DEL': 'Delta',
        '-EDM': 'Edmonton',
        '-SAS': 'Saskatoon',
        '-REG': 'Regina',
        '-WPG': 'Winnipeg',
        '-TOR': 'Toronto',
        '-VGH': 'Vaughan',
        '-MTL': 'Montreal'
    }

    for suffix, region in suffix_map.items():
        if item_code.endswith(suffix):
            return region

    return 'Delta'  # Default

# ============================================================================
# DATA MIGRATION FUNCTIONS
# ============================================================================

def migrate_warehouses(conn):
    """Migrate warehouse data from TSV"""
    logger.info("Migrating warehouses...")

    # Warehouse mapping from TSV data
    warehouses = [
        ('25', 'Calgary', 'Calgary'),
        ('30', 'Calgary', 'Calgary'),
        ('40', 'Edmonton', 'Edmonton'),
        ('50', 'Toronto', 'Toronto'),
        ('60', 'Regina', 'Regina'),
        ('70', 'Saskatoon', 'Saskatoon'),
        ('80', 'Winnipeg', 'Winnipeg'),
    ]

    with conn.cursor() as cur:
        execute_batch(
            cur,
            "INSERT INTO warehouses (warehouse_code, warehouse_name, region) VALUES (%s, %s, %s) "
            "ON CONFLICT (warehouse_code) DO NOTHING",
            warehouses
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(warehouses)} warehouses")

def migrate_vendors(conn):
    """Migrate vendor data from supply.tsv"""
    logger.info("Migrating vendors...")

    df = pd.read_csv(DATA_DIR / "supply.tsv", sep='\t')

    # Extract unique vendors
    vendors = df[['VendorCode', 'VendorName']].drop_duplicates().dropna()

    vendor_list = [
        (row['VendorCode'], row['VendorName'])
        for _, row in vendors.iterrows()
    ]

    with conn.cursor() as cur:
        execute_batch(
            cur,
            "INSERT INTO vendors (vendor_code, vendor_name) VALUES (%s, %s) "
            "ON CONFLICT (vendor_code) DO UPDATE SET vendor_name = EXCLUDED.vendor_name",
            vendor_list
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(vendor_list)} vendors")

def migrate_items(conn):
    """Migrate item data from items.tsv"""
    logger.info("Migrating items...")

    df = pd.read_csv(DATA_DIR / "items.tsv", sep='\t')

    # Prepare data
    items = []
    for _, row in df.iterrows():
        region = parse_region(row['Item No.'])
        items.append((
            row['Item No.'],
            row['Item Description'],
            row.get('ItemGroup'),
            region,
            row['BaseUoM'],
            row.get('PurchUoM'),
            row.get('QtyPerPurchUoM'),
            row.get('SalesUoM'),
            row.get('QtyPerSalesUoM'),
            row.get('PreferredVendor'),
            row.get('LastVendorCode_Fallback'),
            row.get('LastPurchaseDate_Fallback'),
            row.get('MOQ', 0),
            row.get('OrderMultiple', 1)
        ))

    with conn.cursor() as cur:
        execute_batch(
            cur,
            """INSERT INTO items (
                item_code, item_description, item_group, region,
                base_uom, purch_uom, qty_per_purch_uom, sales_uom, qty_per_sales_uom,
                preferred_vendor_code, last_vendor_code, last_purchase_date,
                moq, order_multiple
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_code) DO UPDATE SET
                item_description = EXCLUDED.item_description,
                item_group = EXCLUDED.item_group,
                region = EXCLUDED.region,
                updated_at = NOW()""",
            items
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(items)} items")

def migrate_inventory_current(conn):
    """Migrate current inventory from items.tsv"""
    logger.info("Migrating inventory_current...")

    df = pd.read_csv(DATA_DIR / "items.tsv", sep='\t')

    inventory = []
    for _, row in df.iterrows():
        inventory.append((
            row['Item No.'],
            row['Warehouse'],
            row['CurrentStock'],
            row['IncomingStock'],
            row['CommittedStock'],
            row['BaseUoM'],
            row.get('UnitCost')
        ))

    with conn.cursor() as cur:
        execute_batch(
            cur,
            """INSERT INTO inventory_current (
                item_code, warehouse_code, on_hand_qty, on_order_qty,
                committed_qty, uom, unit_cost
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_code, warehouse_code) DO UPDATE SET
                on_hand_qty = EXCLUDED.on_hand_qty,
                on_order_qty = EXCLUDED.on_order_qty,
                committed_qty = EXCLUDED.committed_qty,
                unit_cost = EXCLUDED.unit_cost,
                updated_at = NOW()""",
            inventory
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(inventory)} inventory records")

def migrate_sales_orders(conn):
    """Migrate sales orders from sales.tsv"""
    logger.info("Migrating sales_orders...")

    df = pd.read_csv(DATA_DIR / "sales.tsv", sep='\t')

    # Clean and prepare data
    df['Posting Date'] = pd.to_datetime(df['Posting Date'], errors='coerce')
    df['PromiseDate'] = pd.to_datetime(df['PromiseDate'], errors='coerce')
    df = df.dropna(subset=['Posting Date'])

    sales_orders = []
    for _, row in df.iterrows():
        sales_orders.append((
            str(row.get('Document Type', '')) + '-' + str(row['Posting Date'].date()) + '-' + str(row['Item No.']),
            1,  # line_number (simplified)
            row['Posting Date'].date(),
            row['PromiseDate'].date() if pd.notna(row['PromiseDate']) else None,
            row.get('CustomerCode'),
            row.get('Description'),
            row['Item No.'],
            row.get('Description'),
            row['OrderedQty'],
            0,  # shipped_qty (assume 0 for historical)
            row.get('RowValue'),
            row['Warehouse'],
            row.get('Linked_SpecialOrder_Num'),
            row.get('Document Type')
        ))

    with conn.cursor() as cur:
        execute_batch(
            cur,
            """INSERT INTO sales_orders (
                order_number, line_number, posting_date, promise_date,
                customer_code, customer_name, item_code, item_description,
                ordered_qty, shipped_qty, row_value, warehouse_code,
                linked_special_order_num, document_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_number, line_number) DO NOTHING""",
            sales_orders
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(sales_orders)} sales orders")

def migrate_purchase_orders(conn):
    """Migrate purchase orders from supply.tsv"""
    logger.info("Migrating purchase_orders...")

    df = pd.read_csv(DATA_DIR / "supply.tsv", sep='\t')

    # Clean and prepare data
    df['PO_Date'] = pd.to_datetime(df['PO_Date'], errors='coerce')
    df['EventDate'] = pd.to_datetime(df['EventDate'], errors='coerce')
    df = df.dropna(subset=['PO_Date'])

    purchase_orders = []
    for _, row in df.iterrows():
        # Calculate lead time
        lead_time_days = None
        if pd.notna(row['EventDate']) and pd.notna(row['PO_Date']):
            lead_time_days = (row['EventDate'] - row['PO_Date']).days

        purchase_orders.append((
            str(row.get('DataType', '')) + '-' + str(row['PO_Date'].date()) + '-' + str(row['ItemCode']),
            1,  # line_number
            row['PO_Date'].date(),
            row['EventDate'].date() if pd.notna(row['EventDate']) else None,
            row['VendorCode'],
            row.get('VendorName'),
            row['ItemCode'],
            row['Quantity'],
            0,  # received_qty (assume 0 for historical)
            row.get('RowValue_SourceCurrency'),
            row.get('Currency', 'CAD'),
            row.get('ExchangeRate', 1.0),
            row['Warehouse'],
            row.get('FreightTerms'),
            row.get('FOB'),
            lead_time_days
        ))

    with conn.cursor() as cur:
        execute_batch(
            cur,
            """INSERT INTO purchase_orders (
                po_number, line_number, po_date, event_date,
                vendor_code, vendor_name, item_code,
                ordered_qty, received_qty, row_value, currency, exchange_rate,
                warehouse_code, freight_terms, fob, lead_time_days
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (po_number, line_number) DO NOTHING""",
            purchase_orders
        )
        conn.commit()
        logger.info(f"✅ Migrated {len(purchase_orders)} purchase orders")

def calculate_last_sale_dates(conn):
    """Calculate and update last_sale_date for all items"""
    logger.info("Calculating last_sale_date...")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE items i
            SET last_sale_date = (
                SELECT MAX(so.posting_date)
                FROM sales_orders so
                WHERE so.item_code = i.item_code
            )
            WHERE EXISTS (
                SELECT 1 FROM sales_orders so WHERE so.item_code = i.item_code
            )
        """)
        updated = cur.rowcount
        conn.commit()
        logger.info(f"✅ Updated last_sale_date for {updated} items")

def refresh_materialized_views(conn):
    """Refresh all materialized views"""
    logger.info("Refreshing materialized views...")

    views = [
        'mv_latest_costs',
        'mv_latest_pricing',
        'mv_vendor_lead_times',
        'mv_forecast_summary',
        'mv_forecast_accuracy_summary'
    ]

    with conn.cursor() as cur:
        for view in views:
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                conn.commit()
                logger.info(f"✅ Refreshed {view}")
            except Exception as e:
                logger.warning(f"⚠️  Could not refresh {view}: {e}")
                # Try without CONCURRENTLY
                try:
                    cur.execute(f"REFRESH MATERIALIZED VIEW {view}")
                    conn.commit()
                    logger.info(f"✅ Refreshed {view} (without CONCURRENTLY)")
                except Exception as e2:
                    logger.error(f"❌ Failed to refresh {view}: {e2}")

# ============================================================================
# MAIN MIGRATION SCRIPT
# ============================================================================

def main():
    """Run full migration"""
    logger.info("Starting TSV to PostgreSQL migration...")
    start_time = datetime.now()

    try:
        conn = get_connection()

        # Migrate in order (respecting foreign keys)
        migrate_warehouses(conn)
        migrate_vendors(conn)
        migrate_items(conn)
        migrate_inventory_current(conn)
        migrate_sales_orders(conn)
        migrate_purchase_orders(conn)

        # Post-migration updates
        calculate_last_sale_dates(conn)
        refresh_materialized_views(conn)

        conn.close()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Migration completed successfully in {elapsed:.1f} seconds")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    main()
```

---

### 4.3 Phase 3: Data Validation

#### SQL Script: `002_validate_data.sql`

```sql
-- ============================================================================
-- SCRIPT: 002_validate_data.sql
-- PURPOSE: Validate migrated data for integrity and accuracy
-- USAGE: Run after migration to verify data quality
-- ============================================================================

-- Check 1: Row counts
SELECT 'items' as table_name, COUNT(*) as row_count FROM items
UNION ALL
SELECT 'warehouses', COUNT(*) FROM warehouses
UNION ALL
SELECT 'vendors', COUNT(*) FROM vendors
UNION ALL
SELECT 'inventory_current', COUNT(*) FROM inventory_current
UNION ALL
SELECT 'sales_orders', COUNT(*) FROM sales_orders
UNION ALL
SELECT 'purchase_orders', COUNT(*) FROM purchase_orders;

-- Expected output (approximate):
-- items: 2,646
-- warehouses: 7
-- vendors: ~200
-- inventory_current: 2,646
-- sales_orders: ~70,000
-- purchase_orders: ~10,000

-- Check 2: Foreign key integrity
SELECT 'Items without region' as check_name, COUNT(*) as issue_count
FROM items WHERE region = 'Delta' AND item_code NOT LIKE '%-DEL%'

UNION ALL

SELECT 'Inventory without items', COUNT(*)
FROM inventory_current ic
WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.item_code = ic.item_code)

UNION ALL

SELECT 'Sales without items', COUNT(*)
FROM sales_orders so
WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.item_code = so.item_code)

UNION ALL

SELECT 'Purchase without vendors', COUNT(*)
FROM purchase_orders po
WHERE NOT EXISTS (SELECT 1 FROM vendors v WHERE v.vendor_code = po.vendor_code);

-- Expected output: All counts should be 0

-- Check 3: Data quality
SELECT 'Items with negative inventory' as check_name, COUNT(*) as issue_count
FROM inventory_current WHERE on_hand_qty < 0

UNION ALL

SELECT 'Sales with zero quantity', COUNT(*)
FROM sales_orders WHERE ordered_qty <= 0

UNION ALL

SELECT 'Purchase with zero quantity', COUNT(*)
FROM purchase_orders WHERE ordered_qty <= 0

UNION ALL

SELECT 'Items without description', COUNT(*)
FROM items WHERE item_description IS NULL OR item_description = '';

-- Expected output: All counts should be 0

-- Check 4: Margin data availability
SELECT 'Items with cost data' as check_name, COUNT(*) as item_count
FROM items i
WHERE EXISTS (SELECT 1 FROM mv_latest_costs c WHERE c.item_code = i.item_code)

UNION ALL

SELECT 'Items with price data', COUNT(*)
FROM items i
WHERE EXISTS (SELECT 1 FROM mv_latest_pricing p WHERE p.item_code = i.item_code)

UNION ALL

SELECT 'Items with margin data', COUNT(*)
FROM items i
WHERE EXISTS (
    SELECT 1
    FROM mv_latest_costs c
    JOIN mv_latest_pricing p ON c.item_code = p.item_code
    WHERE c.item_code = i.item_code
);

-- Check 5: Forecast coverage
SELECT 'Items with active forecasts' as check_name, COUNT(*) as item_count
FROM items i
WHERE EXISTS (
    SELECT 1 FROM forecasts f
    WHERE f.item_code = i.item_code AND f.status = 'Active'
);

-- Expected: Should be close to total item count (2,646)

-- Check 6: Regional distribution
SELECT region as warehouse_region, COUNT(*) as item_count
FROM items
GROUP BY region
ORDER BY item_count DESC;

-- Check 7: Date ranges
SELECT 'Sales date range' as check_name,
    MIN(posting_date) as earliest_date,
    MAX(posting_date) as latest_date
FROM sales_orders

UNION ALL

SELECT 'Purchase date range',
    MIN(po_date),
    MAX(po_date)
FROM purchase_orders;

-- Check 8: Materialized view freshness
SELECT 'mv_latest_costs' as view_name, COUNT(*) as row_count FROM mv_latest_costs
UNION ALL
SELECT 'mv_latest_pricing', COUNT(*) FROM mv_latest_pricing
UNION ALL
SELECT 'mv_vendor_lead_times', COUNT(*) FROM mv_vendor_lead_times;
```

---

## SECTION 5: COST OPTIMIZATION PLAN

### 5.1 Storage Reduction Techniques

#### Technique 1: Use Appropriate Data Types

**Before (Inefficient):**
```sql
unit_price             TEXT,                -- Variable length, slower
quantity               NUMERIC(20,6),       -- Overkill precision
item_description       TEXT                 -- No max length
```

**After (Optimized):**
```sql
unit_price             NUMERIC(12,4),       -- Fixed width, indexed
quantity               NUMERIC(12,3),       -- Sufficient precision
item_description       VARCHAR(500)         -- Max length, faster
```

**Savings:** ~30% storage reduction

---

#### Technique 2: Compress Large Text Columns

```sql
-- Enable TOAST compression (automatic in PostgreSQL)
ALTER TABLE items SET (TOAST.TARGET = 100);

-- Or use pg_trgm for partial indexing
CREATE INDEX idx_items_description_trgm ON items
USING gin (item_description gin_trgm_ops);

-- Query:
SELECT * FROM items WHERE item_description % 'chemical';
```

---

#### Technique 3: Partitioning for Easy Archival

```sql
-- Partition sales_orders by year
CREATE TABLE sales_orders (
    -- ... same columns ...
) PARTITION BY RANGE (posting_date);

-- Create partitions
CREATE TABLE sales_orders_2023 PARTITION OF sales_orders
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE sales_orders_2024 PARTITION OF sales_orders
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE sales_orders_2025 PARTITION OF sales_orders
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Archive old data (DROP instead of DELETE)
DROP TABLE sales_orders_2023;  -- Instant, no vacuum needed
```

**Savings:** No bloat, instant archival

---

#### Technique 4: Use Partial Indexes

```sql
-- Instead of indexing all rows:
-- CREATE INDEX idx_all_items ON items(region);

-- Only index active items:
CREATE INDEX idx_active_items_by_region ON items(region)
    WHERE is_active = TRUE;

-- Savings: 50% smaller index if 50% of items are inactive
```

---

#### Technique 5: Materialized Views for Expensive Aggregations

```sql
-- Instead of calculating margins every query (slow):
CREATE MATERIALIZED VIEW mv_item_margins AS
SELECT
    i.item_code,
    (p.unit_price - c.total_landed_cost) as gross_margin_amt,
    ((p.unit_price - c.total_landed_cost) / p.unit_price) * 100 as gross_margin_pct
FROM items i
JOIN pricing p ON i.item_code = p.item_code
JOIN costs c ON i.item_code = c.item_code;

-- Refresh nightly instead of calculating on every query
REFRESH MATERIALIZED VIEW mv_item_margins;
```

**Savings:** 10x faster queries, 100x less CPU

---

### 5.2 Query Optimization Tips

#### Tip 1: Use EXPLAIN ANALYZE

```sql
-- Check query performance
EXPLAIN ANALYZE
SELECT * FROM v_inventory_status_with_forecast
WHERE available_qty < 100;

-- Look for:
-- - Seq Scan (bad, should use Index Scan)
-- - Filter (should be Index Cond)
-- - High cost (should be <1000 for simple queries)
```

---

#### Tip 2: Use VACUUM ANALYZE Regularly

```sql
-- Reclaim space and update statistics
VACUUM ANALYZE items;
VACUUM ANALYZE sales_orders;
VACUUM ANALYZE purchase_orders;

-- Or use autovacuum (enabled by default)
-- Check settings:
SHOW autovacuum;
```

---

#### Tip 3: Use Connection Pooling

```python
# In Streamlit app
import psycopg2_pool

connection_pool = psycopg2_pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,  # Don't exceed Railway connection limit
    dsn=DATABASE_URL
)

# Get connection from pool
conn = connection_pool.getconn()
try:
    # Run queries
    pass
finally:
    connection_pool.putconn(conn)
```

---

#### Tip 4: Batch Inserts Instead of Single Row Inserts

```python
# BAD: Single row insert (slow)
for item in items:
    cursor.execute("INSERT INTO items VALUES (...)", item)

# GOOD: Batch insert (100x faster)
execute_batch(cursor, "INSERT INTO items VALUES (...)", items)
```

---

### 5.3 Archival Strategy

#### Strategy: Automatic Partition Dropping

```python
# Script: archive_old_data.py
import psycopg2
from datetime import datetime

def archive_old_sales_data(conn, years_to_keep=3):
    """Archive sales orders older than N years"""
    cutoff_year = datetime.now().year - years_to_keep

    with conn.cursor() as cur:
        # Drop old partitions
        cur.execute(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'sales_orders_{cutoff_year}%'
        """)

        old_partitions = cur.fetchall()

        for (table_name,) in old_partitions:
            print(f"Dropping {table_name}...")
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")

        conn.commit()
        print(f"✅ Archived {len(old_partitions)} partitions")

if __name__ == "__main__":
    conn = psycopg2.connect(DATABASE_URL)
    archive_old_sales_data(conn, years_to_keep=3)
    conn.close()
```

---

## SECTION 6: DEPLOYMENT CHECKLIST

### 6.1 Pre-Migration Tasks

- [ ] **Review and answer questions from Section 1**
- [ ] **Obtain SAP B1 price list export** (for margin monitoring)
- [ ] **Clarify cost column source of truth** (UnitCost vs LastPurchasePrice_Fallback)
- [ ] **Validate TSV file integrity** (no corrupted rows)
- [ ] **Set up Railway PostgreSQL instance**
- [ ] **Test database connection locally**
- [ ] **Backup existing TSV files**

---

### 6.2 Migration Steps

#### Step 1: Create Database Schema

```bash
# 1. Connect to Railway PostgreSQL
psql $DATABASE_URL

# 2. Run schema creation script
\i 001_create_schema.sql

# 3. Verify tables created
\dt

# Expected output:
-- items
-- warehouses
-- vendors
-- inventory_current
-- costs
-- pricing
-- sales_orders
-- purchase_orders
-- forecasts
-- forecast_accuracy
-- margin_snapshots
-- margin_alerts
```

---

#### Step 2: Migrate Data from TSV to PostgreSQL

```bash
# 1. Install dependencies
pip install psycopg2-binary pandas

# 2. Set DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:password@host.railway.app:5432/dbname"

# 3. Run migration script
python migrate_tsv_to_postgres.py

# Expected output:
-- ✅ Migrated 7 warehouses
-- ✅ Migrated 200 vendors
-- ✅ Migrated 2646 items
-- ✅ Migrated 2646 inventory records
-- ✅ Migrated 70081 sales orders
-- ✅ Migrated 10272 purchase orders
-- ✅ Updated last_sale_date for 1500 items
-- ✅ Refreshed 5 materialized views
-- ✅ Migration completed successfully in 45.2 seconds
```

---

#### Step 3: Validate Data

```bash
# Run validation script
psql $DATABASE_URL -f 002_validate_data.sql

# Check output for:
-- ✅ Row counts match TSV files
-- ✅ No foreign key violations
-- ✅ No data quality issues
-- ✅ Margin data available
-- ✅ Forecast coverage >90%
```

---

#### Step 4: Update Streamlit App

```python
# In app.py or src/data_pipeline.py

# OLD: Load from TSV
df_items = pd.read_csv('data/raw/items.tsv', sep='\t')

# NEW: Load from PostgreSQL
import psycopg2
import pandas as pd

def load_items_from_postgres():
    conn = psycopg2.connect(DATABASE_URL)
    query = """
        SELECT
            i.*,
            ic.on_hand_qty,
            ic.on_order_qty,
            ic.committed_qty,
            ic.available_qty
        FROM items i
        JOIN inventory_current ic ON i.item_code = ic.item_code
        WHERE i.is_active = TRUE
    """
    df_items = pd.read_sql(query, conn)
    conn.close()
    return df_items

# Update all data loading functions to use PostgreSQL
```

---

#### Step 5: Test Application

```bash
# 1. Run Streamlit locally
streamlit run app.py

# 2. Test all tabs:
-- Inventory Status
-- Forecast Analysis
-- Margin Monitoring (if price data available)
-- Vendor Performance
-- Spatial Optimization

# 3. Check for errors:
-- Connection errors
-- Query timeouts
-- Missing data
-- Incorrect calculations
```

---

#### Step 6: Deploy to Railway

```bash
# 1. Create railway.toml
cat > railway.toml << EOF
[build]
builder = "nixpacks"

[deploy]
startCommand = "streamlit run app.py --server.port=$PORT"
healthcheckPath = "/_stcore/health"
healthcheckTimeout = 300

[[services]]
name = "web"
serviceType = "web"
EOF

# 2. Deploy
railway up

# 3. Check logs
railway logs

# Expected output:
-- Build successful
-- Deployment successful
-- App running at https://your-app.railway.app
```

---

### 6.3 Post-Migration Tasks

- [ ] **Set up automated daily sync** (GitHub Actions or cron job)
- [ ] **Configure automated margin snapshots** (call `refresh_margin_snapshots()`)
- [ ] **Set up monitoring** (Railway metrics, query performance)
- [ ] **Test disaster recovery** (restore from backup)
- [ ] **Document rollback plan**
- [ ] **Train users on new system**

---

### 6.4 Rollback Plan

If migration fails, rollback strategy:

**Option 1: Revert to TSV Files (Immediate)**
```python
# In app.py, add fallback:
USE_POSTGRES = os.getenv('USE_POSTGRES', 'false') == 'true'

if USE_POSTGRES:
    df_items = load_items_from_postgres()
else:
    df_items = pd.read_csv('data/raw/items.tsv', sep='\t')
```

**Option 2: Restore from Backup (5 minutes)**
```bash
# Railway automatically creates backups
# Restore via dashboard:
-- PostgreSQL → "Backups" → "Restore"
```

**Option 3: Re-migrate from TSV (10 minutes)**
```bash
# Drop all tables
psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migration
python migrate_tsv_to_postgres.py
```

---

## SECTION 7: RAILWAY-SPECIFIC CONSIDERATIONS

### 7.1 Railway PostgreSQL Limits

**Free Tier:**
- Storage: 1 GB
- RAM: 512 MB (shared)
- CPU: 0.25 vCPU (shared)
- Connections: 60 (soft limit)

**Paid Tier (Eco/Performance):**
- Storage: $0.50/GB/month
- RAM: 512 MB - 16 GB
- CPU: 0.25 - 8 vCPU
- Connections: Up to 500

**Our Estimates:**
- Storage: ~30 MB (3% of free tier)
- RAM: ~70 MB working set (14% of free tier)
- Connections: 1-5 (Streamlit = single user)

**Verdict:** Free tier is sufficient for production use

---

### 7.2 Railway Best Practices

#### Practice 1: Use Connection Pooling

```python
# Streamlit re-runs script on every interaction
# Avoid opening too many connections

import streamlit as st
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

@st.cache_resource
def get_connection_pool():
    """Create connection pool (cached across reruns)"""
    return ThreadedConnectionPool(
        minconn=1,
        maxconn=5,  # Conservative limit
        dsn=st.secrets["DATABASE_URL"]
    )

# Get connection from pool
pool = get_connection_pool()
conn = pool.getconn()
try:
    # Run queries
    pass
finally:
    pool.putconn(conn)
```

---

#### Practice 2: Use Railway Secrets for Credentials

```bash
# In Railway dashboard:
-- PostgreSQL → "Variables" → "Add Variable"
-- Name: DATABASE_URL
-- Value: postgresql://...

# In Python code:
import os
import streamlit as st

DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL"))
```

---

#### Practice 3: Monitor Railway Metrics

```bash
# Railway provides built-in metrics:
-- CPU Usage
-- Memory Usage
-- Storage Usage
-- Connection Count
-- Query Performance

# Access via dashboard:
-- PostgreSQL → "Metrics"
```

**Alert Thresholds:**
- CPU > 80% for 5 minutes: Scale up or optimize queries
- RAM > 90% for 5 minutes: Scale up or reduce dataset
- Storage > 90%: Archive old data or upgrade
- Connections > 50: Implement connection pooling

---

#### Practice 4: Use Railway's Automated Backups

```bash
# Railway automatically backs up databases daily
- Retention: 7 days (free tier)
- Restore: Via dashboard in 2 minutes

# Manual backup (before major changes):
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

---

#### Practice 5: Optimize for Cold Starts

Railway spins down inactive services. To minimize cold start time:

```python
# Use st.cache_data for query results
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_inventory_summary():
    conn = get_connection()
    query = "SELECT * FROM v_inventory_status_with_forecast"
    df = pd.read_sql(query, conn)
    conn.close()
    return df
```

---

### 7.3 Cost Optimization Summary

**Current Costs (Free Tier):**
- Storage: 30 MB / 1 GB (3%) = **$0/month**
- RAM: 70 MB / 512 MB (14%) = **$0/month**
- Total: **$0/month**

**Projected Costs (After 3 Years):**
- Storage: ~100 MB / 1 GB (10%) = **$0/month**
- Growth: ~500 sales orders/month × 36 months = 18,000 new rows
- Still within free tier

**Optimization Impact:**
- Without optimization: ~200 MB storage, $0.10/month
- With optimization: ~100 MB storage, $0/month
- **Savings: $1.20/year**

---

## CONCLUSION

This comprehensive migration plan provides:

1. **Clear questions** to understand your business needs
2. **Optimized schema** designed for Railway's constraints
3. **Margin monitoring system** with real-time alerts
4. **Complete migration scripts** ready to run
5. **Cost optimization strategies** to stay within free tier
6. **Step-by-step deployment checklist** for production

**Next Steps:**
1. Review Section 1 (Questions & Requirements) with your team
2. Obtain SAP B1 price list export
3. Set up Railway PostgreSQL instance
4. Run migration scripts in development environment
5. Test thoroughly before production deployment

**Estimated Timeline:**
- Planning: 1 day
- Migration: 1 day
- Testing: 2-3 days
- Deployment: 1 day
- **Total: 1 week**

**Support:**
If you encounter issues during migration, refer to:
- Railway documentation: https://docs.railway.app/
- PostgreSQL documentation: https://www.postgresql.org/docs/
- This migration plan (all sections)
