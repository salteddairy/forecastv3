"""
Forecasting Module - Tournament Approach
Implements model competition (SMA, Holt-Winters, Prophet) to select best forecast
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
import logging

# Initialize logger first, before any other imports that might need it
logger = logging.getLogger(__name__)

# Optional: Import joblib for parallel processing
try:
    from joblib import Parallel, delayed
    JOB_LIB_AVAILABLE = True
except ImportError:
    JOB_LIB_AVAILABLE = False
    logger.warning("joblib not available. Parallel processing disabled.")

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def calculate_dynamic_forecast_horizon(monthly_data: pd.Series, avg_lead_time_days: int = 21) -> int:
    """
    Calculate optimal forecast horizon based on item characteristics.

    Strategy: Now defaults to 12 months (1 year) for all items to support annual planning.
    Previously used dynamic horizons (1-6 months) for inventory turnover optimization.

    Parameters:
    -----------
    monthly_data : pd.Series
        Monthly demand time series
    avg_lead_time_days : int
        Average supplier lead time in days (not used in 12-month model)

    Returns:
    --------
    int
        Recommended forecast horizon in months (always 12 for annual planning)
    """
    # For annual planning, always use 12 months
    # This allows comparison of forecast vs actual over a full year
    if len(monthly_data) < 12:
        # If we don't have enough history, use what we have (minimum 3 months)
        return max(3, len(monthly_data))

    return 12  # Always forecast 12 months for annual planning

# Import forecasting libraries
from statsmodels.tsa.holtwinters import SimpleExpSmoothing, Holt
from statsmodels.tsa.forecasting.theta import ThetaModel
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not available. Install with: pip install prophet")


def prepare_monthly_data(df_sales: pd.DataFrame, item_code: str) -> pd.Series:
    """
    Prepare monthly time series data for a specific item.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe
    item_code : str
        Item code to prepare data for

    Returns:
    --------
    pd.Series
        Monthly demand time series with Period index
    """
    # Filter for specific item
    item_data = df_sales[df_sales['item_code'] == item_code].copy()

    # Ensure numeric qty
    item_data['qty'] = pd.to_numeric(item_data['qty'], errors='coerce')
    item_data = item_data.dropna(subset=['qty'])

    # Aggregate by month
    item_data['year_month'] = item_data['date'].dt.to_period('M')
    monthly_demand = item_data.groupby('year_month')['qty'].sum()

    # Ensure we have a complete monthly index (fill missing months with 0)
    if len(monthly_demand) > 0:
        full_index = pd.period_range(monthly_demand.index.min(),
                                     monthly_demand.index.max(),
                                     freq='M')
        monthly_demand = monthly_demand.reindex(full_index, fill_value=0)

    return monthly_demand


def train_test_split(monthly_data: pd.Series, train_pct: float = 0.8) -> Tuple[pd.Series, pd.Series]:
    """
    Split time series into train and test sets.

    Parameters:
    -----------
    monthly_data : pd.Series
        Monthly time series data
    train_pct : float
        Percentage of data to use for training (default: 0.8)

    Returns:
    --------
    Tuple[pd.Series, pd.Series]
        Train and test series
    """
    split_idx = int(len(monthly_data) * train_pct)
    train = monthly_data[:split_idx]
    test = monthly_data[split_idx:]
    return train, test


def calculate_rmse(actual: pd.Series, forecast: np.array) -> float:
    """
    Calculate Root Mean Square Error.

    Parameters:
    -----------
    actual : pd.Series
        Actual values
    forecast : np.array
        Forecasted values

    Returns:
    --------
    float
        RMSE value
    """
    mse = np.mean((actual.values - forecast) ** 2)
    return np.sqrt(mse)


def calculate_mape(actual: pd.Series, forecast: np.array) -> float:
    """
    Calculate Mean Absolute Percentage Error.

    Parameters:
    -----------
    actual : pd.Series
        Actual values
    forecast : np.array
        Forecasted values

    Returns:
    --------
    float
        MAPE value as percentage

    Notes:
    ------
    MAPE = mean(|actual - forecast| / actual) * 100
    Handles zero values in actual by excluding them from calculation
    """
    # Filter out zero values to avoid division by zero
    non_zero_mask = actual.values != 0
    if not non_zero_mask.any():
        return np.nan

    actual_nonzero = actual.values[non_zero_mask]
    forecast_nonzero = forecast[:len(actual)][non_zero_mask]

    mape = np.mean(np.abs((actual_nonzero - forecast_nonzero) / actual_nonzero)) * 100
    return mape


def forecast_sma(train: pd.Series, test: pd.Series, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    Simple Moving Average (3-month) forecast.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    # Calculate 3-month moving average
    window = min(3, len(train))

    if len(train) < 3:
        # Not enough data, use mean
        forecast_value = train.mean()
    else:
        forecast_value = train.tail(window).mean()

    # Create forecast array
    forecast = np.full(forecast_horizon, forecast_value)

    # Calculate RMSE on test set
    if len(test) > 0:
        # For SMA, we compare test values to the forecast value
        test_forecast = np.full(len(test), forecast_value)
        rmse = calculate_rmse(test, test_forecast)
    else:
        rmse = np.nan

    return forecast, rmse


def forecast_holt_winters(train: pd.Series, test: pd.Series, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    Holt-Winters (Double Exponential Smoothing) forecast.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    try:
        # Use Holt's linear trend method (double exponential smoothing)
        model = Holt(train, initialization_method='estimated')

        # Fit model
        fitted_model = model.fit(optimized=True)

        # Forecast
        forecast = fitted_model.forecast(forecast_horizon)

        # Calculate RMSE on test set
        if len(test) > 0:
            test_forecast = fitted_model.forecast(len(test))
            rmse = calculate_rmse(test, test_forecast)
        else:
            rmse = np.nan

        return forecast.values, rmse

    except Exception as e:
        # Fallback to SMA if Holt-Winters fails
        logger.warning(f"Holt-Winters failed: {e}. Falling back to SMA.")
        return forecast_sma(train, test, forecast_horizon)


def forecast_prophet(train: pd.Series, test: pd.Series, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    Prophet forecast (only if enough history data).

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    if not PROPHET_AVAILABLE:
        logger.warning("Prophet not available. Install with: pip install prophet")
        logger.info("Falling back to SMA model")
        return forecast_sma(train, test, forecast_horizon)

    if len(train) < 18:
        # Not enough data for Prophet, use SMA
        return forecast_sma(train, test, forecast_horizon)

    try:
        # Prepare data for Prophet
        train_df = pd.DataFrame({
            'ds': train.index.to_timestamp(),
            'y': train.values
        })

        # Create and fit Prophet model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=0.95
        )
        model.fit(train_df)

        # Make future dataframe
        future_dates = model.make_future_dataframe(periods=forecast_horizon, freq='M')

        # Generate forecast
        forecast_results = model.predict(future_dates)

        # Extract forecast values (last forecast_horizon values)
        forecast = forecast_results.tail(forecast_horizon)['yhat'].values

        # Calculate RMSE on test set
        if len(test) > 0:
            # Create test dates
            test_dates = pd.date_range(start=train.index.max().to_timestamp(),
                                      periods=len(test)+1,
                                      freq='M')[1:]

            test_df = pd.DataFrame({'ds': test_dates})
            test_forecast = model.predict(test_df)['yhat'].values
            rmse = calculate_rmse(test, test_forecast)
        else:
            rmse = np.nan

        return forecast, rmse

    except Exception as e:
        logger.warning(f"Prophet failed: {e}. Falling back to SMA.")
        return forecast_sma(train, test, forecast_horizon)


def forecast_theta(train: pd.Series, test: pd.Series, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    Theta decomposition forecast.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    try:
        # Theta model with automatic method selection
        # Statsmodels ThetaModel uses 'method' parameter, not 'd'
        model = ThetaModel(train, method='auto')
        fitted_model = model.fit()

        # Forecast
        forecast = fitted_model.forecast(steps=forecast_horizon)

        # Calculate RMSE on test set
        if len(test) > 0:
            test_forecast = fitted_model.forecast(len(test))
            rmse = calculate_rmse(test, test_forecast)
        else:
            rmse = np.nan

        return forecast.values, rmse

    except Exception as e:
        logger.warning(f"Theta model failed: {e}. Falling back to SMA.")
        return forecast_sma(train, test, forecast_horizon)


def forecast_arima(train: pd.Series, test: pd.Series, forecast_horizon: int = 6,
                   max_order: int = 3) -> Tuple[np.array, float]:
    """
    ARIMA forecast with automatic order selection using AIC.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)
    max_order : int
        Maximum p,d,q order to search (default: 3)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    try:
        if len(train) < 12:
            # Not enough data for ARIMA
            return forecast_sma(train, test, forecast_horizon)

        # Simple grid search for best AIC
        best_aic = np.inf
        best_order = (1, 1, 1)
        best_model = None

        for p in range(0, max_order + 1):
            for d in range(0, 2):
                for q in range(0, max_order + 1):
                    try:
                        model = ARIMA(train, order=(p, d, q))
                        fitted = model.fit()
                        if fitted.aic < best_aic:
                            best_aic = fitted.aic
                            best_order = (p, d, q)
                            best_model = fitted
                    except (ValueError, np.linalg.LinAlgError, RuntimeError):
                        # ARIMA fitting can fail with various errors during grid search
                        continue

        if best_model is None:
            # Fallback to simple ARIMA(1,1,1)
            model = ARIMA(train, order=(1, 1, 1))
            best_model = model.fit()

        # Forecast
        forecast_result = best_model.forecast(steps=forecast_horizon)
        forecast = forecast_result.values if hasattr(forecast_result, 'values') else forecast_result

        # Calculate RMSE on test set
        if len(test) > 0:
            test_forecast = best_model.forecast(len(test))
            test_forecast_vals = test_forecast.values if hasattr(test_forecast, 'values') else test_forecast
            rmse = calculate_rmse(test, test_forecast_vals)
        else:
            rmse = np.nan

        return forecast, rmse

    except Exception as e:
        logger.warning(f"ARIMA failed: {e}. Falling back to SMA.")
        return forecast_sma(train, test, forecast_horizon)


