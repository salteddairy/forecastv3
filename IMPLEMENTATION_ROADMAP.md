# Implementation Roadmap: Local App → Web Application

## Project Overview

**Current State:** Local Streamlit application with flat files (TSV, Parquet)
**Target State:** Production web application with Railway backend, PostgreSQL database, and multi-user support

**Timeline Estimate:** 3-6 months depending on team size and complexity

---

## Phase 1: Foundation (Weeks 1-4)

### Goal: Set up infrastructure and basic web application

#### Week 1: Infrastructure Setup
- [ ] **Railway Project Setup**
  - Create Railway account and project
  - Set up PostgreSQL database (Production)
  - Set up Redis for caching
  - Set up Railway Volume for file storage
  - Configure environment variables

- [ ] **Local Development Environment**
  - Set up Docker Compose for local development
  - PostgreSQL + Redis containers
  - Create `.env` file template
  - Set up virtual environment

#### Week 2: Database Schema & Migrations
- [ ] **Database Setup**
  - Run schema creation scripts (see `DATABASE_SCHEMA_DESIGN.md`)
  - Set up Alembic for migrations
  - Create initial migration
  - Test schema locally

- [ ] **Base Models**
  - Create SQLAlchemy models for core tables
  - Set up database connection management
  - Create base repository classes

#### Week 3: FastAPI Backend Skeleton
- [ ] **FastAPI Project Structure**
  ```
    forecast-webapp/
    ├── alembic/                 # Database migrations
    ├── api/
    │   ├── __init__.py
    │   ├── dependencies.py      # Dependency injection
    │   ├── routes/              # API endpoints
    │   └── middleware.py        # Auth, CORS, etc.
    ├── core/
    │   ├── config.py            # Settings
    │   ├── security.py          # Authentication
    │   └── database.py          # DB connection
    ├── models/
    │   ├── item.py
    │   ├── inventory.py
    │   ├── pricing.py
    │   ├── forecast.py
    │   └── ...
    ├── repositories/
    │   ├── base.py
    │   ├── item_repository.py
    │   └── ...
    ├── services/
    │   ├── sap_sync.py
    │   ├── forecast_service.py
    │   └── ...
    ├── tasks/                   # Background jobs
    │   ├── forecasting.py
    │   └── sync.py
    ├── tests/
    ├── scripts/                 # Utility scripts
    └── main.py                  # FastAPI app entry
  ```

- [ ] **Core API Setup**
  - FastAPI app initialization
  - CORS middleware
  - Request/response logging
  - Error handlers
  - Health check endpoint

#### Week 4: Basic Authentication
- [ ] **Authentication System**
  - JWT token-based authentication
  - User model and table
  - Login/logout endpoints
  - Password hashing (bcrypt)
  - Role-based access control (Admin, User, Read-Only)

---

## Phase 2: Data Migration & SAP Sync (Weeks 5-8)

### Goal: Migrate existing data and establish SAP B1 sync pipeline

#### Week 5: Data Migration Scripts
- [ ] **TSV to Database Migration**
  - Script to load `sales.tsv` → `sales_orders` + `sales_order_lines`
  - Script to load `supply.tsv` → `purchase_orders` + `purchase_order_lines`
  - Script to load `items.tsv` → `items` + `inventory_current`
  - Script to load cached forecasts → `forecasts` table
  - Data validation and cleanup

- [ ] **Historical Data Loading**
  - Load all historical sales orders
  - Load all historical purchase orders
  - Populate inventory transactions
  - Verify data integrity

#### Week 6: SAP B1 Integration
- [ ] **SAP B1 Service Layer Setup**
  - SAP B1 Service Layer API client
  - Authentication (OAuth2 or Basic)
  - Connection testing

- [ ] **Incremental Sync Design**
  - Delta sync logic (only changed records since last sync)
  - Sync logs table for tracking
  - Error handling and retry logic
  - Conflict resolution

#### Week 7: Sync Pipeline Implementation
- [ ] **Pull from SAP B1**
  - Items master sync
  - Sales orders sync
  - Purchase orders sync
  - Inventory levels sync
  - Pricing sync
  - Costs sync

- [ ] **Background Jobs**
  - Celery setup with Redis broker
  - Scheduled sync tasks (hourly/daily)
  - Task monitoring and alerts

#### Week 8: Sync Testing & Validation
- [ ] **Testing**
  - Full sync test
  - Incremental sync test
  - Error recovery test
  - Performance test (large datasets)

