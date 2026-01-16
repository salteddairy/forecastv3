# Railway Deployment Plan
## SAP B1 Forecast Analyzer - Streamlit + PostgreSQL Architecture

**Version:** 2.0 (Updated for Railway PostgreSQL Only)
**Date:** 2026-01-16
**Status:** Infrastructure Ready - Schema Application Pending
**Dependencies:** Railway project exists, database scripts written

---

## Executive Summary

**Goal:** Deploy Streamlit app with Railway PostgreSQL database
- **Frontend:** Streamlit (hosted on Railway)
- **Backend:** Railway PostgreSQL (all data storage)
- **Integration:** SAP B1UP for scheduled data extraction (future)
- **Cost:** $0/month (Railway free tier)

**Architecture Change:** Removed Supabase, using Railway PostgreSQL for ALL data storage

**Key Principle:** Single database (Railway PostgreSQL) with Streamlit direct access

---

## Architecture Overview (Updated)

```
┌─────────────────────────────────────────────────────────────┐
│                    SAP B1 System                             │
│  ┌──────────────┐      ┌────────────────────────────────┐  │
│  │  Sales Data  │      │        B1UP Add-on             │  │
│  │  Inventory   │ ───▶ │  (Scheduled Query Execution)    │  │
│  │  Supply      │      │  - Export TSV files            │  │
│  └──────────────┘      │  - Upload to Railway           │  │
│                        │  - Schedule: Daily 2AM          │  │
│                        └────────────┬───────────────────┘  │
└─────────────────────────────────────┼───────────────────────┘
                                         │
                                         │ TSV upload (future)
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Railway Platform                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Streamlit App (Web Service)                         │  │
│  │  - Port 8501                                         │  │
│  │  - Direct database access                           │  │
│  │  - Forecasting & optimization                        │  │
│  └───────────┬──────────────────────────────────────────┘  │
│              │                                              │
│              │ SQLAlchemy (connection pooling)              │
│              ▼                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Database                                  │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │ Core Tables                                     │   │  │
│  │  │ - items (2,645 rows)                           │   │  │
│  │  │ - inventory_current (2,645 rows)               │   │  │
│  │  │ - sales_orders (70,080 rows)                   │   │  │
│  │  │ - purchase_orders (10,000 rows)                │   │  │
│  │  │ - vendors, warehouses, costs, pricing           │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │ Materialized Views                             │   │  │
│  │  │ - mv_latest_costs                              │   │  │
│  │  │ - mv_latest_pricing                            │   │  │
│  │  │ - mv_vendor_lead_times                         │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │ Standard Views                                  │   │  │
│  │  │ - v_inventory_status_with_forecast             │   │  │
│  │  │ - v_items_with_costs                           │   │  │
│  │  │ - v_low_margin_items                           │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Storage: ~30 MB (3% of 1 GB free tier)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Current State (Development)
```
SAP B1 → Manual TSV export → data/raw/ → Streamlit app (load from files)
```

### Target State (Production - After Migration)
```
SAP B1 → Manual TSV export → migration script → Railway PostgreSQL
                                                           ↓
                                                  Streamlit app (queries)
```

### Future State (Automated - B1UP Integration)
```
SAP B1 → B1UP scheduled query → Railway API → migration script → Railway PostgreSQL
                                                                       ↓
                                                              Streamlit app (queries)