def forecast_sarima(train: pd.Series, test: pd.Series, forecast_horizon: int = 6,
                    seasonal_period: int = 12) -> Tuple[np.array, float]:
    """
    SARIMA forecast for seasonal data.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)
    seasonal_period : int
        Seasonal period (default: 12 for monthly data)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    try:
        if len(train) < 24:
            # Not enough data for SARIMA
            return forecast_arima(train, test, forecast_horizon)

        # Try SARIMA with seasonal order
        # (p,d,q) × (P,D,Q)s
        model = SARIMAX(train,
                        order=(1, 1, 1),
                        seasonal_order=(1, 1, 1, seasonal_period),
                        enforce_stationarity=False,
                        enforce_invertibility=False)
        fitted_model = model.fit(disp=False, maxiter=50)

        # Forecast
        forecast_result = fitted_model.forecast(steps=forecast_horizon)
        forecast = forecast_result.values if hasattr(forecast_result, 'values') else forecast_result

        # Calculate RMSE on test set
        if len(test) > 0:
            test_forecast = fitted_model.forecast(len(test))
            test_forecast_vals = test_forecast.values if hasattr(test_forecast, 'values') else test_forecast
            rmse = calculate_rmse(test, test_forecast_vals)
        else:
            rmse = np.nan

        return forecast, rmse

    except Exception as e:
        logger.warning(f"SARIMA failed: {e}. Falling back to ARIMA.")
        return forecast_arima(train, test, forecast_horizon)


def forecast_croston(train: pd.Series, test: pd.Series, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    Croston's method for intermittent demand forecasting.

    Separates demand size estimation from inter-arrival time estimation.

    Parameters:
    -----------
    train : pd.Series
        Training data
    test : pd.Series
        Test data
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Forecast array, RMSE)
    """
    try:
        # Separate non-zero demand periods
        non_zero_demand = train[train > 0]

        if len(non_zero_demand) < 2:
            # Not enough non-zero demand, use SMA
            return forecast_sma(train, test, forecast_horizon)

        # Calculate inter-arrival times (periods between demands)
        demand_indices = train[train > 0].index
        if len(demand_indices) > 1:
            intervals = np.diff(demand_indices.astype(int))
            avg_interval = np.mean(intervals)
        else:
            avg_interval = 1.0

        # Simple exponential smoothing for demand size
        demand_size = non_zero_demand.iloc[-1]  # Latest demand

        # Croston's forecast: demand_size / avg_interval
        forecast_value = demand_size / max(avg_interval, 1)

        # Create forecast array
        forecast = np.full(forecast_horizon, forecast_value)

        # Calculate RMSE on test set
        if len(test) > 0:
            # For Croston's, compare test zeros vs forecast
            test_forecast = np.full(len(test), forecast_value)
            rmse = calculate_rmse(test, test_forecast)
        else:
            rmse = np.nan

        return forecast, rmse

    except Exception as e:
        logger.warning(f"Croston's method failed: {e}. Falling back to SMA.")
        return forecast_sma(train, test, forecast_horizon)


