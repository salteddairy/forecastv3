"""
SAP B1 Inventory & Forecast Analyzer - Streamlit Dashboard
"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import logging

# Initialize logging
from src.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="SAP B1 Inventory Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .stockout-critical {
        background-color: #ffcccc;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border-left: 4px solid #ff0000;
    }
    .stockout-high {
        background-color: #ffe6cc;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border-left: 4px solid #ff6600;
    }
    .stockout-medium {
        background-color: #fff3cc;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border-left: 4px solid #ffcc00;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<h1 class="main-header">📊 SAP B1 Inventory & Forecast Analyzer</h1>', unsafe_allow_html=True)

# Sidebar
st.sidebar.header("Configuration")

# Import cache manager
from src.cache_manager import load_cached_forecasts, save_forecasts_to_cache, should_refresh_cache, clear_cache, get_cache_info

# Cache Status
st.sidebar.subheader("Cache Status")
cache_info = get_cache_info()

if cache_info['exists']:
    age = cache_info['age_hours']
    if age < 1:
        age_str = f"{age*60:.0f} minutes ago"
    else:
        age_str = f"{age:.1f} hours ago"

    if cache_info['valid']:
        st.sidebar.success(f"✅ Forecasts: {cache_info['item_count']:,} items")
        st.sidebar.caption(f"Cached: {age_str}")
    else:
        st.sidebar.warning("⚠️ Cache: Invalid (data changed)")
        st.sidebar.caption("Will refresh on load")
else:
    st.sidebar.info("📭 No cached forecasts")
    st.sidebar.caption("First run will be slower")

if st.sidebar.button("🔄 Refresh Forecasts", help="Regenerate forecasts (clears cache)"):
    clear_cache()
    st.cache_resource.clear()
    st.rerun()

st.sidebar.markdown("---")

# Forecast Sample Size Selector
st.sidebar.subheader("Forecast Scope")
st.sidebar.markdown("*Choose how many items to forecast*")

forecast_mode = st.sidebar.radio(
    "Select Mode",
    ["Quick Test (100 items)", "Sample (500 items)", "Standard (1000 items)", "Full (All Items - Complete Analysis)"],
    index=0,
    help="Fewer items = faster testing. Use Full mode for production."
)

if forecast_mode == "Quick Test (100 items)":
    n_samples = 100
    mode_desc = "Quick Test"
elif forecast_mode == "Sample (500 items)":
    n_samples = 500
    mode_desc = "Sample"
elif forecast_mode == "Standard (1000 items)":
    n_samples = 1000
    mode_desc = "Standard"
else:  # Full mode
    n_samples = None
    mode_desc = "Full"

if n_samples:
    st.sidebar.info(f"📊 {mode_desc}: Forecasting {n_samples:,} items")
    st.sidebar.caption(f"Estimated: {n_samples * 0.3:.0f}s sequential, {n_samples * 0.3 / 4:.0f}s with joblib")
else:
    st.sidebar.info(f"📊 {mode_desc}: Forecasting ALL items")
    st.sidebar.caption("Estimated: 10-20 min sequential, 2-4 min with joblib")

st.sidebar.markdown("---")

# Data Loading Section
st.sidebar.header("📥 Data Loading")

# Initialize session state for pipeline lock
if 'pipeline_running' not in st.session_state:
    st.session_state.pipeline_running = False
if 'pipeline_progress' not in st.session_state:
    st.session_state.pipeline_progress = {"percent": 0, "message": ""}

# Check if pipeline is already running
if st.session_state.pipeline_running:
    st.sidebar.warning("⏳ Pipeline already running...")
    st.sidebar.info("Please wait for current pipeline to complete")
    progress = st.session_state.pipeline_progress
    if progress['message']:
        st.sidebar.caption(f"{progress['message']} ({progress['percent']}%)")

@st.cache_data
def load_data_pipeline(_n_samples=None, _use_cache=True, _sales_hash="", _items_hash="", _supply_hash=""):
    """
    Load and process data using modular pipeline with progress tracking.
    Always runs full pipeline (data + forecasts + reports).

    Note: File hashes are included in cache key to ensure cache invalidates
    when source data changes, even if function parameters remain the same.

    Uses @st.cache_data because this returns mutable data (DataFrames, dicts).
    """
    from src.data_pipeline import DataPipeline

    data_dir = Path("data/raw")

    # Create progress bar
    progress_bar = st.progress(0, "Initializing...")
    status_text = st.empty()

    def progress_callback(percent, message):
        """Update progress bar and status"""
        progress_bar.progress(percent / 100)
        status_text.text(message)
        # Also update session state for cross-runs communication
        st.session_state.pipeline_progress = {"percent": percent, "message": message}

    try:
        # Set pipeline running flag
        st.session_state.pipeline_running = True

        pipeline = DataPipeline()

        # Always run full pipeline
        result = pipeline.run_full_pipeline(
            data_dir,
            n_samples=_n_samples,
            use_cache=_use_cache,
            progress_callback=progress_callback
        )

        # Add timestamp for reports
        result['report_generated_at'] = pd.Timestamp.now()

        # Clean up UI
        progress_bar.empty()
        status_text.empty()

        return result

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        raise e
    finally:
        # Always clear pipeline running flag
        st.session_state.pipeline_running = False
        st.session_state.pipeline_progress = {"percent": 0, "message": ""}


# Initialize session state for data loading
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# Load data button
if st.sidebar.button("🔄 Load/Reload Data", type="primary", help="Load data and generate forecasts"):
    # Check if pipeline is already running
    if st.session_state.pipeline_running:
        st.sidebar.error("❌ Pipeline already running!")
        st.sidebar.warning("Please wait for current pipeline to complete")
    else:
        st.session_state.data_loaded = True
        st.cache_resource.clear()
        st.rerun()

# Prevent loading if pipeline is already running
if st.session_state.pipeline_running:
    st.sidebar.warning("⏳ Pipeline running in another tab/session")
    st.sidebar.info("Please wait or check other browser tabs")
    st.stop()

# Only load data if user has clicked the load button
if st.session_state.data_loaded:
    # Try to load data
    try:
        # Calculate file hashes for cache invalidation
        import hashlib
        data_dir = Path("data/raw")

        def get_file_hash(filepath):
            """Calculate hash of file for cache key"""
            if not filepath.exists():
                return ""
            stat = filepath.stat()
            hash_str = f"{filepath.name}_{stat.st_size}_{stat.st_mtime}"
            return hashlib.md5(hash_str.encode()).hexdigest()

        sales_hash = get_file_hash(data_dir / "sales.tsv")
        items_hash = get_file_hash(data_dir / "items.tsv")
        supply_hash = get_file_hash(data_dir / "supply.tsv")

        data = load_data_pipeline(
            _n_samples=n_samples,
            _sales_hash=sales_hash,
            _items_hash=items_hash,
            _supply_hash=supply_hash
        )
        st.sidebar.success("✅ Data loaded successfully!")
    except Exception as e:
        st.sidebar.error(f"❌ Error loading data: {e}")
        st.stop()
else:
    # Show welcome message and instructions
    st.sidebar.title("👋 Welcome!")
    st.sidebar.info("Please select a mode and click 'Load/Reload Data' to begin.")
    st.sidebar.caption("Select your forecast mode above, then click the Load button to process your data.")
    st.stop()

# Display data metrics in sidebar
st.sidebar.subheader("📈 Data Summary")
st.sidebar.metric("Total Items", len(data['items']))
st.sidebar.metric("Sales Orders", f"{len(data['sales']):,}")
st.sidebar.metric("Supply History", f"{len(data['history']):,}")
st.sidebar.metric("Forecasts Generated", len(data['forecasts']))

# Show report timestamp
if 'report_generated_at' in data:
    report_time = data['report_generated_at']
    time_ago = (pd.Timestamp.now() - report_time).total_seconds()
    if time_ago < 60:
        time_str = f"{int(time_ago)} seconds ago"
    elif time_ago < 3600:
        time_str = f"{int(time_ago/60)} minutes ago"
    else:
        time_str = f"{int(time_ago/3600)} hours ago"
    st.sidebar.caption(f"Reports generated: {time_str}")

# Main content area
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📦 Shortage Report",
    "🛒 Purchasing & Orders",
    "💰 Stock vs Special Order",
    "💀 Inventory Health",
    "📊 Forecast Details",
    "🏠 Warehouse",
    "🏢 Vendor Performance",
    "🔍 Data Quality"
])

# ============================================
# TAB 1: Shortage Report
# ============================================
with tab1:
    st.header("📦 Shortage Report")

    # Optimization Method Selection - Now supports BOTH methods simultaneously
    with st.expander("⚙️ Optimization Settings", expanded=False):
        st.markdown("""
        **Select which shortage calculations to show:**

        - **Standard (12-month forecast)**: Compares current stock to full 12-month forecast. Simple but may overestimate shortages.
        - **Constrained EOQ**: Uses reorder points based on warehouse capacity, carrying costs, and lead times. More accurate for ordering.

        **You can select BOTH methods to compare side-by-side!**
        """)

        # Use checkboxes instead of radio - allow multiple selections
        show_standard = st.checkbox("Show Standard (12-month forecast)", value=True, help="Simple forecast-based shortage calculation")
        show_constrained = st.checkbox("Show Constrained EOQ", value=False, help="Advanced EOQ-based optimization considering capacity, costs, and lead times")

        # Info messages
        col1, col2 = st.columns(2)
        with col1:
            if show_standard:
                st.info("📊 **Standard 12-Month** will be shown")
            else:
                st.caption("Standard 12-Month forecast hidden")
        with col2:
            if show_constrained:
                st.info("🔧 **Constrained EOQ** will be shown")
            else:
                st.caption("Constrained EOQ hidden")

    # Generate constrained EOQ data if needed
    if show_constrained and 'stockout_constrained' not in data:
        with st.spinner("Generating constrained optimization..."):
            from src.optimization import calculate_constrained_stockout_predictions
            from src.data_pipeline import DataPipeline

            pipeline = DataPipeline()
            df_items = pipeline.raw_data.get('items')
            df_forecasts = pipeline.forecasts

            # Get vendor lead times from forecasts (has lead_time_days column)
            df_vendor_lead_times = df_forecasts[['item_code', 'lead_time_days']].copy()
            df_vendor_lead_times['vendor_code'] = 'DEFAULT'  # Default vendor

            # Run constrained optimization
            df_constrained = calculate_constrained_stockout_predictions(
                df_items=df_items,
                df_forecasts=df_forecasts,
                df_vendor_lead_times=df_vendor_lead_times,
                config_path='config_inventory_optimization.yaml'
            )

            data['stockout_constrained'] = df_constrained

    # Determine which dataset to display
    if show_constrained and 'stockout_constrained' in data:
        # Constrained is available - let user choose which to view
        view_method = st.radio(
            "View Method",
            ["Standard (12-month)", "Constrained EOQ"],
            index=1 if show_constrained and not show_standard else 0,  # Default to Constrained if it's the only one selected
            help="Choose which shortage calculation to view"
        )
        df_stockout = data['stockout_constrained'] if view_method == "Constrained EOQ" else data['stockout']
    else:
        # Only standard is available
        df_stockout = data['stockout']
        view_method = "Standard (12-month)"

    st.markdown(f"""
    ### {view_method} Shortage Report
    This shows items where **Current Stock + Incoming Stock < Forecasted Demand**.
    Items are sorted by selected criteria and include monthly usage projections.
    """)

    # Filters
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        region_filter = st.selectbox(
            "Filter by Region",
            ['All'] + sorted([x for x in df_stockout['Region'].unique() if x is not None and pd.notna(x)]),
            key='tab1_region_filter'
        )
    with col2:
        urgency_filter = st.selectbox(
            "Filter by Urgency",
            ['All', 'CRITICAL (<30 days)', 'HIGH (30-60 days)', 'MEDIUM (60-90 days)', 'LOW (>90 days)',
             'CRITICAL (<7 days to reorder)', 'HIGH (7-14 days to reorder)', 'MEDIUM (14-30 days to reorder)'],
            key='tab1_urgency_filter'
        )
    with col3:
        # Vendor filter - show vendor names with codes
        vendor_options = ['All']
        if 'TargetVendor' in df_stockout.columns and 'TargetVendorName' in df_stockout.columns:
            vendor_df = df_stockout[['TargetVendor', 'TargetVendorName']].dropna().drop_duplicates()
            vendor_list = vendor_df.apply(lambda row: f"{row['TargetVendorName']} ({row['TargetVendor']})", axis=1).tolist()
            vendor_options.extend(sorted(vendor_list))
        elif 'TargetVendor' in df_stockout.columns:
            vendor_options.extend(sorted([x for x in df_stockout['TargetVendor'].dropna().unique() if x is not None and pd.notna(x)]))
        vendor_filter = st.selectbox(
            "Filter by Vendor",
            vendor_options,
            key='tab1_vendor_filter'
        )
    with col4:
        show_only_stockouts = st.checkbox("Show only items with stockouts", value=True,
                                          key='tab1_stockout_show_stockouts')
    with col5:
        include_inactive = st.checkbox("Include inactive items (>12 months)", value=False,
                                      help="Include items with no sales in the last 12 months",
                                      key='tab1_stockout_include_inactive')

    # Sort options
    col1, col2 = st.columns(2)
    with col1:
        sort_by = st.selectbox(
            "Sort by",
            ['Days Until Stockout', 'Days Until Reorder', 'Region', 'Shortage Quantity', 'Item Code', 'Vendor', 'Reorder Point'],
            key='tab1_sort_by'
        )
    with col2:
        sort_order = st.selectbox(
            "Sort order",
            ['Ascending', 'Descending'],
            key='tab1_sort_order'
        )

    # Apply filters
    df_stockout_filtered = df_stockout.copy()

    if region_filter != 'All':
        df_stockout_filtered = df_stockout_filtered[df_stockout_filtered['Region'] == region_filter]

    if urgency_filter != 'All':
        df_stockout_filtered = df_stockout_filtered[df_stockout_filtered['urgency'] == urgency_filter]

    if vendor_filter != 'All' and 'TargetVendor' in df_stockout_filtered.columns:
        # Extract vendor_code from the filter selection
        if '(' in vendor_filter and vendor_filter.endswith(')'):
            filter_code = vendor_filter.rsplit('(', 1)[1].rstrip(')')
        else:
            filter_code = vendor_filter
        df_stockout_filtered = df_stockout_filtered[df_stockout_filtered['TargetVendor'] == filter_code]

    if show_only_stockouts:
        df_stockout_filtered = df_stockout_filtered[df_stockout_filtered['will_stockout'] == True]

    # Filter out inactive items (no sale in last 12 months)
    if not include_inactive:
        twelve_months_ago = pd.Timestamp.now() - pd.Timedelta(days=365)
        df_stockout_filtered = df_stockout_filtered[
            (df_stockout_filtered['last_sale_date'].isna()) |
            (df_stockout_filtered['last_sale_date'] >= twelve_months_ago)
        ]

    # Apply sorting
    sort_mapping = {
        'Days Until Stockout': 'days_until_stockout',
        'Days Until Reorder': 'days_until_reorder',
        'Region': 'Region',
        'Shortage Quantity': 'shortage_qty',
        'Item Code': 'Item No.',
        'Vendor': 'TargetVendor',
        'Reorder Point': 'reorder_point'
    }
    sort_col = sort_mapping.get(sort_by, 'Region')  # Default to Region if not found
    ascending = sort_order == 'Ascending'

    if sort_col in df_stockout_filtered.columns:
        # Handle None/NaN values in sorting by placing them at the end
        df_stockout_filtered = df_stockout_filtered.sort_values(
            sort_col,
            ascending=ascending,
            na_position='last'  # Put NaN/None values at the end
        )

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Items at Risk",
            len(df_stockout_filtered[df_stockout_filtered['will_stockout'] == True])
        )
    with col2:
        critical_count = len(df_stockout_filtered[
            df_stockout_filtered['urgency'] == 'CRITICAL (<30 days)'
        ])
        st.metric("Critical Stockouts", critical_count)
    with col3:
        total_shortage = df_stockout_filtered['shortage_qty'].sum()
        st.metric("Total Shortage Qty", f"{total_shortage:,.0f}")
    with col4:
        st.metric("Regions Affected", df_stockout_filtered['Region'].nunique())
    with col5:
        vendors_affected = df_stockout_filtered['TargetVendor'].nunique() if 'TargetVendor' in df_stockout_filtered.columns else 0
        st.metric("Vendors Affected", vendors_affected)

    st.divider()

    # Display shortage table
    if len(df_stockout_filtered) > 0:
        # Create display columns with vendor info and monthly forecasts
        display_cols = [
            'Item No.',
            'Item Description',
            'Region',
            'Warehouse',
            'TargetVendor',
            'TargetVendorName',
            'lead_time_days',
        ]

        # Add constrained optimization columns if available
        if view_method == "Constrained EOQ":
            display_cols.extend([
                'reorder_point',
                'optimal_order_quantity',
                'current_position',
                'order_quantity',
            ])
        else:
            display_cols.extend([
                'CurrentStock',
                'IncomingStock',
                'total_available',
            ])

        display_cols.extend([
            'shortage_qty',
        ])

        # Use days_until_reorder for constrained, days_until_stockout for standard
        if view_method == "Constrained EOQ" and 'days_until_reorder' in df_stockout_filtered.columns:
            display_cols.append('days_until_reorder')
        elif 'days_until_stockout' in df_stockout_filtered.columns:
            display_cols.append('days_until_stockout')

        display_cols.append('urgency')

        # Add monthly forecast columns (current + 3 months)
        monthly_cols = ['forecast_month_1', 'forecast_month_2', 'forecast_month_3', 'forecast_month_4']
        for col in monthly_cols:
            if col in df_stockout_filtered.columns:
                display_cols.append(col)

        # Filter to only include columns that exist
        display_cols = [col for col in display_cols if col in df_stockout_filtered.columns]

        df_display = df_stockout_filtered[display_cols].copy()

        # Generate actual month names based on current date
        from datetime import datetime
        current_date = datetime.now()
        month_names = []
        for i in range(4):
            month_date = current_date + pd.DateOffset(months=i)
            month_name = month_date.strftime('%B %Y')  # e.g., "January 2025"
            month_names.append(month_name)

        # Rename columns for display
        column_rename = {
            'Item No.': 'Item Code',
            'Item Description': 'Item Description',
            'Region': 'Region',
            'Warehouse': 'Warehouse',
            'TargetVendor': 'Vendor Code',
            'TargetVendorName': 'Vendor Name',
            'lead_time_days': 'Lead Time (Days)',
            'reorder_point': 'Reorder Point',
            'optimal_order_quantity': 'Optimal Order Qty',
            'current_position': 'Current Position',
            'order_quantity': 'Order Qty Needed',
            'CurrentStock': 'Current Stock',
            'IncomingStock': 'Incoming Stock',
            'total_available': 'Total Available',
            'shortage_qty': 'Shortage Qty',
            'days_until_reorder': 'Days Until Reorder',
            'days_until_stockout': 'Days Until Stockout',
            'urgency': 'Urgency',
            'forecast_month_1': month_names[0],
            'forecast_month_2': month_names[1],
            'forecast_month_3': month_names[2],
            'forecast_month_4': month_names[3]
        }

        df_display = df_display.rename(columns=column_rename)

        # Format numeric columns
        if 'Current Stock' in df_display.columns:
            df_display['Current Stock'] = df_display['Current Stock'].apply(lambda x: f"{x:,.0f}")
        if 'Incoming Stock' in df_display.columns:
            df_display['Incoming Stock'] = df_display['Incoming Stock'].apply(lambda x: f"{x:,.0f}")
        if 'Total Available' in df_display.columns:
            df_display['Total Available'] = df_display['Total Available'].apply(lambda x: f"{x:,.0f}")
        if 'Reorder Point' in df_display.columns:
            df_display['Reorder Point'] = df_display['Reorder Point'].apply(lambda x: f"{x:,.0f}")
        if 'Optimal Order Qty' in df_display.columns:
            df_display['Optimal Order Qty'] = df_display['Optimal Order Qty'].apply(lambda x: f"{x:,.0f}")
        if 'Current Position' in df_display.columns:
            df_display['Current Position'] = df_display['Current Position'].apply(lambda x: f"{x:,.0f}")
        if 'Order Qty Needed' in df_display.columns:
            df_display['Order Qty Needed'] = df_display['Order Qty Needed'].apply(lambda x: f"{x:,.0f}")
        if 'Shortage Qty' in df_display.columns:
            df_display['Shortage Qty'] = df_display['Shortage Qty'].apply(lambda x: f"{x:,.0f}")
        if 'Days Until Stockout' in df_display.columns:
            df_display['Days Until Stockout'] = df_display['Days Until Stockout'].apply(
                lambda x: f"{x:,.0f}" if x < 999 else "No stockout"
            )
        if 'Days Until Reorder' in df_display.columns:
            df_display['Days Until Reorder'] = df_display['Days Until Reorder'].apply(
                lambda x: f"{x:,.0f}" if x < 999 else "Not needed"
            )

        # Format monthly forecast columns
        for i in range(1, 5):
            month_col = f'Month {i}'
            if month_col in df_display.columns:
                df_display[month_col] = df_display[month_col].apply(lambda x: f"{x:,.0f}")

        # Apply urgency styling (support both standard and constrained urgency values)
        def color_urgency(val):
            if 'CRITICAL' in str(val):
                return 'background-color: #ffcccc'
            elif 'HIGH' in str(val):
                return 'background-color: #ffe6cc'
            elif 'MEDIUM' in str(val):
                return 'background-color: #fff3cc'
            return ''

        df_display_styled = df_display.style.applymap(
            color_urgency,
            subset=['Urgency']
        )

        st.dataframe(
            df_display_styled,
            use_container_width=True,
            height=400
        )

        # Download button
        csv = df_display.to_csv(index=False)
        # Generate filename with current date
        from datetime import datetime
        report_date = datetime.now().strftime("%Y-%m-%d")
        st.download_button(
            label="📥 Download Shortage Report",
            data=csv,
            file_name=f"shortage_report_{report_date}.csv",
            mime="text/csv"
        )

        # Constrained EOQ Summary
        if view_method == "Constrained EOQ":
            st.divider()
            st.subheader("📊 Constrained Optimization Summary")

            # Calculate summary metrics
            items_to_order = df_stockout_filtered[df_stockout_filtered['should_order'] == True]

            if len(items_to_order) > 0:
                col1, col2, col3, col4, col5 = st.columns(5)

                with col1:
                    st.metric("Items to Order", len(items_to_order))

                with col2:
                    total_order_qty = items_to_order['order_quantity'].sum()
                    st.metric("Total Order Quantity", f"{total_order_qty:,.0f} units")

                with col3:
                    if 'space_required_sqft' in items_to_order.columns:
                        total_space = items_to_order['space_required_sqft'].sum()
                        st.metric("Space Required", f"{total_space:,.0f} sq ft")

                with col4:
                    if 'total_annual_cost' in items_to_order.columns:
                        total_cost = items_to_order['total_annual_cost'].sum()
                        st.metric("Est. Annual Cost", f"${total_cost:,.0f}")

                with col5:
                    avg_lead_time = items_to_order['lead_time_days'].mean() if 'lead_time_days' in items_to_order.columns else 0
                    st.metric("Avg Lead Time", f"{avg_lead_time:.0f} days")

                # Cost breakdown chart if available
                if all(col in items_to_order.columns for col in ['ordering_cost_annual', 'transportation_cost_annual', 'carrying_cost_annual']):
                    st.subheader("Annual Cost Breakdown")

                    total_ordering = items_to_order['ordering_cost_annual'].sum()
                    total_transport = items_to_order['transportation_cost_annual'].sum()
                    total_carrying = items_to_order['carrying_cost_annual'].sum()

                    cost_data = pd.DataFrame({
                        'Cost Type': ['Ordering', 'Transportation', 'Carrying'],
                        'Annual Cost': [total_ordering, total_transport, total_carrying]
                    })

                    fig_cost = px.bar(
                        cost_data,
                        x='Cost Type',
                        y='Annual Cost',
                        title='Annual Inventory Cost Breakdown',
                        color='Cost Type',
                        text_auto='$,.0f'
                    )
                    fig_cost.update_layout(showlegend=False)
                    st.plotly_chart(fig_cost, use_container_width=True)
            else:
                st.info("✅ No items need ordering - all above reorder point!")
    else:
        st.info("🎉 No items match the current filters!")

    # Chart: Stockouts by Region
    st.subheader("Stockouts by Region")
    region_stockouts = df_stockout_filtered[df_stockout_filtered['will_stockout'] == True].groupby('Region').size().reset_index(name='count')

    if len(region_stockouts) > 0:
        fig = px.bar(
            region_stockouts,
            x='Region',
            y='count',
            title='Number of Stockouts by Region',
            color='count',
            color_continuous_scale='Reds'
        )
        fig.update_layout(xaxis_title="Region", yaxis_title="Number of Stockouts")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No stockouts to display.")

# ============================================
# TAB 2: Purchasing & Orders (NEW)
# ============================================
with tab2:
    st.header("🛒 Automated Purchasing & Order Generator")
    st.markdown("""
    This module automates purchase order creation using **industry-standard reorder point logic**.

    ### How It Works:
    1. **Reorder Point** = Lead Time Demand + Safety Stock
       - Calculates when each item needs to be reordered
    2. **Order Quantity** = Order-Up-To Level - Current Position
       - Orders enough to reach target stock level
    3. **Vendor Grouping** - Groups items by vendor for efficient PO creation
    4. **SAP Ready** - Export format ready to paste into SAP B1

    ### Formulas Used:
    - **Lead Time Demand** = Avg Monthly Demand × (Lead Time Days / 30)
    - **Safety Stock** = (Z-score × σ × √(Lead Time)) + Buffer Days × Daily Demand
    - **Order-Up-To** = Reorder Point + (Order Cycle × Monthly Demand)
    """)

    # Check if data is loaded
    if 'stockout' not in data or len(data['stockout']) == 0:
        st.warning("📊 Please load data first to generate purchase orders.")
    else:
        from src.automated_ordering import AutomatedOrderingSystem, get_vendor_lead_times

        # Get supply chain data for lead times
        df_supply = data.get('schedule', pd.DataFrame())
        df_items = data.get('items', pd.DataFrame())
        df_forecasts = data.get('forecasts', pd.DataFrame())

        if not df_supply.empty and not df_items.empty and not df_forecasts.empty:
            # Calculate lead times per item
            with st.spinner("Calculating lead times..."):
                df_lead_times = get_vendor_lead_times(df_supply, df_items)

                # Merge vendor lead times into forecasts
                df_forecasts_with_lt = df_forecasts.merge(
                    df_lead_times[['item_code', 'vendor_code', 'lead_time_days', 'sample_count']],
                    on='item_code',
                    how='left'
                )

                # Fill missing lead times with vendor average or default
                df_forecasts_with_lt['lead_time_days'] = df_forecasts_with_lt['lead_time_days'].fillna(21)

            # Initialize ordering system
            ordering_system = AutomatedOrderingSystem()

            # Calculate reorder points
            with st.spinner("Calculating reorder points and order quantities..."):
                df_ordering = ordering_system.calculate_reorder_points(
                    df_forecasts=df_forecasts_with_lt,
                    df_inventory=data['stockout'],
                    df_vendor_lead_times=df_forecasts_with_lt
                )

                # Add vendor_name from items data for better display
                if 'TargetVendorName' in data['stockout'].columns:
                    vendor_name_map = data['stockout'][['TargetVendor', 'TargetVendorName']].dropna().drop_duplicates()
                    vendor_name_map.columns = ['vendor_code', 'vendor_name']
                    df_ordering = df_ordering.merge(vendor_name_map, on='vendor_code', how='left')
                    # For items with vendor_code but no vendor_name in stockout, try items data
                    if 'TargetVendorName' in df_items.columns:
                        item_vendor_map = df_items[['TargetVendor', 'TargetVendorName']].dropna().drop_duplicates()
                        item_vendor_map.columns = ['vendor_code', 'vendor_name_items']
                        df_ordering = df_ordering.merge(item_vendor_map, on='vendor_code', how='left')
                        df_ordering['vendor_name'] = df_ordering['vendor_name'].fillna(df_ordering['vendor_name_items'])
                        df_ordering = df_ordering.drop(columns=['vendor_name_items'])
                elif 'TargetVendorName' in df_items.columns:
                    vendor_name_map = df_items[['TargetVendor', 'TargetVendorName']].dropna().drop_duplicates()
                    vendor_name_map.columns = ['vendor_code', 'vendor_name']
                    df_ordering = df_ordering.merge(vendor_name_map, on='vendor_code', how='left')

                # Fallback to vendor_code if vendor_name is missing
                df_ordering['vendor_name'] = df_ordering['vendor_name'].fillna(df_ordering['vendor_code'])

            # Show summary
            st.subheader("📊 Ordering Summary")

            summary_col1, summary_col2, summary_col3, summary_col4, summary_col5 = st.columns(5)

            with summary_col1:
                items_to_order = df_ordering['should_order'].sum()
                st.metric("Items to Order", items_to_order)

            with summary_col2:
                critical_items = ((df_ordering['order_urgency'] == 'CRITICAL - Order Now') |
                                 (df_ordering['order_urgency'] == 'URGENT - Past Due')).sum()
                st.metric("Critical Items", critical_items)

            with summary_col3:
                total_value = df_ordering[df_ordering['should_order']]['order_value'].sum() if 'order_value' in df_ordering.columns else 0
                st.metric("Total Order Value", f"${total_value:,.2f}")

            with summary_col4:
                avg_lead_time = df_ordering['lead_time_days'].mean()
                st.metric("Avg Lead Time", f"{avg_lead_time:.0f} days")

            with summary_col5:
                vendors_count = df_ordering['vendor_code'].nunique()
                st.metric("Vendors to Order From", vendors_count)

            st.divider()

            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                show_all_items = st.checkbox("Show all items (not just items to order)", value=False,
                                            key='tab2_show_all_items')
            with col2:
                urgency_filter = st.selectbox(
                    "Filter by Urgency",
                    ['All'] + sorted([x for x in df_ordering['order_urgency'].unique() if x is not None and pd.notna(x)]),
                    key='tab2_urgency_filter'
                )
            with col3:
                # Build vendor filter options with names (sorted by name)
                vendor_options = df_ordering[['vendor_code', 'vendor_name']].dropna().drop_duplicates()
                vendor_options_list = vendor_options.apply(lambda row: f"{row['vendor_name']} ({row['vendor_code']})", axis=1).tolist()
                vendor_options_list = sorted(['All'] + vendor_options_list)
                vendor_filter = st.selectbox(
                    "Filter by Vendor",
                    vendor_options_list,
                    key='tab2_vendor_filter'
                )

            # Apply filters
            df_filtered = df_ordering.copy()

            if not show_all_items:
                df_filtered = df_filtered[df_filtered['should_order'] == True]

            if urgency_filter != 'All':
                df_filtered = df_filtered[df_filtered['order_urgency'] == urgency_filter]

            if vendor_filter != 'All':
                # Extract vendor_code from the filter selection
                if '(' in vendor_filter and vendor_filter.endswith(')'):
                    filter_code = vendor_filter.rsplit('(', 1)[1].rstrip(')')
                else:
                    filter_code = vendor_filter
                df_filtered = df_filtered[df_filtered['vendor_code'] == filter_code]

            # Display ordering table
            st.subheader(f"📋 Order List ({len(df_filtered)} items)")

            if len(df_filtered) > 0:
                # Select columns to display
                order_display_cols = [
                    'item_code',
                    'Item No.',
                    'Item Description',
                    'vendor_name',
                    'vendor_code',
                    'lead_time_days',
                    'avg_monthly_demand',
                    'demand_cv',
                    'safety_stock',
                    'reorder_point',
                    'order_up_to_level',
                    'CurrentStock',
                    'OnOrder',
                    'Committed',
                    'current_position',
                    'order_quantity',
                    'order_quantity_rounded',
                    'order_value',
                    'should_order',
                    'days_until_reorder',
                    'order_urgency',
                    'stock_status'
                ]

                order_display_cols = [col for col in order_display_cols if col in df_filtered.columns]

                df_order_display = df_filtered[order_display_cols].copy()

                # Rename for display
                order_rename = {
                    'item_code': 'Item Code',
                    'Item No.': 'Item Number',
                    'Item Description': 'Description',
                    'vendor_name': 'Vendor Name',
                    'vendor_code': 'Vendor Code',
                    'lead_time_days': 'Lead Time (Days)',
                    'avg_monthly_demand': 'Avg Monthly Demand',
                    'demand_cv': 'Demand CV',
                    'safety_stock': 'Safety Stock',
                    'reorder_point': 'Reorder Point',
                    'order_up_to_level': 'Order Up-To Level',
                    'CurrentStock': 'Current Stock',
                    'OnOrder': 'On Order',
                    'Committed': 'Committed',
                    'current_position': 'Current Position',
                    'order_quantity': 'Order Qty (Calc)',
                    'order_quantity_rounded': 'Order Qty',
                    'order_value': 'Order Value ($)',
                    'should_order': 'Should Order',
                    'days_until_reorder': 'Days Until Reorder',
                    'order_urgency': 'Order Urgency',
                    'stock_status': 'Stock Status'
                }

                df_order_display = df_order_display.rename(columns=order_rename)

                # Format numeric columns
                if 'Avg Monthly Demand' in df_order_display.columns:
                    df_order_display['Avg Monthly Demand'] = df_order_display['Avg Monthly Demand'].apply(lambda x: f"{x:,.1f}")
                if 'Safety Stock' in df_order_display.columns:
                    df_order_display['Safety Stock'] = df_order_display['Safety Stock'].apply(lambda x: f"{x:,.0f}")
                if 'Reorder Point' in df_order_display.columns:
                    df_order_display['Reorder Point'] = df_order_display['Reorder Point'].apply(lambda x: f"{x:,.0f}")
                if 'Order Up-To Level' in df_order_display.columns:
                    df_order_display['Order Up-To Level'] = df_order_display['Order Up-To Level'].apply(lambda x: f"{x:,.0f}")
                if 'Current Position' in df_order_display.columns:
                    df_order_display['Current Position'] = df_order_display['Current Position'].apply(lambda x: f"{x:,.0f}")

                # Highlight urgency with color
                def highlight_urgency(val):
                    if 'URGENT' in str(val) or 'CRITICAL' in str(val):
                        return 'background-color: #ffebee; font-weight: bold'
                    elif 'HIGH' in str(val):
                        return 'background-color: #fff3e0'
                    elif 'MEDIUM' in str(val):
                        return 'background-color: #e8f5e9'
                    return ''

                df_order_display_styled = df_order_display.style.applymap(
                    highlight_urgency,
                    subset=['Order Urgency']
                )

                st.dataframe(
                    df_order_display_styled,
                    use_container_width=True,
                    height=400
                )

                st.divider()

                # Generate vendor-grouped POs
                st.subheader("📦 Generate Purchase Orders by Vendor")

                col1, col2, col3 = st.columns(3)

                with col1:
                    include_non_critical = st.checkbox("Include non-critical items", value=False)

                with col2:
                    export_format = st.selectbox("Export Format", ['View in Browser', 'Download Excel', 'Download CSV'])

                with col3:
                    generate_po = st.button("🔄 Generate Purchase Orders")

                if generate_po or 'generate_po' in st.session_state:
                    st.session_state['generate_po'] = True

                    # Generate vendor POs
                    with st.spinner("Generating purchase orders..."):
                        vendor_pos = ordering_system.generate_vendor_purchase_orders(
                            df_ordering,
                            include_non_critical=include_non_critical
                        )

                    if vendor_pos:
                        st.success(f"Generated {len(vendor_pos)} purchase orders")

                        # Display vendor summary
                        st.subheader("Vendor Summary")

                        summary_data = []
                        for vendor_code, po_items in vendor_pos.items():
                            total_value = po_items['order_quantity_rounded'].multiply(
                                po_items.get('UnitCost', pd.Series([0], index=po_items.index))
                            ).sum()

                            summary_data.append({
                                'Vendor': vendor_code,
                                'Item Count': len(po_items),
                                'Total Value': total_value,
                                'Avg Lead Time': po_items['lead_time_days'].mean() if 'lead_time_days' in po_items.columns else 0
                            })

                        df_summary = pd.DataFrame(summary_data)
                        st.dataframe(df_summary, use_container_width=True)

                        # Expand to show PO details by vendor
                        with st.expander("📋 View Purchase Order Details by Vendor", expanded=False):
                            for vendor_code, po_items in vendor_pos.items():
                                st.markdown(f"### {vendor_code}")

                                # Select columns that exist
                                po_columns = ['Item No.', 'Item Description', 'order_quantity_rounded', 'UnitCost', 'lead_time_days', 'order_urgency']
                                po_columns = [col for col in po_columns if col in po_items.columns]

                                # Format for display
                                po_display = po_items[po_columns].copy()
                                if len(po_display) > 0:
                                    column_rename = {
                                        'Item No.': 'Item',
                                        'Item Description': 'Description',
                                        'order_quantity_rounded': 'Qty',
                                        'UnitCost': 'Unit Cost',
                                        'lead_time_days': 'Lead Time',
                                        'order_urgency': 'Urgency'
                                    }
                                    po_display = po_display.rename(columns=column_rename)
                                    st.dataframe(po_display, use_container_width=True)

                        # Export options
                        if export_format == 'Download Excel':
                            try:
                                output_path = "purchase_orders.xlsx"
                                ordering_system.export_to_excel(vendor_pos, output_path)

                                with open(output_path, 'rb') as f:
                                    st.download_button(
                                        label="📥 Download Excel File",
                                        data=f,
                                        file_name="purchase_orders.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            except ImportError:
                                st.warning("Excel export requires openpyxl. Install with: pip install openpyxl")

                        elif export_format == 'Download CSV':
                            # Flatten for CSV
                            df_sap = ordering_system.format_for_sap_import(vendor_pos)

                            csv = df_sap.to_csv(index=False)
                            st.download_button(
                                label="📥 Download CSV for SAP",
                                data=csv,
                                file_name=f"sap_purchase_orders_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )

            else:
                st.info("No items match the current filters.")

        else:
            st.warning("⚠️ Missing required data. Please ensure sales, supply, items, and forecasts are loaded.")

# ============================================
# TAB 3: Stock vs Special Order
# ============================================
with tab3:
    st.header("💰 Stock vs Special Order Analysis")
    st.markdown("""
    This analysis identifies items where the **Total Cost of Ownership (TCO)** suggests switching from
    Stock to Special Order (or vice versa). The recommendation is based on comparing:
    - **Cost to Stock**: Carrying cost + standard freight
    - **Cost to Special Order**: Special order surcharge + expedited freight

    **Annual Savings** shows the potential cost reduction by switching to the recommended approach.
    """)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        show_only_switches = st.checkbox("Show only items recommended to switch", value=True,
                                         key='tco_show_switches')
    with col2:
        min_savings = st.number_input(
            "Minimum Annual Savings ($)",
            min_value=0,
            max_value=10000,
            value=100,
            step=50,
            key='tco_min_savings'
        )
    with col3:
        include_inactive_tco = st.checkbox("Include inactive items (>12 months)", value=False,
                                          help="Include items with no sales in the last 12 months",
                                          key='tco_include_inactive')

    # Apply filters
    df_tco_filtered = data['tco'].copy()

    if show_only_switches:
        df_tco_filtered = df_tco_filtered[df_tco_filtered['should_switch'] == True]

    df_tco_filtered = df_tco_filtered[df_tco_filtered['annual_savings'] >= min_savings]

    # Filter out inactive items (no sale in last 12 months)
    if not include_inactive_tco:
        twelve_months_ago = pd.Timestamp.now() - pd.Timedelta(days=365)
        df_tco_filtered = df_tco_filtered[
            (df_tco_filtered['last_sale_date'].isna()) |
            (df_tco_filtered['last_sale_date'] >= twelve_months_ago)
        ]

    # Sort by annual savings (descending)
    df_tco_filtered = df_tco_filtered.sort_values('annual_savings', ascending=False, na_position='last')

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Items to Switch", len(df_tco_filtered[df_tco_filtered['should_switch'] == True]))
    with col2:
        total_savings = df_tco_filtered['annual_savings'].sum()
        st.metric("Total Annual Savings", f"${total_savings:,.2f}")
    with col3:
        avg_savings = df_tco_filtered['annual_savings'].mean()
        st.metric("Avg Savings per Item", f"${avg_savings:,.2f}")
    with col4:
        total_demand = df_tco_filtered['annual_demand'].sum()
        st.metric("Annual Affected Demand", f"{total_demand:,.0f} units")

    st.divider()

    # Display TCO table
    if len(df_tco_filtered) > 0:
        # Create display columns
        display_cols = [
            'Item No.',
            'Item Description',
            'Region',
            'UnitCost',
            'annual_demand',
            'cost_to_stock_annual',
            'cost_to_special_annual',
            'recommendation',
            'annual_savings',
            'savings_percent'
        ]

        df_display = df_tco_filtered[display_cols].copy()

        # Rename columns for display
        df_display.columns = [
            'Item Code',
            'Description',
            'Region',
            'Unit Cost',
            'Annual Demand',
            'Cost to Stock',
            'Cost to Special Order',
            'Recommendation',
            'Annual Savings',
            'Savings %'
        ]

        # Format numeric columns
        df_display['Unit Cost'] = df_display['Unit Cost'].apply(lambda x: f"${x:,.2f}")
        df_display['Annual Demand'] = df_display['Annual Demand'].apply(lambda x: f"{x:,.0f}")
        df_display['Cost to Stock'] = df_display['Cost to Stock'].apply(lambda x: f"${x:,.2f}")
        df_display['Cost to Special Order'] = df_display['Cost to Special Order'].apply(lambda x: f"${x:,.2f}")
        df_display['Annual Savings'] = df_display['Annual Savings'].apply(lambda x: f"${x:,.2f}")
        df_display['Savings %'] = df_display['Savings %'].apply(lambda x: f"{x:.1f}%")

        # Color code recommendations
        def color_recommendation(val):
            if val == 'STOCK':
                return 'background-color: #d4edda'
            else:
                return 'background-color: #fff3cd'

        # Display table
        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )

        # Download button
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="📥 Download TCO Analysis",
            data=csv,
            file_name="tco_analysis.csv",
            mime="text/csv"
        )

        # Chart: Top 10 Items by Annual Savings
        st.subheader("Top 10 Items by Annual Savings")
        top_10 = df_tco_filtered.head(10)

        fig = px.bar(
            top_10,
            x='Item No.',
            y='annual_savings',
            title='Top 10 Items: Annual Savings from Switching',
            color='annual_savings',
            color_continuous_scale='Greens',
            text=top_10['annual_savings'].apply(lambda x: f"${x:,.0f}")
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(xaxis_title="Item Code", yaxis_title="Annual Savings ($)")
        st.plotly_chart(fig, use_container_width=True)

        # Chart: Savings Distribution by Region
        st.subheader("Savings Distribution by Region")
        region_savings = df_tco_filtered.groupby('Region')['annual_savings'].sum().reset_index()

        fig = px.pie(
            region_savings,
            values='annual_savings',
            names='Region',
            title='Total Annual Savings by Region',
            hole=0.4
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💡 No items match the current filters. Try adjusting the savings threshold.")

# ============================================
# TAB 3: Inventory Health
# ============================================
with tab3:
    st.header("💀 Inventory Health Report")
    st.markdown("""
    Identify dead stock (no movement for 2+ years), shelf life risks (FG-RE items with 6-month expiry),
    and take action to optimize inventory value.
    """)

    # Check if inventory health data is available
    inventory_health = data.get('inventory_health', {})

    if not inventory_health or 'summary' not in inventory_health:
        st.warning("⚠️ No inventory health data available.")
        st.info("💡 This report analyzes dead stock (2+ years no movement) and shelf life risks for FG-RE items.")
    else:
        summary = inventory_health['summary']

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            dead_count = summary.get('dead_stock', {}).get('count', 0)
            st.metric("Dead Stock Items", dead_count,
                     help="Items with no movement for 2+ years")

        with col2:
            dead_value = summary.get('dead_stock', {}).get('value', 0)
            st.metric("Dead Stock Value", f"${dead_value:,.2f}",
                     help="Total value of dead stock")

        with col3:
            shelf_risk_count = summary.get('shelf_life_risk', {}).get('high_risk_count', 0)
            st.metric("Shelf Life Risk Items", shelf_risk_count,
                     help="FG-RE items with >70% of shelf life consumed")

        with col4:
            shelf_risk_value = summary.get('shelf_life_risk', {}).get('value_at_risk', 0)
            st.metric("Value at Risk", f"${shelf_risk_value:,.2f}",
                     help="Total value of items at risk of expiry")

        st.divider()

        # Dead Stock Section
        st.subheader("💀 Dead Stock Analysis (2+ Years No Movement)")

        if 'dead_stock' in inventory_health and not inventory_health['dead_stock'].empty:
            df_dead = inventory_health['dead_stock'].copy()

            # Filters
            col1, col2, col3 = st.columns(3)

            with col1:
                min_stock = st.number_input("Minimum Stock Value", min_value=0, value=100, step=100,
                                           key='tab4_min_stock')

            with col2:
                urgency_filter = st.selectbox("Urgency", ["All", "DEAD STOCK (2+ years)", "SLOW MOVING (1-2 years)"],
                                              key='tab4_urgency_filter')

            with col3:
                has_stock_only = st.checkbox("Only items with stock", value=True,
                                            key='tab4_has_stock_only')

            # Apply filters
            filtered = df_dead.copy()

            if min_stock > 0:
                filtered = filtered[filtered['inventory_value'] >= min_stock]

            if urgency_filter != "All":
                filtered = filtered[filtered['urgency'] == urgency_filter]

            if has_stock_only:
                filtered = filtered[filtered['CurrentStock'] > 0]

            # Sort by value (highest first)
            filtered = filtered.sort_values('inventory_value', ascending=False, na_position='last')

            if len(filtered) > 0:
                st.info(f"Showing {len(filtered)} items meeting criteria")

                # Display columns
                display_cols = ['Item No.', 'Item Description', 'ItemGroup',
                               'CurrentStock', 'UnitCost', 'inventory_value',
                               'days_inactive', 'urgency', 'Warehouse']

                display_df = filtered[display_cols].copy()
                display_df.columns = ['Item', 'Description', 'Group',
                                     'Stock', 'Unit Cost', 'Value',
                                     'Days Inactive', 'Urgency', 'Warehouse']

                # Format value column
                display_df['Value'] = display_df['Value'].apply(lambda x: f"${x:,.2f}")
                display_df['Unit Cost'] = display_df['Unit Cost'].apply(lambda x: f"${x:.2f}")

                # Color code urgency
                def highlight_urgency(row):
                    if row['Urgency'] == 'DEAD STOCK (2+ years)':
                        return ['background-color: #FFCCCB' for _ in range(len(row))]
                    elif row['Urgency'] == 'SLOW MOVING (1-2 years)':
                        return ['background-color: #FFE4B5' for _ in range(len(row))]
                    return ['' for _ in range(len(row))]

                styled_df = display_df.style.apply(highlight_urgency, axis=1)
                st.dataframe(styled_df, use_container_width=True, height=400)

                # Export button
                if st.button("📥 Export Dead Stock Report"):
                    csv = filtered[display_cols].to_csv(index=False)
                    st.download_button(
                        label="Download dead_stock_report.csv",
                        data=csv,
                        file_name="dead_stock_report.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No items match your filters.")
        else:
            st.info("📊 No dead stock detected or no data available.")

        st.divider()

        # Shelf Life Risk Section
        st.subheader("⚠️ Shelf Life Risk (FG-RE Items - 6 Month Expiry)")

        if 'shelf_life_risk' in inventory_health and not inventory_health['shelf_life_risk'].empty:
            df_shelf = inventory_health['shelf_life_risk'].copy()

            # Filters
            col1, col2 = st.columns(2)

            with col1:
                risk_filter = st.selectbox("Risk Level", ["All", "HIGH RISK", "EXPIRED"],
                                          key='tab4_shelf_risk_filter')
            with col2:
                show_action_required_only = st.checkbox("Only action required", value=True,
                                                       key='tab4_shelf_action_only')

            # Apply filters
            filtered = df_shelf.copy()

            if risk_filter == "HIGH RISK":
                filtered = filtered[filtered['action_required'] == True]
            elif risk_filter == "EXPIRED":
                filtered = filtered[filtered['months_of_stock'] > 6]

            if show_action_required_only:
                filtered = filtered[filtered['action_required'] == True]

            # Sort by risk (months of stock descending)
            filtered = filtered.sort_values('months_of_stock', ascending=False, na_position='last')

            if len(filtered) > 0:
                st.info(f"Found {len(filtered)} FG-RE items requiring attention")

                # Display columns
                display_cols = ['Item No.', 'Item Description',
                               'CurrentStock', 'IncomingStock', 'total_stock',
                               'avg_monthly_usage', 'months_of_stock',
                               'expiry_risk', 'ordering_recommendation',
                               'stock_value']

                display_df = filtered[display_cols].copy()
                display_df.columns = ['Item', 'Description',
                                     'Current', 'Incoming', 'Total Stock',
                                     'Monthly Usage', 'Months of Stock',
                                     'Risk', 'Recommendation',
                                     'Value']

                # Format value
                display_df['Value'] = display_df['Value'].apply(lambda x: f"${x:,.2f}")

                # Color code risk
                def highlight_risk(row):
                    if 'EXPIRED' in str(row['Risk']):
                        return ['background-color: #FF6B6B' for _ in range(len(row))]
                    elif 'HIGH' in str(row['Risk']):
                        return ['background-color: #FFD93D' for _ in range(len(row))]
                    return ['' for _ in range(len(row))]

                styled_df = display_df.style.apply(highlight_risk, axis=1)
                st.dataframe(styled_df, use_container_width=True, height=400)

                # Action items
                st.subheader("🎯 Recommended Actions")

                action_count = len(filtered[filtered['action_required'] == True])

                if action_count > 0:
                    st.warning(f"""
                    **{action_count} items require immediate action:**

                    1. **DO NOT ORDER** items with >6 months of stock
                    2. **Monitor items** with 4-6 months of stock - order conservatively
                    3. **Consider discounts** for slow-moving FG-RE items
                    4. **Review sales promotions** to increase turnover

                    Remember: FG-RE items have a **6-month shelf life** and you practice FIFO.
                    Current stock age is estimated based on months-of-stock on hand.
                    """)
                else:
                    st.success("✅ No FG-RE items require immediate action!")

                # Export
                if st.button("📥 Export Shelf Life Risk Report"):
                    csv = filtered[display_cols].to_csv(index=False)
                    st.download_button(
                        label="Download shelf_life_risk_report.csv",
                        data=csv,
                        file_name="shelf_life_risk_report.csv",
                        mime="text/csv"
                    )
            else:
                st.success("✅ No FG-RE items at risk of expiry!")
        else:
            st.info("📊 No FG-RE items found or no shelf life data available.")

        st.divider()

        # Summary and Recommendations
        st.subheader("📋 Summary & Recommendations")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Dead Stock Action Items:**

            1. **Review dead stock items** - Consider clearance, return to vendor, or write-off
            2. **Investigate root cause** - Why did these items stop moving?
               - Obsolete products?
               - Poor sales performance?
               - Seasonal items not reordered?
            3. **Prevent future dead stock** - Set up automatic alerts for items approaching 2 years inactive
            4. **Optimize ordering** - Use forecast data to prevent overstocking slow movers
            """)

        with col2:
            st.markdown("""
            **Shelf Life Action Items:**

            1. **FG-RE items are time-sensitive** - 6-month shelf life requires careful inventory management
            2. **Monitor stock age** - Even with FIFO, high stock levels increase expiry risk
            3. **Order conservatively** - Use the "months of stock" metric to guide ordering decisions
            4. **Sales promotions** - Consider discounts for items approaching 4+ months of stock
            5. **Supplier communication** - Work with suppliers on smaller, more frequent orders
            """)

