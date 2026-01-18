"""
Theta forecasting model.
Extracted from src/forecasting.py:335-373
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from statsmodels.tsa.forecasting.theta import ThetaModel

from forecasting_engine.models.base import ForecastModel
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


class ThetaModel(ForecastModel):
    """
    Theta forecasting model.

    Best for:
    - Simple, robust baseline
    - Items with 12+ months of history
    - Comparing against more complex models

    Uses automatic method selection.
    """

    def __init__(self):
        super().__init__("Theta")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using Theta model.

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
        if len(train) < settings.theta_min_months:
            logger.debug(
                f"Insufficient data for Theta: {len(train)} months "
                f"(need {settings.theta_min_months}), falling back to SMA"
            )
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)

        try:
            # Theta model (API may vary by statsmodels version)
            try:
                model = ThetaModel(train, method='auto')
            except TypeError:
                # Older statsmodels API - no method parameter
                model = ThetaModel(train)
            fitted_model = model.fit()

            # Forecast
            forecast = fitted_model.forecast(steps=forecast_horizon)

            # Convert to numpy array if needed
            if hasattr(forecast, 'values'):
                forecast_values = forecast.values
            else:
                forecast_values = np.array(forecast)

            # Calculate RMSE on test set
            if len(test) > 0:
                test_forecast = fitted_model.forecast(len(test))
                test_forecast_vals = test_forecast.values if hasattr(test_forecast, 'values') else test_forecast
                rmse = np.sqrt(np.mean((test.values - test_forecast_vals) ** 2))
            else:
                rmse = np.nan

            return forecast_values, rmse

        except Exception as e:
            logger.warning(f"Theta model failed: {e}. Falling back to SMA.")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)
