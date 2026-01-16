# Railway PostgreSQL Migration Status

**Date:** 2026-01-16
**Status:** IN PROGRESS - Infrastructure Ready, Data Migration Pending
**Railway Project:** sap-railway-pipeline
**PostgreSQL Services:** 3 instances detected

---

## Executive Summary

**Current State:**
- ✅ Railway project created with PostgreSQL databases
- ✅ Database schema migration script written
- ✅ Database connection module implemented
- ✅ Data migration script created
- ❓ Database schema NOT yet applied to production database
- ❓ TSV data NOT yet migrated to PostgreSQL

**Next Critical Step:** Apply database schema and migrate data

---

## Railway Infrastructure Status

### Railway Project Details

```
Project Name: sap-railway-pipeline
Project IDs:
  - 6b29b7de-2219-4e37-bc15-cb46afba97b2 (created: 2026-01-15)
  - 995dd47f-b45d-493d-847c-1c4b8d59b640 (created: 2026-01-13)

Services Detected:
  - Postgres (primary database)
  - Postgres-qBea (possibly dev/staging)
  - Postgres-B08X (possibly testing)

Status: Active
```

### Database Configuration Files

| File | Status | Purpose |
|------|--------|---------|
| `railway.toml` | ✅ Created | Railway deployment config for Streamlit app |
| `.env.example` | ✅ Created | Environment variables template |
| `src/database.py` | ✅ Created | SQLAlchemy connection pooling & utilities |
| `database/migrations/001_initial_schema.sql` | ✅ Created | Complete database schema |
| `scripts/migrate_tsv_data.py` | ✅ Created | TSV to PostgreSQL migration script |

---

## Database Schema

### Schema File: `database/migrations/001_initial_schema.sql`

**Status:** Written but NOT yet applied to Railway database

**Tables Created (11 total):**
1. `warehouses` - Warehouse and location definitions
2. `vendors` - Supplier master data from SAP B1
3. `items` - Master product catalog from SAP B1
4. `inventory_current` - Current inventory levels from SAP B1
5. `costs` - Purchase cost history for margin calculations
6. `pricing` - Sales price history from SAP B1
7. `sales_orders` - Historical sales orders (demand history)
8. `purchase_orders` - Purchase order history for lead time analysis
9. `forecasts` - Forecast results by item and model
10. `forecast_accuracy` - Model performance metrics
11. `margin_alerts` - Margin monitoring alerts

**Materialized Views (3):**
1. `mv_latest_costs` - Latest cost per item for margin calculations
2. `mv_latest_pricing` - Latest active prices per item and price level
3. `mv_vendor_lead_times` - Vendor performance metrics for purchasing

**Views (3):**
1. `v_inventory_status_with_forecast` - Real-time inventory with forecasts
2. `v_items_with_costs` - Items with latest cost and pricing
3. `v_low_margin_items` - Items below margin threshold

**Indexes:** 25+ indexes for performance optimization

**Estimated Storage:** ~30 MB (well within Railway free tier of 1 GB)

---

## Database Connection Module

### File: `src/database.py`

**Features Implemented:**
- ✅ SQLAlchemy connection pooling (pool_size: 5, max_overflow: 10)
- ✅ Streamlit-compatible (cached connection pool with `@st.cache_resource`)
- ✅ Context manager support for safe connection handling
- ✅ Query execution helpers (`execute_query`, `execute_write`, `execute_batch`)
- ✅ Materialized view refresh utilities
- ✅ Database health check function
- ✅ Migration helper function
- ✅ Streamlit data caching utilities

**Connection Priority:**
1. Streamlit secrets (Railway production)
2. Environment variable `DATABASE_URL` (local development)
3. SQLite fallback (for local testing only)

---

## Data Migration Script

### File: `scripts/migrate_tsv_data.py`

**Functions Implemented:**
- ✅ `migrate_warehouses()` - Migrate warehouses from TSV data
- ✅ `migrate_vendors()` - Migrate vendors from supply TSV
- ✅ `migrate_items()` - Migrate items from TSV
- ✅ `migrate_inventory()` - Migrate current inventory levels
- ✅ `migrate_sales()` - Migrate sales orders (samples 1000 for testing)
- ✅ `migrate_purchase_orders()` - Migrate purchase orders (samples 1000 for testing)
- ✅ `migrate_costs()` - Migrate cost data
- ✅ `run_migration()` - Complete migration orchestration

**Status:** Script created but NOT yet executed

---

## What Has NOT Been Done Yet

### Critical Missing Steps:

