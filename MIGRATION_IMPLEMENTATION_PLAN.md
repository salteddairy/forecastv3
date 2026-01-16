# Web App Migration & Implementation Plan
## SAP B1 Forecast Analyzer - Production Architecture

**Version:** 1.0
**Date:** 2026-01-12
**Status:** Planning Phase - Implementation Pending
**Dependencies:** Tool must be 100% tested locally first

---

## Executive Summary

**Goal:** Migrate Streamlit app to modular web architecture using existing infrastructure
- **Frontend:** Vercel (existing)
- **Backend:** Railway (recommended, cheaper than Render)
- **Database:** Supabase (existing) - processed data only
- **Integration:** SAP B1UP for scheduled data extraction

**Cost Target:** $5-15/month (vs $25-50+ on Render)

**Key Principle:** Supabase stores lightweight processed results only, not raw SAP data

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SAP B1 System                             │
│  ┌──────────────┐      ┌────────────────────────────────┐  │
│  │  Sales Data  │      │        B1UP Add-on             │  │
│  │  Inventory   │ ───▶ │  (Scheduled Query Execution)    │  │
│  │  Supply      │      │  - Export queries              │  │
│  └──────────────┘      │  - Upload to Railway API       │  │
│                        │  - Schedule: Daily 2AM          │  │
│                        └────────────┬───────────────────┘  │
└─────────────────────────────────────┼───────────────────────┘
                                         │
                                         │ JSON/TSV via POST
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Railway Backend                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Endpoints (FastAPI)                              │  │
│  │  - POST /api/data/ingest     (Receive B1UP data)      │  │
│  │  - POST /api/forecasts/generate (Run forecasting)     │  │
│  │  - GET  /api/warehouses       (Warehouse config)      │  │
│  │  - GET  /api/reports/shortage (Get results)          │  │
│  └───────────┬──────────────────────────────────────────┘  │
│              │                                              │
│              ▼                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Processing Layer                                     │  │
│  │  - Data validation & cleaning                        │  │
│  │  - Forecasting tournament (existing code)            │  │
│  │  - Optimization analysis                             │  │
│  │  - Result aggregation                                │  │
│  └───────────┬──────────────────────────────────────────┘  │
│              │                                              │
│              │ Write processed results                     │
│              ▼                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  File System (Railway Volume)                        │  │
│  │  - Raw TSV files (temporary, 7-day retention)        │  │
│  │  - Forecast cache (parquet, persistent)              │  │
│  │  - Dimension cache (persistent)                      │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────┘
                            │ Read processed data
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Supabase (Minimal Storage)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  warehouse_capacities (10 rows x 10 KB = 0.1 MB)     │  │
│  │  - location, total_skids, dimensions                 │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  forecast_results (3,700 rows x 1 KB = 3.7 MB)      │  │
│  │  - item_code, forecast values, winning_model         │  │
│  │  - Updated: Daily                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  shortage_alerts (500 rows x 500 B = 0.25 MB)       │  │
│  │  - item_code, shortage_qty, urgency                 │  │
│  │  - Updated: Daily                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  tco_analysis (3,700 rows x 1 KB = 3.7 MB)          │  │
│  │  - item_code, recommendation, annual_savings         │  │
│  │  - Updated: Daily                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Total: ~8 MB (well within 500MB free tier)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ GraphQL/REST API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Vercel Frontend                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module: Forecasts (/forecasts)                       │  │
│  │  - Item search & detail view                          │  │
│  │  - Forecast chart visualization                      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module: Shortages (/shortages)                      │  │
│  │  - Shortage report table                             │  │
│  │  - Urgency filtering                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module: Warehouses (/warehouses)                    │  │
│  │  - Capacity management UI                            │  │
│  │  - CRUD operations                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Module: TCO (/tco)                                  │  │
│  │  - Stock vs Special Order analysis                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  [Future Modules]                                    │  │
│  │  - Purchasing (/purchasing)                         │  │
│  │  - Vendors (/vendors)                               │  │
│  │  - Reports (/reports)                               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow: End-to-End

### 1. Data Ingestion (Automated, Daily 2AM)

```
SAP B1 → B1UP Query → Railway API → Temporary File Storage
         (scheduled)     (POST /api/data/ingest)
```

**B1UP Query Configuration:**
```sql
-- Query 1: Sales Orders (Last 12 months)
SELECT
    T0."ItemCode" as "item_code",
    T0."DocDate" as "date",
    T0."Quantity" as "quantity",
    T1."UOM_Code" as "uom"
FROM INV1 T0
INNER JOIN OITM T1 ON T0."ItemCode" = T1."ItemCode"
WHERE T0."DocDate" >= DATEADD(MONTH, -12, GETDATE())

-- Query 2: Inventory Status
SELECT
    T0."ItemCode" as "Item No.",
    T0."OnHand" as "CurrentStock",
    T0."UOM_Code" as "BaseUoM",
    T1."UOM_Entry" as "SalesUoM",
    T1."UOM_Code" as "SalesUoM_Cd",
    T2."AltQty" as "QtyPerSalesUoM"
FROM OITM T0
LEFT JOIN OUOM T1 ON T0."UOM_Code" = T1."UOM_Code"
LEFT JOIN UOM1 T2 ON T0."ItemCode" = T2."ItemCode" AND T1."UOM_Entry" = T2."UOMEntry"

-- Query 3: Supply Schedule
SELECT
    T0."ItemCode",
    T0."DocDueDate" as "due_date",
    T0."OpenQty" as "quantity",
    T0."CardCode" as "vendor_code"
FROM POR1 T0
WHERE T0."LineStatus" = 'O'
```

