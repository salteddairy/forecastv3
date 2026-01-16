# Web Application Migration Guide
## SAP B1 Inventory & Forecast Analyzer

**Version:** 1.0
**Date:** 2026-01-12
**Status:** Planning Guide (Not Yet Implemented)

---

## Executive Summary

This document outlines best practices for migrating the Streamlit-based forecasting application to a production web application while keeping costs low and maintaining code quality.

**Current State:**
- Streamlit desktop/server app
- Local file-based data processing
- Single-user focus
- TSV file inputs from SAP B1

**Target State:**
- Multi-user web application
- Cloud-hosted with auto-scaling
- Database-backed data storage
- Real-time SAP B1 integration
- Authentication and permissions

---

## Architecture Options

### Option 1: Streamlit Cloud (Easiest, Low Cost) ⭐ Recommended

**Pros:**
- Zero code changes required
- Free tier available (up to 1GB RAM)
- Deploy from GitHub in minutes
- Automatic SSL/HTTPS
- Built-in authentication

**Cons:**
- Limited to Streamlit ecosystem
- Resource constraints on free tier
- Less customization control

**Cost:** Free - $39/month (Professional)

**Migration Effort:** 1-2 hours

---

### Option 2: FastAPI + React (Best Performance, Medium Cost)

**Pros:**
- Modern REST API architecture
- Full frontend customization
- Better performance for large datasets
- Separation of concerns
- Easy to scale API independently

**Cons:**
- Significant rewrite required
- Frontend/backend development
- More infrastructure to manage

**Cost:** $20-100/month (depends on hosting)

**Migration Effort:** 2-4 weeks

---

### Option 3: Django + Vue.js (Enterprise-Ready, Higher Cost)

**Pros:**
- Full-featured framework
- Built-in admin panel
- ORM for database management
- Authentication/permissions built-in
- Large ecosystem

**Cons:**
- Overkill for this application
- Steeper learning curve
- Heavier resource usage

**Cost:** $40-200/month

**Migration Effort:** 4-6 weeks

---

## Recommended Stack: Option 1 (Streamlit Cloud)

Given the current codebase and requirement for low cost, **Option 1 is strongly recommended**.

### Architecture

```
┌─────────────────────────────────────────┐
│         Streamlit Cloud App             │
│  (Your existing app.py with minor      │
│   modifications for multi-user)        │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│      Cloud Storage (S3/GCS)             │
│  - Persistent cache storage             │
│  - User uploads                         │
│  - Configuration files                  │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   Database (Optional - PostgreSQL)      │
│  - User preferences                     │
│  - Audit logs                           │
│  - Historical forecast results          │
└─────────────────────────────────────────┘
```

---

## Deployment Strategies

### Strategy 1: Streamlit Cloud (Recommended)