def forecast_ensemble_simple(results: Dict, forecast_horizon: int = 6,
                             method: str = 'mean') -> Tuple[np.array, float]:
    """
    Simple ensemble forecast combining multiple models.

    Parameters:
    -----------
    results : Dict
        Dictionary of model results with forecasts and RMSEs
    forecast_horizon : int
        Number of months to forecast (default: 6)
    method : str
        Ensemble method: 'mean', 'median', 'trimmed_mean'

    Returns:
    --------
    Tuple[np.array, float]
        (Ensemble forecast array, ensemble RMSE)
    """
    try:
        # Collect all forecasts
        forecasts = []
        for model_name, model_result in results.items():
            if 'forecast' in model_result and len(model_result['forecast']) >= forecast_horizon:
                forecasts.append(model_result['forecast'][:forecast_horizon])

        if len(forecasts) == 0:
            # No valid forecasts, return SMA-like result
            return np.full(forecast_horizon, 0), np.nan

        forecasts_array = np.array(forecasts)

        if method == 'mean':
            ensemble_forecast = np.mean(forecasts_array, axis=0)
        elif method == 'median':
            ensemble_forecast = np.median(forecasts_array, axis=0)
        elif method == 'trimmed_mean':
            # Remove best and worst, average the rest
            if len(forecasts) >= 3:
                # For each time period, sort and trim
                ensemble_forecast = np.zeros(forecast_horizon)
                for i in range(forecast_horizon):
                    period_values = forecasts_array[:, i]
                    sorted_vals = np.sort(period_values)
                    trimmed = sorted_vals[1:-1]  # Remove min and max
                    ensemble_forecast[i] = np.mean(trimmed)
            else:
                ensemble_forecast = np.mean(forecasts_array, axis=0)
        else:
            ensemble_forecast = np.mean(forecasts_array, axis=0)

        # Calculate ensemble RMSE as average of model RMSEs
        rmse_values = [v.get('rmse', np.nan) for v in results.values() if 'rmse' in v]
        valid_rmses = [r for r in rmse_values if not np.isnan(r)]
        ensemble_rmse = np.mean(valid_rmses) if valid_rmses else np.nan

        return ensemble_forecast, ensemble_rmse

    except Exception as e:
        logger.warning(f"Simple ensemble failed: {e}")
        # Return first available forecast
        for model_result in results.values():
            if 'forecast' in model_result:
                return model_result['forecast'][:forecast_horizon], model_result.get('rmse', np.nan)
        return np.full(forecast_horizon, 0), np.nan


