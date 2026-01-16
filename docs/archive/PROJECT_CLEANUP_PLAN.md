# Project Cleanup & Organization Plan

**Date:** 2026-01-16
**Status:** Ready for Execution

---

## Current Issues

1. **31 markdown files** cluttering the project root
2. **Test files** (`test_*.py`) scattered in root
3. **Config files** not centralized
4. **No archive** for old documentation
5. **No clear structure** for different doc types

---

## Target Structure

```
forecastv3/
├── app.py                          # Main Streamlit app
├── pyproject.toml                  # Python project config
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Test configuration
├── railway.toml                    # Railway deployment config
├── railway-worker.toml             # Railway worker config
├── railway_settings.json           # Railway settings
│
├── config.yaml                     # App configuration
├── config_inventory_optimization.yaml  # Inventory optimization config
├── uom_mapping.yaml                # UoM mapping configuration
│
├── docs/                           # ALL documentation
│   ├── README.md                   # Project overview (NEW)
│   ├── index.md                    # Documentation index (NEW)
│   │
│   ├── guides/                     # How-to guides
│   │   ├── FORECASTING_TOOL_GUIDE.md
│   │   ├── INVENTORY_OPTIMIZATION_GUIDE.md
│   │   ├── WEBAPP_MIGRATION_GUIDE.md
│   │   └── RUN_APP.md
│   │
│   ├── reports/                    # Analysis & benchmark reports
│   │   ├── BENCHMARK_REPORT.md
│   │   ├── REAL_DATA_VALIDATION_REPORT.md
│   │   ├── PERFORMANCE_OPTIMIZATION_SUMMARY.md
│   │   ├── PERFORMANCE_ANALYSIS.md
│   │   └── REGIONAL_FORECAST_IMPACT_ANALYSIS.md
│   │
│   ├── planning/                   # Project planning documents
│   │   ├── PROJECT_STATUS.md
│   │   ├── IMPLEMENTATION_PLAN.md
│   │   ├── IMPLEMENTATION_ROADMAP.md
│   │   ├── MIGRATION_IMPLEMENTATION_PLAN.md
│   │   └── RAILWAY_DEPLOYMENT_SOLUTION.md
│   │
│   ├── database/                   # Database & migration docs
│   │   ├── DATABASE_SCHEMA_DESIGN.md
│   │   ├── RAILWAY_POSTGRESQL_MIGRATION_PLAN.md
│   │   └── SAP_B1_DATA_RECOMMENDATIONS.md
│   │
│   ├── consolidation/              # Item master consolidation docs
│   │   ├── FORECASTING_CONSOLIDATION_ANALYSIS.md
│   │   └── FORECASTING_TOOL_GUIDE.md
│   │
│   └── archive/                    # Old/historical docs
│       ├── CODE_REVIEW_SUMMARY.md
│       ├── IMPLEMENTATION_SUMMARY.md
│       ├── PROJECT_REVIEW_SUMMARY.md
│       ├── SRED_PROJECT_LOG.md
│       ├── FIXES_SUMMARY.md
│       ├── BUG_FIX_PLAN.md
│       ├── CRITICAL_BUGS_FIXED.md
│       ├── IMPROVEMENTS_AND_BUG_FIXES_SUMMARY.md
│       ├── CONCURRENT_EXECUTION_FIX.md
│       ├── CONCURRENCY_GUARD_IMPLEMENTATION.md
│       ├── TIMING_FEATURES.md
│       ├── INVENTORY_HEALTH_IMPLEMENTATION.md
│       ├── CONSTRAINED_OPTIMIZATION_IMPLEMENTATION.md
│       ├── SHORTAGE_LOGIC_RECOMMENDATIONS.md
│       ├── WEBAPP_STRUCTURE.md
│       ├── RAILWAY_DEPLOYMENT_EXECUTIVE_SUMMARY.md
│       └── project_brief.md
│
├── src/                            # Source code (already organized)
├── scripts/                        # Utility scripts
├── tests/                          # Test files
├── data/                           # Data files
│   ├── raw/                        # Raw TSV exports from SAP
│   ├── sap_queries/                # SAP query results (NEW)
│   ├── cache/                      # Cached forecasts
│   └── logs/                       # Application logs
│
├── queries/                        # SQL queries for SAP B1
├── database/                       # Database migration scripts
│
└── venv/                           # Virtual environment (ignored by git)
```

