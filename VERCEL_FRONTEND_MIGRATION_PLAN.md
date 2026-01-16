# Modern Frontend Migration Plan
## Streamlit → Next.js on Vercel

**Version:** 1.0
**Date:** 2026-01-16
**Goal:** Modern, beautiful frontend without sacrificing functionality

---

## Executive Summary

**Current State:**
- Streamlit app (functional but limited UI)
- Railway PostgreSQL database (all data)
- Manual TSV exports for data updates

**Target State:**
- **Next.js 14** (App Router) on **Vercel**
- **shadcn/ui** component library (modern, accessible, beautiful)
- **Recharts** for data visualization (maintains chart visibility)
- **React Query** for data fetching (optimized database queries)
- Railway PostgreSQL backend (unchanged)
- Direct database connection via server components

**Key Benefits:**
- Modern, professional UI
- Better performance (server components, edge caching)
- Superior mobile experience
- More design flexibility
- Maintain all data visualization capabilities

**Estimated Time:** 40-60 hours (1-2 weeks)

---

## Architecture Comparison

### Current (Streamlit)

```
┌─────────────────────────────────┐
│  Streamlit App (on Railway)     │
│  - Python-based                  │
│  - Limited UI customization      │
│  - Built-in charts (Plotly)      │
│  - Server-side rendering only    │
└──────────┬──────────────────────┘
           │ Direct queries
           ▼
┌─────────────────────────────────┐
│  Railway PostgreSQL              │
│  - 11 tables                     │
│  - 3 materialized views          │
└─────────────────────────────────┘
```

### Target (Next.js + Vercel)

```
┌─────────────────────────────────┐
│  Next.js 14 App (on Vercel)     │
│  - TypeScript                    │
│  - App Router                    │
│  - Server Components             │
│  - Client Components for UI     │
│  ┌───────────────────────────┐  │
│  │  UI Layer (Client)         │  │
│  │  - shadcn/ui components   │  │
│  │  - Recharts for data viz   │  │
│  │  - TailwindCSS styling     │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │  Data Layer (Server)       │  │
│  │  - React Query             │  │
│  │  - Direct DB queries       │  │
│  │  - API routes (optional)   │  │
│  └───────────────────────────┘  │
└──────────┬──────────────────────┘
           │ Direct queries
           ▼
┌─────────────────────────────────┐
│  Railway PostgreSQL              │
│  - 11 tables                     │
│  - 3 materialized views          │
└─────────────────────────────────┘
```

---

## Tech Stack

### Frontend Framework
- **Next.js 14** (App Router)
  - Server Components for data fetching
  - Client Components for interactivity
  - Route groups for modular structure
  - Built-in optimization (image, font, script)

### UI Component Library
- **shadcn/ui** (based on Radix UI)
  - Beautiful, accessible components
  - Copy-paste components (full customization)
  - Tailwind CSS-based
  - Excellent dark mode support
  - Components: DataTable, Charts, Forms, Modals, etc.

### Data Visualization
- **Recharts** (primary charting library)
  - Maintains all Streamlit chart types
  - Responsive by default
  - TypeScript support
  - Composable components
- **Plotly.js** (fallback for complex charts)
  - For interactive 3D plots if needed
  - Maintains parity with Streamlit

### Data Fetching
- **React Query** (TanStack Query v5)
  - Server state management
  - Automatic refetching
  - Cache management
  - Optimistic updates

### Database Connection
- **Neon Serverless Driver** OR **Drizzle ORM**
  - Direct PostgreSQL connection from Next.js
  - Server-side queries (no API needed)
  - Type-safe queries with Drizzle
  - Connection pooling included

### Styling
- **Tailwind CSS 3.4**
  - Utility-first CSS
  - Dark mode out of the box
  - Responsive design
  - Custom theming

### Deployment
- **Vercel** (native Next.js platform)
  - Automatic deployments
  - Edge functions
  - Analytics included
  - Free tier sufficient

---

## UI/UX Design Principles

### Visual Design

**Color Palette (Professional Inventory System)**
```css
Primary:   Blue-600  (#2563eb) - Trust, reliability
Secondary: Slate-700 (#334155) - Professional, neutral
Accent:    Emerald-500 (#10b981) - Success, positive metrics
Warning:   Amber-500  (#f59e0b) - Alerts, attention
Danger:    Rose-600   (#e11d48) - Shortages, critical issues
```

