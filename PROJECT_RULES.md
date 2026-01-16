# Project Rules & Guidelines

**Version:** 1.0
**Last Updated:** 2026-01-16
**Status:** Active

---

## Core Principles

1. **Clean Root Directory** - Only essential files in project root
2. **Organized Documentation** - All docs in `docs/` with proper categorization
3. **Consistent Naming** - `UPPER_CASE` for constants, `snake_case` for functions/files
4. **No Orphaned Files** - Every file has a purpose and a place
5. **Archive Old Docs** - Historical documents go to `docs/archive/`

---

## File Organization Rules

### Root Directory (Keep Minimal)

**Allowed in root:**
```
forecastv3/
├── app.py                      # Main Streamlit app
├── pyproject.toml              # Python project config
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test configuration
├── railway.toml                # Railway deployment config
├── config.yaml                 # App configuration
├── config_inventory_optimization.yaml
├── uom_mapping.yaml            # UoM configuration
├── README.md                   # Project overview (NEW - needed)
└── .gitignore                  # Git ignore rules
```

**NOT allowed in root:**
- ❌ Test files (go in `tests/`)
- ❌ Scripts (go in `scripts/`)
- ❌ Documentation (go in `docs/`)
- ❌ Log files (go in `data/logs/`)
- ❌ Cache files (go in `data/cache/`)
- ❌ Backup files (delete or archive)
- ❌ Random `.py` files (organize properly)

### Directory Structure

```
forecastv3/
├── src/                        # Source code modules
│   ├── __init__.py
│   ├── forecasting.py
│   ├── ingestion.py
│   ├── consolidation.py
│   └── ...
│
├── scripts/                    # Utility and admin scripts
│   ├── test_consolidation.py
│   ├── check_consolidation_readiness.py
│   └── ...
│
├── tests/                      # Test files
│   ├── __init__.py
│   ├── test_forecasting.py
│   ├── test_ingestion.py
│   └── ...
│
├── docs/                       # ALL documentation
│   ├── README.md               # Docs overview
│   ├── index.md                # Docs index
│   ├── guides/                 # How-to guides
│   ├── reports/                # Analysis reports
│   ├── planning/               # Project planning
│   ├── database/               # Database docs
│   ├── consolidation/          # Consolidation docs
│   └── archive/                # Old docs (read-only)
│
├── data/                       # Data files
│   ├── raw/                    # SAP exports (TSV)
│   ├── sap_queries/            # SAP query results
│   ├── cache/                  # Cached data
│   └── logs/                   # Application logs
│
├── queries/                    # SQL queries for SAP B1
├── database/                   # Database migrations
└── venv/                       # Virtual environment (gitignored)
```

---

## Documentation Rules

### File Naming

**Use descriptive names:**
- ✅ `FORECASTING_TOOL_GUIDE.md`
- ✅ `REGIONAL_FORECAST_IMPACT_ANALYSIS.md`
- ✅ `RAILWAY_DEPLOYMENT_SOLUTION.md`

**Avoid vague names:**
- ❌ `notes.md`
- ❌ `todo.md`
- ❌ `analysis.md`

### Document Categories

**1. Guides** (`docs/guides/`)
- How-to documentation
- User guides
- Setup instructions
- Example: `FORECASTING_TOOL_GUIDE.md`

**2. Reports** (`docs/reports/`)
- Analysis results
- Benchmark reports
- Validation reports
- Example: `BENCHMARK_REPORT.md`

**3. Planning** (`docs/planning/`)
- Project status
- Implementation plans
- Roadmaps
- Example: `PROJECT_STATUS.md`

**4. Database** (`docs/database/`)
- Schema designs
- Migration plans
- Data recommendations
- Example: `DATABASE_SCHEMA_DESIGN.md`

**5. Consolidation** (`docs/consolidation/`)
- Item master consolidation docs
- Regional forecasting analysis
- Example: `FORECASTING_CONSOLIDATION_ANALYSIS.md`

**6. Archive** (`docs/archive/`)
- Old/historical documents
- Read-only (no longer updated)
- Example: `CODE_REVIEW_SUMMARY.md` (from 2025)

### When to Archive

Move documents to `docs/archive/` when:
1. They are >6 months old
2. They describe completed phases
3. They are superseded by newer docs
4. They are historical reference only

**Do NOT archive:**
- Active project plans (`PROJECT_STATUS.md`)
- Current guides (`FORECASTING_TOOL_GUIDE.md`)
- Recent reports (<3 months)

---

## Code Organization Rules

### Source Code (`src/`)

**Module structure:**
```python
# src/forecasting.py
"""
Brief description of module.

Longer description if needed.
"""
import logging

logger = logging.getLogger(__name__)

# Constants
CONSTANT_VALUE = "value"

# Functions
def function_name(param1: type, param2: type) -> return_type:
    """Brief description."""
    # Implementation
    pass

# Classes
class ClassName:
    """Brief description."""

    def __init__(self):
        """Initialize."""
        pass
```

**File naming:**
- ✅ `forecasting.py`
- ✅ `consolidation.py`
- ✅ `inventory_health.py`
- ❌ `forecast.py` (too short)
- ❌ `new_consolidation_v2.py` (use version control)

### Scripts (`scripts/`)

**Utility scripts:**
- Test scripts: `test_*.py` or `check_*.py`
- Migration scripts: `migrate_*.py`
- Admin scripts: `admin_*.py`

**Example:**
- ✅ `test_consolidation.py`
- ✅ `check_consolidation_readiness.py`
- ✅ `migrate_tsv_data.py`

### Tests (`tests/`)

**Test naming:**
- ✅ `test_forecasting.py`
- ✅ `test_ingestion.py`
- ✅ `test_uom_conversion.py`

