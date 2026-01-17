# Database Migration 004: Simplify Order Tables

## Status

**Migration Created:** ✅ Complete
**Ingestion Service Deployed:** 🔄 In Progress
**Database Migration Applied:** ⏳ Pending (Railway database temporarily unavailable)

---

## What This Migration Does

Removes order tracking requirements from `sales_orders` and `purchase_orders` tables:
- Adds auto-increment `id` column as primary key
- Makes `order_number`, `line_number`, `po_number` optional (nullable)
- Creates business key indexes for UPSERT operations
- **No impact on forecasting functionality**

---

## How to Apply This Migration

### Option 1: Railway Console (Recommended)

1. Go to https://railway.com/project/6b29b7de-2219-4e37-bc15-cb46afba97b2
2. Select the PostgreSQL database service (Postgres-B08X)
3. Click "New Query"
4. Copy and paste the contents of `004_simplify_order_tables.sql`
5. Click "Run Query"

### Option 2: Railway CLI

```bash
cd D:\code\forecastv3\ingestion_service
railway run
```

Then paste the SQL commands:
```sql
-- Add id columns
ALTER TABLE sales_orders ADD COLUMN IF NOT EXISTS id BIGSERIAL PRIMARY KEY;
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS id BIGSERIAL PRIMARY KEY;

-- Make order fields optional
ALTER TABLE sales_orders ALTER COLUMN order_number DROP NOT NULL;
ALTER TABLE sales_orders ALTER COLUMN line_number DROP NOT NULL;
ALTER TABLE purchase_orders ALTER COLUMN po_number DROP NOT NULL;
ALTER TABLE purchase_orders ALTER COLUMN line_number DROP NOT NULL;

-- Create business key indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_orders_business_key
ON sales_orders (item_code, posting_date, warehouse_code, customer_code)
WHERE customer_code IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_orders_business_key_no_customer
ON sales_orders (item_code, posting_date, warehouse_code)
WHERE customer_code IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_purchase_orders_business_key
ON purchase_orders (item_code, po_date, warehouse_code, vendor_code);
```

### Option 3: Python Script (After Database is Available)

```bash
cd D:\code\forecastv3\ingestion_service
python ../database/migrations/apply_004_simplify.py
```

---

## Verification

After applying the migration, verify it worked:

```sql
-- Check sales_orders
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'sales_orders'
AND column_name IN ('id', 'order_number', 'line_number')
ORDER BY column_name;

-- Should show:
-- id            | NO   (primary key)
-- line_number   | YES  (nullable)
-- order_number  | YES  (nullable)

-- Check purchase_orders
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'purchase_orders'
AND column_name IN ('id', 'po_number', 'line_number')
ORDER BY column_name;

-- Should show:
-- id            | NO   (primary key)
-- line_number   | YES  (nullable)
-- po_number     | YES  (nullable)
```

---

## Testing After Migration

Once the migration is applied, test the ingestion:

```bash
cd D:\code\forecastv3\tests\middleware_test_data
python send_all_test_data.py
```

Expected result: All 8 data types should ingest successfully without errors.

---

## Files Changed

**Created:**
- `database/migrations/004_simplify_order_tables.sql`
- `database/migrations/apply_004_simplify.py`

**Modified:**
- `ingestion_service/app/models.py` - Made order identifiers optional
- `ingestion_service/app/database.py` - Updated conflict keys to use business keys
- `tests/generate_middleware_test_data.py` - Removed order numbers from test data

---

## Rollback (If Needed)

If you need to revert this migration:

```sql
-- Remove unique indexes
DROP INDEX IF EXISTS idx_sales_orders_business_key;
DROP INDEX IF EXISTS idx_sales_orders_business_key_no_customer;
DROP INDEX IF EXISTS idx_purchase_orders_business_key;

-- Drop id columns (this will fail if data exists, so backup first)
ALTER TABLE sales_orders DROP COLUMN IF EXISTS id;
ALTER TABLE purchase_orders DROP COLUMN IF EXISTS id;

-- Restore NOT NULL constraints
ALTER TABLE sales_orders ALTER COLUMN order_number SET NOT NULL;
ALTER TABLE sales_orders ALTER COLUMN line_number SET NOT NULL;
ALTER TABLE purchase_orders ALTER COLUMN po_number SET NOT NULL;
ALTER TABLE purchase_orders ALTER COLUMN line_number SET NOT NULL;
```

---

**Created:** 2026-01-17
**Author:** Claude Code AI
**Status:** ⏳ Awaiting Database Availability