**B1UP Upload Script (SQL in B1UP):**
```sql
-- After query execution, POST results to Railway
-- Use B1UP's HTTP POST action
URL: https://your-backend.railway.app/api/data/ingest
Method: POST
Headers:
  Content-Type: application/json
  Authorization: Bearer YOUR_API_KEY
Body: (Query results as JSON)
```

---

### 2. Processing Pipeline (Railway Backend)

```
Raw Data → Validate → Clean → Cache → Forecast → Optimize → Results
            ↓                    ↓
         Railway            Railway
         Volume             Volume
         (temporary)        (persistent)
```

**Processing Steps:**

1. **Receive Raw Data** (`POST /api/data/ingest`)
   - Validate schema
   - Check for missing fields
   - Save to temporary Railway volume
   - Return job ID

2. **Clean & Prepare** (Background job)
   - Run existing cleaning logic
   - UOM conversion
   - Calculate last sale dates
   - Save cleaned data to cache

3. **Generate Forecasts** (On-demand or scheduled)
   - Load from cache (if exists) or run forecasting tournament
   - Use existing code from `src/forecasting.py`
   - Save results to Railway volume (parquet)

4. **Optimization Analysis** (On-demand)
   - Load forecasts + inventory
   - Run existing code from `src/optimization.py`
   - Calculate shortages, TCO

5. **Write to Supabase** (Final results only)
   - Forecast summary (3,700 items × 10 columns = ~370KB)
   - Shortage alerts (500 items × 8 columns = ~40KB)
   - TCO analysis (3,700 items × 15 columns = ~560KB)
   - Warehouse configs (10 locations × 8 columns = ~1KB)

---

### 3. Frontend Data Access (On-Demand)

```
Vercel Frontend → Supabase Direct → Display
                      (via Supabase client)
```

**Why Supabase?**
- Fast reads (indexed, cached)
- Real-time subscriptions
- Built-in auth
- Direct connection (no backend needed for reads)
- FREE within 500MB

---

## Supabase Schema (Minimal - Processed Data Only)

### Table: `warehouse_capacities`
```sql
CREATE TABLE warehouse_capacities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    location_code VARCHAR(10) UNIQUE NOT NULL,
    total_skids INTEGER NOT NULL,
    used_skids INTEGER DEFAULT 0,
    skid_length_cm FLOAT DEFAULT 120,
    skid_width_cm FLOAT DEFAULT 100,
    max_height_cm FLOAT DEFAULT 150,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by UUID REFERENCES auth.users(id)
);

-- Row Level Security
ALTER TABLE warehouse_capacities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read" ON warehouse_capacities
    FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated write" ON warehouse_capacities
    FOR ALL USING (auth.role() = 'authenticated');

-- Indexes
CREATE INDEX idx_warehouse_location ON warehouse_capacities(location_code);
```

**Size estimate:** 10 rows × ~100 bytes = **1 KB**

---

### Table: `forecast_results`
```sql
CREATE TABLE forecast_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id UUID NOT NULL,
    item_code VARCHAR(50) NOT NULL,
    winning_model VARCHAR(50),
    forecast_month_1 FLOAT,
    forecast_month_2 FLOAT,
    forecast_month_3 FLOAT,
    forecast_month_4 FLOAT,
    forecast_month_5 FLOAT,
    forecast_month_6 FLOAT,
    forecast_horizon INTEGER DEFAULT 6,
    rmse FLOAT,
    mape FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, item_code)
);

-- Indexes
CREATE INDEX idx_forecast_job ON forecast_results(job_id);
CREATE INDEX idx_forecast_item ON forecast_results(item_code);
CREATE INDEX idx_forecast_created ON forecast_results(created_at DESC);
CREATE INDEX idx_forecast_model ON forecast_results(winning_model);
```

**Size estimate:** 3,700 rows × ~1 KB = **3.7 MB**

---

### Table: `shortage_alerts`
```sql
CREATE TABLE shortage_alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id UUID NOT NULL,
    item_code VARCHAR(50) NOT NULL,
    region VARCHAR(10),
    shortage_qty FLOAT,
    will_stockout BOOLEAN,
    urgency VARCHAR(50),
    days_until_stockout FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, item_code)
);

-- Indexes
CREATE INDEX idx_shortage_job ON shortage_alerts(job_id);
CREATE INDEX idx_shortage_urgency ON shortage_alerts(urgency);
CREATE INDEX idx_shortage_region ON shortage_alerts(region);
```

**Size estimate:** 500 rows × ~200 bytes = **100 KB**

---