**Test structure:**
```python
# tests/test_forecasting.py
import pytest
from src.forecasting import prepare_monthly_data

def test_prepare_monthly_data():
    """Test monthly data preparation."""
    # Test implementation
    pass
```

---

## Data File Rules

### Raw Data (`data/raw/`)

**Files:**
- SAP exports: `items.tsv`, `sales.tsv`, `supply.tsv`
- Tab-separated values (TSV) format
- Do NOT modify directly (read-only)

### SAP Query Results (`data/sap_queries/`)

**Purpose:** Temporary holding for SAP query exports

**Process:**
1. Run SQL query in SAP B1
2. Export results to clipboard
3. Paste into TSV file
4. Run validation script
5. Move to `data/raw/` if validated

**Files:**
- `query1_complete_item_analysis.tsv`
- `query2_regional_variants.tsv`
- `query3_transaction_history.tsv`

### Cache (`data/cache/`)

**Files:**
- `forecasts.parquet` - Cached forecasts
- `signatures.json` - Data signatures
- Benchmark results: `*_results.json`

**Rules:**
- Can be deleted (will regenerate)
- Do NOT commit to git (large files)
- Add to `.gitignore`

### Logs (`data/logs/`)

**Files:**
- `app.log` - Application logs
- `errors.log` - Error logs

**Rules:**
- Rotate regularly (keep last 30 days)
- Do NOT commit to git
- Add to `.gitignore`

---

## Git Rules

### .gitignore

**Must include:**
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Data (too large for git)
data/cache/
data/logs/
*.parquet
*.log

# Railway
railway_settings.json

# OS
.DS_Store
Thumbs.db
nul

# Temporary files
*.tmp
*.bak
*~
```

### Commit Messages

**Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks

**Examples:**
```
feat(consolidation): Add warehouse-aware forecasting

- Update prepare_monthly_data() to accept warehouse parameter
- Add forecast_items_by_warehouse() function
- Update purchase ordering logic for multi-warehouse items

Closes #123
```

```
docs(archive): Move old reports to archive

- Move 2025 benchmark reports to docs/archive/
- Update index with new locations
```

---

## Naming Conventions

### Files and Directories

**Python files:** `snake_case`
- ✅ `forecasting.py`
- ✅ `test_consolidation.py`
- ❌ `Forecasting.py`

**Documentation:** `UPPER_CASE_WITH_UNDERSCORES`
- ✅ `FORECASTING_TOOL_GUIDE.md`
- ✅ `REGIONAL_FORECAST_IMPACT_ANALYSIS.md`
- ❌ `forecasting-guide.md`

**Directories:** `snake_case`
- ✅ `docs/`
- ✅ `sap_queries/`
- ❌ `Docs/`
- ❌ `SAP_Queries/`

### Code

**Functions:** `snake_case`
```python
def prepare_monthly_data():
    pass
```

**Classes:** `PascalCase`
```python
class ForecastModel:
    pass
```

**Constants:** `UPPER_CASE`
```python
MAX_FORECAST_HORIZON = 12
DEFAULT_SERVICE_LEVEL = 0.95
```

**Variables:** `snake_case`
```python
item_code = "BX010155"
warehouse_data = df.copy()
```

---

## Code Quality Rules

### Documentation Strings

**All functions must have docstrings:**
```python
def function_name(param1: type, param2: type) -> return_type:
    """
    Brief description of what the function does.

    Longer description if needed. Explain the algorithm,
    edge cases, and any important details.

    Parameters:
    -----------
    param1 : type
        Description of param1
    param2 : type
        Description of param2

    Returns:
    --------
    return_type
        Description of return value

    Examples:
    ---------
    >>> function_name("input")
    "output"
    """
    pass
```

### Type Hints

**Use type hints for all function parameters:**
```python
from typing import List, Dict, Optional

def get_items(
    filepath: Path,
    filters: Optional[Dict[str, str]] = None
) -> pd.DataFrame:
    """Load items from file with optional filters."""
    pass
```

### Error Handling

**Log errors, don't just print:**
```python
import logging

logger = logging.getLogger(__name__)

def process_data(data: pd.DataFrame) -> pd.DataFrame:
    """Process data with error handling."""
    try:
        # Processing logic
        pass
    except ValueError as e:
        logger.error(f"Invalid data format: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error processing data")
        raise
```

---

## Maintenance Rules

### Weekly Tasks

1. **Clean up root directory** - Move any stray files
2. **Archive old docs** - Move documents >6 months old to archive
3. **Rotate logs** - Delete logs older than 30 days
4. **Update PROJECT_STATUS** - Mark completed tasks

### Monthly Tasks

1. **Review documentation** - Update or archive outdated docs
2. **Clean up cache** - Delete old cache files
3. **Update dependencies** - Check for security updates
4. **Archive completed work** - Move finished phase docs to archive

### On Project Milestones

1. **Create milestone report** - Add to `docs/reports/`
2. **Update PROJECT_STATUS** - Mark milestone complete
3. **Archive phase docs** - Move completed phase docs to archive
4. **Update README** - Reflect current status

---

## Violation Consequences

### First Offense
- Gentle reminder
- Link to this document

### Second Offense
- Request correction
- Explain why it matters

### Third Offense
- Fix it yourself (if you have access)
- Escalate to project lead

---

## Questions?

**If unsure where something goes:**
1. Check this document first
2. Look at existing examples
3. Ask the team
4. When in doubt: `docs/` is probably right

**Remember:** A clean project is a maintainable project. Take the extra 30 seconds to put things in the right place.

---

**Document Version:** 1.0
**Last Updated:** 2026-01-16
**Next Review:** 2026-04-16 (quarterly)