**Typography**
- Heading: **Inter** (modern sans-serif)
- Body: **Inter** (readable at all sizes)
- Monospace: **JetBrains Mono** (for numbers/codes)

**Layout Patterns**
- Sidebar navigation (collapsible)
- Data tables with virtual scrolling
- Dashboard cards with metrics
- Modal dialogs for detail views
- Tab-based content organization

---

## Feature Mapping: Streamlit → Next.js

### 1. Dashboard Tab

**Streamlit Features:**
- KPI cards (total items, shortages, forecasts)
- Summary metrics
- Quick actions

**Next.js Implementation:**
```
/app/dashboard/page.tsx
├── DashboardMetrics (Server Component)
│   ├── MetricCard (total items)
│   ├── MetricCard (total shortages)
│   ├── MetricCard (forecast coverage)
│   └── MetricCard (margin alerts)
├── QuickActions (Client Component)
│   └── ActionButton (generate forecast, import data)
└── RecentActivity (Server Component)
    └── ActivityList
```

**Components:**
- `MetricCard` - Shows KPI with trend indicator
- `QuickActions` - Buttons for common tasks
- `ActivityList` - Recent system events

---

### 2. Forecasts Tab

**Streamlit Features:**
- Item search and filter
- Forecast table (item, model, forecasts)
- Forecast chart (historical + predicted)
- Model comparison view

**Next.js Implementation:**
```
/app/forecasts/page.tsx
├── ForecastFilters (Client Component)
│   ├── SearchInput (item search)
│   ├── RegionSelect (filter by region)
│   └── ModelSelect (filter by model)
├── ForecastTable (Server Component)
│   ├── DataTable (sortable, paginated)
│   │   ├── item_code
│   │   ├── winning_model
│   │   ├── forecast_month_1-6
│   │   └── accuracy_metrics
│   └── RowActions (view details)
└── ForecastDetailModal (Client Component)
    ├── ForecastChart (Recharts LineChart)
    │   ├── Historical data
    │   ├── Forecasts (6 months)
    │   └── Confidence intervals
    └── ModelComparison (Recharts BarChart)
        ├── Model performance
        └── RMSE/MAPE comparison
```

**Data Visualization:**
- **LineChart** - Historical demand + forecasted values
- **BarChart** - Model performance comparison
- **Table** - Sortable, filterable forecast results
- **Badges** - Model names with color coding

**Maintains All Streamlit Features:**
- ✅ Item search
- ✅ Filtering by region/model
- ✅ Sortable columns
- ✅ Forecast visualization
- ✅ Model comparison
- ✅ Export to CSV

---

### 3. Inventory Optimization Tab

**Streamlit Features:**
- EOQ analysis table
- Shortage urgency indicators
- Constrained EOQ (spatial optimization)
- Reorder point recommendations

**Next.js Implementation:**
```
/app/inventory/page.tsx
├── InventoryHeader (Client Component)
│   ├── ViewToggle (standard vs constrained)
│   └── FilterPanel (warehouse, item group)
├── OptimizationTable (Server Component)
│   ├── DataTable (virtual scrolling)
│   │   ├── item_code
│   │   ├── current_stock
│   │   ├── forecast (next 3 months)
│   │   ├── eoq_reorder
│   │   ├── urgency_badge
│   │   └── actions (view details)
│   └── UrgencyIndicator
│       ├── Critical (red)
│       ├── High (orange)
│       ├── Medium (yellow)
│       └── Low (green)
└── OptimizationDetailModal (Client Component)
    ├── StockoutTimeline (Recharts AreaChart)
    │   ├── Projected stock levels
    │   └── Stockout dates
    ├── ReorderRecommendation
    │   ├── EOQ calculation
    │   ├── Reorder point
    │   └── Order now button
    └── SpatialAnalysis (Constrained view only)
        ├── Warehouse availability map
        └── Alternative sourcing
```