def forecast_ensemble_weighted(results: Dict, forecast_horizon: int = 6) -> Tuple[np.array, float]:
    """
    RMSE-weighted ensemble forecast.

    Models with lower RMSE get higher weights. Weight = 1/RMSE (normalized).

    Parameters:
    -----------
    results : Dict
        Dictionary of model results with forecasts and RMSEs
    forecast_horizon : int
        Number of months to forecast (default: 6)

    Returns:
    --------
    Tuple[np.array, float]
        (Weighted ensemble forecast array, weighted RMSE)
    """
    try:
        # Collect forecasts and RMSEs
        valid_models = {}
        for model_name, model_result in results.items():
            if 'forecast' in model_result and 'rmse' in model_result:
                rmse = model_result['rmse']
                if not np.isnan(rmse) and rmse > 0:
                    valid_models[model_name] = model_result

        if len(valid_models) == 0:
            # No valid models, fall back to simple ensemble
            return forecast_ensemble_simple(results, forecast_horizon, 'mean')

        # Calculate inverse RMSE weights
        inv_rmses = {name: 1.0 / result['rmse'] for name, result in valid_models.items()}
        total_inv_rmse = sum(inv_rmses.values())

        # Normalize weights
        weights = {name: inv_rmse / total_inv_rmse for name, inv_rmse in inv_rmses.items()}

        # Calculate weighted forecast
        weighted_forecast = np.zeros(forecast_horizon)
        for model_name, model_result in valid_models.items():
            forecast = model_result['forecast'][:forecast_horizon]
            weight = weights[model_name]
            weighted_forecast += forecast * weight

        # Calculate weighted RMSE (weighted average of individual RMSEs)
        weighted_rmse = sum(result['rmse'] * weights[name]
                           for name, result in valid_models.items())

        return weighted_forecast, weighted_rmse

    except Exception as e:
        logger.warning(f"Weighted ensemble failed: {e}. Falling back to simple ensemble.")
        return forecast_ensemble_simple(results, forecast_horizon, 'mean')


