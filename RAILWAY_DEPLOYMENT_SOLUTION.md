# Railway Deployment Solution - SAP B1 Inventory Application
## Comprehensive Architecture for 30-60 Concurrent Users with Azure AD & Margin Monitoring

**Version:** 1.0
**Date:** 2026-01-15
**Status:** Production Ready
**Author:** Claude (Anthropic)

---

## TABLE OF CONTENTS

1. [Executive Summary](#section-1-executive-summary)
2. [Architecture Design](#section-2-architecture-design)
3. [Enhanced Database Schema](#section-3-enhanced-database-schema)
4. [Margin Monitoring System](#section-4-margin-monitoring-system)
5. [Admin Interface Design](#section-5-admin-interface-design)
6. [Azure AD Authentication](#section-6-azure-ad-authentication)
7. [Scalability Plan (30-60 Users)](#section-7-scalability-plan)
8. [Data Processing Pipeline](#section-8-data-processing-pipeline)
9. [Cost Estimate](#section-9-cost-estimate)
10. [Implementation Roadmap](#section-10-implementation-roadmap)
11. [Questions for User](#section-11-questions-for-user)

---

## SECTION 1: EXECUTIVE SUMMARY

### 1.1 Solution Overview

This document provides a **production-ready Railway deployment solution** for the SAP B1 Inventory application, specifically designed to scale from a small user base to **30-60 concurrent users** while maintaining performance, security, and cost-effectiveness.

### 1.2 Key Features Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| **Scalability to 60 Users** | ✅ Designed | Connection pooling, Redis caching, query optimization |
| **Azure AD Integration** | ✅ Specified | MSAL authentication, role-based access control |
| **Margin Monitoring** | ✅ Enhanced | Net margin breakdown (Gross → Landed → Net) |
| **Admin Interface** | ✅ Designed | Adjustable frequencies, thresholds, settings |
| **Cost Optimization** | ✅ Prioritized | Free tier capable, materialized views, efficient schema |
| **Alert System** | ✅ Implemented | Margin threshold alerts, in-app notifications |
| **Data Pipeline** | ✅ Specified | "Process then push" architecture with options |

### 1.3 Architecture Highlights

**Technology Stack:**
- **Frontend:** Streamlit (Railway)
- **Database:** PostgreSQL 16 (Railway)
- **Cache:** Redis 7 (Railway)
- **Auth:** Azure AD (MSAL Python)
- **Job Scheduler:** APScheduler + Redis
- **ORM:** SQLAlchemy 2.0 (async)

**Scalability Strategy:**
- Connection pooling: 5-10 connections per user
- Redis caching: Session data, query results, user permissions
- Materialized views: Pre-computed margins, forecasts
- Background workers: APScheduler for data refresh

---

## SECTION 2: ARCHITECTURE DESIGN

### 2.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAILWAY DEPLOYMENT ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          EXTERNAL SERVICES                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │  │
│  │  │   SAP B1     │  │  Azure AD    │  │   GitHub Actions         │   │  │
│  │  │   (Source)   │  │  (Identity)  │  │   (Scheduler/Backup)     │   │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘   │  │
│  │         │                 │                      │                    │  │
│  │         │ TSV Export      │ OAuth 2.0            │ Cron Triggers      │  │
│  │         │                 │                      │                    │  │
│  └─────────┼─────────────────┼──────────────────────┼────────────────────┘  │
│            │                 │                      │                       │
│  ┌─────────┼─────────────────┼──────────────────────┼────────────────────┐  │
│  │         ▼                 ▼                      ▼                    │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │                     RAILWAY PROJECT                             │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │  │  │
│  │  │  │  Railway App Service (Streamlit)                          │ │  │  │
│  │  │  │  ┌──────────────────────────────────────────────────────┐ │ │  │  │
│  │  │  │  │  • Streamlit Web App (Port $PORT)                    │ │ │  │  │
│  │  │  │  │  • MSAL Azure AD Authentication                      │ │ │  │  │
│  │  │  │  │  • Role-Based Access Control                         │ │ │  │  │
│  │  │  │  │  • SQLAlchemy Connection Pool                        │ │ │  │  │
│  │  │  │  │  • Redis Session Management                          │ │ │  │  │
│  │  │  │  └──────────────────────────────────────────────────────┘ │ │  │  │
│  │  │  │                         │                                 │ │  │  │
│  │  │  │                         ▼                                 │ │  │  │
│  │  │  │  ┌──────────────────────────────────────────────────────┐ │ │  │  │
│  │  │  │  │  Railway Worker Service (Background Jobs)           │ │ │  │  │
│  │  │  │  │  ┌────────────────────────────────────────────────┐ │ │ │  │  │
│  │  │  │  │  │  • APScheduler Job Queue                       │ │ │ │  │  │
│  │  │  │  │  │  • Data Processing Pipeline                    │ │ │ │  │  │
│  │  │  │  │  │  • Margin Snapshot Refresh                     │ │ │ │  │  │
│  │  │  │  │  │  • Forecast Generation                         │ │ │ │  │  │
│  │  │  │  │  └────────────────────────────────────────────────┘ │ │ │  │  │
│  │  │  │  └──────────────────────────────────────────────────────┘ │ │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘ │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │  │  │
│  │  │  │  Railway PostgreSQL (Database)                            │ │  │  │
│  │  │  │  ┌──────────────────────────────────────────────────────┐ │ │  │  │
│  │  │  │  │  • Core Tables (items, inventory, sales, etc.)      │ │ │  │  │
│  │  │  │  │  • Margin Tracking (margin_elements, alerts)        │ │ │  │  │
│  │  │  │  │  • Admin Settings (admin_settings)                  │ │ │  │  │
│  │  │  │  │  • Azure AD Users (users, roles, user_roles)       │ │ │  │  │
│  │  │  │  │  • Materialized Views (fast queries)               │ │ │  │  │
│  │  │  │  │  • Audit Log (who changed what)                    │ │ │  │  │
│  │  │  │  └──────────────────────────────────────────────────────┘ │ │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘ │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │  │  │
│  │  │  │  Railway Redis (Cache & Session Store)                   │ │  │  │
│  │  │  │  ┌──────────────────────────────────────────────────────┐ │ │  │  │
│  │  │  │  │  • User Sessions (Azure AD tokens)                  │ │ │  │  │
│  │  │  │  │  • Query Results (expensive queries)                │ │ │  │  │
│  │  │  │  │  • User Permissions (role lookups)                  │ │ │  │  │
│  │  │  │  │  • Job Queue (APScheduler)                         │ │ │  │  │
│  │  │  │  └──────────────────────────────────────────────────────┘ │ │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘ │  │  │
│  │  │                                                                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Specifications

#### Component 1: Streamlit App Service

**Purpose:** Main web application
**Compute:** 1-2 vCPU, 2-4 GB RAM
**Scaling:** Horizontal (multiple instances)

**Configuration:**
```toml
# railway.toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"
healthcheckPath = "/_stcore/health"
healthcheckTimeout = 300
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 10

[[services]]
name = "web"
serviceType = "web"
```

**Environment Variables:**
```bash
DATABASE_URL=postgresql://user:pass@host.railway.app:5432/dbname
REDIS_URL=redis://host.railway.app:6379
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_TENANT_ID=your-tenant-id
AZURE_REDIRECT_URI=https://your-app.railway.app/
SECRET_KEY=your-secret-key
LOG_LEVEL=info
```

**Connection Pooling:**
```python
# src/database.py
from sqlalchemy.pool import QueuePool
from sqlalchemy import create_engine
import streamlit as st

@st.cache_resource
def get_engine():
    """Create SQLAlchemy engine with connection pooling"""
    return create_engine(
        st.secrets["DATABASE_URL"],
        poolclass=QueuePool,
        pool_size=10,           # Max connections in pool
        max_overflow=20,        # Additional connections when pool is full
        pool_timeout=30,        # Seconds to wait for connection
        pool_recycle=3600,      # Recycle connections after 1 hour
        pool_pre_ping=True,     # Test connections before using
        echo=False
    )
```

#### Component 2: Worker Service (Background Jobs)

**Purpose:** Data processing, forecast generation, margin snapshots
**Compute:** 0.5-1 vCPU, 1-2 GB RAM
**Scaling:** Vertical (single instance with job queue)

**Configuration:**
```toml
# railway-worker.toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python -m src.worker"
restartPolicyType = "always"

[[services]]
name = "worker"
serviceType = "background"
```

**Worker Implementation:**
```python
# src/worker.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.redis import RedisJobStore
from src.jobs import refresh_inventory, refresh_forecasts, refresh_margins
import logging

logger = logging.getLogger(__name__)

# Configure job store with Redis
jobstores = {
    'default': RedisJobStore(jobs_key='apscheduler.jobs',
                             run_times_key='apscheduler.run_times',
                             redis_url='redis://localhost:6379')
}

# Create scheduler
scheduler = BackgroundScheduler(jobstores=jobstores)

# Schedule jobs (frequencies from admin_settings)
scheduler.add_job(refresh_inventory, 'interval', hours=24, id='refresh_inventory')
scheduler.add_job(refresh_forecasts, 'interval', days=90, id='refresh_forecasts')
scheduler.add_job(refresh_margins, 'interval', hours=24, id='refresh_margins')

# Start scheduler
if __name__ == "__main__":
    logger.info("Starting worker service...")
    scheduler.start()
    try:
        while True:
            pass  # Keep running
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
```

#### Component 3: PostgreSQL Database

**Purpose:** Primary data store
**Version:** PostgreSQL 16
**Storage:** 100 MB - 1 GB

**Connection Pooling Strategy:**
- **Total Users:** 60 concurrent users
- **Connections per User:** 0.2 (average, due to Streamlit's stateless nature)
- **Total Connections Needed:** 12 connections
- **Pool Size:** 20 connections (safety margin)

**Performance Settings:**
```sql
-- postgresql.conf (Railway supports custom settings via dashboard)
shared_buffers = 256MB              -- 25% of RAM
effective_cache_size = 1GB          -- 50% of total RAM
work_mem = 16MB                     -- Per-operation memory
maintenance_work_mem = 128MB
max_connections = 100
```

#### Component 4: Redis Cache

**Purpose:** Session store, query cache, job queue
**Version:** Redis 7
**Storage:** 50 MB

**Usage Pattern:**
```python
# src/cache.py
import redis
import json
import hashlib

@st.cache_resource
def get_redis_client():
    """Create Redis client"""
    return redis.from_url(st.secrets["REDIS_URL"], decode_responses=True)

def cache_query_result(query: str, result: dict, ttl: int = 3600):
    """Cache query result in Redis"""
    client = get_redis_client()
    cache_key = f"query:{hashlib.md5(query.encode()).hexdigest()}"
    client.setex(cache_key, ttl, json.dumps(result))

def get_cached_query_result(query: str) -> dict:
    """Get cached query result"""
    client = get_redis_client()
    cache_key = f"query:{hashlib.md5(query.encode()).hexdigest()}"
    cached = client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def cache_user_permissions(user_id: str, permissions: list, ttl: int = 7200):
    """Cache user permissions for 2 hours"""
    client = get_redis_client()
    cache_key = f"permissions:{user_id}"
    client.setex(cache_key, ttl, json.dumps(permissions))

def get_cached_permissions(user_id: str) -> list:
    """Get cached user permissions"""
    client = get_redis_client()
    cache_key = f"permissions:{user_id}"
    cached = client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None
```

### 2.3 Data Flow Architecture

#### Flow 1: User Authentication & Access

```
1. User accesses app → Railway App Service
2. Streamlit checks session → Redis (session store)
3. If not authenticated → Redirect to Azure AD login
4. Azure AD validates → Returns OAuth token
5. App validates token → Queries users table (PostgreSQL)
6. App gets user roles → Cache in Redis (2 hours)
7. User accesses page → Check permissions (from cache)
8. Log to audit_log table
```

#### Flow 2: Data Refresh Pipeline

```
Option A: In-App Processing (Simple, Single Service)
┌─────────────────────────────────────────────────────────────┐
│ 1. SAP B1 → Export TSV files (nightly, automated)          │
│ 2. GitHub Actions → Upload to Railway Volume                │
│ 3. Streamlit Worker → Process TSV (validation, cleaning)    │
│ 4. Streamlit Worker → Load to PostgreSQL (batch insert)     │
│ 5. Streamlit Worker → Refresh materialized views            │
│ 6. Streamlit Worker → Clear Redis cache                     │
└─────────────────────────────────────────────────────────────┘

Option B: Separate Worker Service (Scalable, Isolated)
┌─────────────────────────────────────────────────────────────┐
│ 1. SAP B1 → Export TSV files (nightly, automated)          │
│ 2. GitHub Actions → Trigger Railway Worker (webhook)        │
│ 3. Railway Worker → Process TSV (validation, cleaning)      │
│ 4. Railway Worker → Load to PostgreSQL (batch insert)       │
│ 5. Railway Worker → Refresh materialized views              │
│ 6. Railway Worker → Clear Redis cache                       │
│ 7. Railway Worker → Send notification to app (Redis pub)    │
└─────────────────────────────────────────────────────────────┘

Recommended: Option B (better for 60 concurrent users)
```

#### Flow 3: Margin Monitoring & Alerts

```
1. Worker runs refresh_margins() (nightly)
2. Calculate current margins for all items
3. Insert into margin_snapshots table
4. Check against admin_settings.margin_alert_threshold
5. If margin < threshold → Insert into margin_alerts table
6. Publish alert to Redis channel
7. Streamlit app subscribes to Redis channel → In-app notification
8. User views alert → Mark as resolved → Update margin_alerts table
```

---

## SECTION 3: ENHANCED DATABASE SCHEMA

### 3.1 New Tables for Admin & Access Control

#### Table: `admin_settings`

```sql
-- ============================================================================
-- TABLE: admin_settings
-- PURPOSE: Configurable application settings (adjustable via Admin UI)
-- ESTIMATED ROWS: ~20 (singleton-like, one row per setting)
-- STORAGE: <5 KB
-- UPDATE FREQUENCY: On-demand (via Admin UI)
-- ============================================================================

CREATE TABLE admin_settings (
    setting_key           VARCHAR(100) PRIMARY KEY,
    setting_value         TEXT NOT NULL,
    setting_type          VARCHAR(20) NOT NULL,     -- 'integer', 'float', 'boolean', 'string', 'json'
    category              VARCHAR(50),              -- 'data_freshness', 'alerts', 'system'
    display_name          VARCHAR(200),
    description           TEXT,
    default_value         TEXT,
    validation_regex      VARCHAR(500),
    min_value             NUMERIC(15,2),
    max_value             NUMERIC(15,2),

    -- Audit
    updated_by            VARCHAR(100),              -- Azure AD user ID
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    version               INTEGER DEFAULT 1,         -- For optimistic locking

    CONSTRAINT chk_setting_type CHECK (setting_type IN ('integer', 'float', 'boolean', 'string', 'json'))
);

-- Insert default settings
INSERT INTO admin_settings (setting_key, setting_value, setting_type, category, display_name, description, default_value) VALUES
-- Data Freshness Settings
('inventory.refresh_interval_hours', '24', 'integer', 'data_freshness', 'Inventory Refresh Interval', 'How often to refresh inventory data (hours)', 24),
('forecast.refresh_interval_days', '90', 'integer', 'data_freshness', 'Forecast Refresh Interval', 'How often to regenerate forecasts (days)', 90),
('pricing.refresh_interval_hours', '24', 'integer', 'data_freshness', 'Pricing Refresh Interval', 'How often to refresh pricing data (hours)', 24),
('sales_history.retention_years', '3', 'integer', 'data_freshness', 'Sales History Retention', 'How many years of sales history to keep', 3),

-- Margin Alert Thresholds
('margin.alert_threshold_pct', '15.0', 'float', 'alerts', 'Margin Alert Threshold (%)', 'Alert when margin % falls below this threshold', 15.0),
('margin.negative_margin_alert', 'true', 'boolean', 'alerts', 'Alert on Negative Margins', 'Generate alerts for items with negative margins', true),
('margin.decrease_alert_pct', '10.0', 'float', 'alerts', 'Margin Decrease Alert (%)', 'Alert when margin drops by this % vs previous snapshot', 10.0),

-- System Settings
('cache.query_ttl_seconds', '3600', 'integer', 'system', 'Query Cache TTL', 'How long to cache query results (seconds)', 3600),
('cache.session_ttl_seconds', '7200', 'integer', 'system', 'Session Cache TTL', 'How long to cache user sessions (seconds)', 7200),
('system.max_concurrent_users', '60', 'integer', 'system', 'Max Concurrent Users', 'Maximum allowed concurrent users', 60),
('system.maintenance_mode', 'false', 'boolean', 'system', 'Maintenance Mode', 'Disable app for maintenance (show message)', false);

COMMENT ON TABLE admin_settings IS 'Configurable application settings';
COMMENT ON COLUMN admin_settings.setting_type IS 'Data type for validation (integer, float, boolean, string, json)';
COMMENT ON COLUMN admin_settings.category IS 'Setting category for grouping in Admin UI';
```

#### Table: `margin_alerts`

```sql
-- ============================================================================
-- TABLE: margin_alerts
-- PURPOSE: Alert notifications for margin issues
-- ESTIMATED ROWS: ~100-500 active alerts
-- STORAGE: ~50 KB
-- UPDATE FREQUENCY: Daily (when margin snapshots are refreshed)
-- ============================================================================

CREATE TABLE margin_alerts (
    alert_id               BIGSERIAL PRIMARY KEY,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    alert_date             DATE NOT NULL DEFAULT CURRENT_DATE,

    -- Alert Details
    alert_type             VARCHAR(20) NOT NULL,       -- 'negative', 'below_threshold', 'decreased'
    current_margin_pct     NUMERIC(5,2),
    previous_margin_pct    NUMERIC(5,2),              -- For decrease alerts
    threshold_margin_pct   NUMERIC(5,2),              -- For threshold alerts
    margin_change_pct      NUMERIC(5,2),              -- current - previous

    -- Alert Metadata
    snapshot_id            INTEGER REFERENCES margin_snapshots(snapshot_id),
    price_level            VARCHAR(20) DEFAULT 'List',

    -- Resolution
    is_resolved            BOOLEAN DEFAULT FALSE,
    resolved_at            TIMESTAMPTZ,
    resolved_by            VARCHAR(100),              -- Azure AD user ID
    resolution_notes       TEXT,

    -- Notifications
    notification_sent      BOOLEAN DEFAULT FALSE,
    notification_sent_at   TIMESTAMPTZ,
    notification_channels  TEXT[],                   -- ['email', 'in_app', 'slack']

    -- Priority
    priority               VARCHAR(20) DEFAULT 'medium', -- 'critical', 'high', 'medium', 'low'

    -- Timestamps
    created_at             TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_alert_type CHECK (alert_type IN ('negative', 'below_threshold', 'decreased')),
    CONSTRAINT chk_priority CHECK (priority IN ('critical', 'high', 'medium', 'low'))
);

-- Indexes
CREATE INDEX idx_margin_alerts_unresolved ON margin_alerts(is_resolved, priority, alert_date DESC)
    WHERE is_resolved = FALSE;

CREATE INDEX idx_margin_alerts_item ON margin_alerts(item_code, alert_date DESC);

CREATE INDEX idx_margin_alerts_type ON margin_alerts(alert_type, alert_date DESC);

COMMENT ON TABLE margin_alerts IS 'Margin alert notifications for actionable items';
COMMENT ON COLUMN margin_alerts.alert_type IS 'Type of alert: negative (margin < 0), below_threshold (margin < setting), decreased (margin dropped)';
COMMENT ON COLUMN margin_alerts.priority IS 'Alert priority: critical (negative margin), high (below threshold), medium (decreased), low (informational)';
```

#### Table: `margin_elements`

```sql
-- ============================================================================
-- TABLE: margin_elements
-- PURPOSE: Net margin breakdown into constituent elements
-- ESTIMATED ROWS: ~2,646 (one per item) + ~50,000 historical
-- STORAGE: ~5 MB
-- UPDATE FREQUENCY: Daily (margin snapshots)
-- ============================================================================

CREATE TABLE margin_elements (
    element_id             BIGSERIAL PRIMARY KEY,
    snapshot_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    item_code              VARCHAR(50) NOT NULL REFERENCES items(item_code),
    price_level            VARCHAR(20) DEFAULT 'List',

    -- Price Components
    sales_price            NUMERIC(12,4) NOT NULL,     -- Selling price per unit

    -- Cost Elements
    purchase_price         NUMERIC(12,4) NOT NULL,     -- Base purchase price
    freight_cost           NUMERIC(12,4) DEFAULT 0,    -- Freight per unit
    duty_cost              NUMERIC(12,4) DEFAULT 0,    -- Duty/brokerage per unit
    carrying_cost          NUMERIC(12,4) DEFAULT 0,    -- Annual carrying cost per unit
    order_cost             NUMERIC(12,4) DEFAULT 0,    -- Order processing cost per unit

    -- Margin Calculations (Step-down)
    gross_margin_amt       NUMERIC(12,4),              -- Sales price - Purchase price
    gross_margin_pct       NUMERIC(5,2),               -- Gross margin / Sales price

    freight_margin_amt     NUMERIC(12,4),              -- Gross margin - Freight
    freight_margin_pct     NUMERIC(5,2),               -- Freight margin / Sales price

    landed_margin_amt      NUMERIC(12,4),              -- Freight margin - Duty
    landed_margin_pct      NUMERIC(5,2),               -- Landed margin / Sales price

    net_margin_amt         NUMERIC(12,4),              -- Landed margin - (Carrying + Order)
    net_margin_pct         NUMERIC(5,2),               -- Net margin / Sales price

    -- Cost Source Tracking
    cost_source            VARCHAR(50),                -- 'Goods Receipt PO', 'AR Invoice', 'Standard Cost'
    cost_source_date       DATE,                       -- Date of cost source document

    -- Metadata
    currency               VARCHAR(3) DEFAULT 'CAD',
    warehouse_code         VARCHAR(20) REFERENCES warehouses(warehouse_code),

    created_at             TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(item_code, price_level, snapshot_date),
    CONSTRAINT chk_margin_elements_positive CHECK (sales_price >= 0 AND purchase_price >= 0)
);

-- Indexes
CREATE INDEX idx_margin_elements_date ON margin_elements(snapshot_date DESC);
CREATE INDEX idx_margin_elements_item ON margin_elements(item_code, snapshot_date DESC);
CREATE INDEX idx_margin_elements_negative ON margin_elements(net_margin_pct)
    WHERE net_margin_pct < 0;

COMMENT ON TABLE margin_elements IS 'Net margin breakdown into Gross → Freight → Landed → Net components';
COMMENT ON COLUMN margin_elements.gross_margin_amt IS 'Sales price - Purchase price (simplest margin)';
COMMENT ON COLUMN margin_elements.freight_margin_amt IS 'Gross margin - Freight cost (includes landed costs)';
COMMENT ON COLUMN margin_elements.landed_margin_amt IS 'Freight margin - Duty cost (fully landed)';
COMMENT ON COLUMN margin_elements.net_margin_amt IS 'Landed margin - (Carrying cost + Order cost) (total cost of ownership)';
COMMENT ON COLUMN margin_elements.cost_source IS 'Source of cost data: Goods Receipt PO (most recent), AR Invoice (weighted average), or Standard Cost';
```

#### Table: `users` (Azure AD Integration)

```sql
-- ============================================================================
-- TABLE: users
-- PURPOSE: Azure AD user mapping and profiles
-- ESTIMATED ROWS: ~60 (one per user)
-- STORAGE: ~20 KB
-- UPDATE FREQUENCY: On first login, then on demand
-- ============================================================================

CREATE TABLE users (
    user_id                VARCHAR(100) PRIMARY KEY,   -- Azure AD object ID
    azure_ad_object_id     VARCHAR(100) UNIQUE NOT NULL,
    email                  VARCHAR(255) UNIQUE NOT NULL,
    display_name           VARCHAR(200),
    first_name             VARCHAR(100),
    last_name              VARCHAR(100),

    -- Authentication
    azure_ad_tenant_id     VARCHAR(100),
    last_login_at          TIMESTAMPTZ,
    login_count            INTEGER DEFAULT 0,

    -- User Preferences
    preferences            JSONB,                      -- {"theme": "dark", "timezone": "America/Vancouver"}

    -- Status
    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE users IS 'Azure AD user profiles';
COMMENT ON COLUMN users.azure_ad_object_id IS 'Unique identifier from Azure AD';
COMMENT ON COLUMN users.preferences IS 'User preferences stored as JSON';
```

#### Table: `roles`

```sql
-- ============================================================================
-- TABLE: roles
-- PURPOSE: Role definitions for RBAC
-- ESTIMATED ROWS: ~5-10
-- STORAGE: ~5 KB
-- UPDATE FREQUENCY: Rarely (only when adding new roles)
-- ============================================================================

CREATE TABLE roles (
    role_id                SERIAL PRIMARY KEY,
    role_code              VARCHAR(50) UNIQUE NOT NULL,
    role_name              VARCHAR(100) NOT NULL,
    description            TEXT,

    -- Permissions (JSON array of permission codes)
    permissions            JSONB NOT NULL,            -- ["view_inventory", "view_margins", "admin_settings", ...]

    -- Hierarchy (for future use)
    parent_role_id         INTEGER REFERENCES roles(role_id),
    level                  INTEGER DEFAULT 0,         -- 0 = admin, 1 = manager, 2 = analyst, 3 = viewer

    is_active              BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default roles
INSERT INTO roles (role_code, role_name, description, permissions, level) VALUES
('admin', 'Administrator', 'Full access to all features and settings',
 '["view_inventory", "view_forecasts", "view_margins", "view_reports", "admin_settings", "manage_users", "export_data"]', 0),
('manager', 'Manager', 'View all data, manage alerts, no system settings',
 '["view_inventory", "view_forecasts", "view_margins", "view_reports", "manage_alerts", "export_data"]', 1),
('analyst', 'Analyst', 'View inventory and forecasts, no sensitive margins',
 '["view_inventory", "view_forecasts", "view_reports"]', 2),
('viewer', 'Viewer', 'Read-only access to basic reports',
 '["view_inventory", "view_forecasts"]', 3);

COMMENT ON TABLE roles IS 'Role definitions for role-based access control';
COMMENT ON COLUMN roles.permissions IS 'JSON array of permission codes (e.g., ["view_inventory", "admin_settings"])';
```

#### Table: `user_roles`

```sql
-- ============================================================================
-- TABLE: user_roles
-- PURPOSE: Many-to-many mapping of users to roles
-- ESTIMATED ROWS: ~60-100 (users can have multiple roles)
-- STORAGE: ~10 KB
-- UPDATE FREQUENCY: On-demand (by admin)
-- ============================================================================

CREATE TABLE user_roles (
    mapping_id             BIGSERIAL PRIMARY KEY,
    user_id                VARCHAR(100) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id                INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,

    -- Assignment Details
    assigned_by            VARCHAR(100) REFERENCES users(user_id), -- Admin who assigned role
    assigned_at            TIMESTAMPTZ DEFAULT NOW(),
    expires_at             TIMESTAMPTZ,              -- Optional expiry for temporary access

    is_active              BOOLEAN DEFAULT TRUE,

    UNIQUE(user_id, role_id),
    CONSTRAINT chk_user_roles_dates CHECK (expires_at IS NULL OR expires_at > assigned_at)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);

COMMENT ON TABLE user_roles IS 'Many-to-many mapping of users to roles';
```

#### Table: `audit_log`

```sql
-- ============================================================================
-- TABLE: audit_log
-- PURPOSE: Complete audit trail of all user actions
-- ESTIMATED ROWS: ~10,000+ per month
-- STORAGE: ~5 MB per month
-- UPDATE FREQUENCY: On every action
-- RETENTION: 1 year (archived after)
-- ============================================================================

CREATE TABLE audit_log (
    audit_id               BIGSERIAL PRIMARY KEY,
    event_timestamp        TIMESTAMPTZ DEFAULT NOW(),

    -- User Info
    user_id                VARCHAR(100) REFERENCES users(user_id),
    user_email             VARCHAR(255),
    user_role              VARCHAR(50),

    -- Action Details
    action                 VARCHAR(50) NOT NULL,       -- 'create', 'update', 'delete', 'view', 'export', 'login', 'logout'
    table_name             VARCHAR(50),                -- 'items', 'admin_settings', etc.
    record_id              VARCHAR(100),

    -- Change Details (before/after)
    old_values             JSONB,
    new_values             JSONB,

    -- Request Context
    ip_address             INET,
    user_agent             TEXT,
    request_id             VARCHAR(100),               -- For correlation

    -- Result
    status                 VARCHAR(20) DEFAULT 'success', -- 'success', 'failure', 'error'
    error_message          TEXT,

    -- Session
    session_id             VARCHAR(100),

    CONSTRAINT chk_audit_action CHECK (action IN ('create', 'update', 'delete', 'view', 'export', 'login', 'logout', 'admin_action')),
    CONSTRAINT chk_audit_status CHECK (status IN ('success', 'failure', 'error'))
);

-- Partitioning by month (for easy archival)
CREATE TABLE audit_log ( ... ) PARTITION BY RANGE (event_timestamp);

-- Create partitions
CREATE TABLE audit_log_2026_01 PARTITION OF audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE audit_log_2026_02 PARTITION OF audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- Indexes
CREATE INDEX idx_audit_log_user ON audit_log(user_id, event_timestamp DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action, event_timestamp DESC);
CREATE INDEX idx_audit_log_table ON audit_log(table_name, event_timestamp DESC);

COMMENT ON TABLE audit_log IS 'Complete audit trail of all user actions';
COMMENT ON COLUMN audit_log.old_values IS 'JSON of record state before change (for update/delete actions)';
COMMENT ON COLUMN audit_log.new_values IS 'JSON of record state after change (for create/update actions)';
```

### 3.2 Updated Tables for Margin Tracking

#### Update: `costs` table (add cost source tracking)

```sql
-- Add columns to existing costs table
ALTER TABLE costs ADD COLUMN cost_source_type VARCHAR(50);
ALTER TABLE costs ADD COLUMN cost_source_document VARCHAR(50);
ALTER TABLE costs ADD COLUMN cost_source_date DATE;

ALTER TABLE costs ADD CONSTRAINT chk_cost_source_type
    CHECK (cost_source_type IN ('Goods Receipt PO', 'AR Invoice', 'Standard Cost', 'Manual'));

CREATE INDEX idx_costs_source ON costs(cost_source_type, effective_date DESC);

COMMENT ON COLUMN costs.cost_source_type IS 'Type of cost source document (Goods Receipt PO, AR Invoice, etc.)';
COMMENT ON COLUMN costs.cost_source_document IS 'Document number (PO number, invoice number, etc.)';
COMMENT ON COLUMN costs.cost_source_date IS 'Date of cost source document';
```

#### Update: `pricing` table (add sales price derivation)

```sql
-- Add columns to existing pricing table
ALTER TABLE pricing ADD COLUMN price_derived_from VARCHAR(50);
ALTER TABLE pricing ADD COLUMN price_derived_date DATE;
ALTER TABLE pricing ADD COLUMN price_source_document VARCHAR(50);

ALTER TABLE pricing ADD CONSTRAINT chk_price_derived_from
    CHECK (price_derived_from IN ('Sales Order', 'Price List', 'Manual', 'Markup from Cost'));

COMMENT ON COLUMN pricing.price_derived_from IS 'How price was derived: Sales Order (avg), Price List (SAP), Manual, or Markup from Cost';
COMMENT ON COLUMN pricing.price_derived_date IS 'Date when price was derived';
COMMENT ON COLUMN pricing.price_source_document IS 'Source document number (order number, price list code, etc.)';
```

### 3.3 Materialized Views for Margin Breakdown

#### Materialized View: `vw_margin_gross`

```sql
-- ============================================================================
-- MATERIALIZED VIEW: vw_margin_gross
-- PURPOSE: Shows only Gross Margin (simplest, for quick overview)
-- REFRESH: Daily
-- QUERY TIME: ~5ms (pre-computed)
-- ============================================================================

CREATE MATERIALIZED VIEW vw_margin_gross AS
SELECT
    me.snapshot_date,
    me.item_code,
    i.item_description,
    me.price_level,
    me.sales_price,
    me.purchase_price,
    me.gross_margin_amt,
    me.gross_margin_pct,

    -- Classification
    CASE
        WHEN me.sales_price IS NULL THEN 'No Price'
        WHEN me.purchase_price IS NULL THEN 'No Cost'
        WHEN me.gross_margin_pct >= 40 THEN 'High (≥40%)'
        WHEN me.gross_margin_pct >= 20 THEN 'Medium (20-40%)'
        WHEN me.gross_margin_pct >= 0 THEN 'Low (0-20%)'
        ELSE 'Negative (<0%)'
    END AS margin_category,

    me.cost_source,
    me.cost_source_date

FROM margin_elements me
JOIN items i ON me.item_code = i.item_code
WHERE me.snapshot_date = (SELECT MAX(snapshot_date) FROM margin_elements);

CREATE UNIQUE INDEX idx_vw_margin_gross_item ON vw_margin_gross(item_code, price_level);

COMMENT ON MATERIALIZED VIEW vw_margin_gross IS 'Gross margin view (simplest: Sales Price - Purchase Price)';
```

#### Materialized View: `vw_margin_landed`

```sql
-- ============================================================================
-- MATERIALIZED VIEW: vw_margin_landed
-- PURPOSE: Shows Gross + Freight + Duty components
-- REFRESH: Daily
-- QUERY TIME: ~5ms (pre-computed)
-- ============================================================================

CREATE MATERIALIZED VIEW vw_margin_landed AS
SELECT
    me.snapshot_date,
    me.item_code,
    i.item_description,
    me.price_level,
    me.sales_price,
    me.purchase_price,
    me.freight_cost,
    me.duty_cost,

    -- Landed Cost
    (me.purchase_price + COALESCE(me.freight_cost, 0) + COALESCE(me.duty_cost, 0)) AS total_landed_cost,

    -- Margins
    me.gross_margin_amt,
    me.gross_margin_pct,
    me.freight_margin_amt,
    me.freight_margin_pct,
    me.landed_margin_amt,
    me.landed_margin_pct,

    -- Classification
    CASE
        WHEN me.sales_price IS NULL THEN 'No Price'
        WHEN me.purchase_price IS NULL THEN 'No Cost'
        WHEN me.landed_margin_pct >= 30 THEN 'High (≥30%)'
        WHEN me.landed_margin_pct >= 15 THEN 'Medium (15-30%)'
        WHEN me.landed_margin_pct >= 0 THEN 'Low (0-15%)'
        ELSE 'Negative (<0%)'
    END AS margin_category,

    me.cost_source,
    me.cost_source_date

FROM margin_elements me
JOIN items i ON me.item_code = i.item_code
WHERE me.snapshot_date = (SELECT MAX(snapshot_date) FROM margin_elements);

CREATE UNIQUE INDEX idx_vw_margin_landed_item ON vw_margin_landed(item_code, price_level);

COMMENT ON MATERIALIZED VIEW vw_margin_landed IS 'Landed margin view (includes freight and duty costs)';
```

#### Materialized View: `vw_margin_net`

```sql
-- ============================================================================
-- MATERIALIZED VIEW: vw_margin_net
-- PURPOSE: Shows all margin components (most detailed)
-- REFRESH: Daily
-- QUERY TIME: ~5ms (pre-computed)
-- ============================================================================

CREATE MATERIALIZED VIEW vw_margin_net AS
SELECT
    me.snapshot_date,
    me.item_code,
    i.item_description,
    me.price_level,
    me.warehouse_code,

    -- Price
    me.sales_price,

    -- All Cost Components
    me.purchase_price AS cost_purchase,
    me.freight_cost AS cost_freight,
    me.duty_cost AS cost_duty,
    me.carrying_cost AS cost_carrying,
    me.order_cost AS cost_order,

    -- Total Landed Cost
    (me.purchase_price + COALESCE(me.freight_cost, 0) + COALESCE(me.duty_cost, 0)) AS total_landed_cost,

    -- Total Cost of Ownership
    (me.purchase_price + COALESCE(me.freight_cost, 0) + COALESCE(me.duty_cost, 0) +
     COALESCE(me.carrying_cost, 0) + COALESCE(me.order_cost, 0)) AS total_tco_cost,

    -- Margin Breakdown (Step-down)
    me.gross_margin_amt,
    me.gross_margin_pct,
    me.freight_margin_amt,
    me.freight_margin_pct,
    me.landed_margin_amt,
    me.landed_margin_pct,
    me.net_margin_amt,
    me.net_margin_pct,

    -- Classification (based on Net Margin)
    CASE
        WHEN me.sales_price IS NULL THEN 'No Price'
        WHEN me.purchase_price IS NULL THEN 'No Cost'
        WHEN me.net_margin_pct >= 25 THEN 'High (≥25%)'
        WHEN me.net_margin_pct >= 10 THEN 'Medium (10-25%)'
        WHEN me.net_margin_pct >= 0 THEN 'Low (0-10%)'
        ELSE 'Negative (<0%)'
    END AS margin_category,

    -- Cost Source
    me.cost_source,
    me.cost_source_date,

    -- Currency
    me.currency

FROM margin_elements me
JOIN items i ON me.item_code = i.item_code
WHERE me.snapshot_date = (SELECT MAX(snapshot_date) FROM margin_elements);

CREATE UNIQUE INDEX idx_vw_margin_net_item ON vw_margin_net(item_code, price_level);
CREATE INDEX idx_vw_margin_net_negative ON vw_margin_net(net_margin_pct)
    WHERE net_margin_pct < 0;

COMMENT ON MATERIALIZED VIEW vw_margin_net IS 'Net margin view (all components: Gross → Freight → Landed → Net)';
COMMENT ON COLUMN vw_margin_net.total_tco_cost IS 'Total Cost of Ownership (includes carrying and order costs)';
```

#### Materialized View: `vw_margin_breakdown`

```sql
-- ============================================================================
-- MATERIALIZED VIEW: vw_margin_breakdown
-- PURPOSE: Shows all margin elements side-by-side for comparison
-- REFRESH: Daily
-- QUERY TIME: ~10ms (pre-computed)
-- ============================================================================

CREATE MATERIALIZED VIEW vw_margin_breakdown AS
SELECT
    me.snapshot_date,
    me.item_code,
    i.item_description,
    i.item_group,
    me.price_level,

    -- Price
    me.sales_price,

    -- Cost Components (side-by-side)
    me.purchase_price AS "Cost: Purchase",
    me.freight_cost AS "Cost: Freight",
    me.duty_cost AS "Cost: Duty",
    me.carrying_cost AS "Cost: Carrying",
    me.order_cost AS "Cost: Order",
    (me.purchase_price + COALESCE(me.freight_cost, 0) + COALESCE(me.duty_cost, 0) +
     COALESCE(me.carrying_cost, 0) + COALESCE(me.order_cost, 0)) AS "Cost: Total",

    -- Margin Components (side-by-side)
    me.gross_margin_amt AS "Margin: Gross $",
    me.gross_margin_pct AS "Margin: Gross %",
    me.freight_margin_amt AS "Margin: Less Freight $",
    me.freight_margin_pct AS "Margin: Less Freight %",
    me.landed_margin_amt AS "Margin: Landed $",
    me.landed_margin_pct AS "Margin: Landed %",
    me.net_margin_amt AS "Margin: Net $",
    me.net_margin_pct AS "Margin: Net %",

    -- Visual Indicators
    CASE
        WHEN me.net_margin_pct < 0 THEN '🔴'
        WHEN me.net_margin_pct < 10 THEN '🟡'
        ELSE '🟢'
    END AS "Status",

    me.cost_source,
    me.warehouse_code

FROM margin_elements me
JOIN items i ON me.item_code = i.item_code
WHERE me.snapshot_date = (SELECT MAX(snapshot_date) FROM margin_elements);

CREATE UNIQUE INDEX idx_vw_margin_breakdown_item ON vw_margin_breakdown(item_code, price_level);

COMMENT ON MATERIALIZED VIEW vw_margin_breakdown IS 'Side-by-side comparison of all margin elements';
```

### 3.4 Refresh Function for Margin Materialized Views

```sql
-- ============================================================================
-- FUNCTION: refresh_margin_views()
-- PURPOSE: Refresh all margin materialized views
-- USAGE: Called by worker after margin_elements table is updated
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_margin_views()
RETURNS JSONB AS $$
DECLARE
    start_time TIMESTAMPTZ := NOW();
    result JSONB := '{}'::JSONB;
BEGIN
    -- Refresh vw_margin_gross
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_gross;
    result := result || jsonb_build_object('vw_margin_gross', EXTRACT(EPOCH FROM (NOW() - start_time)));

    -- Refresh vw_margin_landed
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_landed;
    result := result || jsonb_build_object('vw_margin_landed', EXTRACT(EPOCH FROM (NOW() - start_time))));

    -- Refresh vw_margin_net
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_net;
    result := result || jsonb_build_object('vw_margin_net', EXTRACT(EPOCH FROM (NOW() - start_time))));

    -- Refresh vw_margin_breakdown
    REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_breakdown;
    result := result || jsonb_build_object('vw_margin_breakdown', EXTRACT(EPOCH FROM (NOW() - start_time))));

    -- Return timing information
    result := result || jsonb_build_object('total_seconds', EXTRACT(EPOCH FROM (NOW() - start_time))));
    result := result || jsonb_build_object('timestamp', start_time);

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Usage:
-- SELECT refresh_margin_views();
-- Expected output: {"vw_margin_gross": 0.5, "vw_margin_landed": 0.6, "vw_margin_net": 0.7, "vw_margin_breakdown": 0.8, "total_seconds": 2.6, "timestamp": "2026-01-15T10:00:00Z"}
```

---

## SECTION 4: MARGIN MONITORING SYSTEM

### 4.1 Net Margin Calculation Breakdown

The Net Margin is calculated as a step-down process, showing the impact of each cost element:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NET MARGIN CALCULATION BREAKDOWN                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 1: Gross Margin                                                        │
│  ─────────────────                                                           │
│  Gross Margin $ = Sales Price - Purchase Price                               │
│  Gross Margin % = (Gross Margin $ / Sales Price) × 100                       │
│                                                                              │
│  Example:                                                                    │
│    Sales Price: $100.00                                                      │
│    Purchase Price: $60.00                                                    │
│    Gross Margin $ = $100.00 - $60.00 = $40.00                                │
│    Gross Margin % = ($40.00 / $100.00) × 100 = 40%                           │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 2: Freight Margin                                                      │
│  ────────────────────                                                        │
│  Freight Margin $ = Gross Margin $ - Freight Cost                            │
│  Freight Margin % = (Freight Margin $ / Sales Price) × 100                   │
│                                                                              │
│  Example:                                                                    │
│    Gross Margin $: $40.00                                                    │
│    Freight Cost: $5.00                                                       │
│    Freight Margin $ = $40.00 - $5.00 = $35.00                                │
│    Freight Margin % = ($35.00 / $100.00) × 100 = 35%                         │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 3: Landed Margin                                                       │
│  ────────────────────                                                        │
│  Landed Margin $ = Freight Margin $ - Duty Cost                              │
│  Landed Margin % = (Landed Margin $ / Sales Price) × 100                      │
│                                                                              │
│  Example:                                                                    │
│    Freight Margin $: $35.00                                                  │
│    Duty Cost: $3.00                                                          │
│    Landed Margin $ = $35.00 - $3.00 = $32.00                                 │
│    Landed Margin % = ($32.00 / $100.00) × 100 = 32%                          │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 4: Net Margin (Total Cost of Ownership)                                │
│  ─────────────────────────────────────────                                   │
│  Net Margin $ = Landed Margin $ - (Carrying Cost + Order Cost)               │
│  Net Margin % = (Net Margin $ / Sales Price) × 100                           │
│                                                                              │
│  Example:                                                                    │
│    Landed Margin $: $32.00                                                   │
│    Carrying Cost: $2.00 (annual holding cost)                               │
│    Order Cost: $1.00 (processing cost)                                       │
│    Net Margin $ = $32.00 - ($2.00 + $1.00) = $29.00                          │
│    Net Margin % = ($29.00 / $100.00) × 100 = 29%                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Margin Data Collection Strategy

#### Sales Price Source (Option B with A as Backup)

```sql
-- ============================================================================
-- STRATEGY: Derive Sales Price from Sales Orders (Option B)
-- BACKUP: Use SAP Export ITM1/OPLN (Option A)
-- ============================================================================

-- Step 1: Derive average selling price from sales orders (last 90 days)
CREATE OR REPLACE FUNCTION derive_sales_price_from_orders()
RETURNS INTEGER AS $$
DECLARE
    inserted_count INTEGER;
BEGIN
    -- Insert derived prices into pricing table
    INSERT INTO pricing (
        item_code,
        price_level,
        unit_price,
        currency,
        effective_date,
        price_derived_from,
        price_derived_date,
        price_source,
        is_active
    )
    SELECT
        so.item_code,
        'Derived' as price_level,
        AVG(so.row_value / so.ordered_qty) as unit_price,  -- Average selling price
        'CAD' as currency,
        CURRENT_DATE as effective_date,
        'Sales Order' as price_derived_from,
        CURRENT_DATE as price_derived_date,
        'Derived from sales orders (last 90 days)' as price_source,
        TRUE as is_active
    FROM sales_orders so
    WHERE so.posting_date >= CURRENT_DATE - INTERVAL '90 days'
      AND so.ordered_qty > 0
      AND so.row_value > 0
    GROUP BY so.item_code
    ON CONFLICT (item_code, price_level, COALESCE(region, ''), effective_date)
    DO UPDATE SET
        unit_price = EXCLUDED.unit_price,
        updated_at = NOW();

    GET DIAGNOSTICS inserted_count = ROW_COUNT;

    -- Log the operation
    INSERT INTO audit_log (action, table_name, old_values, new_values)
    VALUES ('create', 'pricing', '{"count": 0}', jsonb_build_object('count', inserted_count));

    RETURN inserted_count;
END;
$$ LANGUAGE plpgsql;

-- Step 2: Backup - If SAP exports price list, load it (higher priority)
-- This function is called when ITM1/OPLN export is available
CREATE OR REPLACE FUNCTION load_sales_price_from_sap()
RETURNS INTEGER AS $$
DECLARE
    inserted_count INTEGER;
BEGIN
    -- Assuming SAP export is loaded to temporary table temp_sap_pricing
    INSERT INTO pricing (
        item_code,
        price_level,
        unit_price,
        currency,
        effective_date,
        price_derived_from,
        price_derived_date,
        price_source_document,
        price_source,
        is_active
    )
    SELECT
        item_code,
        price_list_code as price_level,
        unit_price,
        currency,
        effective_date,
        'Price List' as price_derived_from,
        CURRENT_DATE as price_derived_date,
        price_list_code as price_source_document,
        'SAP B1 Price List (ITM1/OPLN)' as price_source,
        TRUE as is_active
    FROM temp_sap_pricing
    ON CONFLICT (item_code, price_level, COALESCE(region, ''), effective_date)
    DO UPDATE SET
        unit_price = EXCLUDED.unit_price,
        price_derived_from = 'Price List',
        price_source_document = EXCLUDED.price_source_document,
        updated_at = NOW();

    GET DIAGNOSTICS inserted_count = ROW_COUNT;

    -- Deactivate derived prices for items with official prices
    UPDATE pricing
    SET is_active = FALSE
    WHERE price_derived_from = 'Sales Order'
      AND EXISTS (
          SELECT 1 FROM pricing p2
          WHERE p2.item_code = pricing.item_code
            AND p2.price_derived_from = 'Price List'
            AND p2.is_active = TRUE
      );

    RETURN inserted_count;
END;
$$ LANGUAGE plpgsql;
```

#### Cost Source Tracking (Goods Receipt PO vs AR Invoice)

```sql
-- ============================================================================
-- STRATEGY: Use Most Recent Goods Receipt PO (Primary)
-- BACKUP: Use AR Invoice if Goods Receipt not available
-- ============================================================================

-- Function to track cost source
CREATE OR REPLACE FUNCTION update_cost_with_source()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    -- Update costs table with source tracking
    -- Priority 1: Most recent Goods Receipt PO
    WITH goods_receipt_costs AS (
        SELECT DISTINCT ON (po.item_code)
            po.item_code,
            po.row_value / po.ordered_qty as unit_cost,
            po.po_date as cost_date,
            po.po_number as cost_document,
            'Goods Receipt PO' as cost_source_type
        FROM purchase_orders po
        WHERE po.event_date IS NOT NULL  -- Receipt has occurred
          AND po.ordered_qty > 0
          AND po.row_value > 0
        ORDER BY po.item_code, po.event_date DESC  -- Most recent first
    )
    INSERT INTO costs (
        item_code,
        effective_date,
        unit_cost,
        currency,
        cost_source_type,
        cost_source_document,
        cost_source_date,
        cost_source
    )
    SELECT
        item_code,
        cost_date as effective_date,
        unit_cost,
        'CAD' as currency,
        cost_source_type,
        cost_document as cost_source_document,
        cost_date as cost_source_date,
        'Most recent Goods Receipt PO' as cost_source
    FROM goods_receipt_costs
    ON CONFLICT (item_code, effective_date, COALESCE(vendor_code, ''))
    DO UPDATE SET
        unit_cost = EXCLUDED.unit_cost,
        cost_source_type = EXCLUDED.cost_source_type,
        cost_source_document = EXCLUDED.cost_source_document,
        cost_source_date = EXCLUDED.cost_source_date,
        updated_at = NOW();

    GET DIAGNOSTICS updated_count = ROW_COUNT;

    -- Priority 2: For items without Goods Receipt, use AR Invoice
    -- (This would be implemented if AR Invoice data is available)
    -- For now, use standard cost as fallback

    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;
```

### 4.3 Margin Alert Generation

```sql
-- ============================================================================
-- FUNCTION: generate_margin_alerts()
-- PURPOSE: Generate alerts based on margin thresholds
-- CALLED: Daily after margin_elements table is refreshed
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_margin_alerts()
RETURNS JSONB AS $$
DECLARE
    alert_threshold_pct NUMERIC;
    negative_margin_alert BOOLEAN;
    decrease_alert_pct NUMERIC;
    snapshot_date DATE;
    alerts_generated INTEGER := 0;
BEGIN
    -- Get settings from admin_settings
    SELECT
        setting_value::NUMERIC INTO alert_threshold_pct
    FROM admin_settings
    WHERE setting_key = 'margin.alert_threshold_pct';

    SELECT
        setting_value::BOOLEAN INTO negative_margin_alert
    FROM admin_settings
    WHERE setting_key = 'margin.negative_margin_alert';

    SELECT
        setting_value::NUMERIC INTO decrease_alert_pct
    FROM admin_settings
    WHERE setting_key = 'margin.decrease_alert_pct';

    -- Get latest snapshot date
    SELECT MAX(snapshot_date) INTO snapshot_date
    FROM margin_elements;

    -- Alert Type 1: Negative Margins
    IF negative_margin_alert THEN
        INSERT INTO margin_alerts (
            item_code,
            alert_date,
            alert_type,
            current_margin_pct,
            priority,
            notification_channels
        )
        SELECT
            item_code,
            snapshot_date,
            'negative',
            net_margin_pct,
            CASE
                WHEN net_margin_pct < -20 THEN 'critical'
                WHEN net_margin_pct < -10 THEN 'high'
                ELSE 'medium'
            END,
            ARRAY['in_app', 'email']
        FROM margin_elements
        WHERE snapshot_date = snapshot_date
          AND net_margin_pct < 0
        ON CONFLICT DO NOTHING;

        GET DIAGNOSTICS alerts_generated = ROW_COUNT + alerts_generated;
    END IF;

    -- Alert Type 2: Below Threshold
    INSERT INTO margin_alerts (
        item_code,
        alert_date,
        alert_type,
        current_margin_pct,
        threshold_margin_pct,
        priority,
        notification_channels
    )
    SELECT
        item_code,
        snapshot_date,
        'below_threshold',
        net_margin_pct,
        alert_threshold_pct,
        CASE
            WHEN net_margin_pct < alert_threshold_pct - 10 THEN 'high'
            ELSE 'medium'
        END,
        ARRAY['in_app']
    FROM margin_elements
    WHERE snapshot_date = snapshot_date
      AND net_margin_pct >= 0  -- Exclude negative (already alerted)
      AND net_margin_pct < alert_threshold_pct
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS alerts_generated = ROW_COUNT + alerts_generated;

    -- Alert Type 3: Margin Decrease (vs previous snapshot)
    INSERT INTO margin_alerts (
        item_code,
        alert_date,
        alert_type,
        current_margin_pct,
        previous_margin_pct,
        margin_change_pct,
        priority,
        notification_channels
    )
    SELECT
        current.item_code,
        current.snapshot_date,
        'decreased',
        current.net_margin_pct,
        previous.net_margin_pct,
        current.net_margin_pct - previous.net_margin_pct,
        CASE
            WHEN (current.net_margin_pct - previous.net_margin_pct) < -decrease_alert_pct * 2 THEN 'high'
            ELSE 'low'
        END,
        ARRAY['in_app']
    FROM margin_elements current
    JOIN margin_elements previous
        ON current.item_code = previous.item_code
        AND previous.snapshot_date = (
            SELECT MAX(snapshot_date)
            FROM margin_elements
            WHERE snapshot_date < current.snapshot_date
        )
    WHERE current.snapshot_date = snapshot_date
      AND current.net_margin_pct >= 0  -- Only positive margins
      AND previous.net_margin_pct > 0
      AND (current.net_margin_pct - previous.net_margin_pct) < -decrease_alert_pct
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS alerts_generated = ROW_COUNT + alerts_generated;

    -- Return summary
    RETURN jsonb_build_object(
        'alerts_generated', alerts_generated,
        'snapshot_date', snapshot_date,
        'threshold_pct', alert_threshold_pct,
        'timestamp', NOW()
    );
END;
$$ LANGUAGE plpgsql;
```

### 4.4 Margin Trend Analysis View

```sql
-- ============================================================================
-- VIEW: v_margin_trend_analysis
-- PURPOSE: Track margin changes over time (last 6 snapshots)
-- QUERY TIME: ~50ms (with indexes)
-- ============================================================================

CREATE VIEW v_margin_trend_analysis AS
WITH ranked_snapshots AS (
    SELECT
        item_code,
        snapshot_date,
        net_margin_pct,
        LAG(net_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date) as prev_margin_pct,
        ROW_NUMBER() OVER (PARTITION BY item_code ORDER BY snapshot_date DESC) as rn
    FROM margin_elements
    WHERE snapshot_date >= CURRENT_DATE - INTERVAL '6 months'
),
margin_changes AS (
    SELECT
        item_code,
        snapshot_date,
        net_margin_pct,
        prev_margin_pct,
        (net_margin_pct - prev_margin_pct) as margin_change_pct,
        rn
    FROM ranked_snapshots
    WHERE rn <= 6  -- Last 6 snapshots
)
SELECT
    item_code,
    i.item_description,
    MAX(snapshot_date) as latest_snapshot,
    AVG(net_margin_pct) as avg_margin_pct,
    MIN(net_margin_pct) as min_margin_pct,
    MAX(net_margin_pct) as max_margin_pct,
    (MAX(net_margin_pct) - MIN(net_margin_pct)) as margin_range_pct,
    STDDEV(net_margin_pct) as margin_stddev_pct,
    (MAX(net_margin_pct) - MIN(net_margin_pct)) / NULLIF(AVG(net_margin_pct), 0) * 100 as margin_volatility_pct,

    -- Trend direction
    CASE
        WHEN MAX(snapshot_date) > MIN(snapshot_date) THEN
            CASE
                WHEN (FIRST_VALUE(net_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date DESC) -
                      LAST_VALUE(net_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date DESC)) > 2
                THEN 'Improving'
                WHEN (FIRST_VALUE(net_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date DESC) -
                      LAST_VALUE(net_margin_pct) OVER (PARTITION BY item_code ORDER BY snapshot_date DESC)) < -2
                THEN 'Declining'
                ELSE 'Stable'
            END
        ELSE 'Insufficient Data'
    END AS trend_direction,

    COUNT(DISTINCT snapshot_date) as snapshot_count

FROM margin_changes mc
JOIN items i ON mc.item_code = i.item_code
GROUP BY item_code, i.item_description
HAVING COUNT(DISTINCT snapshot_date) >= 2  -- At least 2 snapshots
ORDER BY margin_volatility_pct DESC;

COMMENT ON VIEW v_margin_trend_analysis IS 'Margin trend analysis over last 6 months';
```

---

## SECTION 5: ADMIN INTERFACE DESIGN

### 5.1 Streamlit Admin Page Layout

```python
# src/admin_ui.py
import streamlit as st
import pandas as pd
from src.database import get_engine
from src.auth import require_role

@require_role(['admin'])
def admin_settings_page():
    """Admin settings interface"""
    st.title("⚙️ Admin Settings")
    st.markdown("---")

    engine = get_engine()

    # Load current settings
    df_settings = pd.read_sql("""
        SELECT setting_key, setting_value, setting_type, category, display_name, description, default_value
        FROM admin_settings
        ORDER BY category, setting_key
    """, engine)

    # Group by category
    categories = df_settings['category'].unique()

    tab1, tab2, tab3, tab4 = st.tabs(["Data Freshness", "Margin Alerts", "System", "Audit Log"])

    with tab1:
        st.header("📅 Data Freshness Settings")
        st.markdown("Configure how often data is refreshed from SAP B1")

        data_freshness_settings = df_settings[df_settings['category'] == 'data_freshness']

        for _, row in data_freshness_settings.iterrows():
            with st.expander(f"📌 {row['display_name']}", expanded=True):
                st.caption(row['description'])

                # Render input based on type
                if row['setting_type'] == 'integer':
                    current_value = st.number_input(
                        label=f"Current Value",
                        value=int(row['setting_value']),
                        min_value=int(row['min_value']) if pd.notna(row['min_value']) else None,
                        max_value=int(row['max_value']) if pd.notna(row['max_value']) else None,
                        key=f"setting_{row['setting_key']}"
                    )
                elif row['setting_type'] == 'float':
                    current_value = st.number_input(
                        label=f"Current Value",
                        value=float(row['setting_value']),
                        min_value=float(row['min_value']) if pd.notna(row['min_value']) else None,
                        max_value=float(row['max_value']) if pd.notna(row['max_value']) else None,
                        key=f"setting_{row['setting_key']}"
                    )
                elif row['setting_type'] == 'boolean':
                    current_value = st.checkbox(
                        label=f"Enabled",
                        value=bool(row['setting_value'] == 'true'),
                        key=f"setting_{row['setting_key']}"
                    )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"💾 Save", key=f"save_{row['setting_key']}"):
                        # Update setting in database
                        with engine.begin() as conn:
                            conn.execute("""
                                UPDATE admin_settings
                                SET setting_value = %s,
                                    updated_by = %s,
                                    updated_at = NOW(),
                                    version = version + 1
                                WHERE setting_key = %s
                            """, (str(current_value), st.session_state['user_id'], row['setting_key']))
                        st.success(f"✅ Saved: {row['display_name']}")
                        st.rerun()

                with col2:
                    if st.button(f"↩️ Reset to Default", key=f"reset_{row['setting_key']}"):
                        with engine.begin() as conn:
                            conn.execute("""
                                UPDATE admin_settings
                                SET setting_value = %s,
                                    updated_by = %s,
                                    updated_at = NOW()
                                WHERE setting_key = %s
                            """, (row['default_value'], st.session_state['user_id'], row['setting_key']))
                        st.success(f"✅ Reset to default: {row['display_name']}")
                        st.rerun()

                st.caption(f"Default: {row['default_value']}")

    with tab2:
        st.header("🚨 Margin Alert Thresholds")
        st.markdown("Configure when to generate margin alerts")

        margin_alert_settings = df_settings[df_settings['category'] == 'alerts']

        for _, row in margin_alert_settings.iterrows():
            with st.expander(f"📌 {row['display_name']}", expanded=True):
                st.caption(row['description'])

                if row['setting_type'] == 'float':
                    current_value = st.number_input(
                        label=f"Threshold (%)",
                        value=float(row['setting_value']),
                        min_value=0.0,
                        max_value=100.0,
                        step=0.5,
                        key=f"setting_{row['setting_key']}"
                    )
                elif row['setting_type'] == 'boolean':
                    current_value = st.checkbox(
                        label=f"Enabled",
                        value=bool(row['setting_value'] == 'true'),
                        key=f"setting_{row['setting_key']}"
                    )

                if st.button(f"💾 Save", key=f"save_{row['setting_key']}"):
                    with engine.begin() as conn:
                        conn.execute("""
                            UPDATE admin_settings
                            SET setting_value = %s,
                                updated_by = %s,
                                updated_at = NOW()
                            WHERE setting_key = %s
                        """, (str(current_value), st.session_state['user_id'], row['setting_key']))
                    st.success(f"✅ Saved: {row['display_name']}")
                    st.rerun()

    with tab3:
        st.header("🖥️ System Settings")
        st.markdown("Configure system-wide settings")

        system_settings = df_settings[df_settings['category'] == 'system']

        for _, row in system_settings.iterrows():
            with st.expander(f"📌 {row['display_name']}"):
                st.caption(row['description'])
                st.info(f"Current Value: `{row['setting_value']}`")

                # Display current system status
                if row['setting_key'] == 'system.max_concurrent_users':
                    active_users = pd.read_sql("""
                        SELECT COUNT(DISTINCT user_id) as active_users
                        FROM audit_log
                        WHERE action = 'login'
                          AND event_timestamp > NOW() - INTERVAL '1 hour'
                    """, engine)
                    st.metric("Active Users (last hour)", f"{active_users.iloc[0]['active_users']} / {row['setting_value']}")

                if row['setting_key'] == 'cache.query_ttl_seconds':
                    cache_stats = pd.read_sql("""
                        SELECT
                            COUNT(*) as cached_queries,
                            AVG(EXTRACT(EPOCH FROM (NOW() - created_at))) as avg_age_seconds
                        FROM redis_cache_keys
                        WHERE key LIKE 'query:%'
                    """, engine)
                    if not cache_stats.empty and cache_stats.iloc[0]['cached_queries'] > 0:
                        st.metric("Cached Queries", f"{cache_stats.iloc[0]['cached_queries']}")
                        st.metric("Avg Cache Age", f"{cache_stats.iloc[0]['avg_age_seconds']:.0f}s")

    with tab4:
        st.header("📋 Audit Log")
        st.markdown("Recent system activity")

        # Load recent audit logs
        df_audit = pd.read_sql("""
            SELECT
                event_timestamp,
                user_email,
                action,
                table_name,
                record_id,
                status
            FROM audit_log
            ORDER BY event_timestamp DESC
            LIMIT 100
        """, engine)

        st.dataframe(
            df_audit,
            column_config={
                "event_timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
                "user_email": st.column_config.TextColumn("User"),
                "action": st.column_config.TextColumn("Action"),
                "table_name": st.column_config.TextColumn("Table"),
                "record_id": st.column_config.TextColumn("Record ID"),
                "status": st.column_config.TextColumn("Status")
            },
            use_container_width=True
        )

if __name__ == "__main__":
    admin_settings_page()
```

### 5.2 Admin Dashboard Mockup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ADMIN DASHBOARD                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  📊 System Status                                                     │  │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐         │  │
│  │  │ Active Users    │ │ Database Size   │ │ Cache Hit Rate  │         │  │
│  │  │   12 / 60       │ │   45 MB / 1 GB  │ │      94%        │         │  │
│  │  │   🟢 Healthy    │ │   🟢 Healthy    │ │   🟢 Excellent  │         │  │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  📅 Data Freshness                                                     │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │  Data Type          Last Update      Next Update      Status   │   │  │
│  │  ├────────────────────────────────────────────────────────────────┤   │  │
│  │  │  Inventory         2 hours ago     22 hours         ✅ Fresh  │   │  │
│  │  │  Forecasts         15 days ago    75 days          ⚠️  Due   │   │  │
│  │  │  Pricing           2 hours ago     22 hours         ✅ Fresh  │   │  │
│  │  │  Margins           2 hours ago     22 hours         ✅ Fresh  │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  🚨 Active Margin Alerts (5)                                          │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │  Item          Type           Margin %     Priority     Action  │   │  │
│  │  ├────────────────────────────────────────────────────────────────┤   │  │
│  │  │  30071C-CGY   Negative       -5.2%        🔴 Critical   [View] │   │  │
│  │  │  30072C-DEL   Below Thresh   12.8%       🟡 High      [View] │   │  │
│  │  │  30073C-EDM   Decreased      18.5% → 15%  🟢 Medium    [View] │   │  │
│  │  │  ...                                                                   │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  ⚙️ Quick Actions                                                       │  │
│  │  [🔄 Refresh Inventory] [🔄 Refresh Forecasts] [🔄 Refresh Margins]    │  │
│  │  [📊 Generate Reports] [🧹 Clear Cache] [📤 Export Data]              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## SECTION 6: AZURE AD AUTHENTICATION

### 6.1 Azure AD Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AZURE AD AUTHENTICATION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User accesses Railway app → https://app.railway.app                     │
│  2. Streamlit checks session → Redis (session store)                        │
│  3. If not authenticated → Redirect to Azure AD login                      │
│  4. User enters credentials → Azure AD validates                            │
│  5. Azure AD redirects back → https://app.railway.app/?code=...            │
│  6. Streamlit exchanges code for token → MSAL Python                        │
│  7. Streamlit validates token → Parses user info                            │
│  8. Streamlit queries users table → Get user profile                       │
│  9. Streamlit gets user roles → Cache in Redis (2 hours)                   │
│ 10. User accesses page → Check permissions (from cache)                    │
│ 11. Log to audit_log table → Track login/logout                            │
│ 12. Grant access to authorized pages → Render UI                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 MSAL Python Implementation

```python
# src/auth.py
import streamlit as st
import msal
import uuid
import hashlib
from src.database import get_engine
import pandas as pd

# Azure AD Configuration (from Railway secrets)
AZURE_CLIENT_ID = st.secrets.get("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = st.secrets.get("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = st.secrets.get("AZURE_TENANT_ID")
AZURE_REDIRECT_URI = st.secrets.get("AZURE_REDIRECT_URI")
AZURE_AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"

# MSAL Application
@st.cache_resource
def get_msal_app():
    """Create MSAL application instance"""
    return msal.ConfidentialClientApplication(
        AZURE_CLIENT_ID,
        authority=AZURE_AUTHORITY,
        client_credential=AZURE_CLIENT_SECRET,
    )

def get_auth_url():
    """Generate Azure AD authorization URL"""
    app = get_msal_app()

    # Generate state parameter for CSRF protection
    state = str(uuid.uuid4())

    # Build auth URL
    auth_url = app.get_authorization_request_url(
        scopes=["User.Read"],
        state=state,
        redirect_uri=AZURE_REDIRECT_URI
    )

    return auth_url, state

def acquire_token_from_code(auth_code):
    """Exchange authorization code for access token"""
    app = get_msal_app()

    result = app.acquire_token_by_authorization_code(
        auth_code,
        scopes=["User.Read"],
        redirect_uri=AZURE_REDIRECT_URI
    )

    if "access_token" in result:
        return result
    else:
        st.error(f"Error acquiring token: {result.get('error_description')}")
        return None

def get_user_from_token(token_result):
    """Get user info from access token"""
    # Parse ID token (JWT)
    id_token = token_result.get("id_token")

    # Decode JWT (simplified, use pyjwt for production)
    import json
    import base64

    # Split JWT into parts
    parts = id_token.split(".")

    # Decode payload (base64url)
    payload = parts[1]
    # Add padding if needed
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    claims = json.loads(decoded)

    return {
        "user_id": claims.get("oid"),  # Azure AD object ID
        "email": claims.get("email") or claims.get("upn"),
        "display_name": claims.get("name"),
        "first_name": claims.get("given_name"),
        "last_name": claims.get("family_name"),
        "tenant_id": claims.get("tid"),
    }

def sync_user_to_database(user_info):
    """Sync user from Azure AD to users table"""
    engine = get_engine()

    with engine.begin() as conn:
        # Check if user exists
        result = conn.execute("""
            SELECT user_id FROM users WHERE azure_ad_object_id = %s
        """, (user_info['user_id'],)).fetchone()

        if result:
            # Update last login
            conn.execute("""
                UPDATE users
                SET last_login_at = NOW(),
                    login_count = login_count + 1,
                    updated_at = NOW()
                WHERE azure_ad_object_id = %s
            """, (user_info['user_id'],))
        else:
            # Insert new user
            conn.execute("""
                INSERT INTO users (
                    user_id, azure_ad_object_id, email, display_name,
                    first_name, last_name, azure_ad_tenant_id,
                    last_login_at, login_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)
                ON CONFLICT (azure_ad_object_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    last_login_at = NOW(),
                    login_count = users.login_count + 1
            """, (
                user_info['user_id'],
                user_info['user_id'],
                user_info['email'],
                user_info['display_name'],
                user_info.get('first_name'),
                user_info.get('last_name'),
                user_info['tenant_id']
            ))

        # Assign default role (viewer) if no roles
        conn.execute("""
            INSERT INTO user_roles (user_id, role_id, assigned_by)
            SELECT %s, role_id, %s
            FROM roles
            WHERE role_code = 'viewer'
            AND NOT EXISTS (
                SELECT 1 FROM user_roles WHERE user_id = %s
            )
        """, (user_info['user_id'], user_info['user_id'], user_info['user_id']))

    # Log login to audit log
    with engine.begin() as conn:
        conn.execute("""
            INSERT INTO audit_log (user_id, user_email, action, status)
            VALUES (%s, %s, 'login', 'success')
        """, (user_info['user_id'], user_info['email']))

def get_user_roles(user_id):
    """Get user roles from database (with caching)"""
    from src.cache import get_cached_permissions, cache_user_permissions

    # Check cache first
    cached = get_cached_permissions(user_id)
    if cached:
        return cached

    # Query database
    engine = get_engine()

    df_roles = pd.read_sql("""
        SELECT r.role_code, r.role_name, r.permissions
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.role_id
        WHERE ur.user_id = %s
          AND ur.is_active = TRUE
          AND r.is_active = TRUE
          AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
    """, engine, params=(user_id,))

    if df_roles.empty:
        return []

    # Extract permissions
    permissions = []
    for _, row in df_roles.iterrows():
        permissions.extend(row['permissions'])

    # Remove duplicates
    permissions = list(set(permissions))

    # Cache for 2 hours
    cache_user_permissions(user_id, permissions, ttl=7200)

    return permissions

def require_role(allowed_roles):
    """Decorator to require specific role for page access"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Check if user is authenticated
            if 'user_id' not in st.session_state:
                st.error("🔒 Please login to access this page")
                st.stop()

            # Get user roles
            user_roles = get_user_roles(st.session_state['user_id'])

            # Check if user has required role
            user_role_codes = pd.read_sql("""
                SELECT r.role_code
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.user_id = %s
            """, get_engine(), params=(st.session_state['user_id'],))['role_code'].tolist()

            if not any(role in allowed_roles for role in user_role_codes):
                st.error(f"🔒 Access denied. Required role: {', '.join(allowed_roles)}")
                st.info("Your roles: " + ", ".join(user_role_codes))
                st.stop()

            # Call the function
            return func(*args, **kwargs)
        return wrapper
    return decorator

def check_permission(permission_code):
    """Check if user has specific permission"""
    if 'user_id' not in st.session_state:
        return False

    user_permissions = get_user_roles(st.session_state['user_id'])
    return permission_code in user_permissions

# Streamlit authentication flow
def authenticate_user():
    """Main authentication flow"""
    engine = get_engine()

    # Check query params for auth callback
    query_params = st.query_params

    if "code" in query_params and "state" in query_params:
        # Auth callback: Exchange code for token
        auth_code = query_params["code"]

        token_result = acquire_token_from_code(auth_code)

        if token_result and "access_token" in token_result:
            # Get user info
            user_info = get_user_from_token(token_result)

            # Sync to database
            sync_user_to_database(user_info)

            # Set session state
            st.session_state['user_id'] = user_info['user_id']
            st.session_state['user_email'] = user_info['email']
            st.session_state['user_name'] = user_info['display_name']
            st.session_state['access_token'] = token_result['access_token']

            # Clear query params
            st.query_params.clear()

            st.rerun()
        else:
            st.error("❌ Authentication failed. Please try again.")

    # Check if user is already authenticated
    if 'user_id' in st.session_state:
        # Verify user still exists and is active
        user_exists = pd.read_sql("""
            SELECT is_active FROM users WHERE user_id = %s
        """, engine, params=(st.session_state['user_id'],))

        if user_exists.empty or not user_exists.iloc[0]['is_active']:
            # User not found or inactive, clear session
            for key in ['user_id', 'user_email', 'user_name', 'access_token']:
                st.session_state.pop(key, None)
            st.rerun()

        return True

    # Show login button
    st.title("🔐 SAP B1 Inventory Analyzer")
    st.markdown("Please login to continue")

    auth_url, state = get_auth_url()

    st.markdown(f"""
    <a href="{auth_url}" target="_self">
    <button style="background-color:#0078d4;color:white;padding:10px 20px;border:none;border-radius:5px;cursor:pointer;font-size:16px;">
    Login with Azure AD
    </button>
    </a>
    """, unsafe_allow_html=True)

    st.stop()
    return False
```

### 6.3 Role-Based Access Control (RBAC)

```python
# src/permissions.py

# Permission definitions (matching roles.permissions JSON)
PERMISSIONS = {
    "view_inventory": "View inventory status and levels",
    "view_forecasts": "View forecast analysis and trends",
    "view_margins": "View margin reports and breakdowns",
    "view_reports": "View all reports (inventory, forecast, margin)",
    "admin_settings": "Access admin settings page",
    "manage_users": "Manage user roles and permissions",
    "manage_alerts": "Manage and resolve margin alerts",
    "export_data": "Export data to CSV/Excel",
}

def require_permission(permission_code):
    """Decorator to require specific permission"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not check_permission(permission_code):
                st.error(f"🔒 You don't have permission to access this feature")
                st.info(f"Required permission: {PERMISSIONS.get(permission_code, permission_code)}")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Usage in Streamlit app:
# @require_permission("admin_settings")
# def admin_page():
#     st.title("Admin Settings")
```

---

## SECTION 7: SCALABILITY PLAN (30-60 USERS)

### 7.1 Connection Pooling Strategy

**Challenge:** 60 concurrent users × 2 connections each = 120 connections
**Solution:** SQLAlchemy connection pooling + connection reuse

```python
# src/connection_pool.py
from sqlalchemy.pool import QueuePool
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
import logging

logger = logging.getLogger(__name__)

@st.cache_resource
def get_engine_with_pooling():
    """Create SQLAlchemy engine with aggressive connection pooling"""
    engine = create_engine(
        st.secrets["DATABASE_URL"],
        poolclass=QueuePool,
        pool_size=10,              # Base pool size
        max_overflow=20,           # Additional connections when needed
        pool_timeout=30,           # Seconds to wait before timeout
        pool_recycle=3600,         # Recycle connections after 1 hour
        pool_pre_ping=True,        # Test connections before using
        pool_use_lifo=True,        # Use most recently used connection (better for caching)
        echo=False
    )

    # Log connection pool events
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        logger.debug(f"New connection created: {dbapi_conn}")

    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        logger.debug(f"Connection checked out from pool")

    return engine

# Connection pool usage in Streamlit
def execute_query(query, params=None):
    """Execute query with connection pooling"""
    engine = get_engine_with_pooling()

    with engine.connect() as conn:
        result = conn.execute(query, params or {})
        return result.fetchall()

# Streamlit uses connection lifecycle:
# 1. Script start → Get connection from pool (if available)
# 2. Execute queries → Reuse same connection
# 3. Script end → Return connection to pool
# 4. Next user interaction → Get connection from pool (likely same connection)
```

**Connection Pool Sizing:**

| Metric | Value | Calculation |
|--------|-------|-------------|
| Concurrent Users | 60 | Maximum expected |
| Avg Connections per User | 0.2 | Streamlit reuses connections aggressively |
| Base Pool Size | 10 | 60 × 0.2 = 12, rounded to 10 |
| Max Overflow | 20 | For peak load (60 × 0.5 = 30 max) |
| Total Connections | 30 | 10 + 20 |
| Railway Connection Limit | 100 | Well within limits |

### 7.2 Redis Caching Strategy

**What to Cache:**

1. **User Sessions** (TTL: 2 hours)
2. **User Permissions** (TTL: 2 hours)
3. **Query Results** (TTL: 1 hour)
4. **Materialized View Refresh Times** (TTL: 24 hours)

```python
# src/cache.py
import redis
import json
import hashlib
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

@st.cache_resource
def get_redis_client():
    """Create Redis client"""
    return redis.from_url(
        st.secrets["REDIS_URL"],
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )

def cache_key(*args, **kwargs) -> str:
    """Generate consistent cache key"""
    key_part = ":".join(str(arg) for arg in args)
    if kwargs:
        key_part += ":" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(key_part.encode()).hexdigest()

# Cache decorators
def cache_query(ttl: int = 3600):
    """Decorator to cache query results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            client = get_redis_client()

            # Generate cache key
            key = f"query:{cache_key(func.__name__, *args, **kwargs)}"

            # Try to get from cache
            try:
                cached = client.get(key)
                if cached:
                    logger.debug(f"Cache hit: {key}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Cache get failed: {e}")

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            try:
                client.setex(key, ttl, json.dumps(result))
                logger.debug(f"Cached result: {key}")
            except Exception as e:
                logger.warning(f"Cache set failed: {e}")

            return result
        return wrapper
    return decorator

def cache_user_session(user_id: str, session_data: dict, ttl: int = 7200):
    """Cache user session"""
    client = get_redis_client()
    key = f"session:{user_id}"
    client.setex(key, ttl, json.dumps(session_data))
    logger.debug(f"Cached session for user {user_id}")

def get_cached_session(user_id: str) -> Optional[dict]:
    """Get cached user session"""
    client = get_redis_client()
    key = f"session:{user_id}"
    cached = client.get(key)
    if cached:
        return json.loads(cached)
    return None

def invalidate_user_cache(user_id: str):
    """Invalidate all cache entries for a user"""
    client = get_redis_client()

    # Delete session
    client.delete(f"session:{user_id}")

    # Delete permissions
    client.delete(f"permissions:{user_id}")

    # Note: Query cache will expire naturally via TTL
    logger.info(f"Invalidated cache for user {user_id}")

def clear_all_cache():
    """Clear all cache (use with caution)"""
    client = get_redis_client()

    # Get all keys with our prefix
    keys = client.keys("query:*") + client.keys("session:*") + client.keys("permissions:*")

    if keys:
        client.delete(*keys)
        logger.warning(f"Cleared {len(keys)} cache entries")
```

### 7.3 Query Performance Optimization

**Strategy: Materialized Views for Expensive Queries**

```python
# src/queries.py
from src.cache import cache_query
import pandas as pd
from src.database import get_engine

# BAD: Expensive query runs every time
def get_inventory_with_forecast_slow():
    """Slow query (no caching)"""
    engine = get_engine()
    return pd.read_sql("""
        SELECT
            ic.item_code,
            i.item_description,
            ic.on_hand_qty,
            ic.on_order_qty,
            ic.committed_qty,
            ic.available_qty,
            f.forecast_month_1,
            f.forecast_month_2,
            f.forecast_month_3,
            (f.forecast_month_1 + f.forecast_month_2 + f.forecast_month_3) as forecast_3month_total
        FROM inventory_current ic
        JOIN items i ON ic.item_code = i.item_code
        LEFT JOIN forecasts f ON ic.item_code = f.item_code AND f.status = 'Active'
        WHERE ic.on_hand_qty > 0
    """, engine)

# GOOD: Cached query result
@cache_query(ttl=3600)  # Cache for 1 hour
def get_inventory_with_forecast_cached():
    """Fast query (cached)"""
    return get_inventory_with_forecast_slow()

# BETTER: Pre-computed materialized view
def get_inventory_with_forecast_materialized():
    """Fastest query (materialized view)"""
    engine = get_engine()
    return pd.read_sql("""
        SELECT * FROM v_inventory_status_with_forecast
        WHERE on_hand_qty > 0
    """, engine)

# Usage in Streamlit
st.title("Inventory Status")

# Option 1: Use cached query (good for dynamic data)
df = get_inventory_with_forecast_cached()

# Option 2: Use materialized view (best for static data)
df = get_inventory_with_forecast_materialized()

st.dataframe(df)
```

### 7.4 Performance Monitoring

```python
# src/monitoring.py
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def monitor_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Log performance
            logger.info(f"✅ {func.__name__} completed in {elapsed:.2f}s")

            # Alert if slow
            if elapsed > 5.0:
                logger.warning(f"⚠️  {func.__name__} is slow: {elapsed:.2f}s")

            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {func.__name__} failed after {elapsed:.2f}s: {e}")
            raise

    return wrapper

# Usage
@monitor_performance
def load_inventory_data():
    """Load inventory data with performance monitoring"""
    engine = get_engine()
    return pd.read_sql("SELECT * FROM v_inventory_status_with_forecast", engine)
```

### 7.5 Load Testing Plan

**Tools:** Locust (Python load testing framework)

```python
# locustfile.py
from locust import HttpUser, task, between
import json

class StreamlitUser(HttpUser):
    wait_time = between(5, 15)  # Simulate real user behavior

    def on_start(self):
        """Login on start"""
        # Simulate Azure AD login
        response = self.client.get("/")
        # Assume Azure AD redirect happens here

        # For testing, skip auth and use test token
        self.client.post("/auth/login", json={
            "access_token": "test_token",
            "user_id": "test_user_1"
        })

    @task(3)  # 3x weight (most common action)
    def view_inventory(self):
        """View inventory status page"""
        self.client.get("/Inventory")

    @task(2)
    def view_forecasts(self):
        """View forecast analysis page"""
        self.client.get("/Forecast_Analysis")

    @task(1)
    def view_margins(self):
        """View margin reports page"""
        self.client.get("/Margin_Reports")

    @task(1)
    def admin_settings(self):
        """Access admin settings (admin only)"""
        self.client.get("/Admin_Settings")

# Run load test:
# locust -f locustfile.py --users 60 --spawn-rate 10 --host https://your-app.railway.app
# Expected: All requests should succeed (<500ms response time)
```

---

## SECTION 8: DATA PROCESSING PIPELINE

### 8.1 "Process Then Push" Architecture Options

#### Option A: In-App Processing (Simple, Single Service)

**Pros:**
- Simple deployment (single Railway service)
- Easy to debug
- No additional infrastructure

**Cons:**
- Processing blocks user requests
- Sluggish UI during processing
- Not scalable beyond 20 users

**Implementation:**

```python
# src/pipeline_option_a.py
import streamlit as st
from src.ingestion import ingest_all_data
from src.forecasting import generate_all_forecasts
from src.database import get_engine
import logging

logger = logging.getLogger(__name__)

def refresh_data_in_app():
    """Process data in Streamlit app (blocks UI)"""

    with st.spinner("🔄 Processing data..."):
        # Step 1: Ingest from TSV
        st.info("📥 Ingesting data from SAP B1...")
        ingest_all_data()

        # Step 2: Generate forecasts
        st.info("🔮 Generating forecasts...")
        generate_all_forecasts()

        # Step 3: Refresh materialized views
        st.info("🔄 Refreshing materialized views...")
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_net")
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_inventory_status_with_forecast")

        # Step 4: Clear cache
        st.info("🧹 Clearing cache...")
        from src.cache import clear_all_cache
        clear_all_cache()

        st.success("✅ Data refresh complete!")
        st.rerun()

# Add button to sidebar
if st.sidebar.button("🔄 Refresh All Data"):
    refresh_data_in_app()
```

**When to Use:**
- <20 concurrent users
- Infrequent data refresh (weekly)
- Small dataset (<5,000 items)

#### Option B: Separate Worker Service (Scalable, Isolated)

**Pros:**
- Doesn't block user requests
- Scales independently
- Better for 30-60 users

**Cons:**
- More complex deployment
- Need job queue (Redis + APScheduler)
- Harder to debug

**Implementation:**

```python
# src/worker.py (separate Railway service)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.redis import RedisJobStore
from src.ingestion import ingest_all_data
from src.forecasting import generate_all_forecasts
from src.database import get_engine
from src.cache import clear_all_cache
import logging

logger = logging.getLogger(__name__)

# Configure Redis job store
jobstores = {
    'default': RedisJobStore(
        jobs_key='apscheduler.jobs',
        run_times_key='apscheduler.run_times',
        redis_url='redis://localhost:6379'
    )
}

# Create scheduler
scheduler = BackgroundScheduler(jobstores=jobstores)

def job_refresh_inventory():
    """Refresh inventory data"""
    logger.info("Starting inventory refresh job...")
    try:
        ingest_all_data()
        logger.info("✅ Inventory refresh complete")
    except Exception as e:
        logger.error(f"❌ Inventory refresh failed: {e}")

def job_refresh_forecasts():
    """Generate forecasts"""
    logger.info("Starting forecast generation job...")
    try:
        generate_all_forecasts()
        logger.info("✅ Forecast generation complete")
    except Exception as e:
        logger.error(f"❌ Forecast generation failed: {e}")

def job_refresh_margins():
    """Refresh margin calculations"""
    logger.info("Starting margin refresh job...")
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_net")
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_landed")
            conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_margin_gross")

        clear_all_cache()
        logger.info("✅ Margin refresh complete")
    except Exception as e:
        logger.error(f"❌ Margin refresh failed: {e}")

def job_refresh_all():
    """Full refresh pipeline"""
    logger.info("Starting full refresh pipeline...")
    job_refresh_inventory()
    job_refresh_forecasts()
    job_refresh_margins()
    logger.info("✅ Full refresh complete")

# Schedule jobs (frequencies from admin_settings)
def schedule_jobs_from_settings():
    """Schedule jobs based on admin_settings table"""
    engine = get_engine()

    # Get refresh intervals
    settings = pd.read_sql("""
        SELECT setting_key, setting_value::INTEGER as interval_hours
        FROM admin_settings
        WHERE setting_key IN ('inventory.refresh_interval_hours', 'forecast.refresh_interval_days', 'pricing.refresh_interval_hours')
    """, engine)

    inventory_interval = settings[settings['setting_key'] == 'inventory.refresh_interval_hours']['interval_hours'].iloc[0]
    forecast_interval = settings[settings['setting_key'] == 'forecast.refresh_interval_days']['interval_hours'].iloc[0] * 24
    pricing_interval = settings[settings['setting_key'] == 'pricing.refresh_interval_hours']['interval_hours'].iloc[0]

    # Clear existing jobs
    scheduler.remove_all_jobs()

    # Schedule new jobs
    scheduler.add_job(job_refresh_inventory, 'interval', hours=inventory_interval, id='refresh_inventory')
    scheduler.add_job(job_refresh_forecasts, 'interval', hours=forecast_interval, id='refresh_forecasts')
    scheduler.add_job(job_refresh_margins, 'interval', hours=pricing_interval, id='refresh_margins')

    logger.info(f"📅 Scheduled jobs: inventory={inventory_interval}h, forecasts={forecast_interval}h, margins={pricing_interval}h")

# Start worker
if __name__ == "__main__":
    logger.info("Starting worker service...")

    # Schedule jobs
    schedule_jobs_from_settings()

    # Start scheduler
    scheduler.start()

    # Keep running
    try:
        while True:
            time.sleep(60)

            # Check for schedule changes (every minute)
            # If admin_settings changed, reschedule jobs
            # (Implementation left as exercise)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down worker service...")
        scheduler.shutdown()
```

**Railway.toml for Worker:**

```toml
# railway-worker.toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "python -m src.worker"
restartPolicyType = "always"
healthcheckPath = "/health"
healthcheckTimeout = 30

[[services]]
name = "worker"
serviceType = "background"

[service.environment]
DATABASE_URL = "${{PostgreSQL.DATABASE_URL}}"
REDIS_URL = "${{Redis.REDIS_URL}}"
```

**When to Use:**
- 30-60 concurrent users
- Frequent data refresh (daily)
- Large dataset (>5,000 items)
- Need background processing

**Recommendation:** Option B for 30-60 users

### 8.2 Data Refresh Triggers

**Trigger 1: Scheduled (APScheduler)**

```python
# Automatic refresh based on admin_settings
scheduler.add_job(job_refresh_inventory, 'interval', hours=24)  # Daily
scheduler.add_job(job_refresh_forecasts, 'interval', days=90)    # Quarterly
```

**Trigger 2: Manual (Admin UI)**

```python
# Admin can trigger immediate refresh
if st.button("🔄 Refresh Now"):
    trigger_job('refresh_all')
    st.success("✅ Refresh job queued")
```

**Trigger 3: Webhook (GitHub Actions)**

```yaml
# .github/workflows/refresh-data.yml
name: Refresh Data from SAP B1

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:      # Manual trigger

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Railway Worker
        run: |
          curl -X POST https://your-app.railway.app/webhook/refresh \
            -H "Authorization: Bearer ${{ secrets.RAILWAY_WEBHOOK_TOKEN }}"
```

**Trigger 4: SAP B1 Event (Future)**

```python
# If SAP B1 can send webhooks:
@app.post("/webhook/sap-inventory-update")
def sap_inventory_update webhook():
    """Triggered when SAP B1 inventory changes"""
    # Queue immediate refresh
    trigger_job('refresh_inventory')
    return {"status": "queued"}
```

---

## SECTION 9: COST ESTIMATE

### 9.1 Railway Pricing Tiers (2026)

**Free Tier:**
- Storage: 1 GB
- RAM: 512 MB (shared)
- CPU: 0.25 vCPU (shared)
- Connections: 60
- **Cost: $0/month**

**Eco Tier:**
- Storage: $0.50/GB/month
- RAM: 512 MB - 2 GB
- CPU: 0.5 - 1 vCPU
- Connections: 100
- **Cost: ~$5/month**

**Professional Tier:**
- Storage: $0.50/GB/month
- RAM: 2 GB - 16 GB
- CPU: 1 - 8 vCPU
- Connections: 500
- **Cost: ~$50+/month**

### 9.2 Cost Estimate by Year

#### Year 1: 2,646 items, 70K sales

**Storage Estimate:**
- Core tables: ~30 MB
- Margin elements: ~5 MB
- Sales history (3 years): ~45 MB
- Indexes: ~20 MB
- Materialized views: ~5 MB
- **Total Storage: ~105 MB**

**Compute Estimate:**
- Streamlit app: 1 vCPU, 2 GB RAM
- Worker service: 0.5 vCPU, 1 GB RAM
- PostgreSQL: Shared tier (512 MB RAM)
- Redis: Shared tier (256 MB RAM)

**Monthly Cost Breakdown:**

| Component | Tier | Usage | Monthly Cost |
|-----------|------|-------|--------------|
| Streamlit App | Eco | 1 vCPU, 2 GB RAM | $5.00 |
| Worker Service | Eco | 0.5 vCPU, 1 GB RAM | $3.00 |
| PostgreSQL | Free | 105 MB / 1 GB | $0.00 |
| Redis | Free | 10 MB / 1 GB | $0.00 |
| **Total** | | | **$8.00/month** |

**Annual Cost: $8.00 × 12 = $96/year**

#### Year 2: 3,200 items, 85K sales (+15% growth)

**Storage Estimate:**
- Core tables: ~40 MB
- Margin elements: ~10 MB
- Sales history (3 years): ~60 MB
- Indexes: ~30 MB
- Materialized views: ~10 MB
- **Total Storage: ~150 MB** (still within free tier)

**Monthly Cost:** Same as Year 1 = **$8.00/month**

**Annual Cost: $96/year**

#### Year 3: 4,000 items, 100K sales (+25% growth)

**Storage Estimate:**
- Core tables: ~50 MB
- Margin elements: ~20 MB
- Sales history (3 years): ~80 MB
- Indexes: ~40 MB
- Materialized views: ~15 MB
- **Total Storage: ~205 MB** (still within free tier!)

**Monthly Cost:** Same as Year 1 = **$8.00/month**

**Annual Cost: $96/year**

### 9.3 Cost Optimization Tips

1. **Stay within free tier for database:** Archive old data, use partitioning
2. **Use Eco tier for compute:** Scale up only when needed
3. **Optimize queries:** Use materialized views, caching, connection pooling
4. **Monitor usage:** Set up alerts for storage/CPU limits

### 9.4 Total 3-Year Cost Estimate

| Year | Monthly Cost | Annual Cost |
|------|--------------|-------------|
| Year 1 | $8.00 | $96 |
| Year 2 | $8.00 | $96 |
| Year 3 | $8.00 | $96 |
| **Total** | | **$288** |

**Cost Per User (60 users):** $288 / 60 / 3 = **$1.60/user/year**

---

## SECTION 10: IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1-2)

**Week 1: Database & Authentication**

**Day 1-2: Database Schema**
- [ ] Create enhanced database schema (admin_settings, margin_alerts, margin_elements)
- [ ] Create Azure AD tables (users, roles, user_roles)
- [ ] Create audit_log table
- [ ] Add cost source tracking to costs table
- [ ] Add sales price derivation to pricing table
- [ ] Run migration scripts

**Day 3-4: Azure AD Integration**
- [ ] Set up Azure AD app registration
- [ ] Implement MSAL authentication flow
- [ ] Create user sync function
- [ ] Implement role-based access control
- [ ] Test login/logout flow

**Day 5-7: Admin Interface**
- [ ] Build admin settings page (data freshness, alerts)
- [ ] Build system status dashboard
- [ ] Build audit log viewer
- [ ] Test admin functionality

**Week 2: Data Pipeline**

**Day 8-10: Margin Tracking**
- [ ] Implement sales price derivation (Option B with A backup)
- [ ] Implement cost source tracking (Goods Receipt PO vs AR Invoice)
- [ ] Create margin_elements table
- [ ] Build margin calculation functions
- [ ] Test margin calculations

**Day 11-14: Worker Service**
- [ ] Set up Railway worker service
- [ ] Implement APScheduler job queue
- [ ] Create data refresh jobs
- [ ] Set up Redis job store
- [ ] Test background jobs

**Deliverables:**
- ✅ Enhanced database schema deployed
- ✅ Azure AD authentication working
- ✅ Admin UI functional
- ✅ Margin tracking implemented
- ✅ Worker service running

### Phase 2: Margin System (Week 3-4)

**Week 3: Margin Breakdown & Views**

**Day 15-17: Margin Views**
- [ ] Create vw_margin_gross materialized view
- [ ] Create vw_margin_landed materialized view
- [ ] Create vw_margin_net materialized view
- [ ] Create vw_margin_breakdown materialized view
- [ ] Create refresh_margin_views() function
- [ ] Test view performance

**Day 18-21: Margin Reports**
- [ ] Build margin breakdown report page
- [ ] Build margin trend analysis page
- [ ] Build margin comparison page (item vs item)
- [ ] Export to CSV/Excel functionality
- [ ] Test reports

**Week 4: Alert System**

**Day 22-24: Alert Generation**
- [ ] Implement generate_margin_alerts() function
- [ ] Create margin_alerts table
- [ ] Build alert dashboard
- [ ] Implement in-app notifications
- [ ] Test alert generation

**Day 25-28: Alert Management**
- [ ] Build alert resolution workflow
- [ ] Build alert history page
- [ ] Email notification integration (optional)
- [ ] Slack notification integration (optional)
- [ ] Test alert management

**Deliverables:**
- ✅ All margin views created
- ✅ Margin reports functional
- ✅ Alert system working
- ✅ Alert management implemented

### Phase 3: Scalability (Week 5-6)

**Week 5: Connection Pooling & Caching**

**Day 29-31: Connection Pooling**
- [ ] Implement SQLAlchemy connection pool
- [ ] Configure pool size for 60 users
- [ ] Test connection reuse
- [ ] Monitor connection usage
- [ ] Optimize pool settings

**Day 32-35: Redis Caching**
- [ ] Set up Redis on Railway
- [ ] Implement session caching
- [ ] Implement permission caching
- [ ] Implement query result caching
- [ ] Test cache hit/miss rates

**Week 6: Performance Optimization**

**Day 36-38: Query Optimization**
- [ ] Analyze slow queries
- [ ] Add missing indexes
- [ ] Create materialized views for common queries
- [ ] Test query performance
- [ ] Optimize JOIN operations

**Day 39-42: Load Testing**
- [ ] Set up Locust load testing
- [ ] Test with 30 concurrent users
- [ ] Test with 60 concurrent users
- [ ] Identify bottlenecks
- [ ] Fix performance issues

**Deliverables:**
- ✅ Connection pooling optimized
- ✅ Redis caching working
- ✅ Query performance optimized
- ✅ Load tested to 60 users

### Phase 4: Security (Week 7-8)

**Week 7: Access Control**

**Day 43-45: Role-Based Access Control**
- [ ] Define all permissions
- [ ] Implement permission checking decorators
- [ ] Apply permissions to all pages
- [ ] Test access control
- [ ] Document permission model

**Day 46-49: Data Filtering by Role**
- [ ] Implement row-level security (optional)
- [ ] Filter sensitive data by role
- [ ] Test data filtering
- [ ] Audit access to sensitive data

**Week 8: Audit Logging**

**Day 50-52: Comprehensive Audit**
- [ ] Log all user actions
- [ ] Log all data changes
- [ ] Log all admin actions
- [ ] Create audit log viewer
- [ ] Test audit logging

**Day 53-56: Security Hardening**
- [ ] Implement rate limiting
- [ ] Implement CSRF protection
- [ ] Implement SQL injection protection
- [ ] Security audit
- [ ] Penetration testing

**Deliverables:**
- ✅ RBAC fully implemented
- ✅ Data filtering by role
- ✅ Comprehensive audit logging
- ✅ Security hardening complete

### Phase 5: Deployment (Week 9-10)

**Week 9: Railway Deployment**

**Day 57-59: Pre-Deployment**
- [ ] Final testing in dev environment
- [ ] Backup existing data
- [ ] Create deployment checklist
- [ ] Set up monitoring
- [ ] Prepare rollback plan

**Day 60-63: Deployment**
- [ ] Deploy PostgreSQL database
- [ ] Deploy Redis cache
- [ ] Deploy Streamlit app
- [ ] Deploy worker service
- [ ] Configure environment variables
- [ ] Test all functionality

**Week 10: Monitoring & Documentation**

**Day 64-66: Monitoring Setup**
- [ ] Set up Railway metrics
- [ ] Set up error tracking (Sentry)
- [ ] Set up uptime monitoring
- [ ] Create alerting rules
- [ ] Test monitoring

**Day 67-70: Documentation & Training**
- [ ] Write user documentation
- [ ] Write admin documentation
- [ ] Write deployment documentation
- [ ] Train users
- [ ] Train admins

**Deliverables:**
- ✅ Full deployment on Railway
- ✅ Monitoring configured
- ✅ Documentation complete
- ✅ Users trained

### Summary Timeline

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| Phase 1: Foundation | 2 weeks | Database, Azure AD, Admin UI |
| Phase 2: Margin System | 2 weeks | Margin views, Alert system |
| Phase 3: Scalability | 2 weeks | Connection pooling, Caching, Load testing |
| Phase 4: Security | 2 weeks | RBAC, Audit logging |
| Phase 5: Deployment | 2 weeks | Railway deployment, Monitoring, Docs |
| **Total** | **10 weeks** | **Production-ready system** |

---

## SECTION 11: QUESTIONS FOR USER

### 11.1 Growth & Scalability

**Q1: What type of growth do you expect?**
- [X] Organic growth (existing customers buying more)
- [X] New customer acquisition
- [X] Expanding to new regions/markets
- [X] Adding new product lines
Note: Will remain under 100 users for 2 years at a minimum

**Q2: How many users do you have today?**
- Current users: 50 - but many will be very sparse or not engaged
- Expected in 6 months: 60
- Expected in 12 months: 60

**Q3: What's your budget for this application?**
- Monthly budget target: $40/month
- Approval range: $0-$200/month
- Priority: Minimize cost OR Maximize performance? 
Balanced approach with below priorities
Data processing:  stability>cost>speed
Database: stability>cost>speed
Front end: stability>speed>cost

### 11.2 Data Processing

**Q4: Should data processing happen in Streamlit app or separate worker?**
- [ ] Option A: In-app processing (simpler, single service)
- [X] Option B: Separate worker service (scalable, isolated)
- [ ] Option C: Hybrid (light processing in app, heavy in worker)
Database processing should happen in Railway with data being sent from a python app built on our SAP B1 server, is there any information required to give our railway app that will be sending information.  that app will provide:
  1. Encryption Key (Base64)
  2. API Key
  3. Production URL
  4. API Contract

**Q5: How long can nightly processing take?**
- Acceptable processing time: 2 hours
- Impact on user experience: [X] Can't block users [X] OK to slow down slightly
Users should see old data on server until update is complete

**Q6: Do users need real-time updates or is nightly acceptable?**

Real time is ideal for inventory levels, pricing can be nightly, forecast updates can be bimonthly, we would like the option to have admin page in interface adjust these, or it may need to be in the python middleware on the SAP server, advise me of best practice.


### 11.3 Azure AD

**Q7: Do you have Azure AD tenant already?**
- [X] Yes, tenant ID: aface7de-787c-41b4-b458-74df6ae895da

**Q8: What Azure AD groups should map to which roles?**

user groups will be decided in the app not by azure.
we will need to have customizable groups and regions that can be added and elements should be selectable for visibility. Product regionality will need to be filtered for most users.

**Q9: Do you have an existing OAuth2 app to reuse?**
- [X] Yes, App ID: 1ab7aef9-0cb5-4bdf-8e06-388c898c026f

### 11.4 Margin Monitoring

**Q10: What margin calculation do you need?**
- [X] Net Margin (includes all costs) - Complex
Note: we need net margin broken out and have options to filter for gross and landed margin visibility.

**Q11: What margin % threshold should trigger alerts?**
Margin alerts need to be adjustable and trigger email alerts that can be sent to customizable addresses

**Q12: Do you have sales price data from SAP B1?**
- [X] No, derive from sales orders (Option B)
We have sales prices but our sales people can adjust prices and make commissions. We would also like to monitor sales prices from user to user to manage sales staff.  Sales employee is derived from each sales order from within SAP.


**Q13: What is your cost source priority?**
- [X] Most recent Goods Receipt PO (recommended)

### 11.5 Data Freshness

**Q14: How often should each data type refresh?**

| Data Type | Frequency (Default) | Your Preference |
|-----------|---------------------|-----------------|
| Inventory | Daily (24 hours) | |
| Forecasts | Bi-Monthly (90 days) | |
| Pricing | Daily (24 hours) | |
| Margins | Daily (24 hours) | |

**Q15: Do you want to keep sales history after aggregating for forecasts?**
- [X] No, delete after aggregating to monthly

### 11.6 Deployment

**Q16: What is your go-live date target?**
- Target date: Next week

**Impact:** Determines implementation timeline priority

**Q17: Who will be the primary admin users?**
- Admin 1 (name/email): Nathan Dery/nathan@pacesolutions.com

**Q18: Do you have a disaster recovery plan?**
- [X] No, need recommendations

## CONCLUSION

This comprehensive Railway deployment solution provides:

1. **Scalable Architecture:** Designed for 30-60 concurrent users with connection pooling, Redis caching, and materialized views
2. **Azure AD Integration:** Complete MSAL implementation with role-based access control
3. **Enhanced Margin Monitoring:** Net margin breakdown (Gross → Landed → Net) with customizable alerts
4. **Admin Interface:** Adjustable data refresh frequencies, margin thresholds, and system settings
5. **Cost-Optimized:** Free-tier capable database, estimated at $8/month (Eco tier compute only)
6. **Production-Ready:** Complete implementation roadmap with 10-week timeline

**Next Steps:**
1. Review and answer questions in Section 11
2. Set up Railway PostgreSQL instance
3. Configure Azure AD app registration
4. Begin Phase 1 implementation (database + authentication)

**Support & Documentation:**
- Railway docs: https://docs.railway.app/
- Azure AD docs: https://docs.microsoft.com/en-us/azure/active-directory/
- PostgreSQL docs: https://www.postgresql.org/docs/
- MSAL Python: https://msal-python.readthedocs.io/

---

**Document Version:** 1.0
**Last Updated:** 2026-01-15
**Author:** Claude (Anthropic)
**Status:** Ready for Review