**Enhanced UI Features (Beyond Streamlit):**
- **Virtual scrolling** - Handle thousands of rows without lag
- **Inline editing** - Adjust parameters directly in table
- **Drag-to-reorder** - Prioritize items manually
- **Heatmap view** - Visual urgency indicator
- **Real-time filtering** - Instant results as you type

---

### 4. Margins Tab

**Streamlit Features:**
- Items with costs and pricing
- Margin percentage calculation
- Low margin alerts (< 20%)
- Filter by margin threshold

**Next.js Implementation:**
```
/app/margins/page.tsx
├── MarginFilters (Client Component)
│   ├── ThresholdSlider (0-100%)
│   ├── RegionSelect
│   └── CategorySelect
├── MarginSummary (Server Component)
│   ├── SummaryCard (average margin)
│   ├── SummaryCard (low margin count)
│   └── SummaryCard (potential savings)
├── MarginTable (Server Component)
│   ├── DataTable
│   │   ├── item_code
│   │   ├── unit_cost
│   │   ├── unit_price
│   │   ├── margin_pct
│   │   ├── margin_bar (visual)
│   │   └── trend_indicator
│   └── MarginBar (mini bar chart)
└── MarginDetailModal (Client Component)
    ├── MarginTrendChart (Recharts LineChart)
    │   ├── Margin history (12 months)
    │   └── Benchmark comparison
    ├── CostBreakdown
    │   ├── Unit cost
    │   ├── Freight
    │   ├── Duty
    │   └── Total landed cost
    └── PriceAnalysis
        ├── Current price
        ├── Recommended price
        └── Competitor comparison (future)
```

**Enhanced UI Features:**
- **Color-coded margins** - Red (<10%), Yellow (10-20%), Green (>20%)
- **Margin trend indicators** - ↑↓ showing improvement/decline
- **Mini sparklines** - 12-month trend in table
- **Bulk pricing editor** - Update multiple prices at once

---

### 5. Settings Tab

**Streamlit Features:**
- Configuration parameters
- Data refresh triggers
- System status

**Next.js Implementation:**
```
/app/settings/page.tsx
├── SettingsNav (Client Component)
│   ├── General
│   ├── Data Sources
│   ├── Forecasting
│   └── System
├── GeneralSettings (Server Component)
│   ├── Form (warehouse config)
│   ├── Form (vendor config)
│   └── SaveButton
├── DataSettings (Server Component)
│   ├── DataStatusCard
│   │   ├── Last update timestamp
│   │   ├── Record counts
│   │   └── RefreshButton
│   └── ImportForm
│       ├── File upload
│       └── Import log
├── ForecastingSettings (Server Component)
│   ├── Form (forecast horizon)
│   ├── Form (model selection)
│   └── RunForecastButton
└── SystemStatus (Server Component)
    ├── DatabaseHealth
    ├── CacheStatus
    └── VersionInfo
```

---

## Component Library Structure

### UI Components (`/components/ui`)

Based on shadcn/ui, will include:

**Data Display:**
- `DataTable` - Sortable, filterable tables with virtual scroll
- `MetricCard` - KPI display with trend
- `StatusBadge` - Color-coded status indicators
- `ProgressChart` - Visual progress bars

**Forms:**
- `Form` - Type-safe forms with React Hook Form
- `Select` - Dropdown selects
- `DatePicker` - Date range picker
- `Input` - Text inputs with validation
- `Switch` - Toggle switches
- `Slider` - Range sliders

**Feedback:**
- `Alert` - Notifications
- `Toast` - Temporary messages
- `Modal` - Dialog windows
- `ConfirmDialog` - Confirmation prompts

**Navigation:**
- `Sidebar` - Collapsible sidebar
- `Breadcrumb` - Page navigation
- `Tabs` - Tabbed content
- `Pagination` - Table pagination

**Charts (`/components/charts`):**
- `LineChart` - Time series data
- `BarChart` - Categorical comparisons
- `AreaChart` - Stock levels over time
- `HeatMap` - Urgency visualization
- `SparkLine` - Mini trend charts

---

## Project Structure