```

---

## Database Schema

### Tables (11 total)

1. **warehouses** - Warehouse definitions
2. **vendors** - Supplier master data
3. **items** - Product catalog (2,645 items)
4. **inventory_current** - Current inventory levels
5. **costs** - Purchase cost history
6. **pricing** - Sales price history
7. **sales_orders** - Historical sales (70,080 orders)
8. **purchase_orders** - PO history for lead times
9. **forecasts** - Forecast results by item/model
10. **forecast_accuracy** - Model performance metrics
11. **margin_alerts** - Margin monitoring

### Materialized Views (3)

- **mv_latest_costs** - Latest cost per item (margin calculations)
- **mv_latest_pricing** - Latest active prices per item
- **mv_vendor_lead_times** - Vendor performance metrics

### Views (3)

- **v_inventory_status_with_forecast** - Real-time inventory + forecasts
- **v_items_with_costs** - Items with cost and pricing
- **v_low_margin_items** - Items below margin threshold

**Schema File:** `database/migrations/001_initial_schema.sql`
**Estimated Storage:** ~30 MB

---

## Current Implementation Status

### ✅ Completed

| Component | Status | Details |
|-----------|--------|---------|
| **Railway Project** | ✅ Created | `sap-railway-pipeline` with 3 PostgreSQL services |
| **Database Schema** | ✅ Written | `001_initial_schema.sql` (11 tables + views) |
| **Database Module** | ✅ Implemented | `src/database.py` (connection pooling, utilities) |
| **Migration Script** | ✅ Created | `scripts/migrate_tsv_data.py` (7 migrate functions) |
| **Railway Config** | ✅ Created | `railway.toml` (Streamlit deployment) |
| **Environment Template** | ✅ Created | `.env.example` (all variables documented) |
| **Local Streamlit App** | ✅ Working | All bugs fixed, tested successfully |

### ❌ Not Started (Critical Path)

| Component | Status | Blocker |
|-----------|--------|---------|
| **Schema Applied** | ❌ Not done | Railway project not linked |
| **Data Migrated** | ❌ Not done | Schema not applied yet |
| **DATABASE_URL Set** | ❌ Not done | Railway project not linked |
| **Streamlit Updated** | ❌ Not done | Data migrated not yet |
| **B1UP Integration** | ❌ Not done | Future phase |

---

## Implementation Phases

### Phase 0: Prerequisites (COMPLETED ✅)

- [x] Railway account created
- [x] Railway project created (`sap-railway-pipeline`)
- [x] PostgreSQL services provisioned (3 instances)
- [x] Database schema designed and written
- [x] Database connection module implemented
- [x] Migration scripts created
- [x] Local Streamlit app tested and bug-free

### Phase 1: Database Setup (CRITICAL - Next Step)

**Goal:** Apply schema and migrate data to Railway PostgreSQL

**Tasks:**

1. **Link Railway project** (requires interactive terminal)
   ```bash
   cd D:\code\forecastv3
   railway link
   # Select: sap-railway-pipeline (6b29b7de...)
   ```

2. **Get DATABASE_URL**
   ```bash
   railway variables
   # Copy DATABASE_URL value
   # Example: postgresql://postgres:password@containers-us-west-1.railway.app:7923/railway
   ```

3. **Apply database schema**
   ```bash
   # Option A: Use psql
   psql $DATABASE_URL < database/migrations/001_initial_schema.sql

   # Option B: Use Python
   python -c "from src.database import run_migration; run_migration('database/migrations/001_initial_schema.sql')"

   # Option C: Use Railway console
   railway open
   # Select Postgres service
   # Run: \i database/migrations/001_initial_schema.sql
   ```

4. **Verify schema creation**
   ```bash
   psql $DATABASE_URL -c "\dt"  # Should show 11 tables
   psql $DATABASE_URL -c "\dm"  # Should show 3 materialized views
   psql $DATABASE_URL -c "\dv"  # Should show 3 views
   ```

5. **Set DATABASE_URL locally**
   ```bash
   # Create .env file
   echo "DATABASE_URL=<your-database-url>" > .env
   ```

6. **Test database connection**
   ```bash
   python src/database.py
   # Expected: Database health: healthy
   ```

**Deliverable:**
- Database schema applied to Railway PostgreSQL
- All tables, indexes, materialized views created
- Local environment can connect to Railway database

**Time Estimate:** 30 minutes

---

### Phase 2: Data Migration

**Goal:** Migrate existing TSV data to PostgreSQL

**Tasks:**

1. **Verify TSV files exist**
   ```bash
   ls -lh data/raw/
   # Should have: items.tsv, sales.tsv, supply.tsv
   ```

2. **Run migration script**
   ```bash
   python scripts/migrate_tsv_data.py
   ```

3. **Verify data migrated**
   ```bash
   psql $DATABASE_URL -c "
   SELECT
     (SELECT COUNT(*) FROM items) as items,
     (SELECT COUNT(*) FROM inventory_current) as inventory,
     (SELECT COUNT(*) FROM sales_orders) as sales,
     (SELECT COUNT(*) FROM purchase_orders) as purchases,
     (SELECT COUNT(*) FROM costs) as costs
   "

   # Expected:
   # items: ~2,645
   # inventory_current: ~2,645
   # sales_orders: 1,000 (sampled for testing)
   # purchase_orders: 1,000 (sampled for testing)
   # costs: ~2,645
   ```

4. **Refresh materialized views**
   ```bash
   psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW mv_latest_costs"
   psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW mv_latest_pricing"
   psql $DATABASE_URL -c "REFRESH MATERIALIZED VIEW mv_vendor_lead_times"
   ```

5. **Full data migration** (if sampling was used)
   - Edit `scripts/migrate_tsv_data.py`
   - Remove sampling limits from `migrate_sales()` and `migrate_purchase_orders()`
   - Re-run migration script

**Deliverable:**
- All historical data in PostgreSQL database
- Materialized views populated with latest data
- Database ready for Streamlit app queries

**Time Estimate:** 1-2 hours (depending on data volume)

---

### Phase 3: Streamlit App Integration

**Goal:** Update Streamlit app to use Railway PostgreSQL

**Tasks:**

1. **Create database-backed data loading module**
   ```python
   # src/data_loader.py
   from src.database import execute_query

   def load_items_from_db():
       query = "SELECT * FROM items"
       return execute_query(query)

   def load_inventory_from_db():
       query = "SELECT * FROM inventory_current"
       return execute_query(query)

   # ... etc for all data loading functions
   ```

2. **Update app.py to use database**
   - Replace `pd.read_csv('data/raw/items.tsv')` with `load_items_from_db()`
   - Replace all TSV file loading with database queries
   - Update caching to use `@st.cache_data` with database queries

3. **Add database health indicator to UI**
   ```python
   # In app.py sidebar
   health = check_database_health()
   st.sidebar.metric("Database", health["status"])
   ```

4. **Test all tabs with database data**
   - [ ] Dashboard tab
   - [ ] Forecasts tab
   - [ ] Inventory Optimization tab
   - [ ] Margins tab
   - [ ] Settings tab

5. **Verify forecasting works with database**
   - Load sales data from database
   - Run forecasting tournament
   - Compare results with TSV-based forecasts
   - Verify accuracy is maintained

**Deliverable:**
- Streamlit app fully migrated to Railway PostgreSQL
- All functionality working with database queries
- Performance verified acceptable

**Time Estimate:** 4-6 hours

---

### Phase 4: Railway Deployment

**Goal:** Deploy Streamlit app to Railway

**Tasks:**

1. **Add DATABASE_URL to Railway variables**
   ```bash
   railway variables set DATABASE_URL=$DATABASE_URL
   ```

2. **Update railway.toml (if needed)**
   - Verify Streamlit port configuration
   - Add health checks
   - Configure environment variables

3. **Deploy to Railway**
   ```bash
   railway up
   ```

4. **Verify deployment**
   ```bash
   railway open
   # Should open Streamlit app in browser
   ```

5. **Test deployed app**
   - Check all tabs load correctly
   - Verify database queries work
   - Test forecasting functionality
   - Check for any deployment errors

6. **Monitor performance**
   - Check Railway logs for errors
   - Monitor database connection pool usage
   - Verify page load times are acceptable

**Deliverable:**
- Streamlit app live on Railway
- Accessible via public URL
- All features working correctly
- Performance monitored and optimized

**Time Estimate:** 2-3 hours

---

### Phase 5: B1UP Integration (Future - Optional)

**Goal:** Automate data extraction from SAP B1

**This phase is OPTIONAL and can be implemented later.**

**High-Level Tasks:**

1. **Create B1UP queries** (SQL in SAP B1)
   - Sales orders query (last 12 months)
   - Inventory snapshot query
   - Purchase orders query

2. **Configure B1UP HTTP POST**
   - Endpoint: `https://your-app.railway.app/api/data/ingest`
   - Authentication: API key
   - Schedule: Daily 2 AM