# UPDATED FORECAST DETAILS TAB CONTENT
# Copy this content to replace lines 942-1313 in app.py

# ============================================
# TAB 4: Forecast Details (UPDATED - 12 Month Forecasts + Accuracy Tracking)
# ============================================
with tab4:
    st.header("📊 Forecast Details by Product")
    st.markdown("""
    This view shows detailed **12-month** forecasts for individual products including historical performance,
    model comparison, and accuracy metrics from forecast tracking.
    """)

    # Product selector and options
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Get list of items with forecasts
        if 'forecasts' not in data or data['forecasts'].empty:
            st.error("No forecast data available. Please load data first.")
            st.stop()

        item_list = sorted([x for x in data['forecasts']['item_code'].unique() if x is not None and pd.notna(x)])

        if not item_list:
            st.warning("No items found in forecast data.")
            st.stop()

        selected_item = st.selectbox(
            "Select Item",
            options=item_list,
            index=0,
            help="Choose an item to view detailed forecast"
        )

    with col2:
        # Display options
        show_history = st.checkbox("Show historical sales", value=True,
                                   key='forecast_show_history')
        show_forecast_range = st.checkbox("Show confidence range", value=False,
                                         key='forecast_show_range')

    with col3:
        # Column visibility controls
        st.markdown("**Column Filters**")
        show_item_code = st.checkbox("Item Code", value=True, key='col_item_code')
        show_description = st.checkbox("Description", value=True, key='col_description')
        show_model = st.checkbox("Forecast Model", value=True, key='col_model')
        show_confidence = st.checkbox("Confidence %", value=True, key='col_confidence')
        show_accuracy = st.checkbox("Accuracy Tracking", value=True, key='col_accuracy')

    # Get forecast data for selected item
    df_forecasts_filtered = data['forecasts'][data['forecasts']['item_code'] == selected_item]

    if df_forecasts_filtered.empty:
        st.error(f"No forecast data found for item: {selected_item}")
        st.stop()

    df_item_forecast = df_forecasts_filtered.iloc[0]

    # Get historical sales for this item
    df_sales_filtered = data['sales'][data['sales']['item_code'] == selected_item]

    if df_sales_filtered.empty:
        st.warning(f"No sales history found for item: {selected_item}")
        df_sales_monthly = pd.DataFrame(columns=['date', 'qty'])
    else:
        df_sales_item = df_sales_filtered.copy()
        df_sales_item['date'] = pd.to_datetime(df_sales_item['date'], errors='coerce')
        df_sales_item['qty'] = pd.to_numeric(df_sales_item['qty'], errors='coerce')

        # Aggregate monthly
        df_sales_monthly = df_sales_item.groupby(df_sales_item['date'].dt.to_period('M'))['qty'].sum().reset_index()
        df_sales_monthly['date'] = df_sales_monthly['date'].dt.to_timestamp()

    # Get item details
    item_mask = data['items']['Item No.'] == selected_item
    if item_mask.any():
        item_details = data['items'][item_mask].iloc[0]
    else:
        item_details = None

    # Display item info with column visibility
    info_cols = []
    if show_item_code:
        info_cols.append(st.container())
    if show_description:
        info_cols.append(st.container())
    if show_model:
        info_cols.append(st.container())
    if show_confidence:
        info_cols.append(st.container())

    for i, col in enumerate(info_cols):
        with col:
            if i == 0 and show_item_code:
                st.metric("Item Code", selected_item)
            elif i == 1 and show_description and item_details is not None:
                desc = str(item_details['Item Description'])
                display_desc = desc[:30] + "..." if len(desc) > 30 else desc
                st.metric("Description", display_desc)
            elif i == 2 and show_model:
                st.metric("Forecast Model", str(df_item_forecast['winning_model']))
            elif i == 3 and show_confidence:
                conf_pct = df_item_forecast.get('forecast_confidence_pct', 0)
                if pd.notna(conf_pct):
                    st.metric("Forecast Confidence", f"{conf_pct:.1f}%")
                else:
                    st.metric("Forecast Confidence", "N/A")

    st.divider()

    # ============================================
    # FORECAST ACCURACY TRACKING SECTION (NEW)
    # ============================================
    if show_accuracy:
        st.subheader("📈 Forecast Accuracy Tracking")

        # Load accuracy metrics if available
        try:
            from src.forecast_accuracy import get_accuracy_metrics, ForecastAccuracyTracker

            df_accuracy = get_accuracy_metrics()

            if not df_accuracy.empty:
                # Filter for this item
                item_accuracy = df_accuracy[df_accuracy['item_code'] == selected_item]

                if not item_accuracy.empty:
                    # Get most recent accuracy data
                    latest_accuracy = item_accuracy.sort_values('snapshot_date', na_position='last').iloc[-1]

                    acc_col1, acc_col2, acc_col3, acc_col4 = st.columns(4)

                    with acc_col1:
                        mape = latest_accuracy['mape']
                        if pd.notna(mape):
                            st.metric("MAPE", f"{mape:.1f}%")
                            if mape < 10:
                                st.success("Excellent")
                            elif mape < 20:
                                st.info("Good")
                            elif mape < 30:
                                st.warning("Fair")
                            else:
                                st.error("Poor")
                        else:
                            st.metric("MAPE", "N/A")

                    with acc_col2:
                        rmse = latest_accuracy['rmse']
                        st.metric("RMSE", f"{rmse:.2f}" if pd.notna(rmse) else "N/A")

                    with acc_col3:
                        bias = latest_accuracy['bias']
                        if pd.notna(bias):
                            bias_label = "Over-forecast" if bias > 0 else "Under-forecast" if bias < 0 else "Unbiased"
                            st.metric("Bias", f"{bias:+.1f} ({bias_label})")
                        else:
                            st.metric("Bias", "N/A")

                    with acc_col4:
                        snapshot_date = pd.to_datetime(latest_accuracy['snapshot_date'])
                        age_days = (pd.Timestamp.now() - snapshot_date).days
                        st.metric("Last Comparison", f"{age_days} days ago")

                    # Show accuracy trend
                    if len(item_accuracy) > 1:
                        st.markdown("**Accuracy Over Time**")
                        accuracy_trend = item_accuracy.sort_values('snapshot_date', na_position='last')[['snapshot_date', 'mape']].copy()
                        accuracy_trend['snapshot_date'] = pd.to_datetime(accuracy_trend['snapshot_date']).dt.strftime('%Y-%m-%d')
                        accuracy_trend = accuracy_trend.rename(columns={'snapshot_date': 'Date', 'mape': 'MAPE (%)'})
                        st.dataframe(accuracy_trend, use_container_width=True, hide_index=True)
                else:
                    st.info("📊 No accuracy data available yet for this item. Accuracy tracking requires comparing previous forecasts to actual sales data.")
            else:
                st.info("📊 Forecast accuracy tracking will begin after the first monthly update. This requires comparing previous forecasts to actual sales data.")
        except Exception as e:
            st.warning(f"Accuracy tracking unavailable: {e}")

        st.divider()

    # ============================================
    # 12-MONTH FORECAST CHART
    # ============================================
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Historical Sales & 12-Month Forecast")

        # Prepare 12-month forecast data
        forecast_months = [f'forecast_month_{i+1}' for i in range(12)]
        forecast_values = [df_item_forecast.get(m) for m in forecast_months]

        # Get last date from sales data
        if len(df_sales_monthly) > 0:
            last_date = df_sales_monthly['date'].max()
            forecast_dates = pd.date_range(
                start=last_date + pd.DateOffset(months=1),
                periods=12,
                freq='MS'
            )
        else:
            forecast_dates = pd.date_range(start=pd.Timestamp.now(), periods=12, freq='MS')

        # Create chart
        fig = go.Figure()

        # Add historical sales
        if show_history and len(df_sales_monthly) > 0:
            fig.add_trace(go.Scatter(
                x=df_sales_monthly['date'],
                y=df_sales_monthly['qty'],
                mode='lines+markers',
                name='Historical Sales',
                line=dict(color='#1f77b4', width=2)
            ))

        # Add 12-month forecast
        fig.add_trace(go.Scatter(
            x=forecast_dates,
            y=forecast_values,
            mode='lines+markers',
            name='12-Month Forecast',
            line=dict(color='#ff7f0e', width=2, dash='dash')
        ))

        # Add confidence range (optional)
        if show_forecast_range:
            rmse = df_item_forecast.get(f'rmse_{df_item_forecast["winning_model"]}', 0)
            upper_bound = [v + rmse if pd.notna(v) else v for v in forecast_values]
            lower_bound = [max(0, v - rmse) if pd.notna(v) else v for v in forecast_values]

            fig.add_trace(go.Scatter(
                x=forecast_dates.tolist() + forecast_dates.tolist()[::-1],
                y=upper_bound + lower_bound[::-1],
                fill='toself',
                fillcolor='rgba(255, 127, 14, 0.2)',
                line=dict(color='rgba(255, 255, 255, 0)'),
                name='95% Confidence Range',
                showlegend=True
            ))

        fig.update_layout(
            title=f"12-Month Forecast: {selected_item}",
            xaxis_title="Month",
            yaxis_title="Quantity",
            hovermode='x unified',
            height=400,
            legend=dict(x=0.01, y=0.99)
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("12-Month Forecast Table")

        # Create forecast table with all 12 months
        forecast_table_data = []
        for i in range(12):
            forecast_val = forecast_values[i]
            month_name = forecast_dates[i].strftime('%b %Y')
            forecast_table_data.append({
                'Month': month_name,
                'Forecast': f"{forecast_val:,.0f}" if pd.notna(forecast_val) else "N/A"
            })

        df_forecast_table = pd.DataFrame(forecast_table_data)

        st.dataframe(
            df_forecast_table,
            use_container_width=True,
            hide_index=True,
            height=400
        )

    st.divider()

    # ============================================
    # MODEL COMPARISON (12 MONTHS)
    # ============================================
    st.subheader("📊 Model Comparison: All Forecasts Side-by-Side")

    # Column selector for model comparison
    show_all_12 = st.checkbox("Show all 12 months", value=False, key='show_all_12_months')
    months_to_show = 12 if show_all_12 else 6

    # Get forecasts from all models
    model_comparison_data = []

    for month_idx in range(1, months_to_show + 1):
        month_data = {'Month': f'Month {month_idx}'}

        # Get forecast from each model if available
        for model in ['sma', 'holt_winters', 'prophet']:
            col_name = f'forecast_{model}_month_{month_idx}'
            if col_name in df_item_forecast:
                forecast_val = df_item_forecast[col_name]
                month_data[model.upper()] = f"{forecast_val:,.0f}" if pd.notna(forecast_val) else "N/A"
            else:
                # Fall back to the main forecast columns (these are from the winning model)
                forecast_col = f'forecast_month_{month_idx}'
                if model == df_item_forecast['winning_model'].lower().replace('-', '_') and forecast_col in df_item_forecast:
                    forecast_val = df_item_forecast[forecast_col]
                    month_data[model.upper()] = f"{forecast_val:,.0f} ✓" if pd.notna(forecast_val) else "N/A"
                else:
                    month_data[model.upper()] = "N/A"

        model_comparison_data.append(month_data)

    df_comparison = pd.DataFrame(model_comparison_data)

    # Style the winning model
    def highlight_winner(val):
        if '✓' in str(val):
            return 'background-color: #d4edda; font-weight: bold'
        return ''

    df_comparison_styled = df_comparison.style.applymap(highlight_winner)
    st.dataframe(df_comparison_styled, use_container_width=True)

    # ============================================
    # MODEL ACCURACY METRICS
    # ============================================
    st.markdown("### Model Accuracy Metrics")

    accuracy_cols = st.columns(3)
    models_display = ['SMA', 'Holt-Winters', 'Prophet']

    for idx, model in enumerate(models_display):
        with accuracy_cols[idx]:
            model_key = model.lower().replace('-', '_')
            rmse_col = f'rmse_{model_key}'

            if rmse_col in df_item_forecast:
                rmse_val = df_item_forecast[rmse_col]
                if pd.notna(rmse_val):
                    # Calculate MAPE
                    avg_demand = df_sales_monthly['qty'].mean() if len(df_sales_monthly) > 0 else 0
                    mape = (rmse_val / avg_demand * 100) if avg_demand > 0 else 0

                    is_winner = model == df_item_forecast['winning_model']

                    st.markdown(f"**{model}**")
                    if is_winner:
                        st.success("🏆 Winning Model")
                    st.metric("RMSE", f"{rmse_val:.2f}")
                    st.metric("MAPE", f"{mape:.1f}%")
                else:
                    st.markdown(f"**{model}**")
                    st.info("N/A (Insufficient data)")
            else:
                st.markdown(f"**{model}**")
                st.info("N/A (Not run)")

    st.divider()

    # ============================================
    # FORECAST METRICS AND INSIGHTS
    # ============================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Model Performance Comparison")

        # Get RMSE values
        models = ['SMA', 'Holt-Winters', 'Prophet']
        rmse_data = []

        for model in models:
            rmse_col = f'rmse_{model}'
            if rmse_col in df_item_forecast:
                rmse_val = df_item_forecast[rmse_col]
                if pd.notna(rmse_val):
                    rmse_data.append({
                        'Model': model,
                        'RMSE': f"{rmse_val:.2f}",
                        'Status': '🏆 Winner' if model == df_item_forecast['winning_model'] else ''
                    })

        df_model_comparison = pd.DataFrame(rmse_data)
        st.dataframe(
            df_model_comparison,
            use_container_width=True,
            hide_index=True
        )

    with col2:
        st.subheader("Forecast Metrics")

        # Calculate metrics
        history_months = int(df_item_forecast.get('history_months', 0))
        train_months = int(df_item_forecast.get('train_months', 0))
        test_months = int(df_item_forecast.get('test_months', 0))
        forecast_horizon = int(df_item_forecast.get('forecast_horizon', 12))
        conf_pct = df_item_forecast.get('forecast_confidence_pct', 0)

        # Calculate demand trend
        if len(df_sales_monthly) >= 6:
            recent_3 = df_sales_monthly.tail(3)['qty'].sum()
            previous_3 = df_sales_monthly.iloc[-6:-3]['qty'].sum()
            if previous_3 > 0:
                trend_pct = ((recent_3 - previous_3) / previous_3) * 100
                trend_indicator = "📈 Increasing" if trend_pct > 10 else "📉 Decreasing" if trend_pct < -10 else "➡️ Stable"
                trend_value = f"{trend_pct:+.1f}%"
            else:
                trend_indicator = "➡️ Stable"
                trend_value = "N/A"
        else:
            trend_indicator = "Insufficient Data"
            trend_value = "N/A"

        # Calculate demand volatility
        if len(df_sales_monthly) > 0 and df_sales_monthly['qty'].mean() > 0:
            demand_cv = (df_sales_monthly['qty'].std() / df_sales_monthly['qty'].mean()) * 100
            volatility_label = "Low" if demand_cv < 50 else "Medium" if demand_cv < 100 else "High"
        else:
            demand_cv = 0
            volatility_label = "N/A"

        metrics_data = {
            'Metric': [
                'History Months',
                'Forecast Horizon',
                'Train/Test Split',
                'Forecast Confidence',
                'Demand Trend',
                'Volatility (CV)'
            ],
            'Value': [
                f"{history_months} months",
                f"{forecast_horizon} months",
                f"{train_months}/{test_months}",
                f"{conf_pct:.1f}%" if pd.notna(conf_pct) else "N/A",
                f"{trend_value} ({trend_indicator})",
                f"{demand_cv:.1f}% ({volatility_label})"
            ]
        }

        df_metrics = pd.DataFrame(metrics_data)
        st.dataframe(
            df_metrics,
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # ============================================
    # INSIGHTS AND RECOMMENDATIONS
    # ============================================
    st.subheader("📈 Forecast Insights & Recommendations")

    insight_col1, insight_col2, insight_col3 = st.columns(3)

    with insight_col1:
        st.markdown("**Model Reliability**")
        if history_months >= 24:
            st.success("✅ Excellent: 2+ years of history")
            st.caption("Forecasts are highly reliable with this much data")
        elif history_months >= 12:
            st.info("📊 Good: 1+ year of history")
            st.caption("Forecasts have reasonable confidence")
        else:
            st.warning("⚠️ Limited: <12 months history")
            st.caption("Consider increasing safety stock due to uncertainty")

    with insight_col2:
        st.markdown("**Demand Stability**")
        if demand_cv < 50:
            st.success("✅ Stable Demand")
            st.caption("Low volatility = accurate forecasts")
        elif demand_cv < 100:
            st.info("📊 Moderate Volatility")
            st.caption("Monitor forecasts closely, adjust safety stock")
        else:
            st.warning("⚠️ High Volatility")
            st.caption("Consider higher safety stock buffers")

    with insight_col3:
        st.markdown("**Forecast Confidence**")
        if pd.notna(conf_pct):
            if conf_pct >= 80:
                st.success(f"✅ High Confidence ({conf_pct:.0f}%)")
                st.caption("Forecasts are highly reliable")
            elif conf_pct >= 60:
                st.info(f"📊 Moderate Confidence ({conf_pct:.0f}%)")
                st.caption("Forecasts have reasonable accuracy")
            else:
                st.warning(f"⚠️ Low Confidence ({conf_pct:.0f}%)")
                st.caption("High uncertainty - monitor closely")
        else:
            st.warning("⚠️ No confidence data")
            st.caption("Unable to calculate confidence")


# ============================================
# TAB 5: Warehouse Capacity Management
# ============================================
with tab5:
    st.header("🏠 Warehouse Capacity Management")
    st.markdown("""
    Manage warehouse skid space capacities by location. This information is used for spatial
    optimization to ensure orders don't exceed available warehouse space.
    """)

    # Load current warehouse capacities
    from src.spatial_optimization import WarehouseCapacityManager, DimensionManager

    # Initialize managers
    dm = DimensionManager()
    cm = WarehouseCapacityManager(dm)

    # Load current capacities
    capacities = cm.load_warehouse_capacities()

    # Display current configuration
    st.subheader("Current Warehouse Capacities")

    if capacities:
        # Convert to DataFrame for display
        warehouse_data = []
        for location, space in capacities.items():
            warehouse_data.append({
                'Location': location,
                'Total Skids': space.total_skids,
                'Used Skids': space.used_skids,
                'Available Skids': space.available_skids,
                'Utilization %': f"{space.utilization_pct:.1f}",
                'Skid Length (cm)': space.skid_length_cm,
                'Skid Width (cm)': space.skid_width_cm,
                'Max Height (cm)': space.max_height_cm
            })

        df_warehouses = pd.DataFrame(warehouse_data)
        st.dataframe(df_warehouses, use_container_width=True, hide_index=True)

        # Visualization
        st.subheader("Capacity Utilization")

        for location, space in capacities.items():
            col1, col2 = st.columns([3, 1])

            with col1:
                # Progress bar for utilization
                st.progress(space.utilization_pct / 100)
                st.caption(f"{location}: {space.available_skids} skids available")

            with col2:
                st.metric(space.location, f"{space.utilization_pct:.1f}%")

        st.divider()

    # Edit/Add warehouse capacities
    st.subheader("Edit or Add Warehouse Capacities")

    with st.expander("➕ Add New Warehouse", expanded=False):
        with st.form("add_warehouse_form"):
            new_location = st.text_input(
                "Location Code",
                placeholder="e.g., CGY, TOR, EDM",
                help="3-4 letter location code"
            ).upper()

            new_total = st.number_input(
                "Total Skid Spaces",
                min_value=1,
                max_value=10000,
                value=100,
                help="Total number of skid spaces available"
            )

            new_used = st.number_input(
                "Used Skid Spaces",
                min_value=0,
                max_value=10000,
                value=0,
                help="Currently occupied skid spaces"
            )

            new_length = st.number_input(
                "Skid Length (cm)",
                min_value=50,
                max_value=300,
                value=120,
                help="Standard skid/pallet length"
            )

            new_width = st.number_input(
                "Skid Width (cm)",
                min_value=50,
                max_value=300,
                value=100,
                help="Standard skid/pallet width"
            )

            new_height = st.number_input(
                "Max Stack Height (cm)",
                min_value=100,
                max_value=500,
                value=150,
                help="Maximum stacking height"
            )

            submitted = st.form_submit_button("Add Warehouse")

            if submitted and new_location:
                filepath = Path("data/raw/warehouse_capacities.tsv")

                # Load existing data
                if filepath.exists():
                    df_existing = pd.read_csv(filepath, sep='\t')
                else:
                    df_existing = pd.DataFrame(columns=[
                        'Location', 'Total_Skids', 'Used_Skids',
                        'Skid_Length_cm', 'Skid_Width_cm', 'Max_Height_cm'
                    ])

                # Check if location already exists
                if new_location in df_existing['Location'].values:
                    st.error(f"❌ Location {new_location} already exists! Use the edit section below.")
                else:
                    # Add new warehouse
                    new_row = pd.DataFrame([{
                        'Location': new_location,
                        'Total_Skids': new_total,
                        'Used_Skids': new_used,
                        'Skid_Length_cm': new_length,
                        'Skid_Width_cm': new_width,
                        'Max_Height_cm': new_height
                    }])

                    df_updated = pd.concat([df_existing, new_row], ignore_index=True)
                    df_updated.to_csv(filepath, sep='\t', index=False)

                    st.success(f"✅ Added warehouse {new_location}!")
                    st.rerun()

    # Edit existing warehouses
    if capacities:
        st.subheader("Edit Existing Warehouses")

        # Select warehouse to edit
        locations = list(capacities.keys())
        selected_location = st.selectbox("Select warehouse to edit", locations)

        if selected_location:
            space = capacities[selected_location]

            with st.form(f"edit_warehouse_{selected_location}"):
                st.write(f"Editing: **{selected_location}**")

                edited_total = st.number_input(
                    "Total Skid Spaces",
                    min_value=float(space.used_skids) if space.used_skids is not None else 0.0,  # Can't be less than used
                    max_value=10000.0,
                    value=float(space.total_skids) if space.total_skids is not None else 100.0,
                    key=f"total_{selected_location}"
                )

                edited_used = st.number_input(
                    "Used Skid Spaces",
                    min_value=0.0,
                    max_value=float(edited_total) if edited_total is not None else 100.0,
                    value=float(space.used_skids) if space.used_skids is not None else 0.0,
                    key=f"used_{selected_location}"
                )

                edited_length = st.number_input(
                    "Skid Length (cm)",
                    min_value=50.0,
                    max_value=300.0,
                    value=float(space.skid_length_cm) if space.skid_length_cm is not None else 120.0,
                    key=f"length_{selected_location}"
                )

                edited_width = st.number_input(
                    "Skid Width (cm)",
                    min_value=50.0,
                    max_value=300.0,
                    value=float(space.skid_width_cm) if space.skid_width_cm is not None else 100.0,
                    key=f"width_{selected_location}"
                )

                edited_height = st.number_input(
                    "Max Stack Height (cm)",
                    min_value=100.0,
                    max_value=500.0,
                    value=float(space.max_height_cm) if space.max_height_cm is not None else 300.0,
                    key=f"height_{selected_location}"
                )

                col_save, col_delete = st.columns(2)

                with col_save:
                    save_submitted = st.form_submit_button("Save Changes")

                with col_delete:
                    delete_key = f'delete_{selected_location}'
                    if f'confirm_delete_{selected_location}' not in st.session_state:
                        st.session_state[f'confirm_delete_{selected_location}'] = False

                    delete_submitted = st.form_submit_button("Delete Warehouse")

                if save_submitted:
                    filepath = Path("data/raw/warehouse_capacities.tsv")
                    df_existing = pd.read_csv(filepath, sep='\t')

                    # Update row
                    mask = df_existing['Location'] == selected_location
                    df_existing.loc[mask, 'Total_Skids'] = edited_total
                    df_existing.loc[mask, 'Used_Skids'] = edited_used
                    df_existing.loc[mask, 'Skid_Length_cm'] = edited_length
                    df_existing.loc[mask, 'Skid_Width_cm'] = edited_width
                    df_existing.loc[mask, 'Max_Height_cm'] = edited_height

                    df_existing.to_csv(filepath, sep='\t', index=False)

                    st.success(f"✅ Updated {selected_location}!")
                    st.rerun()

                if delete_submitted:
                    if not st.session_state[f'confirm_delete_{selected_location}']:
                        st.session_state[f'confirm_delete_{selected_location}'] = True
                        st.error(f"⚠️ Click again to confirm deletion of {selected_location}")
                    else:
                        filepath = Path("data/raw/warehouse_capacities.tsv")
                        df_existing = pd.read_csv(filepath, sep='\t')

                        # Delete row
                        df_existing = df_existing[df_existing['Location'] != selected_location]
                        df_existing.to_csv(filepath, sep='\t', index=False)

                        st.success(f"✅ Deleted {selected_location}")
                        st.rerun()

    # Import/Export functionality
    st.divider()
    st.subheader("Import/Export")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📥 Export to TSV", key='export_warehouse'):
            filepath = Path("data/raw/warehouse_capacities.tsv")
            if filepath.exists():
                with open(filepath, 'rb') as f:
                    st.download_button(
                        label="Download warehouse_capacities.tsv",
                        data=f,
                        file_name="warehouse_capacities.tsv",
                        mime="text/tab-separated-values",
                        key='download_warehouse_tsv'
                    )
            else:
                st.warning("No warehouse data to export")

    with col2:
        st.write("**Import from TSV**")
        uploaded_file = st.file_uploader(
            "Upload warehouse_capacities.tsv",
            type=['tsv'],
            help="Replace existing warehouse data",
            key='upload_warehouse_tsv'
        )

        if uploaded_file:
            # Save uploaded file
            filepath = Path("data/raw/warehouse_capacities.tsv")
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'wb') as f:
                f.write(uploaded_file.getbuffer())

            st.success("✅ Warehouse data imported!")
            st.rerun()

    # Instructions
    st.divider()
    st.info("""
    💡 **Tips:**
    - **Location Code**: Use 3-4 letter codes (CGY, TOR, EDM, etc.)
    - **Skid Dimensions**: Standard sizes are 120x100cm with 150cm max height
    - **Used Skids**: This is calculated from current stock, but can be manually overridden
    - **Utilization**: Shows % of warehouse space currently occupied
    - **Import/Export**: Use TSV files to backup or transfer warehouse configurations
    """)


# ============================================
# TAB 6: Vendor Performance
# ============================================
with tab6:
    st.header("🏢 Vendor Performance Analytics")
    st.markdown("""
    Analyze vendor lead time performance, identify fastest suppliers, and make data-driven sourcing decisions.
    """)

    # Check if vendor data is available
    vendor_data = data.get('vendor', {})

    if not vendor_data or 'vendor_perf' not in vendor_data:
        st.warning("⚠️ No vendor performance data available. This feature requires supply history with vendor information.")
        st.info("💡 Ensure your supply.tsv file includes VendorCode and lead_time_days columns.")
    else:
        vendor_perf = vendor_data['vendor_perf']
        vendor_stats = vendor_data['vendor_stats']
        fastest_vendors = vendor_data.get('fastest_vendors', pd.DataFrame())
        item_vendor_stats = vendor_data.get('item_vendor_stats', pd.DataFrame())

        # KPI Cards
        st.subheader("📊 Vendor Performance Overview")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_vendors = len(vendor_perf)
            st.metric("Total Vendors", total_vendors)

        with col2:
            if len(vendor_perf) > 0:
                top_vendor = vendor_perf.iloc[0]
                st.metric("Top Vendor", f"{top_vendor['VendorCode']} ({top_vendor['overall_score']:.0f}/100)")

        with col3:
            avg_lead_time = vendor_stats['median_lead_time'].mean()
            st.metric("Avg Lead Time", f"{avg_lead_time:.1f} days")

        with col4:
            multi_vendor_items = fastest_vendors['vendor_options'].gt(1).sum() if len(fastest_vendors) > 0 else 0
            st.metric("Items with Multi-Vendor", multi_vendor_items)

        st.divider()

        # Vendor Leaderboard
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🏆 Vendor Leaderboard")

            # Display top vendors
            display_cols = ['rank', 'VendorCode', 'overall_score', 'speed_score',
                           'consistency_score', 'median_lead_time', 'count', 'unique_items']

            display_df = vendor_perf[display_cols].copy()
            display_df.columns = ['Rank', 'Vendor', 'Score', 'Speed',
                                 'Consistency', 'Lead Time (days)', 'Orders', 'Items']

            # Highlight top 3
            def highlight_top3(val):
                if isinstance(val, int) and val <= 3:
                    return ['background-color: #90EE90' if val == 1 else
                            'background-color: #FFD700' if val == 2 else
                            'background-color: #FFA500' if val == 3 else '' for _ in val]
                return ['' for _ in val]

            styled_df = display_df.style.apply(highlight_top3, subset=['Rank'])
            st.dataframe(styled_df, use_container_width=True, height=300)

        with col2:
            st.subheader("⚡ Fastest Vendors by Category")

            # Fastest by lead time
            if len(vendor_stats) > 0:
                fastest = vendor_stats.nsmallest(5, 'median_lead_time')[['VendorCode', 'median_lead_time', 'count']]
                fastest.columns = ['Vendor', 'Avg Lead Time', 'Orders']
                st.dataframe(fastest, use_container_width=True)

                # Most reliable (lowest CV)
                st.markdown("**Most Consistent Vendors:**")
                reliable = vendor_stats.nsmallest(5, 'cv')[['VendorCode', 'cv', 'count']]
                reliable.columns = ['Vendor', 'CV (lower=better)', 'Orders']
                st.dataframe(reliable, use_container_width=True)

        st.divider()

        # Item-Vendor Analysis
        st.subheader("🔍 Item-Vendor Lead Time Details")

        if len(item_vendor_stats) > 0:
            # Add filters
            col1, col2, col3 = st.columns(3)

            with col1:
                search_item = st.text_input("Search by Item Code", key='vendor_search_item')

            with col2:
                min_confidence = st.slider(
                    "Minimum Confidence (sample size)",
                    min_value=1,
                    max_value=20,
                    value=3,
                    help="Minimum number of observations to trust item-vendor specific data",
                    key='vendor_min_conf'
                )

            with col3:
                show_fallback_only = st.checkbox("Show vendor fallbacks only", value=False, key='vendor_fallback')

            # Filter data
            filtered = item_vendor_stats.copy()

            if search_item:
                filtered = filtered[filtered['ItemCode'].str.contains(search_item, case=False, na=False)]

            if min_confidence:
                filtered = filtered[filtered['count'] >= min_confidence]

            if show_fallback_only:
                filtered = filtered[filtered['use_fallback'] == True]

            # Display
            if len(filtered) > 0:
                display_cols = ['ItemCode', 'VendorCode', 'effective_mean_lead_time',
                               'mean_lead_time', 'use_fallback', 'count', 'cv']
                display_df = filtered[display_cols].copy()
                display_df.columns = ['Item', 'Vendor', 'Effective Lead Time',
                                     'Item-Vendor Avg', 'Using Fallback', 'Samples', 'CV']

                # Color code fallback rows
                def highlight_fallback(row):
                    if row['Using Fallback']:
                        return ['background-color: #FFE4B5' for _ in range(len(row))]
                    return ['' for _ in range(len(row))]

                styled_df = display_df.style.apply(highlight_fallback, axis=1)
                st.dataframe(styled_df, use_container_width=True)
            else:
                st.info("No results match your filters.")

        st.divider()

        # Vendor Comparison Tool
        st.subheader("🔄 Compare Vendors")

        if len(vendor_stats) > 1:
            col1, col2 = st.columns(2)

            with col1:
                vendor_a = st.selectbox("Select Vendor A", vendor_stats['VendorCode'].unique(), key='compare_vendor_a')

            with col2:
                vendor_b = st.selectbox("Select Vendor B",
                                      [v for v in vendor_stats['VendorCode'].unique() if v != vendor_a],
                                      key='compare_vendor_b')

            if vendor_a and vendor_b:
                # Compare metrics
                v_a_data = vendor_stats[vendor_stats['VendorCode'] == vendor_a].iloc[0]
                v_b_data = vendor_stats[vendor_stats['VendorCode'] == vendor_b].iloc[0]

                comparison_df = pd.DataFrame({
                    'Metric': ['Median Lead Time', 'Mean Lead Time', 'Std Dev', 'CV (Consistency)',
                             'Total Orders', 'Unique Items'],
                    vendor_a: [
                        f"{v_a_data['median_lead_time']:.1f} days",
                        f"{v_a_data['mean_lead_time']:.1f} days",
                        f"{v_a_data['std_lead_time']:.1f}" if pd.notna(v_a_data['std_lead_time']) else 'N/A',
                        f"{v_a_data['cv']:.2f}",
                        int(v_a_data['count']),
                        0  # Will add item coverage later
                    ],
                    vendor_b: [
                        f"{v_b_data['median_lead_time']:.1f} days",
                        f"{v_b_data['mean_lead_time']:.1f} days",
                        f"{v_b_data['std_lead_time']:.1f}" if pd.notna(v_b_data['std_lead_time']) else 'N/A',
                        f"{v_b_data['cv']:.2f}",
                        int(v_b_data['count']),
                        0
                    ]
                })

                st.dataframe(comparison_df, use_container_width=True)

                # Winner highlight
                if v_a_data['median_lead_time'] < v_b_data['median_lead_time']:
                    st.success(f"🏆 {vendor_a} is faster by {v_b_data['median_lead_time'] - v_a_data['median_lead_time']:.1f} days")
                else:
                    st.success(f"🏆 {vendor_b} is faster by {v_a_data['median_lead_time'] - v_b_data['median_lead_time']:.1f} days")

        st.divider()

        # Export vendor data
        st.subheader("📥 Export Vendor Data")

        export_format = st.radio("Select format", ["CSV", "TSV"], horizontal=True, key='vendor_export_format')

        if st.button("Download Vendor Performance Report", key='download_vendor_report'):
            # Create export dataframe
            export_df = vendor_perf.copy()

            if export_format == "CSV":
                csv = export_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="vendor_performance.csv",
                    mime="text/csv",
                    key='download_vendor_csv'
                )
            else:
                tsv = export_df.to_csv(sep='\t', index=False)
                st.download_button(
                    label="Download TSV",
                    data=tsv,
                    file_name="vendor_performance.tsv",
                    mime="text/tab-separated-values",
                    key='download_vendor_tsv'
                )