```
forecast-frontend/
├── app/
│   ├── layout.tsx              # Root layout (sidebar, header)
│   ├── page.tsx                # Dashboard (redirect)
│   ├── (dashboard)/            # Route group
│   │   ├── page.tsx            # Dashboard overview
│   │   └── layout.tsx          # Dashboard layout
│   ├── forecasts/              # Forecast module
│   │   ├── page.tsx            # Forecast list
│   │   ├── [item_code]/        # Forecast detail
│   │   │   └── page.tsx
│   │   └── components/
│   │       ├── ForecastTable.tsx
│   │       ├── ForecastChart.tsx
│   │       └── ModelComparison.tsx
│   ├── inventory/              # Inventory optimization
│   │   ├── page.tsx            # Inventory list
│   │   ├── [item_code]/        # Item detail
│   │   │   └── page.tsx
│   │   └── components/
│   │       ├── OptimizationTable.tsx
│   │       ├── UrgencyBadge.tsx
│   │       └── StockoutChart.tsx
│   ├── margins/                # Margin analysis
│   │   ├── page.tsx            # Margin list
│   │   └── components/
│   │       ├── MarginTable.tsx
│   │       ├── MarginBar.tsx
│   │       └── TrendChart.tsx
│   ├── settings/               # Settings
│   │   ├── page.tsx
│   │   └── components/
│   │       ├── GeneralSettings.tsx
│   │       └── DataSettings.tsx
│   ├── api/                    # API routes (if needed)
│   │   └── forecasts/
│   │       └── route.ts        # Generate forecast endpoint
│   └── globals.css
├── components/
│   ├── ui/                     # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── table.tsx
│   │   ├── dialog.tsx
│   │   └── ... (30+ components)
│   ├── charts/                 # Recharts wrappers
│   │   ├── LineChart.tsx
│   │   ├── BarChart.tsx
│   │   └── AreaChart.tsx
│   ├── layout/
│   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   ├── Header.tsx          # Top header
│   │   └── Footer.tsx
│   └── providers/
│   ├── QueryProvider.tsx       # React Query
│   └── ThemeProvider.tsx       # Dark mode
├── lib/
│   ├── db.ts                   # Database connection
│   ├── queries.ts              # SQL queries
│   └── utils.ts
├── hooks/
│   ├── useForecasts.ts         # Forecast data hooks
│   ├── useInventory.ts         # Inventory data hooks
│   └── useMargins.ts           # Margin data hooks
├── types/
│   ├── forecast.ts
│   ├── inventory.ts
│   └── margin.ts
├── styles/
│   └── globals.css
├── public/
│   └── images/
├── package.json
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── drizzle.config.ts           # ORM config (optional)
```

---

## Database Access Patterns

### Option 1: Direct Connection (Recommended)

**Use Neon Serverless Driver or Drizzle ORM**

```typescript
// lib/db.ts
import { neon } from '@neondatabase/serverless';
import { drizzle } from 'drizzle-orm/neon-http';

const sql = neon(process.env.DATABASE_URL!);
export const db = drizzle(sql);

// app/forecasts/page.tsx
import { db } from '@/lib/db';
import { forecasts, items } from '@/db/schema';

export default async function ForecastsPage() {
  const forecastData = await db
    .select()
    .from(forecasts)
    .leftJoin(items, eq(forecasts.itemCode, items.itemCode))
    .orderBy(desc(forecasts.createdAt));

  return <ForecastTable data={forecastData} />;
}
```

**Benefits:**
- Type-safe queries
- No API layer needed
- Server-side execution
- Automatic connection pooling

---

### Option 2: API Routes (If Needed)

For complex operations or future B1UP integration

```typescript
// app/api/forecasts/generate/route.ts
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const { n_samples } = await request.json();

  // Call Python forecasting service (Railway worker)
  const result = await fetch('https://api.railway.app/forecasts', {
    method: 'POST',
    body: JSON.stringify({ n_samples }),
  });

  return NextResponse.json(await result.json());
}
```

---

## Data Visualization Strategy

### Chart Mapping: Streamlit → Recharts

| Streamlit Chart | Recharts Component | Maintains Features? |
|-----------------|-------------------|---------------------|
| `st.line_chart` | `<LineChart />` | ✅ Tooltips, legends, zoom |
| `st.bar_chart` | `<BarChart />` | ✅ Stacked, grouped, horizontal |
| `st.area_chart` | `<AreaChart />` | ✅ Stacked areas, gradients |
| `st.scatter_chart` | `<ScatterChart />` | ✅ Custom markers, colors |
| `st.metric` | Custom `<MetricCard />` | ✅ Delta, trend indicators |

