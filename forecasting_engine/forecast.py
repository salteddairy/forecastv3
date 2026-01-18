"""
Tournament orchestrator - runs all models and selects winner.
Extracted and adapted from src/forecasting.py:747-913
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

try:
    from joblib import Parallel, delayed
    JOB_LIB_AVAILABLE = True
except ImportError:
    JOB_LIB_AVAILABLE = False

from forecasting_engine.models import MODEL_REGISTRY
from forecasting_engine.models.base import ForecastModel
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


def prepare_monthly_data(
    df_sales: pd.DataFrame,
    item_code: str
) -> pd.Series:
    """
    Prepare monthly time series data for a specific item.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe with columns: [date, item_code, qty, warehouse_code]
    item_code : str
        Item code to prepare data for

    Returns:
    --------
    pd.Series
        Monthly demand time series with Period index
    """
    # Validate input DataFrame
    required_cols = ['date', 'item_code', 'qty']
    missing = set(required_cols) - set(df_sales.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    # Filter for specific item
    item_data = df_sales[df_sales['item_code'] == item_code].copy()

    if item_data.empty:
        logger.warning(f"No sales data found for item {item_code}")
        return pd.Series(dtype=float)

    # Ensure numeric qty
    item_data['qty'] = pd.to_numeric(item_data['qty'], errors='coerce')
    item_data = item_data.dropna(subset=['qty'])

    if item_data.empty:
        logger.warning(f"No valid quantity data for item {item_code}")
        return pd.Series(dtype=float)

    # Aggregate by month
    item_data['year_month'] = item_data['date'].dt.to_period('M')
    monthly_demand = item_data.groupby('year_month')['qty'].sum()

    # Ensure we have a complete monthly index (fill missing months with 0)
    if len(monthly_demand) > 0:
        full_index = pd.period_range(
            monthly_demand.index.min(),
            monthly_demand.index.max(),
            freq='M'
        )
        monthly_demand = monthly_demand.reindex(full_index, fill_value=0)

    return monthly_demand


def train_test_split(
    monthly_data: pd.Series,
    train_pct: float = 0.8
) -> tuple:
    """
    Split time series into train and test sets.

    Parameters:
    -----------
    monthly_data : pd.Series
        Monthly time series data with Period index
    train_pct : float
        Percentage of data to use for training (default: 0.8)

    Returns:
    --------
    tuple
        (train, test) series
    """
    if len(monthly_data) < 3:
        # Not enough data to split
        return monthly_data, pd.Series(dtype=float)

    split_idx = max(2, int(len(monthly_data) * train_pct))  # Ensure at least 2 test samples
    train = monthly_data[:split_idx]
    test = monthly_data[split_idx:]
    return train, test


def calculate_confidence_pct(
    train: pd.Series,
    rmse: float
) -> float:
    """
    Calculate forecast confidence percentage based on RMSE.

    Formula: 100 - (RMSE / mean_demand) * 100
    Higher RMSE relative to mean demand = lower confidence

    Parameters:
    -----------
    train : pd.Series
        Training data
    rmse : float
        Root Mean Square Error

    Returns:
    --------
    float
        Confidence percentage (0-100)
    """
    mean_demand = train.mean()

    if mean_demand <= 0 or pd.isna(rmse) or pd.isna(mean_demand):
        return 50.0  # Default confidence

    confidence = 100 - (rmse / mean_demand) * 100
    return max(0, min(100, confidence))  # Clamp to [0, 100]


def run_model_safely(
    model_class: type,
    train: pd.Series,
    test: pd.Series,
    forecast_horizon: int,
    model_name: str,
    item_code: str
) -> Optional[Dict]:
    """
    Run a single model with comprehensive error handling.

    Parameters:
    -----------
    model_class : type
        Model class to instantiate
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Forecast horizon
    model_name : str
        Name of the model
    item_code : str
        Item code for logging

    Returns:
    --------
    Dict or None
        {forecast: array, rmse: float} or None if failed
    """
    try:
        model = model_class()
        forecast, rmse = model.forecast(train, test, forecast_horizon=forecast_horizon)

        # Validate forecast
        if forecast is None or len(forecast) == 0:
            logger.warning(f"{model_name} returned empty forecast for {item_code}")
            return None

        # Ensure forecast is numeric
        forecast = np.array(forecast, dtype=float)

        # Handle NaN/Inf values
        if not np.isfinite(forecast).all():
            logger.warning(f"{model_name} returned invalid forecast for {item_code}")
            # Replace NaN with 0, Inf with last finite value
            forecast = np.nan_to_num(forecast, nan=0.0, posinf=0.0, neginf=0.0)

        # Ensure non-negative forecasts
        forecast = np.maximum(forecast, 0)

        return {
            'forecast': forecast,
            'rmse': rmse if np.isfinite(rmse) else np.nan
        }
    except Exception as e:
        logger.debug(f"{model_name} failed for {item_code}: {e}")
        return None


def run_tournament_for_item(
    df_sales: pd.DataFrame,
    item_code: str,
    use_advanced_models: bool = True
) -> Dict:
    """
    Run forecasting tournament for a single item.

    Runs all 7 models in parallel, selects winner based on RMSE,
    and generates 12-month forecast.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe with columns: [date, item_code, qty, warehouse_code]
    item_code : str
        Item code to run tournament for
    use_advanced_models : bool
        Whether to use advanced models (default: True)

    Returns:
    --------
    Dict
        Tournament results with forecasts and winning model
        {
            'item_code': str,
            'winning_model': str or None,
            'forecast_horizon': 12,
            'forecast_month_1': float,
            'forecast_month_2': float,
            ...
            'forecast_month_12': float,
            'rmse_prophet': float,
            'rmse_sarima': float,
            ...
            'forecast_confidence_pct': float,
            'history_months': int,
            'train_months': int,
            'test_months': int,
            'avg_monthly_demand': float,
            'demand_cv': float,
            'error': str (if failed)
        }
    """
    logger.debug(f"Running tournament for {item_code}...")

    # Prepare monthly data
    try:
        monthly_data = prepare_monthly_data(df_sales, item_code)
    except Exception as e:
        return {
            'item_code': item_code,
            'error': f'Failed to prepare monthly data: {e}',
            'winning_model': None
        }

    if len(monthly_data) < 3:
        return {
            'item_code': item_code,
            'error': f'Insufficient data ({len(monthly_data)} months < 3 required)',
            'winning_model': None,
            'history_months': len(monthly_data)
        }

    # Split into train/test
    train, test = train_test_split(monthly_data, train_pct=0.8)

    if len(test) == 0:
        return {
            'item_code': item_code,
            'error': 'Insufficient data for testing',
            'winning_model': None,
            'history_months': len(monthly_data),
            'train_months': len(train),
            'test_months': 0
        }

    # Run all models
    results = {}
    forecast_horizon = settings.forecast_horizon

    for model_name, model_class in MODEL_REGISTRY.items():
        # Skip advanced models if disabled
        if not use_advanced_models and model_name in ['Prophet', 'SARIMA', 'ARIMA', 'Theta', 'Croston']:
            continue

        # Skip models with insufficient data (they have internal checks, but we can pre-filter for efficiency)
        if model_name == 'Prophet' and len(train) < settings.prophet_min_months:
            continue
        if model_name == 'SARIMA' and len(train) < settings.sarima_min_months:
            continue
        if model_name in ['ARIMA', 'Theta'] and len(train) < settings.arima_min_months:
            continue

        # Run model with error handling
        result = run_model_safely(
            model_class, train, test, forecast_horizon,
            model_name, item_code
        )

        if result is not None:
            results[model_name] = result

    # Select winner (lowest RMSE)
    valid_models = {k: v for k, v in results.items() if v['rmse'] is not None and not pd.isna(v['rmse'])}

    if not valid_models:
        return {
            'item_code': item_code,
            'error': 'All models failed',
            'winning_model': None,
            'history_months': len(monthly_data),
            'models_attempted': len(results)
        }

    winning_model = min(valid_models.items(), key=lambda x: x[1]['rmse'])[0]
    winning_forecast = results[winning_model]['forecast']
    winning_rmse = results[winning_model]['rmse']

    # Calculate confidence
    confidence_pct = calculate_confidence_pct(train, winning_rmse)

    # Calculate item metrics
    avg_demand = monthly_data.mean()
    std_demand = monthly_data.std()
    cv = (std_demand / avg_demand) if avg_demand > 0 and not pd.isna(avg_demand) else 0

    # Prepare output
    output = {
        'item_code': item_code,
        'winning_model': winning_model,
        'forecast_horizon': forecast_horizon,
        'forecast_confidence_pct': round(confidence_pct, 2),
        'history_months': len(monthly_data),
        'train_months': len(train),
        'test_months': len(test),
        'avg_monthly_demand': round(float(avg_demand), 2) if not pd.isna(avg_demand) else 0,
        'demand_cv': round(float(cv), 2) if not pd.isna(cv) else 0,
        'forecast_period_start': datetime.now().date()
    }

    # Add forecast months (12 months)
    for i in range(12):
        if i < len(winning_forecast):
            val = winning_forecast[i]
            output[f'forecast_month_{i+1}'] = round(float(val), 2) if not pd.isna(val) else None
        else:
            output[f'forecast_month_{i+1}'] = None

    # Add RMSE for all models
    for model_name, model_results in results.items():
        rmse_val = model_results['rmse']
        col_name = f'rmse_{model_name.lower()}'
        output[col_name] = round(float(rmse_val), 2) if not pd.isna(rmse_val) else None

    return output


def run_tournament(
    df_sales: pd.DataFrame,
    item_codes: Optional[List[str]] = None,
    n_samples: int = None,
    use_advanced_models: bool = True,
    parallel: bool = True
) -> pd.DataFrame:
    """
    Run forecasting tournament for multiple items.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe with columns: [date, item_code, qty, warehouse_code]
    item_codes : List[str], optional
        List of item codes to forecast (None = all items)
    n_samples : int, optional
        Number of random items to sample
    use_advanced_models : bool
        Whether to use advanced models (default: True)
    parallel : bool
        Whether to use parallel processing (default: True)

    Returns:
    --------
    pd.DataFrame
        Forecast results for all items
    """
    logger.info("=" * 60)
    logger.info("FORECASTING TOURNAMENT")
    logger.info("=" * 60)

    # Validate input
    required_cols = ['date', 'item_code', 'qty']
    missing = set(required_cols) - set(df_sales.columns)
    if missing:
        raise ValueError(f"Sales DataFrame missing required columns: {missing}")

    # Get item codes
    if item_codes is None:
        item_codes = df_sales['item_code'].unique().tolist()

    # Sample if requested
    if n_samples is not None and n_samples < len(item_codes):
        np.random.seed(42)
        item_codes = np.random.choice(item_codes, size=n_samples, replace=False).tolist()

    logger.info(f"Running tournament for {len(item_codes)} items...")
    logger.info(f"Advanced models: {use_advanced_models}")
    logger.info(f"Parallel processing: {parallel and JOB_LIB_AVAILABLE}")

    # Determine if we should use parallel processing
    use_parallel = (
        parallel and
        JOB_LIB_AVAILABLE and
        len(item_codes) >= settings.parallel_threshold and
        settings.n_jobs != 0
    )

    # Process items
    start_time = datetime.now()

    if use_parallel:
        logger.info(f"Using parallel processing with n_jobs={settings.n_jobs}")
        results = Parallel(n_jobs=settings.n_jobs)(
            delayed(run_tournament_for_item)(df_sales, item_code, use_advanced_models)
            for item_code in item_codes
        )
    else:
        logger.info("Using sequential processing")
        results = []
        for i, item_code in enumerate(item_codes, 1):
            logger.debug(f"[{i}/{len(item_codes)}] Processing {item_code}...")
            result = run_tournament_for_item(df_sales, item_code, use_advanced_models)
            results.append(result)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Tournament completed in {duration:.1f} seconds")

    # Create DataFrame
    df_results = pd.DataFrame(results)

    # Log summary
    logger.info("=" * 60)
    logger.info("TOURNAMENT COMPLETE")
    logger.info(f"Processed: {len(df_results)} items")
    if 'winning_model' in df_results.columns:
        successful = df_results[df_results['winning_model'].notna()]
        logger.info(f"Successful: {len(successful)} items")
        logger.info(f"Failed: {len(df_results) - len(successful)} items")

        if not successful.empty:
            model_dist = successful['winning_model'].value_counts()
            logger.info(f"Model Distribution:")
            for model, count in model_dist.items():
                logger.info(f"  {model}: {count} items")
    logger.info("=" * 60)

    return df_results