# ============================================
# TAB 7: Data Quality Dashboard
# ============================================
with tab7:
    st.header("🔍 Data Quality Dashboard")
    st.markdown("""
    This dashboard shows data quality metrics, UOM conversion status, and system health.
    Use this to identify data issues that may affect forecast accuracy.
    """)

    # Perform UOM validation
    from src.uom_conversion_sap import validate_sap_uom_data
    uom_validation = validate_sap_uom_data(data['items'])

    # Create subtabs for different quality aspects
    dq_tab1, dq_tab2, dq_tab3 = st.tabs(["📊 Data Completeness", "🔧 UOM Issues", "📈 System Metrics"])

    with dq_tab1:
        st.subheader("📊 Data Completeness")

        # Calculate completeness metrics
        total_items = len(data['items'])
        items_with_sales = data['sales']['item_code'].nunique()
        items_with_history = data['history']['ItemCode'].nunique() if len(data['history']) > 0 else 0
        items_with_forecasts = len(data['forecasts'])

        # Create metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Items", f"{total_items:,}")
        with col2:
            st.metric("With Sales Data", f"{items_with_sales:,}",
                     f"{100*items_with_sales/total_items:.0f}%")
        with col3:
            st.metric("With History", f"{items_with_history:,}",
                     f"{100*items_with_history/total_items:.0f}%")
        with col4:
            st.metric("With Forecasts", f"{items_with_forecasts:,}",
                     f"{100*items_with_forecasts/total_items:.0f}%")

        st.divider()

        # Missing data analysis
        st.subheader("Items Missing Key Data")

        # Items without sales
        items_no_sales = data['items'][~data['items']['Item No.'].isin(data['sales']['item_code'])]
        # Items without history
        items_no_history = data['items'][~data['items']['Item No.'].isin(data['history']['ItemCode'])]
        # Items without forecasts
        items_no_forecasts = data['items'][~data['items']['Item No.'].isin(data['forecasts']['item_code'])]

        missing_col1, missing_col2 = st.columns(2)

        with missing_col1:
            st.markdown("### ❌ No Sales Data (Last 12 Months)")
            if len(items_no_sales) > 0:
                st.warning(f"{len(items_no_sales)} items have no sales data in the last 12 months")
                with st.expander("View items without sales data"):
                    # Check which stock column is available
                    if 'CurrentStock_SalesUOM' in data['items'].columns:
                        display_cols = ['Item No.', 'Item Description', 'Warehouse', 'CurrentStock_SalesUOM']
                    else:
                        display_cols = ['Item No.', 'Item Description', 'Warehouse']
                    st.dataframe(
                        items_no_sales[display_cols]
                        .head(100)
                    )
            else:
                st.success("✅ All items have sales data")

        with missing_col2:
            st.markdown("### 📦 No Stock Position")
            # Check which stock column to use
            stock_col = 'CurrentStock_SalesUOM' if 'CurrentStock_SalesUOM' in data['items'].columns else 'CurrentStock'
            items_no_stock = data['items'][data['items'][stock_col] == 0]
            if len(items_no_stock) > 0:
                st.warning(f"{len(items_no_stock)} items have zero stock")
                with st.expander("View items with zero stock"):
                    st.dataframe(
                        items_no_stock[['Item No.', 'Item Description', 'Warehouse', 'SalesUoM']]
                        .head(100)
                    )
            else:
                st.success("✅ All items have stock")

    with dq_tab2:
        st.subheader("🔧 UOM Conversion Issues")

        # Display UOM validation results
        if uom_validation.get('missing_uom_fields'):
            st.error(f"❌ Missing UOM Fields: {uom_validation['missing_uom_fields']}")
            st.info("Please update items.tsv export from Query 3 to include: BaseUoM, SalesUoM, QtyPerSalesUoM")
        else:
            st.success("✅ All required UOM fields present")

        st.divider()

        # Conversion factor issues
        invalid_count = len(uom_validation.get('invalid_conversion_factors', []))
        zero_count = len(uom_validation.get('zero_conversion_factor', []))
        extreme_count = len(uom_validation.get('extreme_conversion_factors', []))

        issue_col1, issue_col2, issue_col3 = st.columns(3)

        with issue_col1:
            if invalid_count > 0:
                st.error(f"Invalid: {invalid_count}")
                st.caption("Items with non-numeric conversion factors")
            else:
                st.success("✅ Valid: 0")

        with issue_col2:
            if zero_count > 0:
                st.warning(f"Zero: {zero_count}")
                st.caption("Items with conversion factor = 0")
            else:
                st.success("✅ Zero: 0")

        with issue_col3:
            if extreme_count > 0:
                st.warning(f"Extreme: {extreme_count}")
                st.caption("Items with unusual conversion factors")
            else:
                st.success("✅ Extreme: 0")

        # Show items with issues
        if invalid_count > 0 or zero_count > 0:
            with st.expander("View items with UOM issues"):
                issue_items = []

                if invalid_count > 0:
                    for item_code in uom_validation['invalid_conversion_factors']:
                        item_data = data['items'][data['items']['Item No.'] == item_code]
                        if len(item_data) > 0:
                            issue_items.append({
                                'Item Code': item_code,
                                'Issue': 'Invalid conversion factor (NaN)',
                                'BaseUoM': item_data.iloc[0]['BaseUoM'],
                                'SalesUoM': item_data.iloc[0]['SalesUoM']
                            })

                if zero_count > 0:
                    for item_code in uom_validation['zero_conversion_factor']:
                        item_data = data['items'][data['items']['Item No.'] == item_code]
                        if len(item_data) > 0:
                            issue_items.append({
                                'Item Code': item_code,
                                'Issue': 'Conversion factor = 0',
                                'BaseUoM': item_data.iloc[0]['BaseUoM'],
                                'SalesUoM': item_data.iloc[0]['SalesUoM']
                            })

                if issue_items:
                    st.dataframe(pd.DataFrame(issue_items))

        st.divider()

        # UOM conversion summary
        st.subheader("UOM Conversion Summary")
        converted_count = data['items']['ConversionFactor'].notna().sum()
        conversion_col1, conversion_col2, conversion_col3 = st.columns(3)

        with conversion_col1:
            st.metric("Items Converted", f"{converted_count:,}")
        with conversion_col2:
            avg_factor = data['items']['ConversionFactor'].mean()
            st.metric("Avg Conversion Factor", f"{avg_factor:.2f}")
        with conversion_col3:
            pail_count = (data['items']['SalesUoM'] == 'Pail').sum()
            drum_count = (data['items']['SalesUoM'] == 'Drum').sum()
            st.metric("Pails/Drums", f"{pail_count:,} / {drum_count:,}")

    with dq_tab3:
        st.subheader("📈 System Metrics")

        # Cache information
        from src.cache_manager import get_cache_info
        cache_info = get_cache_info()

        cache_col1, cache_col2, cache_col3 = st.columns(3)

        with cache_col1:
            cache_status = "✅ Valid" if cache_info.get('valid') else "❌ Invalid"
            st.metric("Cache Status", cache_status)
        with cache_col2:
            if cache_info.get('age_hours'):
                st.metric("Cache Age", f"{cache_info['age_hours']:.1f} hours")
            else:
                st.metric("Cache Age", "N/A")
        with cache_col3:
            st.metric("Cached Items", f"{cache_info.get('item_count', 0):,}")

        st.divider()

        # Data freshness
        st.subheader("📅 Data Freshness")

        # Get data file modification times
        data_dir = Path("data/raw")
        if data_dir.exists():
            file_times = []
            for file in ["sales.tsv", "supply.tsv", "items.tsv"]:
                filepath = data_dir / file
                if filepath.exists():
                    mtime = filepath.stat().st_mtime
                    from datetime import datetime
                    file_dt = datetime.fromtimestamp(mtime)
                    file_times.append({
                        'File': file,
                        'Last Updated': file_dt.strftime('%Y-%m-%d %H:%M'),
                        'Age (hours)': (pd.Timestamp.now() - pd.Timestamp(file_dt)).total_seconds() / 3600
                    })

            if file_times:
                st.dataframe(pd.DataFrame(file_times))

        st.divider()

        # Forecast model distribution
        st.subheader("🤖 Forecast Model Distribution")
        if len(data['forecasts']) > 0:
            model_counts = data['forecasts']['winning_model'].value_counts()
            model_dist_col1, model_dist_col2 = st.columns(2)

            with model_dist_col1:
                st.dataframe(model_counts.to_frame('Count'))

            with model_dist_col2:
                # Simple bar chart
                import plotly.express as px
                fig = px.bar(
                    x=model_counts.index,
                    y=model_counts.values,
                    labels={'x': 'Model', 'y': 'Items'},
                    title='Model Usage',
                    color=model_counts.index,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Forecast Accuracy Tracking
        st.subheader("📈 Forecast Accuracy Tracking")

        if len(data['forecasts']) > 0:
            # Calculate accuracy metrics for each item
            accuracy_data = []

            for _, row in data['forecasts'].iterrows():
                item_code = row['item_code']
                winning_model = row['winning_model']

                # Get RMSE for the winning model
                rmse_col = f'rmse_{winning_model}'
                if rmse_col in row and pd.notna(row[rmse_col]):
                    rmse = row[rmse_col]

                    # Get the forecast period demand (total forecasted)
                    forecast_cols = [f'forecast_month_{i}' for i in range(1, 7)]
                    forecast_period_demand = row[forecast_cols].fillna(0).sum()

                    # Calculate MAPE (Mean Absolute Percentage Error)
                    # MAPE = (RMSE / Avg_Demand) * 100
                    # Use forecast period demand / forecast horizon as average demand
                    forecast_horizon = row.get('forecast_horizon', 6)
                    avg_demand = forecast_period_demand / forecast_horizon if forecast_horizon > 0 else 1

                    if avg_demand > 0:
                        mape = (rmse / avg_demand) * 100
                    else:
                        mape = 0

                    # Calculate accuracy percentage
                    accuracy = max(0, 100 - mape)

                    # Determine accuracy tier
                    if accuracy >= 90:
                        tier = 'Excellent'
                        tier_color = '🟢'
                    elif accuracy >= 80:
                        tier = 'Good'
                        tier_color = '🟡'
                    elif accuracy >= 70:
                        tier = 'Fair'
                        tier_color = '🟠'
                    else:
                        tier = 'Poor'
                        tier_color = '🔴'

                    accuracy_data.append({
                        'Item Code': item_code,
                        'Model': winning_model,
                        'RMSE': f'{rmse:.2f}',
                        'MAPE (%)': f'{mape:.1f}',
                        'Accuracy (%)': f'{accuracy:.1f}',
                        'Tier': f'{tier_color} {tier}'
                    })

            if accuracy_data:
                df_accuracy = pd.DataFrame(accuracy_data)

                # Show summary metrics
                acc_col1, acc_col2, acc_col3 = st.columns(3)

                with acc_col1:
                    avg_accuracy = df_accuracy['Accuracy (%)'].str.rstrip('%').astype(float).mean()
                    st.metric("Avg Forecast Accuracy", f"{avg_accuracy:.1f}%")

                with acc_col2:
                    excellent_count = len(df_accuracy[df_accuracy['Tier'].str.contains('Excellent')])
                    st.metric("Excellent (≥90%)", excellent_count)

                with acc_col3:
                    poor_count = len(df_accuracy[df_accuracy['Tier'].str.contains('Poor')])
                    st.metric("Poor (<70%)", poor_count)

                # Show accuracy table
                with st.expander("View detailed accuracy metrics", expanded=False):
                    # Allow sorting and filtering
                    sort_by_acc = st.selectbox(
                        "Sort by",
                        ['Accuracy (%)', 'RMSE', 'MAPE (%)', 'Model', 'Tier'],
                        key='accuracy_sort'
                    )

                    if sort_by_acc == 'RMSE':
                        df_accuracy['RMSE_num'] = df_accuracy['RMSE'].astype(float)
                        df_display = df_accuracy.sort_values('RMSE_num', ascending=True, na_position='last')
                    elif sort_by_acc == 'MAPE (%)':
                        df_accuracy['MAPE_num'] = df_accuracy['MAPE (%)'].str.rstrip('%').astype(float)
                        df_display = df_accuracy.sort_values('MAPE_num', ascending=False, na_position='last')
                    elif sort_by_acc == 'Accuracy (%)':
                        df_accuracy['Accuracy_num'] = df_accuracy['Accuracy (%)'].str.rstrip('%').astype(float)
                        df_display = df_accuracy.sort_values('Accuracy_num', ascending=False, na_position='last')
                    else:
                        df_display = df_accuracy.sort_values(sort_by_acc, na_position='last')

                    st.dataframe(
                        df_display[['Item Code', 'Model', 'RMSE', 'MAPE (%)', 'Accuracy (%)', 'Tier']],
                        use_container_width=True,
                        height=300
                    )

                # Show accuracy distribution chart
                acc_chart_col1, acc_chart_col2 = st.columns(2)

                with acc_chart_col1:
                    # Accuracy tier distribution
                    tier_counts = df_accuracy['Tier'].str.replace('🟢 ', '').replace('🟡 ', '').replace('🟠 ', '').replace('🔴 ', '').value_counts()

                    fig = px.pie(
                        values=tier_counts.values,
                        names=tier_counts.index,
                        title='Accuracy Tier Distribution',
                        hole=0.4,
                        color_discrete_sequence=['#00cc00', '#cccc00', '#ff9900', '#ff0000']
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)

                with acc_chart_col2:
                    # Accuracy by model
                    model_accuracy = df_accuracy.groupby('Model')['Accuracy (%)'].apply(
                        lambda x: x.str.rstrip('%').astype(float).mean()
                    ).reset_index()

                    fig = px.bar(
                        x=model_accuracy['Model'],
                        y=model_accuracy['Accuracy (%)'],
                        title='Average Accuracy by Model',
                        labels={'Model': 'Model', 'Accuracy (%)': 'Accuracy (%)'},
                        color=model_accuracy['Accuracy (%)'],
                        color_continuous_scale='Greens'
                    )
                    fig.update_layout(yaxis_range=[0, 100], showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No forecast accuracy data available")
        else:
            st.info("No forecasts available for accuracy tracking")

# Footer
st.divider()
# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p><strong>SAP B1 Inventory & Forecast Analyzer v1.0</strong></p>
    <p>Built with Streamlit, Pandas, & Prophet</p>
    <p style='font-size: 0.8rem;'>© 2025 - For Internal Use Only</p>
</div>
""", unsafe_allow_html=True)