- [ ] **Monitoring**
  - Sync status dashboard
  - Error notifications (email/Slack)
  - Data quality alerts

---

## Phase 3: Core API Development (Weeks 9-12)

### Goal: Build REST API for all major features

#### Week 9: Items & Inventory APIs
- [ ] **Items Endpoints**
  ```
  GET    /api/v1/items                    # List items (paginated, filterable)
  GET    /api/v1/items/{item_code}        # Get item details
  GET    /api/v1/items/{item_code}/pricing # Get item pricing
  GET    /api/v1/items/{item_code}/costs  # Get item costs
  GET    /api/v1/items/{item_code}/margins # Get margin analysis
  ```

- [ ] **Inventory Endpoints**
  ```
  GET    /api/v1/inventory                # Current inventory (filterable)
  GET    /api/v1/inventory/{item_code}    # Item inventory by warehouse
  GET    /api/v1/inventory/transactions   # Transaction history
  GET    /api/v1/inventory/status         # On Hand, On Order, Committed
  GET    /api/v1/inventory/availability  # Available to promise
  ```

#### Week 10: Orders APIs
- [ ] **Sales Orders Endpoints**
  ```
  GET    /api/v1/sales-orders             # List orders
  GET    /api/v1/sales-orders/{order_num} # Order details
  GET    /api/v1/sales-orders/lines       # Order lines
  POST   /api/v1/sales-orders             # Create order (optional)
  ```

- [ ] **Purchase Orders Endpoints**
  ```
  GET    /api/v1/purchase-orders          # List POs
  GET    /api/v1/purchase-orders/{po_num}# PO details
  GET    /api/v1/purchase-orders/open     # Open POs (for on-order qty)
  ```

#### Week 11: Forecasting API
- [ ] **Forecast Endpoints**
  ```
  GET    /api/v1/forecasts                # List forecasts
  GET    /api/v1/forecasts/{item_code}    # Item forecast details
  POST   /api/v1/forecasts/generate       # Trigger forecast generation
  GET    /api/v1/forecasts/accuracy       # Historical accuracy
  GET    /api/v1/forecasts/snapshots      # Forecast snapshots
  ```

- [ ] **Background Forecasting**
  - Celery task for forecast generation
  - Progress tracking
  - Email/webhook notifications on completion

#### Week 12: Analytics & Reports API
- [ ] **Analytics Endpoints**
  ```
  GET    /api/v1/analytics/margins        # Margin analysis by item/category
  GET    /api/v1/analytics/sales-trends   # Sales trends
  GET    /api/v1/analytics/forecast-accuracy # Forecast accuracy trends
  GET    /api/v1/reports/shortage         # Shortage report
  GET    /api/v1/reports/stock-vs-special # TCO recommendations
  GET    /api/v1/reports/inventory-health # Dead stock, shelf life
  ```

---

## Phase 4: Frontend Development (Weeks 13-18)

### Goal: Build user interface (Choose ONE approach)

#### Option A: Enhanced Streamlit (Faster - Recommended for MVP)
**Weeks 13-16**

- [ ] **Streamlit with API Backend**
  - Keep Streamlit but connect to FastAPI backend
  - Migrate all local file I/O to API calls
  - Add authentication UI
  - Deploy to Railway/streamlit-cloud

- [ ] **New Pages**
  - Inventory Status page (On Hand, On Order, Committed)
  - Margins & Pricing dashboard
  - Forecast Accuracy tracking
  - Enhanced filtering across all pages

- [ ] **Deployment**
  - Railway app deployment
  - Domain configuration
  - SSL/HTTPS setup

**Pros:** Fastest path to production, familiar codebase
**Cons:** Limited UI customization, scaling challenges

---

#### Option B: Vue.js/React SPA (Scalable - Recommended for Long-term)
**Weeks 13-18**

- [ ] **Frontend Setup**
  - Vue 3 / React + TypeScript
  - Vite build system
  - TailwindCSS or Material-UI
  - Axios for API calls

- [ ] **Core Pages**
  - Login/authentication
  - Dashboard (overview metrics)
  - Items catalog with filtering
  - Inventory status (On Hand, On Order, Committed)
  - Margins & Pricing analysis
  - Forecasts with accuracy tracking
  - Reports (Shortage, Stock vs Special, Health)

- [ ] **Components Library**
  - Data tables with sorting/filtering (use AG Grid or TanStack Table)
  - Charts (use Chart.js, ECharts, or Plotly.js)
  - Date range pickers
  - Export functionality (Excel, PDF)