3. **Create Railway API endpoint** (FastAPI)
   - Receive B1UP data
   - Validate and clean
   - Write to PostgreSQL
   - Trigger forecast refresh

4. **Automate forecast generation**
   - Railway cron job: Daily 4 AM
   - Refresh forecasts after data import
   - Update materialized views

**Time Estimate:** 8-12 hours

**Note:** This phase can be skipped initially. Manual TSV exports work fine.

---

## Cost Analysis

### Railway Costs

**Free Tier:**
- PostgreSQL: 1 GB storage (we need ~30 MB = 3%)
- Compute: 500 hours/month (sufficient for dev + light prod usage)
- Bandwidth: 100 GB/month (sufficient for our usage)

**Estimated Monthly Cost:** $0

**Storage Breakdown:**
```
Items:           2 MB   (2,645 rows)
Inventory:       3 MB   (2,645 rows)
Sales Orders:   15 MB   (70,080 rows)
Purchase Orders: 5 MB   (10,000 rows)
Costs & Pricing: 3 MB   (cost history)
Forecasts:       2 MB   (forecast results)
------------------------
Total:          30 MB   (3% of free tier)
```

### No Additional Costs

- ❌ No Supabase ($0/month saved)
- ❌ No Vercel ($0/month saved)
- ❌ No Redis (not needed initially)
- ✅ Only Railway ($0/month on free tier)

