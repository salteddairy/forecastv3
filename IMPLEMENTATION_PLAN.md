# Incremental Implementation Plan
## SAP B1 Inventory & Margin Analytics - Railway Deployment

**Version:** 1.0
**Date:** 2026-01-15
**Status:** Ready to Execute
**Timeline:** 12 weeks (with early delivery milestones)

---

## Executive Summary

### Your Key Requirements Addressed:

✅ **Scalability:** 50-60 concurrent users (organic + acquisition growth)
✅ **Budget:** $40/month target (current estimate $8-12/month)
✅ **Data Pipeline:** Python app on SAP server → Railway (encrypted API)
✅ **Priority:** Stability > Cost > Speed (data & DB)
✅ **Authentication:** Azure AD (tenant & app ID provided)
✅ **Authorization:** App-based groups/regions (NOT Azure AD groups)
✅ **Margins:** Net margin breakdown with Gross/Landed/Net visibility
✅ **Sales Tracking:** Sales employee tracking (future commission ready)
✅ **Data Freshness:** Real-time inventory ideal, nightly pricing OK
✅ **Processing:** 2-hour acceptable window, non-blocking updates
✅ **Admin:** Streamlit-based (adjustable frequencies & thresholds)

### Future-Ready Architecture:
🔮 **Commission Tracking:** Schema & infrastructure designed for future implementation
🔮 **Sales Performance:** Sales employee margin analysis ready
🔮 **Price Variance:** Track user-to-user price differences

---

## IMPLEMENTATION PHILOSOPHY

### Incremental Delivery Strategy

We'll deliver **working software every 2 weeks**, not a big-bang release. Each increment builds on the previous one, ensuring you have a usable system at all times.

### Three Parallel Tracks

| Track | Purpose | Frequency | Status |
|-------|---------|-----------|--------|
| **Track A: Core Infrastructure** | Database, API, Authentication | Weeks 1-4 | 🔴 Critical Path |
| **Track B: Data & Margins** | SAP integration, margin system | Weeks 2-8 | 🟡 High Priority |
| **Track C: Features & UX** | Admin UI, reports, alerts | Weeks 3-12 | 🟢 Enhancements |

### Project Structure

```
D:\code\forecastv3\
├── app.py                          # Main Streamlit app (existing)
├── requirements.txt                 # Python dependencies
├── IMPLEMENTATION_PLAN.md          # This file
├── RAILWAY_DEPLOYMENT_SOLUTION.md  # Technical specifications
│
├── api/                            # NEW: FastAPI backend for SAP integration
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── inventory.py            # Inventory data endpoints
│   │   ├── sales.py                # Sales data endpoints
│   │   ├── pricing.py              # Pricing data endpoints
│   │   └── forecasts.py            # Forecast data endpoints
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                 # API key authentication
│   │   └── encryption.py           # Encryption/decryption
│   └── schemas/
│       ├── __init__.py
│       └── models.py               # Pydantic models
│
├── database/                       # NEW: Database management
│   ├── __init__.py
│   ├── migrations/                 # Schema migration scripts
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_margin_system.sql
│   │   ├── 003_azure_ad_users.sql
│   │   ├── 004_commission_tracking.sql  # FUTURE: Pre-designed
│   │   └── 005_audit_log.sql
│   ├── seeds/                      # Seed data scripts
│   │   ├── initial_admin.sql
│   │   └── initial_roles.sql
│   └── functions/                  # Stored procedures
│       ├── margin_calculations.sql
│       └── alert_triggers.sql
│
├── src/
│   ├── azure_auth.py               # NEW: Azure AD integration
│   ├── database.py                 # NEW: Database connection & pooling
│   ├── cache.py                    # NEW: Redis caching layer
│   ├── rbac.py                     # NEW: Role-based access control
│   ├── data_pipeline.py            # EXISTING: Will be refactored
│   ├── forecasting.py              # EXISTING: Will be refactored
│   ├── optimization.py             # EXISTING: Keep as-is
│   └── admin/                      # NEW: Admin interface
│       ├── __init__.py
│       ├── settings.py             # Settings management
│       ├── users.py                # User & role management
│       └── alerts.py               # Alert configuration
│
├── sap_integration/                # NEW: SAP B1 server-side scripts
│   ├── __init__.py
│   ├── exporter.py                 # TSV export from SAP B1
│   ├── uploader.py                 # Upload to Railway API
│   ├── scheduler.py                # Scheduled job runner
│   └── config.yaml                 # SAP connection settings
│
├── tests/                          # NEW: Test suite
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_auth.py
│   └── test_margins.py
│
├── scripts/                        # NEW: Utility scripts
│   ├── setup_railway.sh            # Initial Railway setup
│   ├── migrate_data.py             # Data migration script
│   └── backup_database.py          # Backup automation
│
└── config/                         # NEW: Configuration files
    ├── railway.toml                # Railway app config
    ├── railway-worker.toml         # Railway worker config
    ├── docker-compose.yml          # Local development
    └── .env.example                # Environment variables template
```