### Table: `tco_analysis`
```sql
CREATE TABLE tco_analysis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id UUID NOT NULL,
    item_code VARCHAR(50) NOT NULL,
    recommendation VARCHAR(50),
    annual_savings FLOAT,
    cost_to_stock_annual FLOAT,
    cost_to_special_annual FLOAT,
    current_approach VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, item_code)
);

-- Indexes
CREATE INDEX idx_tco_job ON tco_analysis(job_id);
CREATE INDEX idx_tco_recommendation ON tco_analysis(recommendation);
CREATE INDEX idx_tco_savings ON tco_analysis(annual_savings DESC);
```

**Size estimate:** 3,700 rows × ~200 bytes = **740 KB**

---

### Table: `processing_jobs` (Job tracking)
```sql
CREATE TABLE processing_jobs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL, -- 'forecast', 'shortage', 'tco'
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed
    triggered_by VARCHAR(50), -- 'b1up', 'manual', 'scheduled'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    items_processed INTEGER DEFAULT 0,
    metadata JSONB,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_jobs_status ON processing_jobs(status);
CREATE INDEX idx_jobs_type ON processing_jobs(job_type);
CREATE INDEX idx_jobs_created ON processing_jobs(created_at DESC);
```

**Size estimate:** 365 jobs/year × ~200 bytes = **73 KB/year**

---

### **Total Supabase Storage: ~5-10 MB/year** (well within 500 MB free tier)

---

## Railway Backend Architecture

### Project Structure

```
forecast-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── data.py              # Data ingestion endpoints
│   │   ├── forecasts.py         # Forecast generation
│   │   ├── warehouses.py        # Warehouse CRUD
│   │   └── jobs.py              # Job status & management
│   ├── core/                    # Existing business logic
│   │   ├── __init__.py
│   │   ├── forecasting.py       # (From src/forecasting.py)
│   │   ├── optimization.py      # (From src/optimization.py)
│   │   ├── ingestion.py         # (From src/ingestion.py)
│   │   ├── cleaning.py          # (From src/cleaning.py)
│   │   ├── uom_conversion_sap.py
│   │   └── spatial_optimization.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── forecast.py          # Pydantic models
│   │   ├── job.py
│   │   └── warehouse.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── supabase.py          # Supabase client
│   │   ├── storage.py           # Railway volume storage
│   │   └── cache.py             # Cache management
│   └── workers/
│       ├── __init__.py
│       └── forecast_worker.py   # Background processing
├── tests/
│   ├── test_api.py
│   ├── test_forecasting.py
│   └── test_integration.py
├── scripts/
│   ├── migrate.py               # Copy src/ to app/core/
│   └── seed_supabase.py         # Initial data setup
├── requirements.txt
├── Dockerfile
├── railway.toml
└── README.md
```

---

### Key API Endpoints

#### 1. Data Ingestion (B1UP Integration)

```python
# app/api/data.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from app.models.job import IngestionRequest
import uuid

router = APIRouter(prefix="/api/data", tags=["data"])

@router.post("/ingest")
async def ingest_sap_data(
    data: dict,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(...),
):
    """
    Receive data from B1UP scheduled query

    Expected payload:
    {
        "query_name": "sales_orders" | "inventory" | "supply_schedule",
        "data": [...],  # Query results
        "timestamp": "2026-01-12T02:00:00Z"
    }
    """
    # Validate API key
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Create job record
    job_id = uuid.uuid4()

    # Save raw data to Railway volume
    storage.save_raw_data(job_id, data)

    # Trigger background processing
    background_tasks.add_task(
        process_ingested_data,
        job_id,
        data['query_name']
    )

    return {
        "job_id": str(job_id),
        "status": "pending",
        "message": "Data received, processing started"
    }

@router.get("/ingest/{job_id}/status")
async def get_ingestion_status(job_id: str):
    """Check ingestion job status"""
    job = supabase.table('processing_jobs').select('*').eq('id', job_id).execute()

    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.data[0]
```

---

#### 2. Forecast Generation

```python
# app/api/forecasts.py
from fastapi import APIRouter, BackgroundTasks
from app.models.forecast import ForecastRequest

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])

@router.post("/generate")
async def generate_forecasts(
    request: ForecastRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate forecasts for all items or subset

    Body:
    {
        "n_samples": 100,  # Optional, null = all items
        "use_cache": true,
        "force_refresh": false
    }
    """
    job_id = uuid.uuid4()

    # Create job record
    supabase.table('processing_jobs').insert({
        'id': str(job_id),
        'job_type': 'forecast',
        'status': 'pending',
        'triggered_by': 'manual',
        'metadata': {'n_samples': request.n_samples}
    }).execute()

    # Run in background
    background_tasks.add_task(
        run_forecasting_job,
        job_id,
        request.n_samples,
        request.use_cache,
        request.force_refresh
    )

    return {
        "job_id": str(job_id),
        "status": "pending",
        "estimated_time": "2-5 minutes"
    }

@router.get("/status/{job_id}")
async def get_forecast_status(job_id: str):
    """Poll forecast job status"""
    job = supabase.table('processing_jobs').select('*').eq('id', job_id).execute()

    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.data[0]

@router.get("/item/{item_code}")
async def get_item_forecast(item_code: str):
    """
    Get latest forecast for specific item

    Reads from Supabase (fast, cached)
    """
    result = supabase.table('forecast_results') \
        .select('*') \
        .eq('item_code', item_code.upper()) \
        .order('created_at', desc=True) \
        .limit(1) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Forecast not found")

    return result.data[0]
```