---

## Risk Assessment

### High Risk Items

1. **Schema Migration Failure** - Could corrupt data
   - **Mitigation:** Test migration on sample data first
   - **Rollback:** Keep TSV files as backup
   - **Recovery:** Re-migrate from TSV files

2. **Performance Issues** - Database queries might be slow
   - **Mitigation:** Use indexes appropriately, cache results
   - **Monitoring:** Track query times in Railway logs
   - **Optimization:** Add missing indexes if needed

3. **Connection Pool Exhaustion** - Too many concurrent users
   - **Mitigation:** Tune pool size settings
   - **Monitoring:** Track pool usage
   - **Solution:** Increase pool_size or add caching

### Medium Risk Items

1. **Data Migration Time** - 70,000+ sales orders may take hours
   - **Mitigation:** Use batch inserts, monitor progress
   - **Optimization:** Disable indexes during migration, re-enable after

2. **Streamlit Compatibility** - Some features might not work with database
   - **Mitigation:** Test thoroughly before deployment
   - **Rollback:** Keep TSV-based version as fallback

3. **Railway Free Tier Limits** - Might exceed if usage spikes
   - **Mitigation:** Monitor usage closely, set alerts
   - **Upgrade Path:** Railway paid tiers start at $5/month

---

## Rollback Plan

If database migration fails:

1. **Immediate Rollback**
   - Switch Streamlit app back to TSV file loading
   - Keep Railway database (don't delete, can retry)

2. **Data Safety**
   - TSV files remain untouched (source of truth)
   - Database is disposable (can re-migrate anytime)

3. **Recovery**
   - Fix migration script issue
   - Re-run migration
   - Re-test

---

## Next Steps (Priority Order)

### CRITICAL (Do Today):

1. **Link Railway project** (requires interactive terminal)
   ```bash
   cd D:\code\forecastv3
   railway link
   ```

2. **Apply database schema**
   ```bash
   psql $DATABASE_URL < database/migrations/001_initial_schema.sql
   ```

3. **Verify schema**
   ```bash
   psql $DATABASE_URL -c "\dt"
   ```

### HIGH PRIORITY (Do This Week):

4. **Migrate data**
   ```bash
   python scripts/migrate_tsv_data.py
   ```

5. **Update Streamlit app**
   - Refactor data loading to use database queries
   - Test all functionality

6. **Deploy to Railway**
   ```bash
   railway up
   ```

### MEDIUM PRIORITY (Do Next Week):

7. **Monitor performance**
   - Check Railway logs
   - Optimize slow queries
   - Tune connection pool

8. **Plan B1UP integration** (optional)
   - Design API endpoint
   - Configure B1UP queries
   - Schedule automated exports

---

## Architecture Comparison

### Before (Original Plan with Supabase)
```
SAP B1 → B1UP → Railway API → Railway Volume → Supabase → Vercel Frontend
                                      (raw)      (processed)
```
**Cost:** $5-35/month
**Complexity:** High (4 services)
**Data:** Duplicated (raw + processed)

### After (Simplified Railway Only)
```
SAP B1 → Manual/B1UP → Railway PostgreSQL → Streamlit on Railway
```
**Cost:** $0/month
**Complexity:** Low (1 service)
**Data:** Single source of truth

---

## Monitoring & Maintenance

### Health Checks

- **Database connectivity:** `check_database_health()` in `src/database.py`
- **Materialized view freshness:** Track last refresh time
- **Query performance:** Monitor slow queries in Railway logs
- **Storage usage:** Railway dashboard shows database size

### Regular Maintenance

- **Daily:** Refresh materialized views (if new data added)
- **Weekly:** Check storage usage, review performance
- **Monthly:** Vacuum analyze database, update statistics

### Backup Strategy

- **Railway:** Automatic backups (7-day retention)
- **Export:** Weekly dump to local machine (optional)
- **Source of Truth:** TSV files kept as backup

---

## Summary

**Current State:**
- Infrastructure: ✅ READY (Railway project exists, PostgreSQL running)
- Schema: ⚠️ WRITTEN BUT NOT APPLIED
- Data: ❌ NOT MIGRATED
- App: ❌ NOT UPDATED FOR DATABASE

**Readiness:** 40% complete

**Critical Blocker:** Database schema not yet applied to Railway database

**Estimated Time to Completion:** 8-12 hours (once Railway project is linked)

**Next Action:** Link Railway project and apply database schema

---

**Prepared by:** Claude (AI Assistant)
**Date:** 2026-01-16
**Status:** Ready for Phase 1 implementation