- [ ] **State Management**
  - Pinia (Vue) or Zustand (React) for global state
  - API service layer
  - Error handling
  - Loading states

- [ ] **Deployment**
  - Vercel / Netlify for frontend
  - Railway for backend API
  - CORS configuration

**Pros:** Scalable, better UX, full control
**Cons:** Longer development time

---

## Phase 5: Advanced Features (Weeks 19-24)

### Goal: Add production-ready features

#### Week 19-20: Margins & Pricing Module
- [ ] **Margin Calculations**
  - Real-time margin calculation engine
  - Margin history tracking
  - Margin category management
  - Price optimization recommendations

- [ ] **Pricing Tools**
  - Price change proposals
  - Margin impact analysis
  - Price approval workflow
  - Pricing export for SAP B1

#### Week 21-22: Advanced Forecasting
- [ ] **Enhanced Accuracy Tracking**
  - Monthly accuracy reports
  - Bias detection
  - Model performance comparison
  - Forecast vs actual charts

- [ ] **Forecast Management**
  - Manual forecast adjustments
  - Forecast approval workflow
  - Forecast versioning
  - What-if scenarios

#### Week 23: Notifications & Alerts
- [ ] **Alerting System**
  - Shortage alerts (email/dashboard)
  - Low stock warnings
  - Margin drop alerts
  - Forecast accuracy alerts

- [ ] **Notification Preferences**
  - User-specific settings
  - Alert frequency controls
  - Notification channels (email, Slack, webhook)

#### Week 24: Reports & Exports
- [ ] **Report Generation**
  - PDF report generation
  - Excel export with formatting
  - Scheduled reports (email)
  - Custom report builder

---

## Phase 6: Testing & QA (Weeks 25-26)

### Goal: Ensure production readiness

#### Week 25: Testing
- [ ] **Unit Tests**
  - API endpoint tests (Pytest)
  - Service layer tests
  - Repository tests
  - Target: 80%+ code coverage

- [ ] **Integration Tests**
  - API integration tests
  - Database integration tests
  - SAP sync integration tests
  - Background job tests

- [ ] **Load Testing**
  - API performance tests (Locust)
  - Database query optimization
  - Concurrency testing
  - Stress testing

#### Week 26: Security & Compliance
- [ ] **Security Audit**
  - SQL injection prevention
  - XSS prevention
  - CSRF protection
  - Input validation
  - Rate limiting

- [ ] **Data Privacy**
  - PII identification
  - Data encryption at rest
  - Data encryption in transit
  - Access logging

---

## Phase 7: Deployment & Go-Live (Weeks 27-28)

### Goal: Production deployment

#### Week 27: Pre-Production
- [ ] **Staging Environment**
  - Railway staging project
  - Production-like data
  - UAT with stakeholders

- [ ] **Documentation**
  - API documentation (Swagger/OpenAPI)
  - User guides
  - Admin guides
  - Troubleshooting guides

#### Week 28: Go-Live
- [ ] **Production Deployment**
  - Database backup strategy
  - Blue-green deployment
  - DNS configuration
  - SSL certificates

- [ ] **Monitoring Setup**
  - Application monitoring (Sentry, DataDog)
  - Uptime monitoring
  - Log aggregation
  - Performance dashboards

- [ ] **Support Planning**
  - Runbook creation
  - On-call rotation
  - Escalation procedures
  - User training sessions

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Database** | PostgreSQL 15+ | Relational database, JSONB support |
| **Cache** | Redis 7+ | Caching, session store, Celery broker |
| **Backend** | FastAPI 0.100+ | REST API, async support |
| **ORM** | SQLAlchemy 2.0 | Database ORM, async support |
| **Migrations** | Alembic | Database version control |
| **Task Queue** | Celery | Background jobs, scheduled tasks |
| **ML/AI** | Prophet, scikit-learn | Forecasting models |
| **Data** | Pandas, NumPy | Data processing |
| **Frontend** | Streamlit OR Vue.js/React | User interface |
| **Deployment** | Railway | Hosting platform |
| **Monitoring** | Sentry, DataDog | Error tracking, APM |
| **CI/CD** | GitHub Actions | Automated testing/deployment |

---

## Database Connection Examples

### SQLAlchemy Async Setup
```python
# core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@host/dbname"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session
```

### Repository Pattern
```python
# repositories/item_repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.item import Item

class ItemRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, skip: int = 0, limit: int = 100):
        result = await self.db.execute(
            select(Item).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def get_by_code(self, item_code: str):
        result = await self.db.execute(
            select(Item).where(Item.item_code == item_code)
        )
        return result.scalar_one_or_none()
```

