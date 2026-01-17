-- ============================================================================
-- Railway PostgreSQL Migration: 004_simplify_order_tables.sql
-- Date: 2026-01-17
--
-- Description: Simplify sales_orders and purchase_orders to remove order tracking
--              requirement. Adds auto-increment ID column as primary key.
--
-- Context: Project only needs time-series data for forecasting, not order tracking.
--          This migration simplifies the schema for easier middleware integration.
-- ============================================================================

-- ============================================================================
-- TABLE: sales_orders - Add ID column and simplify primary key
-- ============================================================================

-- Add auto-increment ID column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales_orders' AND column_name = 'id'
    ) THEN
        ALTER TABLE sales_orders ADD COLUMN id BIGSERIAL PRIMARY KEY;
    END IF;
END $$;

-- Drop old composite primary key if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'sales_orders'
        AND constraint_type = 'PRIMARY KEY'
        AND constraint_name != 'sales_orders_pkey'
    ) THEN
        ALTER TABLE sales_orders DROP CONSTRAINT sales_orders_pkey;
    END IF;
END $$;

-- Make order_number and line_number optional (nullable)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales_orders' AND column_name = 'order_number'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE sales_orders ALTER COLUMN order_number DROP NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales_orders' AND column_name = 'line_number'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE sales_orders ALTER COLUMN line_number DROP NOT NULL;
    END IF;
END $$;

COMMENT ON COLUMN sales_orders.id IS 'Auto-increment primary key for forecasting (no order tracking needed)';

-- Create unique index for UPSERT conflict resolution
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_orders_business_key
ON sales_orders (item_code, posting_date, warehouse_code, customer_code)
WHERE customer_code IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_orders_business_key_no_customer
ON sales_orders (item_code, posting_date, warehouse_code)
WHERE customer_code IS NULL;

-- ============================================================================
-- TABLE: purchase_orders - Add ID column and simplify primary key
-- ============================================================================

-- Add auto-increment ID column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'purchase_orders' AND column_name = 'id'
    ) THEN
        ALTER TABLE purchase_orders ADD COLUMN id BIGSERIAL PRIMARY KEY;
    END IF;
END $$;

-- Drop old composite primary key if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'purchase_orders'
        AND constraint_type = 'PRIMARY KEY'
        AND constraint_name != 'purchase_orders_pkey'
    ) THEN
        ALTER TABLE purchase_orders DROP CONSTRAINT purchase_orders_pkey;
    END IF;
END $$;

-- Make po_number and line_number optional (nullable)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'purchase_orders' AND column_name = 'po_number'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE purchase_orders ALTER COLUMN po_number DROP NOT NULL;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'purchase_orders' AND column_name = 'line_number'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE purchase_orders ALTER COLUMN line_number DROP NOT NULL;
    END IF;
END $$;

COMMENT ON COLUMN purchase_orders.id IS 'Auto-increment primary key for forecasting (no order tracking needed)';

-- Create unique index for UPSERT conflict resolution
CREATE UNIQUE INDEX IF NOT EXISTS idx_purchase_orders_business_key
ON purchase_orders (item_code, po_date, warehouse_code, vendor_code);

-- ============================================================================
-- Verify Changes
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 004 completed successfully';
    RAISE NOTICE 'sales_orders now has PRIMARY KEY (id)';
    RAISE NOTICE 'purchase_orders now has PRIMARY KEY (id)';
    RAISE NOTICE 'order_number, line_number, po_number are now optional (nullable)';
END $$;
