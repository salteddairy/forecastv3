"""
SARIMA forecasting model.
Extracted from src/forecasting.py:445-496
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from statsmodels.tsa.statespace.sarimax import SARIMAX

from forecasting_engine.models.base import ForecastModel
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


class SARIMAModel(ForecastModel):
    """
    SARIMA (Seasonal ARIMA) forecasting model.

    Best for:
    - Data with seasonal patterns
    - Complex time series with trend and seasonality
    - Items with 24+ months of history

    Uses (p,d,q) × (P,D,Q)s seasonal ARIMA
    """

    def __init__(self):
        super().__init__("SARIMA")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using SARIMA.

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
        if len(train) < settings.sarima_min_months:
            logger.debug(
                f"Insufficient data for SARIMA: {len(train)} months "
                f"(need {settings.sarima_min_months}), falling back to ARIMA"
            )
            from forecasting_engine.models.arima_model import ARIMAModel
            return ARIMAModel().forecast(train, test, forecast_horizon)

        try:
            # SARIMA with seasonal order
            # (p,d,q) × (P,D,Q)s
            # s = 12 for monthly data with yearly seasonality
            model = SARIMAX(
                train,
                order=(1, 1, 1),           # (p,d,q)
                seasonal_order=(1, 1, 1, 12),  # (P,D,Q,s)
                enforce_stationarity=False,
                enforce_invertibility=False
            )

            fitted_model = model.fit(disp=False, maxiter=50)

            # Forecast
            forecast_result = fitted_model.forecast(steps=forecast_horizon)
            forecast = forecast_result.values if hasattr(forecast_result, 'values') else forecast_result

            # Calculate RMSE on test set
            if len(test) > 0:
                test_forecast = fitted_model.forecast(len(test))
                test_forecast_vals = test_forecast.values if hasattr(test_forecast, 'values') else test_forecast
                rmse = np.sqrt(np.mean((test.values - test_forecast_vals) ** 2))
            else:
                rmse = np.nan

            return forecast, rmse

        except Exception as e:
            logger.warning(f"SARIMA failed: {e}. Falling back to ARIMA.")
            from forecasting_engine.models.arima_model import ARIMAModel
            return ARIMAModel().forecast(train, test, forecast_horizon)