**Enhanced Features:**
- ✅ Responsive by default
- ✅ Animated on load
- ✅ Export to PNG
- ✅ Dark mode support
- ✅ Touch gestures (mobile)

---

## Migration Phases

### Phase 1: Setup & Foundation (Week 1)

**Tasks:**
1. Create Next.js project with TypeScript
2. Install dependencies (Next.js 14, Tailwind, shadcn/ui)
3. Set up database connection (Neon or Drizzle)
4. Create base layout (sidebar, header)
5. Configure authentication (Azure AD)
6. Set up React Query
7. Deploy placeholder to Vercel

**Deliverable:**
- Next.js app running on Vercel
- Database connectivity verified
- Authentication working
- Basic navigation structure

**Time:** 8-12 hours

---

### Phase 2: Dashboard Module (Week 1)

**Tasks:**
1. Create dashboard page
2. Build MetricCard component
3. Fetch KPI data from database
4. Create QuickActions component
5. Add ActivityList for recent events
6. Test with real data
7. Deploy to Vercel

**Deliverable:**
- Functional dashboard page
- All KPIs displaying correctly
- Responsive layout

**Time:** 6-8 hours

---

### Phase 3: Forecasts Module (Week 2)

**Tasks:**
1. Create forecasts list page
2. Build DataTable with sorting/filtering
3. Add ForecastFilters component
4. Create ForecastChart (Recharts)
5. Build ForecastDetailModal
6. Add ModelComparison chart
7. Implement search functionality
8. Add export to CSV
9. Test with full dataset

**Deliverable:**
- Complete forecasts module
- All visualizations working
- Search/filter functioning
- Export functionality

**Time:** 12-16 hours

---

### Phase 4: Inventory Optimization Module (Week 2)

**Tasks:**
1. Create inventory list page
2. Build OptimizationTable with urgency badges
3. Add view toggle (standard vs constrained)
4. Create StockoutTimeline chart
5. Build ReorderRecommendation component
6. Add SpatialAnalysis view (for constrained)
7. Implement inline editing
8. Test performance with large datasets

**Deliverable:**
- Complete inventory module
- EOQ and constrained views
- Visual urgency indicators
- Reorder functionality

**Time:** 12-16 hours

---

### Phase 5: Margins Module (Week 3)

**Tasks:**
1. Create margins list page
2. Build MarginTable with margin bars
3. Add threshold slider
4. Create MarginTrendChart
5. Build CostBreakdown component
6. Add trend indicators
7. Implement bulk price editor
8. Test margin calculations

**Deliverable:**
- Complete margins module
- Visual margin indicators
- Price editing capabilities

**Time:** 8-10 hours

---

### Phase 6: Settings & Polish (Week 3)

**Tasks:**
1. Create settings pages
2. Build configuration forms
3. Add system status indicators
4. Implement data import (manual TSV upload)
5. Add dark mode toggle
6. Optimize performance
7. Add loading states
8. Error handling
9. Mobile responsive testing
10. Accessibility audit

**Deliverable:**
- Complete settings module
- Dark mode working
- Mobile optimized
- Accessible (WCAG AA)

**Time:** 8-12 hours

---

## Implementation Checklist

### Setup
- [ ] Create Next.js 14 project
- [ ] Install Tailwind CSS
- [ ] Install shadcn/ui components
- [ ] Set up database connection
- [ ] Configure environment variables
- [ ] Set up Azure AD authentication
- [ ] Deploy to Vercel

### Dashboard
- [ ] MetricCard component
- [ ] KPI queries
- [ ] QuickActions component
- [ ] ActivityList component
- [ ] Dashboard page

### Forecasts
- [ ] DataTable component
- [ ] Forecast filters
- [ ] ForecastTable component
- [ ] LineChart component
- [ ] ForecastDetailModal
- [ ] ModelComparison chart
- [ ] Export to CSV
- [ ] Search functionality

### Inventory
- [ ] OptimizationTable component
- [ ] UrgencyBadge component
- [ ] View toggle (standard/constrained)
- [ ] AreaChart for stockouts
- [ ] ReorderRecommendation component
- [ ] SpatialAnalysis view
- [ ] Inline editing