---

#### 3. Warehouse CRUD

```python
# app/api/warehouses.py
from fastapi import APIRouter
from app.models.warehouse import WarehouseCreate, WarehouseUpdate

router = APIRouter(prefix="/api/warehouses", tags=["warehouses"])

@router.get("")
async def get_warehouses():
    """Get all warehouse configurations (from Supabase)"""
    result = supabase.table('warehouse_capacities') \
        .select('*') \
        .execute()

    return {'warehouses': result.data}

@router.post("")
async def create_warehouse(warehouse: WarehouseCreate):
    """Create new warehouse (writes to Supabase)"""
    result = supabase.table('warehouse_capacities') \
        .insert(warehouse.dict()) \
        .execute()

    return result.data[0]

@router.put("/{location_code}")
async def update_warehouse(location_code: str, warehouse: WarehouseUpdate):
    """Update warehouse (writes to Supabase)"""
    result = supabase.table('warehouse_capacities') \
        .update(warehouse.dict(exclude_unset=True)) \
        .eq('location_code', location_code.upper()) \
        .execute()

    return result.data[0]

@router.delete("/{location_code}")
async def delete_warehouse(location_code: str):
    """Delete warehouse (from Supabase)"""
    result = supabase.table('warehouse_capacities') \
        .delete() \
        .eq('location_code', location_code.upper()) \
        .execute()

    return {'deleted': True}
```

---

### Background Processing

```python
# app/workers/forecast_worker.py
async def run_forecasting_job(
    job_id: str,
    n_samples: int = None,
    use_cache: bool = True,
    force_refresh: bool = False
):
    """Background task to generate forecasts and save to Supabase"""

    # Update job status
    supabase.table('processing_jobs').update({
        'status': 'running',
        'started_at': datetime.now().isoformat()
    }).eq('id', str(job_id)).execute()

    try:
        # Load data from Railway volume cache
        from app.core.ingestion import load_sales_orders
        df_sales = storage.load_cached_data('sales_cleaned')

        # Run forecasting (existing code)
        from app.core.forecasting import forecast_items
        df_forecasts = forecast_items(df_sales, n_samples=n_samples)

        # Write to Supabase (batch insert)
        forecasts_data = df_forecasts.to_dict('records')
        supabase.table('forecast_results').insert(
            [{
                'job_id': str(job_id),
                **row
            } for row in forecasts_data]
        ).execute()

        # Update job status
        supabase.table('processing_jobs').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'items_processed': len(df_forecasts)
        }).eq('id', str(job_id)).execute()

    except Exception as e:
        # Update job with error
        supabase.table('processing_jobs').update({
            'status': 'failed',
            'error_message': str(e),
            'completed_at': datetime.now().isoformat()
        }).eq('id', str(job_id)).execute()
```

---

## Vercel Frontend Architecture (Modular)

### Project Structure

```
forecast-frontend/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Dashboard/home
│   ├── globals.css
│   ├── (modules)/              # Route groups for modules
│   │   ├── forecasts/
│   │   │   ├── page.tsx        # /forecasts
│   │   │   ├── [item_code]/
│   │   │   │   └── page.tsx    # /forecasts/ITEM001
│   │   │   └── components/
│   │   │       ├── ForecastTable.tsx
│   │   │       ├── ForecastChart.tsx
│   │   │       └── ModelComparison.tsx
│   │   ├── shortages/
│   │   │   ├── page.tsx        # /shortages
│   │   │   └── components/
│   │   │       ├── ShortageTable.tsx
│   │   │       ├── UrgencyFilter.tsx
│   │   │       └── ShortageMap.tsx
│   │   ├── warehouses/
│   │   │   ├── page.tsx        # /warehouses
│   │   │   └── components/
│   │   │       ├── WarehouseTable.tsx
│   │   │       ├── WarehouseForm.tsx
│   │   │       └── UtilizationBar.tsx
│   │   ├── tco/
│   │   │   ├── page.tsx        # /tco
│   │   │   └── components/
│   │   │       ├── TCOTable.tsx
│   │   │       └── SavingsChart.tsx
│   │   └── [future-module]/    # Easy to add new modules
│   │       └── ...
│   ├── api/                    # API routes (if needed)
│   │   └── auth/
│   │       └── route.ts        # Supabase auth callback
│   └── auth/
│       └── signin/
│           └── page.tsx        # Login page
├── components/
│   ├── ui/                     # Reusable UI components
│   │   ├── Button.tsx
│   │   ├── Table.tsx
│   │   ├── Modal.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── Header.tsx          # App header
│   │   ├── Sidebar.tsx         # Navigation
│   │   └── Footer.tsx
│   └── providers/
│       ├── QueryProvider.tsx   # React Query
│       ├── SupabaseProvider.tsx
│       └── ThemeProvider.tsx
├── lib/
│   ├── supabase.ts             # Supabase client
│   ├── api.ts                  # Railway API client
│   └── utils.ts
├── hooks/
│   ├── useSupabase.ts          # Supabase hooks
│   ├── useForecasts.ts         # Custom forecast hooks
│   └── useWarehouses.ts        # Warehouse hooks
├── types/
│   ├── forecast.ts
│   ├── warehouse.ts
│   └── job.ts
├── package.json
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

---

### Module Pattern (Example: Forecasts)

**`app/(modules)/forecasts/components/ForecastTable.tsx`:**

```typescript
'use client';

