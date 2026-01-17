# SAP B1 Inventory & Forecast Analyzer

**Snapshot v1** - SAP B1 Inventory & Forecast Analyzer with TCO-based optimization

---

## Quick Start

```bash
# Activate virtual environment
venv\Scripts\activate

# Run the Streamlit app
streamlit run app.py
```

**See:** [RUN_APP.md](guides/RUN_APP.md) for detailed instructions

---

## Project Status

| Metric | Status |
|--------|--------|
| **Planning** | ✅ 100% Complete |
| **Railway Deployment** | ✅ 80% Complete - Ingestion Service Live |
| **Bug Fixes** | ✅ 5 critical bugs fixed |
| **Performance** | ✅ 30-40% faster pipeline |
| **Consolidation Ready** | ⚠️ 70% - Needs warehouse-aware forecasting |

**Current Status:** Ingestion service deployed on Railway, ready for SAP middleware integration

**See:** [PROJECT_STATUS.md](planning/PROJECT_STATUS.md) for full roadmap

---

## What This Does

1. **Demand Forecasting** - Tournament approach (SMA, Holt-Winters, Prophet, ARIMA)
2. **Inventory Optimization** - TCO analysis (carrying cost vs special order surcharge)
3. **Multi-Warehouse Support** - Forecasting by warehouse/region
4. **Automated Ordering** - Purchase recommendations based on forecast + lead time
5. **SAP B1 Integration** - Export/import via TSV files

**Key Innovation:** Compare "cost to stock" vs "cost to special order" for each item

---

## Technology Stack

### Current Architecture
- **Ingestion API:** FastAPI on Railway (ingestion-service-production-6947.up.railway.app)
- **Database:** PostgreSQL 17 on Railway (11 tables, 5 materialized views, 2 views)
- **Security:** Fernet encryption (AES-128), API key authentication
- **Data Pipeline:** Single entry point architecture (all writes via ingestion API)

### Frontend (Planned - Vercel)
- **Framework:** Next.js (to be built)
- **Deployment:** Vercel
- **Database Access:** Read-only direct PostgreSQL queries

### Legacy (Streamlit App - Local Only)
- **Frontend:** Streamlit (app.py)
- **Data:** TSV exports from SAP B1
- **Forecasting:** Prophet, statsmodels
- **Status:** Being phased out in favor of Railway deployment

---

## Project Structure

```
forecastv3/
├── app.py                    # Main Streamlit app
├── src/                      # Source code modules
├── scripts/                  # Utility scripts
├── tests/                    # Test files
├── docs/                     # Documentation (organized by category)
├── data/                     # Data files
│   ├── raw/                  # SAP exports (TSV)
│   ├── sap_queries/          # SAP query results
│   ├── cache/                # Cached forecasts
│   └── logs/                 # Application logs
├── queries/                  # SQL queries for SAP B1
└── database/                 # Database migrations
```

**See:** [docs/index.md](docs/index.md) for complete documentation

---

## Important Notes

### ⚠️ Critical: Item Master Consolidation

**Forecasting will lose regional accuracy** after item master consolidation without code changes.

**Read:**
- [REGIONAL FORECAST IMPACT ANALYSIS](reports/REGIONAL_FORECAST_IMPACT_ANALYSIS.md)
- [FORECASTING CONSOLIDATION ANALYSIS](consolidation/FORECASTING_CONSOLIDATION_ANALYSIS.md)

**Fix Required:** Implement warehouse-aware forecasting (13 hours, HIGH priority)

### Current Data Quality

- **2,645 items** in item master
- **70,080 sales orders**
- **10,271 purchase orders**
- **91.3% current state** (regional suffixes)
- **8.7% future state** (consolidated)

---

## Recent Achievements

### 2026-01-17 (Today) - Database Schema Simplification
- ✅ Identified that order tracking not needed for forecasting use case
- ✅ Performed full impact assessment (zero breaking changes)
- ✅ Created migration 004 to simplify schema (remove order tracking)
- ✅ Updated Pydantic models to make order identifiers optional
- ✅ Updated database operations to use business keys for UPSERT
- ✅ Regenerated test data without order identifiers
- ✅ Deployed updated ingestion service to Railway
- 🔄 Database migration pending (Railway temporarily unavailable)

