# 🚀 Running the Streamlit App

## Quick Start

### 1. Activate Virtual Environment
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Run the Streamlit App
```bash
streamlit run app.py
```

The app will automatically open in your browser at: **http://localhost:8501**

## App Features

### 📥 Data Loading Section
- **Location**: Sidebar
- **Function**: Loads and processes all SAP B1 data
- **Process**:
  1. Ingestion: Loads sales.tsv, supply.tsv, items.tsv
  2. Cleaning: Removes outliers, imputes missing lead times
  3. Forecasting: Runs tournament (SMA vs Holt-Winters vs Prophet)
  4. Optimization: Calculates TCO and recommendations

### 📦 Tab 1: Shortage Report
**What it shows:**
- Items where **Current Stock + Incoming < Forecasted Demand**
- Sorted by Region
- Highlights urgency of stockout

**Key Metrics:**
- Items at Risk
- Critical Stockouts (< 30 days)
- Total Shortage Quantity
- Regions Affected

**Filters:**
- Filter by Region
- Filter by Urgency Level
- Show only stockouts vs all items

**Columns:**
- Item Code, Region, Warehouse
- Current Stock, Incoming Stock
- Total Available vs 6-Month Forecast
- Shortage Quantity
- Days Until Stockout
- Urgency Level

**Visualizations:**
- Bar chart: Stockouts by Region
- Color-coded urgency indicators

### 💰 Tab 2: Stock vs Special Order
**What it shows:**
- Items recommended to switch from Stock to Special Order (or vice versa)
- Based on Total Cost of Ownership (TCO) analysis

**TCO Formula:**
- **Cost to Stock** = (Carrying Cost % × Unit Cost) + (Standard Freight % × Unit Cost)
- **Cost to Special Order** = (Special Surcharge + Special Freight % × Unit Cost) × Annual Demand

**Key Metrics:**
- Items to Switch
- Total Annual Savings
- Average Savings per Item
- Annual Affected Demand

**Filters:**
- Show only items recommended to switch
- Minimum Annual Savings threshold ($100 default)

**Columns:**
- Item Code, Description, Region
- Unit Cost, Annual Demand
- Cost to Stock (annual)
- Cost to Special Order (annual)
- Recommendation
- Annual Savings ($)
- Savings Percentage

**Visualizations:**
- Bar chart: Top 10 items by annual savings
- Pie chart: Savings distribution by region

## Configuration

Edit `config.yaml` to adjust:

### Carrying Cost Components
```yaml
carrying_cost:
  cost_of_capital_percent: 0.08      # 8%
  storage_percent: 0.10              # 10%
  service_percent: 0.02              # 2%
  risk_percent: 0.05                 # 5%
```

### Shipping Costs
```yaml
shipping:
  standard_freight_percent: 0.05             # 5%
  special_order_freight_percent: 0.15        # 15%
  special_order_fixed_surcharge: 50.0        # $50
```

## Performance Tips

### For Faster Loading (Demo Mode)
The app currently samples **100 items** for forecasting to keep load times reasonable. To change this:

```python
# In app.py, line ~55:
df_forecasts = forecast_items(df_sales, n_samples=100)  # Increase for more items
```

### For Production Use
- Remove `n_samples` parameter to forecast all items
- Expect 5-10 minute load time for 3,000+ items
- Consider using `@st.cache_data` for forecast results

## Troubleshooting

### Port Already in Use
```bash
# Run on different port
streamlit run app.py --server.port 8502
```

### Data Loading Errors
1. Ensure TSV files are in `data/raw/` folder:
   - `sales.tsv`
   - `supply.tsv`
   - `items.tsv`

2. Check file formats are correct (tab-separated)

### Prophet Not Working
Prophet may fail on items with < 18 months history. The app automatically falls back to SMA/Holt-Winters in these cases.

## Data Export

Both tabs include **Download** buttons to export:
- **Shortage Report** → `shortage_report.csv`
- **TCO Analysis** → `tco_analysis.csv`

## System Requirements

- Python 3.11+
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space

## Next Steps

Once the app is running:
1. Click **"🔄 Load/Reload Data"** in the sidebar
2. Wait for data processing (30-60 seconds for demo mode)
3. Explore the **Shortage Report** tab
4. Review **Stock vs Special Order** recommendations
5. Export reports for sharing with stakeholders