def calculate_confidence_intervals(train: pd.Series, forecast_model,
                                   forecast_horizon: int = 6,
                                   alpha: float = 0.05,
                                   n_bootstrap: int = 100) -> Dict:
    """
    Calculate confidence intervals for forecasts using bootstrap resampling.

    Parameters:
    -----------
    train : pd.Series
        Training data
    forecast_model : callable
        Forecasting function that takes (train, test, horizon)
    forecast_horizon : int
        Number of months to forecast
    alpha : float
        Significance level (default: 0.05 for 95% CI)
    n_bootstrap : int
        Number of bootstrap iterations (default: 100)

    Returns:
    --------
    Dict
        Dictionary with lower, upper bounds and point forecast
    """
    try:
        bootstrap_forecasts = []

        for _ in range(n_bootstrap):
            # Resample training data with replacement
            resampled = train.sample(n=len(train), replace=True)
            resampled = resampled.sort_index()

            # Create dummy test set
            test = pd.Series([], dtype=train.dtype)

            # Generate forecast
            forecast, _ = forecast_model(resampled, test, forecast_horizon)
            bootstrap_forecasts.append(forecast)

        bootstrap_array = np.array(bootstrap_forecasts)

        # Calculate percentiles
        lower_bound = np.percentile(bootstrap_array, (alpha / 2) * 100, axis=0)
        upper_bound = np.percentile(bootstrap_array, (1 - alpha / 2) * 100, axis=0)
        point_forecast = np.mean(bootstrap_array, axis=0)

        return {
            'forecast': point_forecast,
            'lower': lower_bound,
            'upper': upper_bound,
            'confidence': 1 - alpha
        }

    except Exception as e:
        logger.warning(f"Bootstrap CI calculation failed: {e}")
        # Return empty confidence intervals
        return {
            'forecast': np.zeros(forecast_horizon),
            'lower': np.zeros(forecast_horizon),
            'upper': np.zeros(forecast_horizon),
            'confidence': 1 - alpha
        }