---

## DETAILED IMPLEMENTATION ROADMAP

## TRACK A: CORE INFRASTRUCTURE (Critical Path)

### Week 1-2: Database Foundation & API Backend

**Goal:** Railway PostgreSQL + FastAPI accepting SAP data

**Day 1-3: Database Setup**
- [ ] Create Railway PostgreSQL project
- [ ] Run initial schema migration (`001_initial_schema.sql`)
- [ ] Set up connection pooling configuration
- [ ] Test database connectivity from local machine
- [ ] Create `database/` module with connection management

**Day 4-5: FastAPI Backend**
- [ ] Create FastAPI project structure
- [ ] Implement API key authentication middleware
- [ ] Implement encryption/decryption utilities
- [ ] Create base API routes (health check)
- [ ] Set up CORS for SAP server access

**Day 6-7: API Endpoints (MVP)**
- [ ] POST /api/v1/inventory (receive inventory data)
- [ ] POST /api/v1/sales (receive sales data)
- [ ] POST /api/v1/pricing (receive pricing data)
- [ ] Implement data validation (Pydantic models)
- [ ] Add error handling and logging

**Day 8-10: SAP Integration Prep**
- [ ] Create `sap_integration/` directory structure
- [ ] Write `exporter.py` (extract data from SAP B1)
- [ ] Write `uploader.py` (send data to Railway API)
- [ ] Create encryption key generation
- [ ] Test API with sample data

**Deliverables:**
- ✅ Railway PostgreSQL running with schema
- ✅ FastAPI accepting SAP data via encrypted API
- ✅ SAP server scripts ready for deployment
- ✅ API documentation (OpenAPI spec)

**Validation:**
- Can POST sample inventory data to API?
- Is data encrypted in transit?
- Does database store data correctly?
- Can query data from database?

---

### Week 3-4: Azure AD + Basic RBAC

**Goal:** Users can log in with Azure AD, see basic data

**Day 11-13: Azure AD Integration**
- [ ] Register OAuth2 app in Azure AD (use your existing app)
- [ ] Implement MSAL authentication in Streamlit
- [ ] Create `azure_users` table
- [ ] Sync Azure AD users to database on login
- [ ] Implement session management with Redis

**Day 14-15: Basic RBAC**
- [ ] Create `roles` and `user_roles` tables
- [ ] Implement app-based role assignment (NOT Azure AD groups)
- [ ] Create default roles: Admin, Manager, Analyst, Viewer
- [ ] Add first user (Nathan) as Admin
- [ ] Test login and role assignment

**Day 16-17: Data Access Control**
- [ ] Implement row-level security by role
- [ ] Add region filtering (product locality)
- [ ] Test data filtering by role
- [ ] Create role permission checking functions

**Day 18-19: Basic UI Updates**
- [ ] Update app.py with login page
- [ ] Add authentication state management
- [ ] Redirect unauthorized users
- [ ] Display user role in sidebar
- [ ] Test logout functionality

**Deliverables:**
- ✅ Azure AD login working
- ✅ App-based role management functional
- ✅ Data filtering by role/region working
- ✅ Session management with Redis

**Validation:**
- Can Nathan log in with Azure AD?
- Does role filter work correctly?
- Can assign roles in app (not Azure AD)?
- Do sessions persist with Redis?

---

## TRACK B: DATA & MARGINS (High Priority)

### Week 5-6: Margin System Foundation

**Goal:** Net margin breakdown with Gross/Landed/Net views

**Day 29-31: Margin Schema**
- [ ] Run migration `002_margin_system.sql`
- [ ] Create `margin_elements` table
- [ ] Create `margin_snapshots` table
- [ ] Add cost tracking (Goods Receipt PO priority)
- [ ] Add sales price derivation logic

**Day 32-34: Margin Views**
- [ ] Create `vw_margin_breakdown` (all elements)
- [ ] Create `vw_margin_gross` (simple view)
- [ ] Create `vw_margin_landed` (intermediate view)
- [ ] Create `vw_margin_net` (complete view)
- [ ] Test view performance

