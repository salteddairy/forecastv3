"""
Prophet forecasting model.
Extracted from src/forecasting.py:263-332
"""
import logging
import pandas as pd
import numpy as np
from typing import Tuple

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

from forecasting_engine.models.base import ForecastModel
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


class ProphetModel(ForecastModel):
    """
    Prophet forecasting model for time series with seasonality.

    Best for:
    - Data with strong seasonal patterns
    - Trend changes
    - Holiday effects
    - Items with 18+ months of history

    Source: Facebook Prophet
    """

    def __init__(self):
        super().__init__("Prophet")
        if not PROPHET_AVAILABLE:
            logger.warning("Prophet not installed. Install with: pip install prophet")

    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using Prophet.

        Parameters:
        -----------
        train : pd.Series
            Training data (monthly time series with Period index)
        test : pd.Series
            Test data (for calculating RMSE)
        forecast_horizon : int
            Number of months to forecast

        Returns:
        --------
        Tuple[np.ndarray, float]
            (forecast_array, rmse)
        """
        # Check if Prophet is available
        if not PROPHET_AVAILABLE:
            logger.warning("Prophet not available, falling back to SMA")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)

        # Check minimum data requirements
        if len(train) < settings.prophet_min_months:
            logger.warning(
                f"Insufficient data for Prophet: {len(train)} months "
                f"(need {settings.prophet_min_months})"
            )
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)

        try:
            # Prepare data for Prophet
            train_df = pd.DataFrame({
                'ds': train.index.to_timestamp(),
                'y': train.values
            })

            # Create and fit Prophet model
            model = Prophet(
                yearly_seasonality=settings.prophet_yearly_seasonality,
                weekly_seasonality=settings.prophet_weekly_seasonality,
                daily_seasonality=settings.prophet_daily_seasonality,
                interval_width=settings.prophet_interval_width
            )

            model.fit(train_df)

            # Make future dataframe
            future_dates = model.make_future_dataframe(
                periods=forecast_horizon,
                freq='ME'  # Use 'ME' instead of deprecated 'M'
            )

            # Generate forecast
            forecast_results = model.predict(future_dates)

            # Extract forecast values (last forecast_horizon values)
            forecast = forecast_results.tail(forecast_horizon)['yhat'].values

            # Calculate RMSE on test set
            if len(test) > 0:
                # Create test dates
                test_dates = pd.date_range(
                    start=train.index.max().to_timestamp(),
                    periods=len(test)+1,
                    freq='ME'  # Use 'ME' instead of deprecated 'M'
                )[1:]

                test_df = pd.DataFrame({'ds': test_dates})
                test_forecast = model.predict(test_df)['yhat'].values

                # Calculate RMSE
                rmse = np.sqrt(np.mean((test.values - test_forecast) ** 2))
            else:
                rmse = np.nan

            return forecast, rmse

        except Exception as e:
            logger.warning(f"Prophet failed: {e}. Falling back to SMA.")
            from forecasting_engine.models.sma_model import SMAModel
            return SMAModel().forecast(train, test, forecast_horizon)