---

## File Migration Plan

### Phase 1: Create Folders (DONE)
- ✅ `docs/guides/`
- ✅ `docs/reports/`
- ✅ `docs/planning/`
- ✅ `docs/database/`
- ✅ `docs/consolidation/`
- ✅ `docs/archive/`
- ✅ `data/sap_queries/`

### Phase 2: Move Documentation Files

**Guides** (`docs/guides/`):
- `FORECASTING_TOOL_GUIDE.md`
- `INVENTORY_OPTIMIZATION_GUIDE.md`
- `WEBAPP_MIGRATION_GUIDE.md`
- `RUN_APP.md`

**Reports** (`docs/reports/`):
- `BENCHMARK_REPORT.md`
- `REAL_DATA_VALIDATION_REPORT.md`
- `PERFORMANCE_OPTIMIZATION_SUMMARY.md`
- `PERFORMANCE_ANALYSIS.md`
- `REGIONAL_FORECAST_IMPACT_ANALYSIS.md`

**Planning** (`docs/planning/`):
- `PROJECT_STATUS.md`
- `IMPLEMENTATION_PLAN.md`
- `IMPLEMENTATION_ROADMAP.md`
- `MIGRATION_IMPLEMENTATION_PLAN.md`
- `RAILWAY_DEPLOYMENT_SOLUTION.md`

**Database** (`docs/database/`):
- `DATABASE_SCHEMA_DESIGN.md`
- `RAILWAY_POSTGRESQL_MIGRATION_PLAN.md`
- `SAP_B1_DATA_RECOMMENDATIONS.md`

**Consolidation** (`docs/consolidation/`):
- `FORECASTING_CONSOLIDATION_ANALYSIS.md`