**Day 35-36: Margin Calculations**
- [ ] Implement sales price derivation from sales orders
- [ ] Implement cost tracking (Goods Receipt PO priority)
- [ ] Calculate freight, duty, carrying, order costs
- [ ] Create margin snapshot function
- [ ] Test margin calculations

**Deliverables:**
- ✅ Complete margin schema in database
- ✅ Four margin views (breakdown, gross, landed, net)
- ✅ Sales price derivation working
- ✅ Cost tracking from Goods Receipt PO

**Validation:**
- Do margin calculations match expectations?
- Can switch between Gross/Landed/Net views?
- Is sales price derived correctly?
- Does cost source priority work?

---

### Week 7-8: Sales Employee Tracking (Future-Ready)

**Goal:** Track sales employee for future commission system

**Day 43-45: Sales Employee Schema**
- [ ] Add `sales_employee` column to relevant tables
- [ ] Create `sales_employees` master table
- [ ] Add `employee_commission_rate` (future-use)
- [ ] Track sales by employee
- [ ] Create employee performance views

**Day 46-47: Price Variance Tracking**
- [ ] Track sales prices by employee
- [ ] Create price variance reports
- [ ] Alert on unusual price deviations
- [ ] Monitor employee discount patterns
- [ ] Create approval workflow (future)

**Day 48-49: Sales Performance Views**
- [ ] Employee sales volume tracking
- [ ] Employee margin contribution
- [ ] Product sales by employee
- [ ] Regional performance by employee
- [ ] Historical performance trends

**Deliverables:**
- ✅ Sales employee tracking infrastructure
- ✅ Price variance monitoring
- ✅ Sales performance views
- ✅ Ready for future commission implementation

**Validation:**
- Can track which employee sold each item?
- Can see price variance by employee?
- Are sales performance metrics accurate?
- Is commission calculation infrastructure ready?

---

## TRACK C: FEATURES & UX (Enhancements)

### Week 9-10: Admin Interface

**Goal:** Streamlit-based admin with adjustable settings

**Day 57-59: Admin Settings Page**
- [ ] Create `src/admin/` module
- [ ] Implement settings management (`settings.py`)
- [ ] Create admin UI in Streamlit
- [ ] Settings tabs:
  - Data Refresh Frequencies
  - Margin Alert Thresholds
  - System Status
  - User Management
- [ ] Save settings to database

**Day 60-62: User Management**
- [ ] User list view (all Azure AD users)
- [ ] Role assignment interface
- [ ] Region/group assignment
- [ ] Permission visibility controls
- [ ] User activity monitoring

**Day 63-64: System Status Dashboard**
- [ ] Last update timestamps (all data types)
- - [ ] Data quality metrics
- [ ] System health indicators
- [ ] User activity summary
- [ ] Storage/usage metrics

**Deliverables:**
- ✅ Complete admin interface in Streamlit
- ✅ Adjustable refresh frequencies
- ✅ Configurable margin thresholds
- ✅ User & role management UI

**Validation:**
- Can adjust inventory refresh frequency?
- Can change margin alert thresholds?
- Can assign roles to users?
- Can assign regions to users?
- Does system status display correctly?

---

### Week 11-12: Margin Alerts & Email Notifications

**Goal:** Automated margin monitoring with email alerts

**Day 71-73: Margin Alert System**
- [ ] Create `margin_alerts` table
- [ ] Implement margin threshold checking function
- [ ] Create alert triggers in database
- [ ] Add alert history tracking
- [ ] Test alert generation

**Day 74-76: Email Notifications**
- [ ] Implement email sending (SMTP/Azure SendGrid)
- [ ] Create email templates for alerts
- [ ] Add customizable alert recipients
- [ ] Implement alert digest (daily/weekly)
- [ ] Test email delivery

**Day 77-78: Alert Management UI**
- [ ] Alert history view
- [ ] Alert acknowledgment workflow
- [ ] Alert configuration by type
- [ ] Recipient management interface
- [ ] Alert testing

**Deliverables:**
- ✅ Automated margin alert system
- ✅ Email notifications working
- ✅ Alert management UI
- ✅ Customizable recipients

**Validation:**
- Do alerts trigger when margins drop below threshold?
- Are emails sent correctly?
- Can customize alert recipients?
- Does alert history work?
- Can acknowledge alerts?

---

## PROJECT STRUCTURE FOR FUTURE COMMISSION TRACKING

### Schema Pre-Design

