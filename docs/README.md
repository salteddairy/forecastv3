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
| **Implementation** | 🔄 10% Complete (Week 0-1) |
| **Bug Fixes** | ✅ 5 critical bugs fixed |
| **Performance** | ✅ 30-40% faster pipeline |
| **Consolidation Ready** | ⚠️ 70% - Needs warehouse-aware forecasting |

**Current Status:** Ready to start Week 1 tasks (Railway deployment)

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

### Current (Streamlit App)
- **Frontend:** Streamlit (app.py)
- **Data:** TSV exports from SAP B1
- **Forecasting:** Prophet, statsmodels
- **Optimization:** TCO-based decision logic

### Planned (Railway Deployment)
- **Backend:** FastAPI (new)
- **Database:** PostgreSQL 16 on Railway
- **Cache:** Redis 7 on Railway
- **Auth:** Azure AD (MSAL)
- **Scheduler:** APScheduler + Redis

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

### 2026-01-16 (Today)
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

**For You (Right Now):**
1. Run `queries/analyze_multi_warehouse_item_fixed.sql` in SAP B1
2. Paste results into `data/sap_queries/*.tsv` files
3. Share results for validation

**This Week:**
1. Validate SAP query results
2. Implement warehouse-aware forecasting (see REGIONAL_FORECAST_IMPACT_ANALYSIS.md)

**Next 2 Weeks:**
1. Create Railway PostgreSQL database
2. Run initial schema migration
3. Create FastAPI backend structure

---

## Support

**Questions?**
- Item master consolidation: See `docs/consolidation/`
- Database issues: See `docs/database/`
- Performance problems: See `docs/reports/PERFORMANCE_*`
- File organization: See `PROJECT_RULES.md`

---

## Project Info

**Version:** Snapshot v1
**Last Updated:** 2026-01-16
**License:** Internal (Pace Solutions)
**Team:** Nathan Dery (nathan@pacesolutions.com)

**Deployment Target:** Railway (PostgreSQL + Redis + FastAPI + Streamlit)
**Budget:** $40/month target
**Timeline:** 12 weeks to full Railway deployment