**Archive** (`docs/archive/):
- `CODE_REVIEW_SUMMARY.md`
- `IMPLEMENTATION_SUMMARY.md`
- `PROJECT_REVIEW_SUMMARY.md`
- `SRED_PROJECT_LOG.md`
- `FIXES_SUMMARY.md`
- `BUG_FIX_PLAN.md`
- `CRITICAL_BUGS_FIXED.md`
- `IMPROVEMENTS_AND_BUG_FIXES_SUMMARY.md`
- `CONCURRENT_EXECUTION_FIX.md`
- `CONCURRENCY_GUARD_IMPLEMENTATION.md`
- `TIMING_FEATURES.md`
- `INVENTORY_HEALTH_IMPLEMENTATION.md`
- `CONSTRAINED_OPTIMIZATION_IMPLEMENTATION.md`
- `SHORTAGE_LOGIC_RECOMMENDATIONS.md`
- `WEBAPP_STRUCTURE.md`
- `RAILWAY_DEPLOYMENT_EXECUTIVE_SUMMARY.md`
- `project_brief.md`

### Phase 3: Move Test Files
- `test_cleaning.py` → `tests/`
- `test_ingestion.py` → `tests/`
- `test_full_pipeline.py` → `tests/`
- `forecast_tab_update.py` → `scripts/` (or delete if obsolete)

### Phase 4: Clean Root Directory
Remove/move from root:
- `benchmark_output.log` → `data/logs/`
- `benchmark_results.json` → `data/cache/`
- `real_data_benchmark_results.json` → `data/cache/`
- `nul` (delete - Windows null device file)

### Phase 5: Create Navigation Files
- `docs/README.md` - Main project documentation
- `docs/index.md` - Documentation index with links

---

## Execution Commands

```powershell
# Phase 2: Move documentation files
mv FORECASTING_TOOL_GUIDE.md docs/guides/
mv INVENTORY_OPTIMIZATION_GUIDE.md docs/guides/
mv WEBAPP_MIGRATION_GUIDE.md docs/guides/
mv RUN_APP.md docs/guides/

mv BENCHMARK_REPORT.md docs/reports/
mv REAL_DATA_VALIDATION_REPORT.md docs/reports/
mv PERFORMANCE_OPTIMIZATION_SUMMARY.md docs/reports/
mv PERFORMANCE_ANALYSIS.md docs/reports/
mv REGIONAL_FORECAST_IMPACT_ANALYSIS.md docs/reports/

mv PROJECT_STATUS.md docs/planning/
mv IMPLEMENTATION_PLAN.md docs/planning/
mv IMPLEMENTATION_ROADMAP.md docs/planning/
mv MIGRATION_IMPLEMENTATION_PLAN.md docs/planning/
mv RAILWAY_DEPLOYMENT_SOLUTION.md docs/planning/

mv DATABASE_SCHEMA_DESIGN.md docs/database/
mv RAILWAY_POSTGRESQL_MIGRATION_PLAN.md docs/database/
mv SAP_B1_DATA_RECOMMENDATIONS.md docs/database/

mv FORECASTING_CONSOLIDATION_ANALYSIS.md docs/consolidation/

mv CODE_REVIEW_SUMMARY.md docs/archive/
mv IMPLEMENTATION_SUMMARY.md docs/archive/
mv PROJECT_REVIEW_SUMMARY.md docs/archive/
mv SRED_PROJECT_LOG.md docs/archive/
mv FIXES_SUMMARY.md docs/archive/
mv BUG_FIX_PLAN.md docs/archive/
mv CRITICAL_BUGS_FIXED.md docs/archive/
mv IMPROVEMENTS_AND_BUG_FIXES_SUMMARY.md docs/archive/
mv CONCURRENT_EXECUTION_FIX.md docs/archive/
mv CONCURRENCY_GUARD_IMPLEMENTATION.md docs/archive/
mv TIMING_FEATURES.md docs/archive/
mv INVENTORY_HEALTH_IMPLEMENTATION.md docs/archive/
mv CONSTRAINED_OPTIMIZATION_IMPLEMENTATION.md docs/archive/
mv SHORTAGE_LOGIC_RECOMMENDATIONS.md docs/archive/
mv WEBAPP_STRUCTURE.md docs/archive/
mv RAILWAY_DEPLOYMENT_EXECUTIVE_SUMMARY.md docs/archive/
mv project_brief.md docs/archive/

# Phase 3: Move test files
mv test_cleaning.py tests/
mv test_ingestion.py tests/
mv test_full_pipeline.py tests/
mv forecast_tab_update.py scripts/

# Phase 4: Clean root directory
mv benchmark_output.log data/logs/
mv benchmark_results.json data/cache/
mv real_data_benchmark_results.json data/cache/
rm nul
```

---

## Files to Keep in Root

**Essential:**
- `app.py` - Main application
- `pyproject.toml` - Python project config
- `requirements.txt` - Dependencies
- `pytest.ini` - Test config
- `railway.toml` - Railway config
- `railway-worker.toml` - Railway worker config
- `railway_settings.json` - Railway settings

**Configuration:**
- `config.yaml` - App config
- `config_inventory_optimization.yaml` - Inventory config
- `uom_mapping.yaml` - UoM mappings

**Optional (could also move to docs/):**
- Create `README.md` in root for quick project overview

---

## Next Steps

1. Execute the file migration commands above
2. Create `docs/README.md` and `docs/index.md`
3. Update any hardcoded paths in scripts
4. Create `.gitignore` rules for temp files
5. Create `PROJECT_RULES.md` for ongoing maintenance

---

**Status:** Ready for execution
**Estimated Time:** 10 minutes
