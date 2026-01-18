"""
Croston's method for intermittent demand forecasting.
Extracted from src/forecasting.py:499-556
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

from forecasting_engine.models.base import ForecastModel

logger = logging.getLogger(__name__)


class CrostonModel(ForecastModel):
    """
    Croston's method for intermittent demand forecasting.

    Best for:
    - Intermittent demand (many zero values)
    - Spare parts
    - Low-volume items

    Separates demand size estimation from inter-arrival time estimation.
    """

    def __init__(self):
        super().__init__("Croston")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using Croston's method.

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
            # Separate non-zero demand periods
            non_zero_demand = train[train > 0]

            if len(non_zero_demand) < 2:
                # Not enough non-zero demand, use SMA
                logger.debug("Insufficient non-zero demand for Croston, falling back to SMA")
                from forecasting_engine.models.sma_model import SMAModel
                return SMAModel().forecast(train, test, forecast_horizon)

            # Calculate inter-arrival times (periods between demands)
            demand_indices = train[train > 0].index
            if len(demand_indices) > 1:
                # Convert PeriodIndex to integers for diff
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
                # For Croston's, compare test values to forecast value
                rmse = np.sqrt(np.mean((test.values - forecast_value) ** 2))
            else:
                rmse = np.nan

            return forecast, rmse

        except Exception as e:
            logger.warning(f"Croston's method failed: {e}. Falling back to SMA.")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)