### 2026-01-17 (Earlier Today) - Database Schema Alignment
- ✅ Fixed schema mismatches in sales_orders, purchase_orders, and pricing tables
- ✅ Updated Pydantic models to match database schema exactly
- ✅ Implemented generated column handling (COALESCE for region_key/vendor_code_key)
- ✅ Fixed UPSERT conflict resolution for complex primary keys
- ✅ Regenerated middleware test data with corrected schema

### 2026-01-16 (Yesterday) - Railway Deployment Complete
- ✅ FastAPI ingestion service deployed to Railway
- ✅ PostgreSQL 17 database schema applied (11 tables, 5 materialized views, 2 views)
- ✅ Fernet encryption implemented for payload security
- ✅ API key authentication configured
- ✅ End-to-end test successful (data ingested and verified)
- ✅ Single entry point architecture established
- ✅ Middleware test data generated (8 data types with samples)

### 2026-01-15 (Yesterday)
- ✅ Created `data/sap_queries/` with TSV templates for SAP exports
- ✅ Fixed SQL queries for SAP B1 compatibility
- ✅ Organized 31 documentation files into `docs/` structure
- ✅ Created `PROJECT_RULES.md` for ongoing maintenance
- ✅ Tested consolidation module with existing data

### 2025 (Archive)
- ✅ Fixed 5 critical bugs (division by zero, cache race conditions)
- ✅ Implemented vectorized operations (100-1000x speedup)
- ✅ Added thread-safe cache with concurrency guards
- ✅ Created consolidation module for item master transition

---

## Quick Links

### Railway Deployment
- **[DATA_PIPELINE_ARCHITECTURE.md](docs/architecture/DATA_PIPELINE_ARCHITECTURE.md)** - Single entry point architecture
- **[ingestion_service/README.md](ingestion_service/README.md)** - FastAPI ingestion service documentation
- **[tests/middleware_test_data/README.md](tests/middleware_test_data/README.md)** - Middleware test data guide

### Documentation
- **[docs/index.md](docs/index.md)** - Complete documentation index
- **[PROJECT_RULES.md](PROJECT_RULES.md)** - File organization & coding standards

### Planning
- **[PROJECT_STATUS.md](planning/PROJECT_STATUS.md)** - Current status & roadmap
- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - 12-week implementation plan

### Guides
- **[RUN_APP.md](guides/RUN_APP.md)** - How to run the app
- **[FORECASTING TOOL GUIDE](guides/FORECASTING_TOOL_GUIDE.md)** - UoM conversion guide

### Reports
- **[REGIONAL FORECAST IMPACT ANALYSIS](reports/REGIONAL_FORECAST_IMPACT_ANALYSIS.md)** - ⚠️ Critical read

---

## Next Actions

**For SAP Middleware Team:**
1. Review middleware test data in `tests/middleware_test_data/`
2. Configure middleware to POST to ingestion API endpoint
3. Test with sample encrypted payloads
4. Begin production data integration

**For Development Team:**
1. Build Next.js frontend on Vercel (read-only database access)
2. Implement forecasting engine as background job
3. Add automated materialized view refresh scheduling

**This Week:**
1. Complete SAP middleware integration testing
2. Validate production data flows
3. Monitor Railway service health and performance

---

## Support

**Questions?**
- Item master consolidation: See `docs/consolidation/`
- Database issues: See `docs/database/`
- Performance problems: See `docs/reports/PERFORMANCE_*`
- File organization: See `PROJECT_RULES.md`

---

## Project Info

**Version:** Railway v1 (Ingestion API Live)
**Last Updated:** 2026-01-16
**License:** Internal (Pace Solutions)
**Team:** Nathan Dery (nathan@pacesolutions.com)

**Railway Deployment:**
- Ingestion API: https://ingestion-service-production-6947.up.railway.app
- Database: PostgreSQL 17 on Railway (Postgres-B08X service)
- Status: ✅ Live and operational

**Deployment Target:** Railway (PostgreSQL) + Vercel (Next.js frontend)
**Budget:** ~$40/month (Railway database + service)
**Timeline:** Ingestion API complete, frontend pending