def run_tournament(df_sales: pd.DataFrame, item_code: str,
                   use_advanced_models: bool = True) -> Dict:
    """
    Run enhanced forecasting tournament with multiple models.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe
    item_code : str
        Item code to run tournament for
    use_advanced_models : bool
        Whether to use advanced models (Theta, ARIMA, SARIMA, Croston)

    Returns:
    --------
    Dict
        Tournament results with forecasts and winning model
    """
    # Prepare monthly data
    monthly_data = prepare_monthly_data(df_sales, item_code)

    if len(monthly_data) < 3:
        # Not enough data
        return {
            'item_code': item_code,
            'error': 'Insufficient data (< 3 months)',
            'winning_model': None,
            'forecasts': {f'month_{i+1}': np.nan for i in range(6)}
        }

    # Calculate dynamic forecast horizon based on item characteristics
    forecast_horizon = calculate_dynamic_forecast_horizon(monthly_data)

    # Split into train/test
    train, test = train_test_split(monthly_data, train_pct=0.8)

    # Run all models with dynamic horizon
    results = {}

    # ========== Baseline Models ==========

    # Model 1: SMA
    sma_forecast, sma_rmse = forecast_sma(train, test, forecast_horizon=forecast_horizon)
    results['SMA'] = {
        'forecast': sma_forecast,
        'rmse': sma_rmse
    }

    # Model 2: Holt-Winters
    hw_forecast, hw_rmse = forecast_holt_winters(train, test, forecast_horizon=forecast_horizon)
    results['Holt-Winters'] = {
        'forecast': hw_forecast,
        'rmse': hw_rmse
    }

    # ========== Advanced Models (if enabled) ==========

    if use_advanced_models:
        # Model 3: Theta (requires 12+ months)
        if len(train) >= 12:
            theta_forecast, theta_rmse = forecast_theta(train, test, forecast_horizon=forecast_horizon)
            results['Theta'] = {
                'forecast': theta_forecast,
                'rmse': theta_rmse
            }

        # Model 4: ARIMA (requires 12+ months)
        if len(train) >= 12:
            arima_forecast, arima_rmse = forecast_arima(train, test, forecast_horizon=forecast_horizon)
            results['ARIMA'] = {
                'forecast': arima_forecast,
                'rmse': arima_rmse
            }

        # Model 5: SARIMA (requires 24+ months)
        if len(train) >= 24:
            sarima_forecast, sarima_rmse = forecast_sarima(train, test, forecast_horizon=forecast_horizon)
            results['SARIMA'] = {
                'forecast': sarima_forecast,
                'rmse': sarima_rmse
            }

        # Model 6: Croston's Method (for intermittent demand)
        # Check if data is intermittent (>50% zeros)
        zero_ratio = (train == 0).sum() / len(train)
        if zero_ratio > 0.3:  # Use Croston for 30%+ intermittent demand
            croston_forecast, croston_rmse = forecast_croston(train, test, forecast_horizon=forecast_horizon)
            results['Croston'] = {
                'forecast': croston_forecast,
                'rmse': croston_rmse
            }

        # Model 7: Prophet (requires 18+ months)
        if len(train) >= 18 and PROPHET_AVAILABLE:
            prophet_forecast, prophet_rmse = forecast_prophet(train, test, forecast_horizon=forecast_horizon)
            results['Prophet'] = {
                'forecast': prophet_forecast,
                'rmse': prophet_rmse
            }

    # ========== Ensemble Models ==========

    # Simple Ensemble (mean)
    ensemble_simple_forecast, ensemble_simple_rmse = forecast_ensemble_simple(
        results, forecast_horizon=forecast_horizon, method='mean'
    )
    results['Ensemble-Simple'] = {
        'forecast': ensemble_simple_forecast,
        'rmse': ensemble_simple_rmse
    }

    # Weighted Ensemble (RMSE-weighted)
    ensemble_weighted_forecast, ensemble_weighted_rmse = forecast_ensemble_weighted(
        results, forecast_horizon=forecast_horizon
    )
    results['Ensemble-Weighted'] = {
        'forecast': ensemble_weighted_forecast,
        'rmse': ensemble_weighted_rmse
    }

    # Select winner (lowest RMSE)
    valid_models = {k: v for k, v in results.items() if not np.isnan(v['rmse'])}

    if not valid_models:
        # All models failed, use SMA
        winning_model = 'SMA'
        winning_forecast = results['SMA']['forecast']
    else:
        winning_model = min(valid_models.items(), key=lambda x: x[1]['rmse'])[0]
        winning_forecast = results[winning_model]['forecast']

    # Calculate item metrics for classification
    avg_demand = monthly_data.mean()
    std_demand = monthly_data.std()
    cv = (std_demand / avg_demand) if avg_demand > 0 else 0

    # Prepare output with dynamic horizon
    output = {
        'item_code': item_code,
        'winning_model': winning_model,
        'forecast_horizon': forecast_horizon,
        'avg_monthly_demand': avg_demand,
        'demand_cv': cv,
        'history_months': len(monthly_data),
        'train_months': len(train),
        'test_months': len(test)
    }

    # Add forecast months (pad to 12 months with NaN for unused months)
    for i in range(12):
        if i < len(winning_forecast):
            output[f'forecast_month_{i+1}'] = winning_forecast[i]
        else:
            output[f'forecast_month_{i+1}'] = np.nan

    # Add RMSE for all models
    for model_name, model_results in results.items():
        output[f'rmse_{model_name}'] = model_results['rmse']

    # Add all model forecasts for comparison
    for model_name, model_results in results.items():
        for i in range(forecast_horizon):
            if i < len(model_results['forecast']):
                output[f'forecast_{model_name}_month_{i+1}'] = model_results['forecast'][i]

    return output


