"""
ARIMA forecasting model.
Extracted from src/forecasting.py:376-442
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from statsmodels.tsa.arima.model import ARIMA

from forecasting_engine.models.base import ForecastModel
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


class ARIMAModel(ForecastModel):
    """
    ARIMA forecasting model.

    Best for:
    - Short-term forecasting
    - High-volume items
    - Items with 12+ months of history

    Uses automatic order selection with AIC.
    """

    def __init__(self):
        super().__init__("ARIMA")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using ARIMA.

        Parameters:
        -----------
        train : pd.Series
            Training data (monthly time series)
        test : pd.Series
            Test data (for calculating RMSE)
        forecast_horizon : int
            Number of months to forecast

        Returns:
        --------
        Tuple[np.ndarray, float]
            (forecast_array, rmse)
        """
        # Check minimum data requirements
        if len(train) < settings.arima_min_months:
            logger.debug(
                f"Insufficient data for ARIMA: {len(train)} months "
                f"(need {settings.arima_min_months}), falling back to SMA"
            )
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)

        try:
            # Simple grid search for best AIC
            best_aic = np.inf
            best_order = (1, 1, 1)
            best_model = None
            max_order = 3

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
                rmse = np.sqrt(np.mean((test.values - test_forecast_vals) ** 2))
            else:
                rmse = np.nan

            return forecast, rmse

        except Exception as e:
            logger.warning(f"ARIMA failed: {e}. Falling back to SMA.")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)