**Steps:**
1. Push code to GitHub repository
2. Create account at [share.streamlit.io](https://share.streamlit.io)
3. Connect GitHub repository
4. Configure app settings
5. Deploy!

**Configuration Files:**

**`requirements.txt`**
```txt
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
prophet>=1.1.4
statsmodels>=0.14.0
plotly>=5.18.0
openpyxl>=3.1.0
pyarrow>=14.0.0
```

**`.streamlit/config.toml`**
```toml
[theme]
primaryColor = "#7792EB"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[client]
showErrorDetails = false
maxUploadSize = 200

[logger]
level = "info"
```

**Cost Breakdown:**
- Free tier: $0/month (limited to community support)
- Professional: $39/month (priority support, faster performance)
- Enterprise: Custom pricing

---

### Strategy 2: FastAPI + Docker

**Architecture:**

```
Frontend (React/Next.js)  →  FastAPI Backend  →  PostgreSQL DB
                                      ↓
                              Forecasting Engine
                              (Your existing Python code)
```

**File Structure:**
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── api/
│   │   ├── forecasts.py     # Forecast endpoints
│   │   ├── inventory.py     # Inventory endpoints
│   │   └── warehouse.py     # Warehouse endpoints
│   ├── models/              # Pydantic models
│   ├── core/                # Your existing src/ code
│   └── database.py          # Database connection
├── Dockerfile
├── requirements.txt
└── docker-compose.yml

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── api/
├── package.json
└── Dockerfile
```

**Hosting Options:**

| Platform | Cost | Pros | Cons |
|----------|------|------|------|
| **Render** | Free - $97/mo | Easy setup, auto-deploys | Cold starts on free tier |
| **Railway** | $5-50/mo | Great DX, built-in DB | Newer platform |
| **Fly.io** | $0-50/mo | Edge deployment, cheap | More complex setup |
| **DigitalOcean** | $12-160/mo | Reliable, full control | Manual scaling |
| **AWS (ECS)** | $20-200/mo | Enterprise features | Expensive, complex |

---

## Best Practices

### 1. State Management

**Current (Streamlit):**
```python
# Everything runs top-to-bottom on each interaction
if 'data' not in st.session_state:
    st.session_state.data = load_data()
```

**Web App (React + FastAPI):**
```python
# FastAPI: /api/forecasts endpoint
@router.get("/forecasts/{item_code}")
async def get_forecast(item_code: str):
    return forecast_service.get(item_code)

# React: Fetch and cache
const { data } = useSWR(`/api/forecasts/${itemCode}`, fetcher)
```

### 2. Data Caching

**Streamlit:**
```python
@st.cache_resource
def load_data():
    return expensive_operation()
```

**FastAPI:**
```python
from functools import lru_cache
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@router.get("/forecasts/{item_code}")
@cache(expire=3600)  # 1 hour
async def get_forecast(item_code: str):
    return expensive_operation()
```

### 3. File Uploads

**Streamlit:**
```python
uploaded_file = st.file_uploader("Upload TSV")
if uploaded_file:
    df = pd.read_csv(uploaded_file, sep='\t')
```

**FastAPI:**
```python
@router.post("/upload")
async def upload_file(file: UploadFile):
    # Save to S3/GCS
    # Process asynchronously
    # Return job ID
    pass
```

### 4. Background Jobs

**For long-running forecasts:**

**Streamlit:** Not supported (blocks UI)

**FastAPI:**
```python
from fastapi import BackgroundTasks

@router.post("/forecast/generate")
async def generate_forecast(
    items: List[str],
    background_tasks: BackgroundTasks
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_forecast_job, job_id, items)
    return {"job_id": job_id}

# Check status
@router.get("/forecast/status/{job_id}")
async def get_status(job_id: str):
    return job_status.get(job_id, {"status": "pending"})
```

---

## Security Considerations

### Authentication

**Streamlit Cloud:**
```python
import streamlit as st

# Simple email/password
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(
    credentials,
    'config.yaml',
    'cookie_name',
    'key_name'
)

name, authentication_status, username = authenticator.login()

if authentication_status:
    authenticator.logout('Logout', 'main')
    # Show app
```

**FastAPI:**
```python
from fastapi.security import HTTPBearer
from jose import jwt

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    user = jwt.decode(token, SECRET_KEY)
    return user

@router.get("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    return user
```

### Data Encryption

**At Rest:**
- Use database encryption (PostgreSQL transparent encryption)
- Encrypt S3 buckets
- Use secrets manager for API keys

**In Transit:**
- HTTPS/TLS 1.3 (automatic on Streamlit Cloud, configure on custom hosting)
- API tokens in headers

### Input Validation

**Pydantic models:**
```python
from pydantic import BaseModel, validator

class ForecastRequest(BaseModel):
    item_code: str
    horizon_months: int = Field(ge=1, le=12)

    @validator('item_code')
    def validate_item_code(cls, v):
        if not re.match(r'^[A-Z0-9-]+$', v):
            raise ValueError('Invalid item code')
        return v
```

---

## Cost Optimization

### 1. Use Free Tiers First

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| Streamlit Cloud | Yes | $39/mo |
| Render (Free) | 750 hours/mo | $7/mo |
| Railway | $5 free credit | $5-20/mo |
| Supabase (Postgres) | 500MB | $25/mo |
| Redis Cloud | 30MB | $7/mo |

### 2. Optimize Compute

**Current Bottleneck:** Forecasting 3,700 items takes ~2 minutes

**Optimization Strategies:**
- **Cache results:** 5-second load vs 2-minute compute
- **Lazy loading:** Only forecast viewed items
- **Batch processing:** Queue overnight jobs
- **Incremental updates:** Only re-forecast changed items

**Expected Cost Impact:**
- Without optimization: Need 4 CPU, 16GB RAM = $160/mo
- With caching: 1 CPU, 2GB RAM = $20/mo

### 3. Storage Optimization

- Use Parquet instead of CSV (10x smaller)
- Compress old forecasts
- Purge cache after 30 days
- Use lifecycle policies for S3

---

## Database Schema (If Using DB)

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    role VARCHAR(50) DEFAULT 'user'
);

-- Warehouses
CREATE TABLE warehouses (
    location_code VARCHAR(10) PRIMARY KEY,
    total_skids INTEGER NOT NULL,
    used_skids INTEGER DEFAULT 0,
    skid_length_cm FLOAT,
    skid_width_cm FLOAT,
    max_height_cm FLOAT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Forecasts (cache)
CREATE TABLE forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_code VARCHAR(50) NOT NULL,
    winning_model VARCHAR(50),
    forecast_month_1 FLOAT,
    forecast_month_2 FLOAT,
    forecast_month_3 FLOAT,
    forecast_month_4 FLOAT,
    forecast_month_5 FLOAT,
    forecast_month_6 FLOAT,
    forecast_horizon INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(item_code, created_at)
);

-- Forecast Jobs (async processing)
CREATE TABLE forecast_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) DEFAULT 'pending',
    item_codes TEXT[], -- Array of item codes
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_forecasts_item ON forecasts(item_code);
CREATE INDEX idx_forecasts_created ON forecasts(created_at DESC);
CREATE INDEX idx_jobs_status ON forecast_jobs(status);
```

---

## Migration Steps

### Phase 1: Streamlit Cloud Deployment (1-2 days)

1. **Prepare Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-org/forecast-app.git
   git push -u origin main
   ```

2. **Create `.streamlit/config.toml`**

3. **Add Requirements**
   - Create `requirements.txt`
   - Pin versions

4. **Deploy to Streamlit Cloud**
   - Sign up at share.streamlit.io
   - "New app" → Connect GitHub
   - Select repository and `app.py`
   - Deploy!

5. **Test**
   - Upload sample data
   - Verify forecasts work
   - Check caching

### Phase 2: Multi-User Support (3-5 days)

1. **Add Authentication**
   - Streamlit authentication
   - User-specific data directories

2. **Database Integration**
   - Add PostgreSQL (Supabase free tier)
   - Migrate warehouse configs to DB
   - Store user preferences

3. **File Storage**
   - Move from local to S3/GCS
   - Handle multi-user uploads

### Phase 3: Advanced Features (1-2 weeks)

1. **Async Job Processing**
   - Celery + Redis
   - Job queue for forecasts
   - Email notifications

2. **API Endpoints**
   - FastAPI wrapper
   - RESTful API for forecasts
   - Mobile app support

---

## Monitoring & Observability

### Streamlit Cloud

Built-in metrics:
- CPU usage
- Memory usage
- Response times
- Error logs

### Custom Monitoring

```python
import sentry_sdk

sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1
)
```

### Logging

```python
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Structured logging
logger.info(
    "forecast_generated",
    extra={
        "item_code": "ITEM001",
        "model": "arima",
        "duration_ms": 1234,
        "timestamp": datetime.now().isoformat()
    }
)
```

---

## Backup & Disaster Recovery

### Data Backup Strategy

1. **Database Backups**
   - Daily automated backups
   - Point-in-time recovery
   - Cross-region replication

2. **File Backups**
   - S3 versioning enabled
   - Lifecycle policies to Glacier
   - Weekly exports to on-prem

3. **Configuration Backups**
   - Git repository for code
   - Environment variables in secrets manager
   - Document manual configurations

---

## Performance Checklist

Before going live:

- [ ] All endpoints return within 5 seconds (or use async)
- [ ] Caching implemented for expensive operations
- [ ] Database queries optimized (use EXPLAIN ANALYZE)
- [ ] Images/static files served via CDN
- [ ] Gzip compression enabled
- [ ] Connection pooling configured
- [ ] Background jobs for long-running tasks
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] SQL injection protection (parameterized queries)
- [ ] XSS protection (input sanitization)

---

## Compliance Considerations

If handling sensitive SAP B1 data:

1. **Data Residency** - Know where data is stored
2. **Access Logs** - Audit trail for all data access
3. **Retention Policy** - When to purge old data
4. **GDPR/CCPA** - Right to deletion, data export
5. **SOC 2** - If required for customers

---

## Summary & Recommendation

### Quick Win: Streamlit Cloud (This Week)

**Cost:** $0-39/month
**Effort:** 4-8 hours
**Best For:** Internal use, small team, quick deployment

**Action Items:**
1. Push to GitHub
2. Deploy to Streamlit Cloud
3. Add basic authentication
4. Configure cloud storage for uploads

### Long Term: FastAPI + React (Next Quarter)

**Cost:** $50-150/month
**Effort:** 4-6 weeks
**Best For:** External customers, custom UI, mobile apps

**Action Items:**
1. Create API roadmap
2. Design database schema
3. Build REST API endpoints
4. Develop React frontend
5. Deploy to production

---

## Resources

**Streamlit Cloud:**
- https://streamlit.io/cloud
- https://docs.streamlit.io/streamlit-cloud

**FastAPI:**
- https://fastapi.tiangolo.com
- https://www.youtube.com/watch?v=7J2lVClu2LE (Tutorial)

**Deployment Platforms:**
- Render: https://render.com
- Railway: https://railway.app
- Fly.io: https://fly.io

**Databases:**
- Supabase: https://supabase.com (PostgreSQL)
- Neon: https://neon.tech (Serverless Postgres)

**Monitoring:**
- Sentry: https://sentry.io
- Datadog: https://www.datadoghq.com

---

**Next Steps:**

1. ✅ Review this guide with stakeholders
2. ⏳ Decide on migration path (Streamlit Cloud vs. Full Rewrite)
3. ⏳ Create migration timeline
4. �irschinal budget approval
5. ⏳ Begin implementation

---

**Questions?** Contact the development team or create an issue in the repository.