### Margins
- [ ] MarginTable component
- [ ] MarginBar component
- [ ] Threshold slider
- [ ] MarginTrendChart
- [ ] CostBreakdown component
- [ ] Bulk price editor
- [ ] Trend indicators

### Settings
- [ ] Settings navigation
- [ ] Configuration forms
- [ ] System status indicators
- [ ] Data import functionality
- [ ] Dark mode toggle

### Polish
- [ ] Loading states
- [ ] Error boundaries
- [ ] Toast notifications
- [ ] Responsive design
- [ ] Accessibility (WCAG AA)
- [ ] Performance optimization

---

## Performance Optimization

### Database Queries
- Use server components for data fetching
- Implement connection pooling
- Add prepared statements
- Use materialized views for complex queries
- Cache expensive calculations

### Frontend
- Virtual scrolling for large tables
- Image optimization (Next.js Image)
- Code splitting (dynamic imports)
- Edge caching (Vercel Edge)
- Prefetch linked pages

### Monitoring
- Vercel Analytics (page views, Core Web Vitals)
- Database query monitoring
- Error tracking (Sentry)
- Performance budgets

---

## Cost Analysis

### Vercel (Frontend)
- **Hobby (Free):**
  - 100 GB bandwidth/month
  - Infinite builds
  - Automatic deployments
  - Analytics included

**Estimated Cost:** $0/month

### Railway (Database - unchanged)
- PostgreSQL free tier: 1 GB (we use ~30 MB)

**Estimated Cost:** $0/month

### Total Cost: $0/month ✅

---

## Comparison: Streamlit vs Next.js

| Feature | Streamlit | Next.js + shadcn/ui |
|---------|-----------|---------------------|
| **UI Customization** | Limited | Unlimited |
| **Performance** | Server-side only | Hybrid (server + client) |
| **Mobile Experience** | Poor | Excellent |
| **Chart Types** | Plotly only | Recharts + Plotly |
| **Type Safety** | None | Full TypeScript |
| **Component Library** | Built-in | shadcn/ui (30+ components) |
| **Development Speed** | Very fast | Moderate |
| **Design Flexibility** | Low | High |
| **SEO** | Poor | Excellent |
| **Deployment** | Railway | Vercel (native) |
| **Cost** | Free | Free |
| **Learning Curve** | Low | Moderate |

**Recommendation:** Next.js provides superior UX while maintaining all functionality.

---

## Risk Assessment

### High Risk

1. **Chart Parity** - Recharts may not match all Plotly features
   - **Mitigation:** Use Plotly.js fallback for complex charts
   - **Validation:** Compare all charts side-by-side

2. **Performance with Large Datasets** - 70,000+ sales orders
   - **Mitigation:** Virtual scrolling, server-side pagination
   - **Testing:** Load test with full dataset

### Medium Risk

1. **Development Time** - Longer than Streamlit
   - **Mitigation:** Use shadcn/ui to accelerate UI development
   - **Timeline:** 2-3 weeks vs 1 week for Streamlit updates

2. **Authentication** - Azure AD integration
   - **Mitigation:** Use NextAuth.js (well-documented)
   - **Testing:** Test early in Phase 1

---

## Next Steps

1. **Review this plan** and confirm architecture
2. **Create Vercel account** (if not exists)
3. **Initialize Next.js project** with dependencies
4. **Set up database connection** and test queries
5. **Build Dashboard** as proof-of-concept
6. **Iterate** through remaining modules

---

## Summary

**Migration Path:**
- Streamlit → Next.js 14 + shadcn/ui
- Railway (unchanged)
- Vercel deployment (new)

**Key Benefits:**
- Modern, professional UI
- Superior user experience
- Better mobile support
- Full data visibility maintained
- Enhanced chart interactivity
- Type-safe development

**Timeline:** 2-3 weeks (40-60 hours)

**Cost:** $0/month (Vercel free tier + Railway free tier)

**Readiness:** Can start immediately once database migration is complete

---

**Prepared by:** Claude (AI Assistant)
**Date:** 2026-01-16
**Status:** Ready for implementation