import { useForecasts } from '@/hooks/useForecasts';
import { DataTable } from '@/components/ui/DataTable';

export function ForecastTable() {
  const { forecasts, isLoading, error } = useForecasts();

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  const columns = [
    { key: 'item_code', label: 'Item Code' },
    { key: 'winning_model', label: 'Model' },
    { key: 'forecast_month_1', label: 'Month 1' },
    { key: 'forecast_month_2', label: 'Month 2' },
    // ...
  ];

  return (
    <DataTable
      data={forecasts}
      columns={columns}
      searchable
      sortable
      pagination
    />
  );
}
```

**`hooks/useForecasts.ts`:**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/lib/supabase';

export function useForecasts() {
  return useQuery({
    queryKey: ['forecasts'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('forecast_results')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(1);

      if (error) throw error;
      return data[0]?.forecasts || [];
    },
    refetchInterval: 5 * 60 * 1000, // Refresh every 5 minutes
  });
}

export function useGenerateForecasts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (nSamples?: number) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_RAILWAY_URL}/api/forecasts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ n_samples: nSamples })
      });
      return response.json();
    },
    onSuccess: (data) => {
      // Poll for completion
      queryClient.prefetchQuery({
        queryKey: ['job', data.job_id],
        queryFn: () => fetch(`/api/jobs/${data.job_id}`).then(r => r.json())
      });
    }
  });
}
```

---

### Adding New Modules (Easy Extension)

**Example: Adding a "Purchasing" module**

```bash
# 1. Create module folder
mkdir -p app/\(modules\)/purchasing/components

# 2. Create page
# app/(modules)/purchasing/page.tsx
export default function PurchasingPage() {
  return (
    <div>
      <h1>Purchasing Module</h1>
      <PurchaseOrderList />
    </div>
  );
}

# 3. Add to sidebar
# components/layout/Sidebar.tsx
const modules = [
  { name: 'Forecasts', href: '/forecasts', icon: '📊' },
  { name: 'Shortages', href: '/shortages', icon: '📦' },
  { name: 'Warehouses', href: '/warehouses', icon: '🏠' },
  { name: 'TCO', href: '/tco', icon: '💰' },
  { name: 'Purchasing', href: '/purchasing', icon: '🛒' }, // NEW
];
```

---

## B1UP Integration Setup

### 1. B1UP Query Configuration

**In B1UP Query Generator:**

```sql
-- Query: Sales Orders for Forecast
-- Schedule: Daily at 2:00 AM
-- Output: JSON
-- Destination: HTTPS POST

SELECT
    T0."ItemCode" as "item_code",
    CAST(T0."DocDate" AS VARCHAR) as "date",
    CAST(T0."Quantity" AS DECIMAL(10,2)) as "quantity"
FROM INV1 T0
INNER JOIN OINV T1 ON T0."DocEntry" = T1."DocEntry"
WHERE T0."DocDate" >= DATEADD(MONTH, -12, GETDATE())
  AND T1."CANCELED" = 'N'
ORDER BY T0."DocDate"
```

### 2. B1UP HTTP POST Configuration

**URL:** `https://your-backend.railway.app/api/data/ingest`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer YOUR_SECRET_API_KEY
X-Query-Name: sales_orders
```

**Body Format (auto-generated by B1UP):**
```json
{
  "query_name": "sales_orders",
  "data": [
    {"item_code": "ITEM001", "date": "2025-01-01", "quantity": 100},
    {"item_code": "ITEM001", "date": "2025-01-15", "quantity": 150},
    ...
  ],
  "timestamp": "2026-01-12T02:00:00Z",
  "row_count": 45230
}
```

### 3. API Key Security

**Generate secure API key:**
```python
import secrets

API_KEY = secrets.token_urlsafe(32)
# Store in Railway environment variable: B1UP_API_KEY
```

**Validate in endpoint:**
```python
RAILWAY_API_KEY = os.getenv("B1UP_API_KEY")

def validate_api_key(provided_key: str) -> bool:
    return secrets.compare_digest(provided_key, RAILWAY_API_KEY)
```

---

## File Storage Strategy

### Railway Volume (Temporary + Cache)

**Directory Structure:**
```
/railway-volume/
├── raw/
│   ├── sales_2026-01-12_020000.json  # Deleted after 7 days
│   ├── inventory_2026-01-12_020000.json
│   └── supply_2026-01-12_020000.json
├── cleaned/
│   ├── sales_cleaned.parquet          # Persistent cache
│   ├── inventory_cleaned.parquet
│   └── supply_cleaned.parquet
└── forecasts/
    ├── forecast_cache.parquet         # Persistent cache
    └── dimensions_cache.pkl           # Persistent cache