1. **❌ Database Schema Not Applied**
   - The `001_initial_schema.sql` file exists but hasn't been executed on the Railway PostgreSQL database
   - **Impact:** No tables exist in the database yet
   - **Next Step:** Run `psql` or use Railway console to apply the schema

2. **❌ Data Not Migrated**
   - The `migrate_tsv_data.py` script exists but hasn't been executed
   - **Impact:** Database is empty, no data to work with
   - **Next Step:** Run migration script after schema is applied

3. **❌ Railway Project Not Linked**
   - Local project not linked to Railway project via `railway link`
   - **Impact:** Cannot use Railway MCP tools directly
   - **Next Step:** Complete `railway link` command (requires interactive terminal)

4. **❌ Environment Variables Not Configured**
   - `DATABASE_URL` not set in local environment or Railway secrets
   - **Impact:** Database connection will fail
   - **Next Step:** Add DATABASE_URL to Railway variables and local .env

5. **❌ Streamlit App Not Updated for Database**
   - Current Streamlit app (`app.py`) still loads from TSV files
   - **Impact:** App won't use Railway database even after migration
   - **Next Step:** Update data loading code to use `src/database.py`

---

## Implementation Checklist

### Phase 1: Database Schema Application (CRITICAL - Do First)

- [ ] 1. Link Railway project to local directory
  ```bash
  railway link
  # Select: sap-railway-pipeline (6b29b7de...)
  ```

- [ ] 2. Get Railway database connection string
  ```bash
  railway variables
  # Copy DATABASE_URL value
  ```

- [ ] 3. Apply database schema to Railway database
  ```bash
  # Option A: Use Railway console
  railway open
  # Select Postgres service
  # Run: \i database/migrations/001_initial_schema.sql

  # Option B: Use psql directly
  psql $DATABASE_URL < database/migrations/001_initial_schema.sql
  ```

- [ ] 4. Verify schema was created
  ```bash
  # In Railway console or psql:
  \dt  # List tables - should show 11 tables
  \dm  # List materialized views - should show 3 views
  ```

### Phase 2: Data Migration

- [ ] 5. Set DATABASE_URL environment variable locally
  ```bash
  # In .env file:
  DATABASE_URL=postgresql://user:password@host:port/database
  ```

- [ ] 6. Test database connection
  ```bash
  python src/database.py
  # Should output: Database health: healthy
  ```

- [ ] 7. Run data migration script
  ```bash
  python scripts/migrate_tsv_data.py
  ```

- [ ] 8. Verify data migration
  ```bash
  # In Railway console or psql:
  SELECT COUNT(*) FROM items;  # Should be ~2,645
  SELECT COUNT(*) FROM inventory_current;  # Should be ~2,645
  SELECT COUNT(*) FROM sales_orders;  # Should be 70,080
  SELECT COUNT(*) FROM purchase_orders;  # Should be ~10,000
  ```

### Phase 3: Streamlit App Integration

- [ ] 9. Update Streamlit app to use database
  - [ ] Replace TSV loading with database queries in `app.py`
  - [ ] Use `src/database.py` functions for all data access
  - [ ] Test all tabs with database data
  - [ ] Verify forecasting works with database queries

- [ ] 10. Update Streamlit secrets for Railway deployment
  - [ ] Add DATABASE_URL to Railway project variables
  - [ ] Test Railway deployment with `railway up`

### Phase 4: Testing & Validation

- [ ] 11. End-to-end testing
  - [ ] Test all Streamlit tabs with database data
  - [ ] Verify forecasting accuracy matches TSV-based results
  - [ ] Test inventory optimization with database queries
  - [ ] Validate margin calculations with materialized views

- [ ] 12. Performance testing
  - [ ] Test query response times
  - [ ] Optimize slow queries if needed
  - [ ] Verify connection pooling works correctly
  - [ ] Test materialized view refresh performance

---

## Architecture Changes (Supabase → Railway)

### What Changed:

**Before (Supabase Plan):**
- Supabase for processed data storage
- Railway for backend processing only
- FastAPI backend separate from Streamlit
- Next.js frontend on Vercel

**After (Railway Only):**
- **Railway PostgreSQL for ALL data storage**
- Streamlit app remains (no architecture change)
- Database-first approach (no separate backend initially)
- **No Supabase** (all data in Railway PostgreSQL)

### Why This Is Better:

1. **Simpler Architecture:** One database instead of two
2. **Lower Cost:** Railway free tier (1 GB) vs Supabase free tier (500 MB)
3. **Easier Deployment:** No backend/frontend separation needed yet
4. **Direct Access:** Streamlit can query Railway PostgreSQL directly
5. **Materialized Views:** Advanced PostgreSQL features available
6. **Connection Pooling:** SQLAlchemy manages connections efficiently

