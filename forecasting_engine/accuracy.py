"""
Accuracy tracking module - database-based.
Converts file-based tracking from src/forecast_accuracy.py to database writes.
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy import text

from forecasting_engine.db import get_session
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


def calculate_accuracy_metrics(
    train: pd.Series,
    test: pd.Series,
    forecast_model,
    forecast_horizon: int = 12
) -> Dict:
    """
    Calculate accuracy metrics by comparing forecast to actuals.

    Parameters:
    -----------
    train : pd.Series
        Training data (monthly time series)
    test : pd.Series
        Test data (actuals to compare against)
    forecast_model
        Forecasting model with forecast() method
    forecast_horizon : int
        Number of months forecast

    Returns:
    --------
    Dict
        Accuracy metrics: mape, rmse, bias, mae
        {
            'mape': float or None,
            'rmse': float,
            'bias': float,
            'mae': float
        }
    """
    if len(test) == 0:
        logger.warning("No test data available for accuracy calculation")
        return {
            'mape': None,
            'rmse': None,
            'bias': None,
            'mae': None
        }

    # Generate forecast for test period
    forecast, _ = forecast_model.forecast(train, test, forecast_horizon=min(forecast_horizon, len(test)))

    # Truncate to test length
    forecast = forecast[:len(test)]

    # Calculate metrics
    actual = test.values

    # MAPE (Mean Absolute Percentage Error) - skip zeros
    non_zero_mask = actual != 0
    if non_zero_mask.any():
        mape = np.mean(np.abs((actual[non_zero_mask] - forecast[non_zero_mask]) / actual[non_zero_mask])) * 100
    else:
        mape = None

    # RMSE (Root Mean Square Error)
    rmse = np.sqrt(np.mean((actual - forecast) ** 2))

    # Bias (mean forecast error) - positive = over-forecast
    bias = np.mean(forecast - actual)

    # MAE (Mean Absolute Error)
    mae = np.mean(np.abs(actual - forecast))

    # Tracking Signal (cumulative forecast error / MAD)
    # Values > 3 or < -3 indicate bias issues
    cumulative_error = np.sum(forecast - actual)
    mad = mae
    tracking_signal = cumulative_error / mad if mad > 0 else np.nan

    return {
        'mape': round(float(mape), 2) if mape is not None and not np.isnan(mape) else None,
        'rmse': round(float(rmse), 2) if not np.isnan(rmse) else None,
        'bias': round(float(bias), 2) if not np.isnan(bias) else None,
        'mae': round(float(mae), 2) if not np.isnan(mae) else None,
        'tracking_signal': round(float(tracking_signal), 2) if not np.isnan(tracking_signal) else None
    }


def write_accuracy_to_db(
    item_code: str,
    forecast_generated_at: datetime,
    winning_model: str,
    forecast_confidence_pct: float,
    metrics: Dict,
    months_compared: int,
    forecast_horizon: int = 12
) -> bool:
    """
    Write accuracy metrics to database.

    Parameters:
    -----------
    item_code : str
        Item code
    forecast_generated_at : datetime
        When forecast was generated
    winning_model : str
        Which model won the tournament
    forecast_confidence_pct : float
        Forecast confidence percentage
    metrics : Dict
        Accuracy metrics (mape, rmse, bias, mae)
    months_compared : int
        Number of months compared
    forecast_horizon : int
        Forecast horizon in months

    Returns:
    --------
    bool
        True if write successful
    """
    query = text("""
        INSERT INTO forecast_accuracy (
            item_code,
            forecast_generated_at,
            winning_model,
            forecast_confidence_pct,
            months_compared,
            forecast_horizon,
            mape,
            rmse,
            bias,
            mae,
            total_forecast,
            total_actual,
            created_at
        ) VALUES (
            :item_code,
            :forecast_generated_at,
            :winning_model,
            :forecast_confidence_pct,
            :months_compared,
            :forecast_horizon,
            :mape,
            :rmse,
            :bias,
            :mae,
            :total_forecast,
            :total_actual,
            NOW()
        )
    """)

    try:
        with get_session() as session:
            session.execute(query, {
                "item_code": item_code,
                "forecast_generated_at": forecast_generated_at,
                "winning_model": winning_model,
                "forecast_confidence_pct": forecast_confidence_pct,
                "months_compared": months_compared,
                "forecast_horizon": forecast_horizon,
                "mape": metrics.get('mape'),
                "rmse": metrics.get('rmse'),
                "bias": metrics.get('bias'),
                "mae": metrics.get('mae'),
                "total_forecast": 0,  # Will update when comparing to actuals
                "total_actual": 0
            })
            session.commit()

        logger.debug(f"Wrote accuracy metrics for {item_code}")
        return True

    except Exception as e:
        logger.error(f"Failed to write accuracy metrics for {item_code}: {e}")
        return False


def update_accuracy_with_actuals(
    item_code: str,
    forecast_generated_at: datetime,
    months_to_compare: int = 3,
    source: str = "database"
) -> bool:
    """
    Update accuracy metrics by comparing previous forecast to actual sales.

    This is run 1+ months after forecast was generated to compare
    predictions to what actually happened.

    Parameters:
    -----------
    item_code : str
        Item code
    forecast_generated_at : datetime
        When forecast was generated
    months_to_compare : int
        Number of months to compare (default: 3)
    source : str
        Data source for actual sales ("database" or "local")

    Returns:
    --------
    bool
        True if update successful
    """
    # Get forecast
    query_forecast = text("""
        SELECT * FROM forecasts
        WHERE item_code = :item_code
          AND forecast_generated_at = :forecast_generated_at
    """)

    # Get actual sales query
    if source == "database":
        query_sales = text("""
            SELECT
                DATE_TRUNC('month', posting_date) as month,
                SUM(ordered_qty) as quantity
            FROM sales_orders
            WHERE item_code = :item_code
              AND posting_date >= :start_date
              AND posting_date < :end_date
              AND NOT is_linked_special_order
            GROUP BY DATE_TRUNC('month', posting_date)
            ORDER BY month
        """)
    else:
        # For local testing - return empty
        logger.warning(f"Local source not implemented for update_accuracy_with_actuals")
        return False

    try:
        with get_session() as session:
            # Get forecast
            result = session.execute(query_forecast, {
                "item_code": item_code,
                "forecast_generated_at": forecast_generated_at
            })
            forecast_row = result.fetchone()

            if not forecast_row:
                logger.warning(f"Forecast not found for {item_code} at {forecast_generated_at}")
                return False

            # Get actual sales
            start_date = forecast_generated_at
            end_date = forecast_generated_at + pd.DateOffset(months=months_to_compare)

            result = session.execute(query_sales, {
                "item_code": item_code,
                "start_date": start_date,
                "end_date": end_date
            })
            actual_sales = result.fetchall()

            if not actual_sales:
                logger.warning(f"No actual sales found for {item_code} in comparison period")
                return False

            # Compare forecast to actual
            total_forecast = 0
            total_actual = 0
            errors = []

            for i, actual_row in enumerate(actual_sales, 1):
                month_key = f'forecast_month_{i}'
                forecast_value = getattr(forecast_row, month_key, 0)
                actual_value = actual_row[1]

                if forecast_value is not None and actual_value is not None:
                    total_forecast += forecast_value
                    total_actual += actual_value
                    errors.append(forecast_value - actual_value)

            if errors:
                # Calculate metrics
                mape = np.mean(np.abs(np.array(errors) / np.array([r[1] for r in actual_sales if r[1] != 0]))) * 100
                rmse = np.sqrt(np.mean(np.array(errors) ** 2))
                bias = np.mean(errors)
                mae = np.mean(np.abs(errors))

                # Update accuracy record
                update_query = text("""
                    UPDATE forecast_accuracy
                    SET
                        total_forecast = :total_forecast,
                        total_actual = :total_actual
                    WHERE item_code = :item_code
                      AND forecast_generated_at = :forecast_generated_at
                """)

                session.execute(update_query, {
                    "total_forecast": total_forecast,
                    "total_actual": total_actual,
                    "item_code": item_code,
                    "forecast_generated_at": forecast_generated_at
                })
                session.commit()

                logger.info(f"Updated accuracy for {item_code}: MAPE={mape:.2f}%, RMSE={rmse:.2f}")
                return True

    except Exception as e:
        logger.error(f"Failed to update accuracy for {item_code}: {e}")
        return False

    return False


def get_accuracy_summary(
    df_accuracy: pd.DataFrame
) -> Dict:
    """
    Generate summary statistics from accuracy metrics.

    Parameters:
    -----------
    df_accuracy : pd.DataFrame
        Accuracy metrics DataFrame

    Returns:
    --------
    Dict
        Summary statistics
    """
    if df_accuracy.empty:
        return {}

    # Filter to rows with valid MAPE
    valid_mape = df_accuracy[df_accuracy['mape'].notna()]

    summary = {
        'total_items': len(df_accuracy),
        'avg_mape': float(valid_mape['mape'].mean()) if len(valid_mape) > 0 else None,
        'median_mape': float(valid_mape['mape'].median()) if len(valid_mape) > 0 else None,
        'avg_rmse': float(df_accuracy['rmse'].mean()) if 'rmse' in df_accuracy.columns and df_accuracy['rmse'].notna().any() else None,
        'avg_bias': float(df_accuracy['bias'].mean()) if 'bias' in df_accuracy.columns and df_accuracy['bias'].notna().any() else None,
        'model_distribution': df_accuracy['winning_model'].value_counts().to_dict() if 'winning_model' in df_accuracy.columns else {},
        'accuracy_categories': {
            'excellent': ((valid_mape['mape'] < 10) & (valid_mape['mape'].notna())).sum(),
            'good': ((valid_mape['mape'] >= 10) & (valid_mape['mape'] < 20)).sum(),
            'fair': ((valid_mape['mape'] >= 20) & (valid_mape['mape'] < 30)).sum(),
            'poor': (valid_mape['mape'] >= 30).sum()
        } if len(valid_mape) > 0 else {}
    }

    return summary


def calculate_backtest_metrics_from_forecast(
    forecast_result: Dict,
    test_actuals: pd.Series
) -> Dict:
    """
    Calculate accuracy metrics from tournament forecast result vs actuals.

    Parameters:
    -----------
    forecast_result : Dict
        Result from run_tournament_for_item()
    test_actuals : pd.Series
        Actual values for test period

    Returns:
    --------
    Dict
        Accuracy metrics
    """
    # Extract forecast months
    forecast_values = []
    for i in range(1, len(test_actuals) + 1):
        key = f'forecast_month_{i}'
        val = forecast_result.get(key)
        if val is not None:
            forecast_values.append(val)
        else:
            # If forecast is missing, use 0
            forecast_values.append(0)

    forecast_arr = np.array(forecast_values)
    actual_arr = test_actuals.values

    # Calculate metrics
    non_zero_mask = actual_arr != 0
    if non_zero_mask.any():
        mape = np.mean(np.abs((actual_arr[non_zero_mask] - forecast_arr[non_zero_mask]) / actual_arr[non_zero_mask])) * 100
    else:
        mape = None

    rmse = np.sqrt(np.mean((actual_arr - forecast_arr) ** 2))
    bias = np.mean(forecast_arr - actual_arr)
    mae = np.mean(np.abs(actual_arr - forecast_arr))

    return {
        'mape': round(float(mape), 2) if mape is not None and not np.isnan(mape) else None,
        'rmse': round(float(rmse), 2) if not np.isnan(rmse) else None,
        'bias': round(float(bias), 2) if not np.isnan(bias) else None,
        'mae': round(float(mae), 2) if not np.isnan(mae) else None
    }


def batch_calculate_accuracy(
    df_forecasts: pd.DataFrame,
    df_sales: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate accuracy metrics for multiple forecasts.

    Parameters:
    -----------
    df_forecasts : pd.DataFrame
        Forecast results from run_tournament()
    df_sales : pd.DataFrame
        Sales data with actual values

    Returns:
    --------
    pd.DataFrame
        Accuracy metrics for each forecast
    """
    accuracy_records = []

    for _, forecast_row in df_forecasts.iterrows():
        item_code = forecast_row['item_code']

        # Get sales data for this item
        item_sales = df_sales[df_sales['item_code'] == item_code].copy()
        if item_sales.empty:
            continue

        # Prepare monthly data
        item_sales['year_month'] = item_sales['date'].dt.to_period('M')
        monthly_sales = item_sales.groupby('year_month')['qty'].sum()

        # Ensure complete index
        if len(monthly_sales) > 0:
            full_index = pd.period_range(
                monthly_sales.index.min(),
                monthly_sales.index.max(),
                freq='M'
            )
            monthly_sales = monthly_sales.reindex(full_index, fill_value=0)

        # Get train/test months from forecast result
        train_months = forecast_row.get('train_months')
        test_months = forecast_row.get('test_months')

        # Convert to int if they're valid numbers, otherwise skip
        try:
            train_months = int(train_months) if pd.notna(train_months) else None
            test_months = int(test_months) if pd.notna(test_months) else None
        except (ValueError, TypeError):
            continue

        if train_months is None or test_months is None or test_months == 0:
            continue

        # Extract test period (last test_months of data)
        if len(monthly_sales) >= (train_months + test_months):
            # We have enough data - use the test period
            test_actuals = monthly_sales.iloc[-test_months:]
        elif len(monthly_sales) > train_months:
            # Use what we have as test data
            test_actuals = monthly_sales.iloc[train_months:]
        else:
            # Not enough data
            continue

        if len(test_actuals) == 0:
            continue

        # Calculate metrics
        metrics = calculate_backtest_metrics_from_forecast(forecast_row, test_actuals)

        # Only record if we have valid metrics
        if metrics['mape'] is not None or metrics['rmse'] is not None:
            accuracy_records.append({
                'item_code': item_code,
                'winning_model': forecast_row.get('winning_model'),
                'forecast_confidence_pct': forecast_row.get('forecast_confidence_pct'),
                'months_compared': len(test_actuals),
                'forecast_horizon': forecast_row.get('forecast_horizon', 12),
                **metrics
            })

    if accuracy_records:
        return pd.DataFrame(accuracy_records)
    else:
        return pd.DataFrame()
