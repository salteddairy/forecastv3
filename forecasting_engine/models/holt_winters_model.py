"""
Holt-Winters (Double Exponential Smoothing) model.
Extracted from src/forecasting.py:220-260
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from statsmodels.tsa.holtwinters import Holt

from forecasting_engine.models.base import ForecastModel

logger = logging.getLogger(__name__)


class HoltWintersModel(ForecastModel):
    """
    Holt-Winters (Double Exponential Smoothing) model.

    Best for:
    - Data with trend
    - Medium-volume items
    - Items with 6+ months of history

    Captures level and trend in the data.
    """

    def __init__(self):
        super().__init__("Holt-Winters")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using Holt's linear trend method.

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
        try:
            # Use Holt's linear trend method (double exponential smoothing)
            model = Holt(train, initialization_method='estimated')

            # Fit model
            fitted_model = model.fit(optimized=True)

            # Forecast
            forecast_result = fitted_model.forecast(forecast_horizon)

            # Convert to numpy array if needed
            if hasattr(forecast_result, 'values'):
                forecast_values = forecast_result.values
            else:
                forecast_values = np.array(forecast_result)

            # Calculate RMSE on test set
            if len(test) > 0:
                test_forecast = fitted_model.forecast(len(test))
                test_forecast_vals = test_forecast.values if hasattr(test_forecast, 'values') else test_forecast
                rmse = np.sqrt(np.mean((test.values - test_forecast_vals) ** 2))
            else:
                rmse = np.nan

            return forecast_values, rmse

        except Exception as e:
            logger.warning(f"Holt-Winters failed: {e}. Falling back to SMA.")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)