```sql
-- FUTURE: Commission Tracking (Pre-Designed, NOT Implementing Now)
-- This migration will be created in Week 12 for future use

-- Table: sales_employees
CREATE TABLE sales_employees (
    employee_id SERIAL PRIMARY KEY,
    employee_code VARCHAR(20) UNIQUE NOT NULL,  -- SAP sales employee code
    employee_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    azure_user_id VARCHAR(100) UNIQUE,  -- Link to Azure AD user
    commission_rate NUMERIC(5,4),        -- Commission % (e.g., 0.05 = 5%)
    base_salary NUMERIC(12,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: sales_commission_rules
CREATE TABLE sales_commission_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,  -- 'margin_based', 'revenue_based', 'tiered'
    commission_rate NUMERIC(5,4),
    margin_threshold NUMERIC(5,2),     -- Minimum margin for commission
    effective_date DATE NOT NULL,
    expiry_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: sales_commission_transactions
CREATE TABLE sales_commission_transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    sale_id BIGINT REFERENCES sales_orders(sale_id),
    employee_id INTEGER REFERENCES sales_employees(employee_id),
    sale_date DATE NOT NULL,
    item_code VARCHAR(50) REFERENCES items(item_code),
    quantity NUMERIC(12,3) NOT NULL,
    unit_price NUMERIC(12,4) NOT NULL,
    unit_cost NUMERIC(12,4) NOT NULL,
    margin_amt NUMERIC(12,2),
    margin_pct NUMERIC(5,2),
    commission_rate NUMERIC(5,4),
    commission_amt NUMERIC(12,2),
    commission_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'paid'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ
);

-- View: Employee Sales Performance
CREATE VIEW vw_employee_sales_performance AS
SELECT
    se.employee_code,
    se.employee_name,
    COUNT(so.sale_id) as total_sales,
    SUM(so.quantity * so.unit_price) as total_revenue,
    SUM(so.quantity * so.unit_cost) as total_cost,
    SUM(so.quantity * (so.unit_price - so.unit_cost)) as total_margin,
    AVG((so.unit_price - so.unit_cost) / so.unit_price * 100) as avg_margin_pct,
    SUM(sct.commission_amt) as total_commission,
    COUNT(DISTINCT so.item_code) as unique_products_sold
FROM sales_employees se
LEFT JOIN sales_orders so ON se.employee_code = so.sales_employee_code
LEFT JOIN sales_commission_transactions sct ON sct.employee_id = se.employee_id
WHERE se.is_active = true
GROUP BY se.employee_id, se.employee_code, se.employee_name;
```

### Infrastructure Ready

**API Endpoints (Pre-Designed, Future):**
- `GET /api/v1/commissions/employee/{id}` - Employee commission summary
- `POST /api/v1/commissions/calculate` - Calculate commissions
- `GET /api/v1/commissions/rules` - Commission rules
- `POST /api/v1/commissions/approve` - Approve commissions

**UI Components (Pre-Designed, Future):**
- Commission tracking page (tab in main app)
- Employee performance dashboard
- Commission approval workflow
- Commission reports by employee/period

---

## WEEKLY DELIVERABLES CHECKLIST

### Week 1-2 (Database & API)
- [ ] Railway PostgreSQL running
- [ ] FastAPI accepting SAP data
- [ ] API documentation complete
- [ ] SAP scripts tested
- [ ] Data validation working

### Week 3-4 (Azure AD & RBAC)
- [ ] Azure AD login working
- [ ] Nathan added as Admin
- [ ] Role filtering working
- [ ] Region filtering working
- [ ] Session management with Redis

### Week 5-6 (Margin System)
- [ ] Margin schema complete
- [ ] Sales price derivation working
- [ ] Cost tracking complete
- [ ] Margin views created
- [ ] Margin calculations accurate

### Week 7-8 (Sales Employee Tracking)
- [ ] Employee tracking infrastructure
- [ ] Price variance monitoring
- [ ] Sales performance views
- [ ] Commission schema designed (future)
- [ ] Data ready for future commissions

### Week 9-10 (Admin Interface)
- [ ] Admin settings page working
- [ ] Frequency adjustment working
- [ ] Threshold configuration working
- [ ] User management UI complete
- [ ] System status dashboard

### Week 11-12 (Alerts & Email)
- [ ] Margin alert system working
- [ ] Email notifications sent
- [ ] Alert management UI
- [ ] Customizable recipients
- [ ] Alert history tracking

---

## MILESTONES & DECISION POINTS

### Milestone 1: Data Pipeline Working (Week 2)
**Decision Point:** Is SAP → Railway API working?
- **Yes:** Proceed to Azure AD integration
- **No:** Debug API, test connectivity, adjust encryption

### Milestone 2: Users Can Log In (Week 4)
**Decision Point:** Is Azure AD authentication working?
- **Yes:** Proceed to margin system
- **No:** Debug MSAL, check Azure AD config, test permissions