def _process_single_item(df_sales: pd.DataFrame, item_code: str, index: int, total: int) -> dict:
    """
    Process a single item for parallel execution.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe
    item_code : str
        Item code to forecast
    index : int
        Current item index for logging
    total : int
        Total number of items for logging

    Returns:
    --------
    dict
        Tournament result for the item
    """
    logger.debug(f"[{index}/{total}] Processing {item_code}...")
    result = run_tournament(df_sales, item_code)

    if 'error' in result:
        logger.debug(f"  SKIPPED ({result['error']})")
    else:
        rmse_col = f"rmse_{result['winning_model']}"
        logger.debug(f"  Winner: {result['winning_model']} (RMSE: {result[rmse_col]:.2f})")

    return result


def forecast_items(df_sales: pd.DataFrame, item_codes: List[str] = None,
                   n_samples: int = None, n_jobs: int = -1, parallel_threshold: int = 10) -> pd.DataFrame:
    """
    Run tournament for multiple items with optional parallel processing.

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe
    item_codes : List[str], optional
        List of item codes to forecast. If None, uses all items
    n_samples : int, optional
        Number of random items to sample
    n_jobs : int, optional
        Number of parallel jobs (default: -1 for all CPUs)
        Only used if joblib is available and item count >= parallel_threshold
    parallel_threshold : int, optional
        Minimum number of items to enable parallel processing (default: 10)

    Returns:
    --------
    pd.DataFrame
        Forecast results with item_code, forecasts, and winning model
    """
    logger.info("=" * 60)
    logger.info("FORECASTING TOURNAMENT")
    logger.info("=" * 60)

    # Get item codes
    if item_codes is None:
        item_codes = df_sales['item_code'].unique()

    # Sample if requested
    if n_samples is not None and n_samples < len(item_codes):
        np.random.seed(42)  # For reproducibility
        item_codes = np.random.choice(item_codes, size=n_samples, replace=False)

    logger.info(f"Running tournament for {len(item_codes)} items...")

    # Determine if we should use parallel processing
    use_parallel = (
        JOB_LIB_AVAILABLE and
        len(item_codes) >= parallel_threshold and
        n_jobs != 0  # n_jobs=0 means force sequential
    )

    if use_parallel:
        logger.info(f"Using parallel processing with n_jobs={n_jobs}")
        # Run in parallel
        results = Parallel(n_jobs=n_jobs)(
            delayed(_process_single_item)(df_sales, item_code, i + 1, len(item_codes))
            for i, item_code in enumerate(item_codes)
        )
    else:
        # Run sequentially
        if JOB_LIB_AVAILABLE and len(item_codes) < parallel_threshold:
            logger.info(f"Using sequential processing (item count < parallel_threshold)")
        else:
            logger.info(f"Using sequential processing (joblib not available)")

        results = []
        for i, item_code in enumerate(item_codes, 1):
            result = _process_single_item(df_sales, item_code, i, len(item_codes))
            results.append(result)

    # Create DataFrame
    df_results = pd.DataFrame(results)

    # Calculate forecast confidence percentage based on RMSE (VECTORIZED)
    # Confidence formula: 100 - (RMSE / mean_demand) * 100
    # Higher RMSE relative to mean demand = lower confidence

    # Get winning model RMSE values (vectorized)
    df_results['winning_model'] = df_results['winning_model'].fillna('')

    # Create RMSE column by extracting from model-specific RMSE columns
    rmse_cols = [col for col in df_results.columns if col.startswith('rmse_')]
    if rmse_cols:
        # Melt RMSE columns and pivot to get winning_model RMSE
        df_rmse = df_results[['item_code'] + rmse_cols].copy()
        # For each row, find the RMSE for the winning model
        df_results['rmse_winning'] = df_results.apply(
            lambda row: row.get(f"rmse_{row['winning_model']}", np.nan) if row['winning_model'] else np.nan,
            axis=1
        )
    else:
        df_results['rmse_winning'] = np.nan

    # Calculate mean demand from forecast period (vectorized)
    forecast_cols = [f'forecast_month_{i+1}' for i in range(6)]
    available_forecast_cols = [col for col in forecast_cols if col in df_results.columns]

    if available_forecast_cols:
        df_results['mean_demand'] = df_results[available_forecast_cols].fillna(0).mean(axis=1)
    else:
        df_results['mean_demand'] = np.nan

    # Calculate confidence (vectorized with np.where)
    df_results['forecast_confidence_pct'] = np.where(
        (df_results['winning_model'].notna()) & (df_results['winning_model'] != '') &
        (df_results['rmse_winning'].notna()) & (df_results['mean_demand'] > 0),
        # Calculate confidence
        np.clip(
            100 - (df_results['rmse_winning'] / df_results['mean_demand']) * 100,
            0,  # Minimum 0%
            100  # Maximum 100%
        ),
        # Default confidence for invalid cases
        np.where(
            (df_results['winning_model'].notna()) & (df_results['winning_model'] != ''),
            50.0,  # Has model but RMSE/mean invalid
            0.0    # No model at all
        )
    )

    # Clean up temporary columns
    df_results = df_results.drop(columns=['rmse_winning', 'mean_demand'], errors='ignore')

    # Reorder columns (12 months of forecasts)
    forecast_cols = [f'forecast_month_{i+1}' for i in range(12)]
    other_cols = ['item_code', 'winning_model', 'forecast_confidence_pct', 'forecast_horizon', 'history_months', 'train_months', 'test_months']
    rmse_cols = [col for col in df_results.columns if col.startswith('rmse_')]

    column_order = other_cols + forecast_cols + rmse_cols
    df_results = df_results[[col for col in column_order if col in df_results.columns]]

    logger.info("=" * 60)
    logger.info("TOURNAMENT COMPLETE")
    logger.info("=" * 60)

    return df_results