```

**Lifecycle Policy:**
- **Raw data:** Delete after 7 days (keep only cleaned)
- **Cleaned data:** Keep until next full refresh
- **Forecasts:** Keep indefinitely, refresh daily
- **Dimensions:** Keep indefinitely

**Implementation:**
```python
# app/services/storage.py
import os
from datetime import datetime, timedelta

class RailwayVolumeStorage:
    def __init__(self, base_path="/data"):
        self.base_path = Path(base_path)
        self.raw_path = self.base_path / "raw"
        self.cleaned_path = self.base_path / "cleaned"
        self.forecasts_path = self.base_path / "forecasts"

    def save_raw_data(self, job_id: str, data: dict):
        """Save raw B1UP data"""
        filename = f"{data['query_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.raw_path / filename

        with open(filepath, 'w') as f:
            json.dump(data, f)

        # Schedule cleanup (7 days)
        self._schedule_cleanup(filepath, days=7)

    def save_cleaned_data(self, table_name: str, df: pd.DataFrame):
        """Save cleaned data as parquet"""
        filepath = self.cleaned_path / f"{table_name}_cleaned.parquet"
        df.to_parquet(filepath, index=False)

    def load_cached_data(self, table_name: str) -> pd.DataFrame:
        """Load from cache"""
        filepath = self.cleaned_path / f"{table_name}_cleaned.parquet"
        if filepath.exists():
            return pd.read_parquet(filepath)
        return None

    def _schedule_cleanup(self, filepath: Path, days: int):
        """Schedule file deletion using Railway cron"""
        # Add to cleanup queue with timestamp
        cleanup_time = datetime.now() + timedelta(days=days)
        cleanup_queue.append({
            'filepath': filepath,
            'delete_at': cleanup_time
        })

    def cleanup_old_files(self):
        """Run daily via Railway cron"""
        now = datetime.now()
        for file in self.raw_path.glob("*"):
            if file.stat().st_mtime < (now - timedelta(days=7)).timestamp():
                file.unlink()
```

---

## Deployment Configuration

### Railway Deployment (`railway.toml`)

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10

# Cron job for cleanup
[[services.cron]]
name = "daily-cleanup"
schedule = "0 3 * * *"  # 3 AM daily
command = "python -m app.tasks.cleanup"

# Cron job for daily forecast generation
[[services.cron]]
name = "daily-forecast"
schedule = "0 4 * * *"  # 4 AM daily (after cleanup)
command = "python -m app.tasks.daily_forecast"
```

### Vercel Deployment (`vercel.json`)

```json
{
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm install",
  "framework": "nextjs",
  "regions": ["iad1"],  // US East
  "env": {
    "NEXT_PUBLIC_RAILWAY_URL": "@railway-url",
    "NEXT_PUBLIC_SUPABASE_URL": "@supabase-url",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY": "@supabase-anon-key"
  },
  "build": {
    "env": {
      "NEXT_PUBLIC_RAILWAY_URL": "@railway-url"
    }
  }
}
```

---

## Environment Variables

### Railway (Backend)
```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key

# B1UP Integration
B1UP_API_KEY=your-secret-api-key-here

# Railway Volume
VOLUME_PATH=/data

# App Settings
LOG_LEVEL=INFO
MAX_FORECAST_ITEMS=3700
CACHE_TTL_SECONDS=3600
```

### Vercel (Frontend)
```bash
# Railway Backend
NEXT_PUBLIC_RAILWAY_URL=https://your-backend.railway.app

# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Feature Flags
NEXT_PUBLIC_ENABLE_FORECASTS=true
NEXT_PUBLIC_ENABLE_WAREHOUSES=true
NEXT_PUBLIC_ENABLE_TCO=true
```

---

## Implementation Phases

### Phase 0: Prerequisites (Current - Complete)
- ✅ Streamlit app fully tested locally
- ✅ All forecasting features working
- ✅ Spatial optimization validated
- ✅ Cache system working
- ✅ Accounts created:
  - Supabase: ✓
  - Railway: Need to create
  - Vercel: ✓

### Phase 1: Backend Setup (Week 1-2)
**Goal:** Deploy FastAPI backend to Railway

**Tasks:**
1. **Day 1-2: Project Setup**
   - [ ] Create Railway project
   - [ ] Set up GitHub repository
   - [ ] Create FastAPI project structure
   - [ ] Copy `src/` to `app/core/`

2. **Day 3-4: Core API**
   - [ ] Implement `/api/data/ingest` endpoint
   - [ ] Add API key authentication
   - [ ] Test with sample B1UP payload
   - [ ] Implement Railway volume storage

3. **Day 5-7: Forecasting Integration**
   - [ ] Migrate forecasting code
   - [ ] Add background job processing
   - [ ] Implement Supabase write logic
   - [ ] Test end-to-end: ingest → forecast → write

4. **Day 8-10: Additional Endpoints**
   - [ ] Warehouse CRUD endpoints
   - [ ] Job status polling
   - [ ] Shortage/TCO report generation
   - [ ] API testing & documentation