### Milestone 3: Margins Calculating (Week 6)
**Decision Point:** Are margin calculations accurate?
- **Yes:** Proceed to sales employee tracking
- **No:** Debug calculations, verify cost sources, test price derivation

### Milestone 4: Admin Functional (Week 10)
**Decision Point:** Is admin interface complete?
- **Yes:** Proceed to alert system
- **No:** Refine UI, add missing settings, test functionality

### Milestone 5: Production Ready (Week 12)
**Decision Point:** Is system ready for production?
- **Yes:** Deploy to Railway, train users, go live
- **No:** Fix critical issues, extend timeline

---

## RISK MITIGATION

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **API Security** | High | Medium | Use encryption keys, rotate quarterly, audit access |
| **Database Performance** | High | Low | Materialized views, connection pooling, query optimization |
| **Azure AD Integration** | Medium | Low | Use existing app, test early, have fallback manual auth |
| **Data Accuracy** | High | Medium | Validate on input, checksum verification, audit logging |
| **Scalability to 60 Users** | Medium | Low | Connection pooling tested, Redis caching, load testing |

### Business Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Budget Overrun** | Medium | Low | Start with free tier, monitor costs weekly, alert at 80% |
| **Timeline Slippage** | Medium | Medium | 2-week increments, working software always, prioritize features |
| **User Adoption** | Medium | Medium | Early user training, documentation, feedback loop |
| **SAP Integration Changes** | Medium | Low | Modular design, API versioning, backward compatibility |

---

## SUCCESS METRICS

### Technical Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| **API Response Time** | < 500ms (p95) | APM monitoring (Railway metrics) |
| **Database Query Time** | < 1s (p95) | Query logging, slow query log |
| **User Login Time** | < 3s | User experience testing |
| **Data Processing Time** | < 2 hours | Job duration logging |
| **System Uptime** | > 99% | Railway monitoring |

### Business Metrics

| Metric | Target | How to Measure |
|--------|--------|---------------|
| **User Satisfaction** | > 4/5 | User feedback surveys |
| **Data Accuracy** | > 99% | Audit sampling |
| **Margin Alert Accuracy** | > 95% | False positive tracking |
| **Cost per User** | < $1/user/month | Railway billing analysis |

---

## NEXT STEPS (Starting This Week)

### Immediate Actions (This Week)

1. **Set Up Railway Projects**
   - Create Railway account (if not exists)
   - Create PostgreSQL service
   - Create Redis service
   - Note connection strings

2. **Create Project Structure**
   - Create `api/` directory
   - Create `database/` directory
   - Create `sap_integration/` directory
   - Create `config/` directory

3. **Run Initial Database Migration**
   - Review `001_initial_schema.sql`
   - Execute on Railway PostgreSQL
   - Verify tables created
   - Test connectivity

4. **Set Up FastAPI Backend**
   - Create FastAPI project
   - Implement API key auth
   - Create base routes
   - Test locally

5. **Prepare SAP Server Scripts**
   - Test TSV export from SAP B1
   - Create data validation scripts
   - Test API endpoint locally
   - Plan deployment to SAP server

### Decision Needed This Week

**Question:** Do you want to start with a **local development environment** first, or go straight to **Railway deployment**?

**Option A: Local Development First**
- Pro: Faster iteration, no cost during development
- Pro: Can test thoroughly before deploying
- Con: Need to migrate to Railway later
- Con: Local environment differs from production

**Option B: Railway Development**
- Pro: Deploy to production environment immediately
- Pro: No migration needed later
- Pro: See real performance/costs early
- Con: Costs money from day 1
- Con: Slower iteration cycle

**My Recommendation:** Start with Railway (Option B) because:
1. Costs are minimal ($8-12/month)
2. You'll see real performance immediately
3. No migration surprises later
4. Can always revert to local if needed

---

## CONCLUSION

This implementation plan delivers:

✅ **Working software every 2 weeks**
✅ **Future-ready architecture** (commission tracking pre-designed)
✅ **Incremental delivery** (no big-bang deployment)
✅ **Risk mitigation** (milestones and decision points)
✅ **Cost control** (monitoring and alerts)
✅ **Quality focus** (validation and testing at each step)

The project structure accommodates **future commission tracking** without requiring re-architecture, and the **three-track approach** ensures critical path items are prioritized while still delivering valuable features early.

**Ready to start Week 1?** Let me know and I'll help you:
1. Set up the Railway projects
2. Create the database schema
3. Build the FastAPI backend
4. Prepare the SAP integration scripts