def main():
    """
    Main function to test forecasting on 5 random items.
    """
    print("\n" + "=" * 60)
    print("TESTING FORECASTING MODULE")
    print("=" * 60)

    # Load data
    from src.ingestion import load_sales_orders

    data_dir = Path("data/raw")
    df_sales = load_sales_orders(data_dir / "sales.tsv")

    print(f"\nLoaded {len(df_sales)} sales orders")

    # Run tournament on 5 random items
    df_results = forecast_items(df_sales, n_samples=5)

    # Print detailed results
    print("\n" + "=" * 60)
    print("FORECAST RESULTS")
    print("=" * 60)

    print("\nForecast Summary:")
    print(df_results[['item_code', 'winning_model', 'forecast_month_1',
                     'forecast_month_2', 'forecast_month_3']].to_string(index=False))

    print("\nModel Distribution:")
    model_counts = df_results['winning_model'].value_counts()
    for model, count in model_counts.items():
        print(f"  {model}: {count} items")

    print("\nDetailed Forecasts (6 months):")
    for idx, row in df_results.iterrows():
        print(f"\nItem: {row['item_code']}")
        print(f"  Winning Model: {row['winning_model']}")

        if pd.isna(row['winning_model']) or row['winning_model'] is None:
            print(f"  Status: Insufficient data for forecasting")
        else:
            print(f"  History: {row['history_months']} months")
            rmse_col = f"rmse_{row['winning_model']}"
            if rmse_col in df_results.columns:
                print(f"  RMSE: {row[rmse_col]:.2f}")
            print(f"  6-Month Forecast:")
            for i in range(1, 7):
                month_col = f'forecast_month_{i}'
                val = row[month_col]
                if pd.notna(val):
                    print(f"    Month {i}: {val:.2f}")
                else:
                    print(f"    Month {i}: N/A")

    return df_results


if __name__ == "__main__":
    main()
