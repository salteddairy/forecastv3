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
        item_list = sorted(data['forecasts']['item_code'].unique())
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
    df_item_forecast = data['forecasts'][data['forecasts']['item_code'] == selected_item].iloc[0]

    # Get historical sales for this item
    df_sales_item = data['sales'][data['sales']['item_code'] == selected_item].copy()
    df_sales_item['date'] = pd.to_datetime(df_sales_item['date'], errors='coerce')
    df_sales_item['qty'] = pd.to_numeric(df_sales_item['qty'], errors='coerce')

    # Aggregate monthly
    df_sales_monthly = df_sales_item.groupby(df_sales_item['date'].dt.to_period('M'))['qty'].sum().reset_index()
    df_sales_monthly['date'] = df_sales_monthly['date'].dt.to_timestamp()

    # Get item details
    item_details = data['items'][data['items']['Item No.'] == selected_item].iloc[0] if len(data['items'][data['items']['Item No.'] == selected_item]) > 0 else None

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
                    latest_accuracy = item_accuracy.sort_values('snapshot_date').iloc[-1]

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
                        accuracy_trend = item_accuracy.sort_values('snapshot_date')[['snapshot_date', 'mape']].copy()
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