---

## Migration Plan Updates Needed

### Files to Update:

1. **MIGRATION_IMPLEMENTATION_PLAN.md** - Remove all Supabase references
   - Remove Supabase schema sections
   - Remove Supabase client setup
   - Replace with Railway PostgreSQL sections
   - Update architecture diagrams

2. **Railway.toml** - Add PostgreSQL service configuration
   - Add database volume mount
   - Add database environment variables
   - Configure health checks for database

3. **app.py** - Update data loading
   - Replace TSV file loading with database queries
   - Use `src/database.py` for all data access
   - Add database health check to UI

---

## Database Health Check

### Current Status: UNKNOWN (Cannot test until linked and configured)

**Expected Output After Setup:**
```python
{
  "status": "healthy",
  "connection": "ok",
  "pool_size": 5,
  "active_connections": 2
}
```

**Test Command:**
```bash
python src/database.py
```

---

## Cost Analysis

### Railway PostgreSQL Costs

**Free Tier:**
- 1 GB storage (we need ~30 MB = 3%)
- 500 hours of compute per month
- Sufficient for development and testing

**Expected Monthly Cost:** $0 (free tier)

**Storage Breakdown:**
- Items: ~2 MB (2,645 items × 11 columns)
- Inventory: ~3 MB (2,645 records × 9 columns)
- Sales Orders: ~15 MB (70,080 orders × 8 columns)
- Purchase Orders: ~5 MB (10,000 POs × 12 columns)
- Costs & Pricing: ~3 MB (cost history)
- Forecasts: ~2 MB (forecast results)
- **Total: ~30 MB (3% of free tier)**

---

## Risk Assessment

### High Risk Items:

1. **❌ Schema Not Applied** - Critical blocker
   - **Mitigation:** Apply schema immediately before any data migration

2. **❌ Database Not Linked** - Cannot proceed
   - **Mitigation:** Complete `railway link` in interactive terminal

3. **❌ Streamlit App Not Updated** - App won't use database
   - **Mitigation:** Plan for major refactoring of data loading code

### Medium Risk Items:

1. **Data Migration Time** - 70,000+ sales orders may take time
   - **Mitigation:** Use batch inserts, monitor progress

2. **Connection Pooling** - May need tuning for workload
   - **Mitigation:** Monitor pool usage, adjust if needed

3. **Materialized View Refresh** - May slow down data updates
   - **Mitigation:** Schedule refresh during low-traffic periods

---

## Next Steps (Priority Order)

### CRITICAL (Do Today):

1. **Link Railway project** (requires interactive terminal)
   ```bash
   railway link
   ```

2. **Get DATABASE_URL** from Railway
   ```bash
   railway variables
   ```

3. **Apply database schema** to Railway database
   ```bash
   psql $DATABASE_URL < database/migrations/001_initial_schema.sql
   ```

4. **Verify schema creation**
   ```bash
   psql $DATABASE_URL -c "\dt"
   ```

### HIGH PRIORITY (Do This Week):

5. **Run data migration script**
   ```bash
   python scripts/migrate_tsv_data.py
   ```

6. **Verify data migrated correctly**
   - Check row counts match expectations
   - Validate data integrity
   - Test queries return expected results

7. **Update Streamlit app to use database**
   - Refactor data loading to use `src/database.py`
   - Test all functionality with database queries
   - Remove TSV file dependencies

8. **Deploy updated app to Railway**
   ```bash
   railway up
   ```

### MEDIUM PRIORITY (Do Next Week):

9. **Set up automated data refresh**
   - Create cron job for daily data sync
   - Implement incremental updates (not full migration)
   - Add error handling and notifications

10. **Optimize database performance**
    - Add missing indexes if queries are slow
    - Tune connection pool settings
    - Optimize materialized view refresh strategy

---

## Summary

**Current State:**
- Infrastructure: ✅ READY (Railway project exists, PostgreSQL running)
- Schema: ⚠️ WRITTEN BUT NOT APPLIED
- Data: ❌ NOT MIGRATED
- App: ❌ NOT UPDATED FOR DATABASE

**Readiness:** 40% complete

**Critical Blocker:** Database schema not yet applied to Railway database

**Estimated Time to Completion:** 2-4 hours (once Railway project is linked)

---

**Next Action:** Link Railway project and apply database schema

**Prepared by:** Claude (AI Assistant)
**Date:** 2026-01-16