**Deliverable:**
- Railway backend deployed at `https://forecast-backend.railway.app`
- All API endpoints tested with Postman
- B1UP can successfully POST data
- Forecasts generate and save to Supabase

---

### Phase 2: Database & Storage (Week 2-3)
**Goal:** Set up Supabase schema & storage

**Tasks:**
1. **Day 1-2: Schema Setup**
   - [ ] Create tables in Supabase
   - [ ] Set up Row Level Security (RLS)
   - [ ] Create indexes
   - [ ] Test queries in Supabase SQL editor

2. **Day 3-4: Supabase Client**
   - [ ] Set up Python Supabase client
   - [ ] Test CRUD operations
   - [ ] Implement batch inserts
   - [ ] Add error handling

3. **Day 5-7: Storage Strategy**
   - [ ] Set up Railway volume
   - [ ] Implement cache system
   - [ ] Add lifecycle policies
   - [ ] Test file persistence

4. **Day 8-10: Data Migration**
   - [ ] Create seed script
   - [ ] Migrate warehouse configs
   - [ ] Migrate dimension cache
   - [ ] Verify data integrity

**Deliverable:**
- Supabase database fully configured
- Railway volume mounted and working
- Cache system operational
- Data migrated from local to cloud

---

### Phase 3: Frontend Foundation (Week 3-4)
**Goal:** Deploy Next.js app to Vercel with base UI

**Tasks:**
1. **Day 1-2: Project Setup**
   - [ ] Create Next.js project
   - [ ] Set up Tailwind CSS
   - [ ] Configure TypeScript
   - [ ] Add React Query, Supabase client

2. **Day 3-4: Layout & Navigation**
   - [ ] Create root layout
   - [ ] Build Sidebar navigation (modular)
   - [ ] Add Header/Footer
   - [ ] Implement responsive design

3. **Day 5-7: Supabase Integration**
   - [ ] Set up Supabase Auth
   - [ ] Implement login/logout
   - [ ] Add protected routes
   - [ ] Test authentication flow

4. **Day 8-10: Core UI Components**
   - [ ] Build reusable UI components
   - [ ] Create data table component
   - [ ] Add chart components (Plotly)
   - [ ] Implement loading states

**Deliverable:**
- Vercel app deployed at `https://forecast-app.vercel.app`
- Authentication working
- Base UI components library
- Navigation structure complete

---

### Phase 4: Module Implementation (Week 5-7)
**Goal:** Implement each module iteratively

**Week 5: Warehouses Module**
- [ ] Warehouse list view
- [ ] Add/edit warehouse forms
- [ ] Utilization visualization
- [ ] Import/export functionality

**Week 6: Forecasts Module**
- [ ] Forecast table (searchable, sortable)
- [ ] Item detail view
- [ ] Forecast charts
- [ ] Model comparison view
- [ ] Generate forecast button (triggers Railway job)

**Week 7: Shortages & TCO Modules**
- [ ] Shortage report table
- [ ] Urgency filtering
- [ ] TCO analysis table
- [ ] Savings visualization

**Deliverable:**
- All 4 modules fully functional
- Data flowing from Supabase
- User can view, edit, interact

---

### Phase 5: Integration & Testing (Week 8)
**Goal:** End-to-end testing & bug fixes

**Tasks:**
1. **Day 1-3: Integration Testing**
   - [ ] Test complete data flow: B1UP → Railway → Supabase → Vercel
   - [ ] Test manual forecast generation
   - [ ] Test warehouse CRUD
   - [ ] Test all filters and sorts

2. **Day 4-6: Edge Cases**
   - [ ] Test error handling (API failures)
   - [ ] Test with large datasets
   - [ ] Test concurrent users
   - [ ] Test file upload limits

3. **Day 7-8: Performance**
   - [ ] Optimize slow queries
   - [ ] Add caching where needed
   - [ ] Test load times
   - [ ] Compress assets

**Deliverable:**
- Production-ready application
- All tests passing
- Performance benchmarks met

---

### Phase 6: B1UP Setup & Automation (Week 9)
**Goal:** Connect SAP B1 via B1UP

**Tasks:**
1. **Day 1-3: B1UP Configuration**
   - [ ] Create SQL queries in B1UP
   - [ ] Set up scheduled execution (2 AM daily)
   - [ ] Configure HTTP POST to Railway
   - [ ] Add API key authentication

2. **Day 4-5: Testing B1UP Flow**
   - [ ] Test manual query execution
   - [ ] Verify data format
   - [ ] Test API endpoint reception
   - [ ] Verify data processing

3. **Day 6-7: Automation**
   - [ ] Enable daily schedule
   - [ ] Set up Railway cron for daily forecast
   - [ ] Add error notifications
   - [ ] Monitor for 1 week

**Deliverable:**
- B1UP fully configured
- Automated daily data pipeline
- Morning forecasts ready by 6 AM

---

### Phase 7: Production Launch (Week 10)
**Goal:** Deploy to production

