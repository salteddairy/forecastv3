-- ============================================================================
-- Railway PostgreSQL Migration: 003_add_line_number_columns.sql
-- Date: 2026-01-17
--
-- Description: Add missing line_number column to sales_orders and purchase_orders
--              to match the expected schema in ingestion service models.
--
-- Context: Initial Railway deployment used older schema without line_number
--          This migration adds the missing column and updates primary keys
-- ============================================================================

-- ============================================================================
-- TABLE: sales_orders - Add line_number column
-- ============================================================================

-- Add line_number column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales_orders' AND column_name = 'line_number'
    ) THEN
        ALTER TABLE sales_orders ADD COLUMN line_number INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- Drop old primary key if using only order_number
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'sales_orders'
        AND constraint_type = 'PRIMARY KEY'
        AND constraint_name = 'sales_orders_pkey'
    ) THEN
        -- Check if primary key is only on order_number (old schema)
        IF EXISTS (
            SELECT 1 FROM information_schema.key_column_usage
            WHERE table_name = 'sales_orders'
            AND constraint_name = 'sales_orders_pkey'
            AND column_name = 'order_number'
        ) THEN
            ALTER TABLE sales_orders DROP CONSTRAINT sales_orders_pkey;
            ALTER TABLE sales_orders ADD PRIMARY KEY (order_number, line_number);
        END IF;
    END IF;
END $$;

COMMENT ON COLUMN sales_orders.line_number IS 'Line number within the order (enables multiple items per order)';

-- ============================================================================
-- TABLE: purchase_orders - Add line_number column
-- ============================================================================

-- Add line_number column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'purchase_orders' AND column_name = 'line_number'
    ) THEN
        ALTER TABLE purchase_orders ADD COLUMN line_number INTEGER NOT NULL DEFAULT 1;
    END IF;
END $$;

-- Drop old primary key if using only po_number
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'purchase_orders'
        AND constraint_type = 'PRIMARY KEY'
        AND constraint_name = 'purchase_orders_pkey'
    ) THEN
        -- Check if primary key is only on po_number (old schema)
        IF EXISTS (
            SELECT 1 FROM information_schema.key_column_usage
            WHERE table_name = 'purchase_orders'
            AND constraint_name = 'purchase_orders_pkey'
            AND column_name = 'po_number'
        ) THEN
            ALTER TABLE purchase_orders DROP CONSTRAINT purchase_orders_pkey;
            ALTER TABLE purchase_orders ADD PRIMARY KEY (po_number, line_number);
        END IF;
    END IF;
END $$;

COMMENT ON COLUMN purchase_orders.line_number IS 'Line number within the order (enables multiple items per order)';

-- ============================================================================
-- Verify Changes
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 003 completed successfully';
    RAISE NOTICE 'sales_orders now has PRIMARY KEY (order_number, line_number)';
    RAISE NOTICE 'purchase_orders now has PRIMARY KEY (po_number, line_number)';
END $$;