---

## API Examples

### FastAPI Endpoint
```python
# api/routes/items.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from repositories.item_repository import ItemRepository

router = APIRouter(prefix="/api/v1/items", tags=["items"])

@router.get("/")
async def list_items(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    repo = ItemRepository(db)
    items = await repo.get_all(skip=skip, limit=limit)
    return {"items": items, "count": len(items)}

@router.get("/{item_code}")
async def get_item(
    item_code: str,
    db: AsyncSession = Depends(get_db)
):
    repo = ItemRepository(db)
    item = await repo.get_by_code(item_code)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

---

## Migration Strategy from Local Files

### Step 1: Export to Database
```python
# scripts/migrate_data.py
import pandas as pd
from sqlalchemy import create_engine
from models.sales_order import SalesOrder, SalesOrderLine

# Load TSV
df_sales = pd.read_csv('data/raw/sales.tsv', sep='\t')

# Write to database
engine = create_engine('postgresql://user:pass@localhost/db')
df_sales.to_sql('sales_orders_staging', engine, if_exists='replace')

# Process into normalized tables
# ... (transformation logic)
```

### Step 2: Update Forecast Module
```python
# Before: Read from Parquet
df_forecasts = pd.read_parquet('data/cache/forecasts.parquet')

# After: Read from Database
async def load_forecasts(db: AsyncSession, item_code: str):
    result = await db.execute(
        select(Forecast)
        .where(Forecast.item_code == item_code)
        .where(Forecast.status == 'Active')
        .order_by(Forecast.forecast_generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

---

## Cost Estimates (Railway)

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| PostgreSQL | Production Plan | ~$15-50/month |
| Redis | Basic | ~$5/month |
| Backend API | 512MB - 1GB | ~$5-10/month |
| Frontend (if separate) | Static | ~$0-5/month |
| Storage Volume | 1-10GB | ~$0.50-5/month |
| **Total** | | **~$25-75/month** |

*Estimates as of 2024, actual costs may vary*

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | Critical | Multiple backups, test runs, validation |
| SAP sync failures | High | Robust error handling, retry logic, alerts |
| Performance issues | Medium | Load testing, query optimization, indexing |
| Budget overrun | Medium | Phased approach, monitoring Railway costs |
| User adoption | Low | Training, documentation, gradual rollout |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| API response time | < 500ms (p95) | APM monitoring |
| Forecast generation time | < 5 min for 10K items | Celery task timing |
| Data sync latency | < 15 min | Sync logs |
| System uptime | > 99.5% | Uptime monitoring |
| User satisfaction | > 4/5 | User feedback |
| Forecast accuracy (MAPE) | < 20% | Accuracy tracking module |

---

## Next Immediate Steps

1. ✅ **Review database schema** - Get stakeholder approval
2. ✅ **Set up Railway account** - Create project and services
3. ✅ **Initialize Alembic** - Set up migrations
4. ✅ **Create base FastAPI project** - Clone starter template
5. ✅ **Plan Phase 1 sprint** - 2-week sprints with clear deliverables

---

## Questions for Stakeholders

Before starting development:

1. **User Base**: How many users? Concurrent users expected?
2. **Data Volume**: Current and projected (items, orders, forecasts)?
3. **SAP B1 Access**: Do you have Service Layer API access? SQL access?
4. **Sync Frequency**: Real-time, hourly, daily?
5. **Compliance**: Any specific requirements (SOC2, HIPAA, etc.)?
6. **Budget**: Monthly budget for hosting?
7. **Timeline**: Hard deadline or flexible?
8. **Frontend Preference**: Streamlit (faster) vs Vue/React (scalable)?
9. **Authentication**: SSO, LDAP, or simple JWT?
10. **Deployment**: Self-managed or managed service (Railway)?

---

## Recommended Quick Start (MVP in 8 weeks)

If you want the fastest path to production:

1. **Week 1-2**: Railway setup + Database schema
2. **Week 3-4**: Data migration + SAP sync (basic)
3. **Week 5-6**: Core APIs (items, inventory, forecasts)
4. **Week 7-8**: Streamlit UI with API backend + Deploy

This gets you a production web app with:
- ✅ Database-backed data
- ✅ Multi-user access
- ✅ Inventory status (On Hand, On Order, Committed)
- ✅ Margins & Pricing visibility
- ✅ 12-month forecasts
- ✅ Accuracy tracking

Enhanced features (Vue.js SPA, advanced reporting) can follow later.