**Tasks:**
1. **Day 1-2: Final Prep**
   - [ ] Set up custom domain (if desired)
   - [ ] Configure SSL (auto on Vercel/Railway)
   - [ ] Set up monitoring (Sentry, etc.)
   - [ ] Create deployment runbook

2. **Day 3-4: User Testing**
   - [ ] Onboard test users
   - [ ] Gather feedback
   - [ ] Fix critical bugs
   - [ ] Update documentation

3. **Day 5: Launch**
   - [ ] Switch to production
   - [ ] Monitor for issues
   - [ ] Be ready to rollback
   - [ ] Celebrate! 🎉

**Deliverable:**
- Production web app live
- Users onboarded
- Monitoring active
- Documentation complete

---

## Cost Summary (Monthly)

| Service | Plan | Cost | Notes |
|---------|------|------|-------|
| **Vercel** | Pro (optional) | $0-20 | Free tier sufficient initially |
| **Railway** | Pay-as-you-go | $5-15 | ~$5 free credit + usage |
| **Supabase** | Free | $0 | 500MB limit, we use ~10MB |
| **Total** | | **$5-35** | Most likely $5-15 range |

### Annual Estimate: $60-420/year (vs $300-600+ on Render)

---

## Monitoring & Maintenance

### Metrics to Track

1. **System Health**
   - API response times (Vercel Analytics)
   - Railway uptime (Railway dashboard)
   - Supabase storage usage (Supabase dashboard)
   - Job success rate (custom dashboard)

2. **Business Metrics**
   - Daily forecast job completion
   - Number of users
   - Most viewed items
   - Warehouse utilization trends

3. **Cost Monitoring**
   - Railway usage (CPU hours, storage)
   - Vercel bandwidth
   - Supabase database size
   - Alert thresholds set

---

## Risk Mitigation

### Risk 1: Railway Costs Spike

**Mitigation:**
- Set spending alerts in Railway ($20, $50 thresholds)
- Use caching aggressively
- Optimize forecast code (use n_samples for testing)
- Monitor CPU usage weekly

### Risk 2: B1UP Integration Fails

**Mitigation:**
- Keep manual file upload as fallback
- Test B1UP in sandbox first
- Have backup export method from SAP
- Document manual process

### Risk 3: Supabase Limits Exceeded

**Mitigation:**
- Monitor storage usage (alert at 400MB)
- Archive old job results (keep 90 days)
- Use compression for large datasets
- Ready to upgrade to Pro tier ($25/mo) if needed

### Risk 4: Frontend Performance

**Mitigation:**
- Use React Query for caching
- Implement pagination (100 items per page)
- Lazy load charts
- Use Vercel Edge Functions where possible

---

## Rollback Plan

If production deployment fails:

1. **Immediate Rollback**
   - Revert GitHub commit
   - Vercel auto-deploys previous version
   - Railway redeploy previous Docker image

2. **Data Safety**
   - Supabase data persists (no rollback needed)
   - Railway volume snapshots (if implemented)
   - Daily backups to local machine

3. **Communication**
   - Notify users of downtime
   - Provide timeline for fix
   - Update status page

---

## Next Steps (After Local Testing Complete)

1. ✅ **Verify local app is 100% working**
   - All 142 tests passing
   - Manual testing complete
   - Edge cases handled

2. ⏳ **Review this plan with stakeholders**
   - Get approval on architecture
   - Confirm budget ($5-35/mo)
   - Set timeline (10 weeks)

3. ⏳ **Set up accounts**
   - Create Railway account
   - Generate API keys
   - Set up repositories

4. ⏳ **Begin Phase 1: Backend Setup**
   - Start with Railway deployment
   - Focus on API endpoints first
   - Test B1UP integration early

5. ⏳ **Iterative development**
   - One module at a time
   - Continuous testing
   - Regular stakeholder demos

---

## Future Module Ideas (Post-Launch)

Once core is stable, consider adding:

1. **Purchasing Module**
   - PO generation based on shortages
   - Vendor consolidation recommendations
   - Purchase approval workflow

2. **Vendor Management**
   - Vendor performance metrics
   - Price tracking
   - Lead time analysis

3. **Advanced Reporting**
   - Custom report builder
   - Scheduled email reports
   - PDF export

4. **Mobile App**
   - React Native using same backend
   - Push notifications for urgent shortages
   - Barcode scanning for inventory

5. **Machine Learning Enhancements**
   - Demand pattern detection
   - Seasonality optimization
   - Anomaly detection

---

## Conclusion

This plan provides a **low-cost, modular migration path** from Streamlit to a production web application:

- **Cost:** $5-35/month (vs $25-50+ on Render)
- **Infrastructure:** Vercel + Railway + Supabase (accounts you have)
- **Timeline:** 10 weeks to full production
- **Risk:** Low - can rollback at any time
- **Scalability:** Modular design allows easy additions

**Key Principle:** Supabase stores only processed results (~10 MB), not raw SAP data. Raw data lives temporarily on Railway volume, keeping database costs minimal.

**Dependencies:** Local Streamlit app must be 100% tested before starting migration.

---

**Questions or concerns? Address them before starting implementation.**

**Ready to proceed? Start with Phase 1 once local testing is complete.**
