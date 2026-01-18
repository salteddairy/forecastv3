"""
Simple Moving Average (SMA) model.
Extracted from src/forecasting.py:179-217
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from forecasting_engine.models.base import ForecastModel

logger = logging.getLogger(__name__)


class SMAModel(ForecastModel):
    """
    Simple Moving Average (3-month) model.

    Best for:
    - Low-volume items
    - Stable demand
    - Fallback when other models fail

    Simple, robust, always works.
    """

    def __init__(self):
        super().__init__("SMA")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using Simple Moving Average (3-month).

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
            rmse = np.sqrt(np.mean((test.values - forecast_value) ** 2))
        else:
            rmse = np.nan

        return forecast, rmse
