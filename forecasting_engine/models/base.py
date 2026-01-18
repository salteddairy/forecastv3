"""
Abstract base class for all forecasting models.
Ensures consistent interface across all models in the tournament.
"""
from abc import ABC, abstractmethod
from typing import Tuple
import pandas as pd
import numpy as np


class ForecastModel(ABC):
    """
    Abstract base class for forecasting models.

    All models must implement the forecast() method with the same signature.
    """

    def __init__(self, name: str):
        """
        Initialize model.

        Parameters:
        -----------
        name : str
            Model name (e.g., "Prophet", "ARIMA")
        """
        self.name = name

    @abstractmethod
    def forecast(
        self,
        train: pd.Series,
        test: pd.Series,
        forecast_horizon: int = 12
    ) -> Tuple[np.ndarray, float]:
        """
        Generate forecast using this model.

        Parameters:
        -----------
        train : pd.Series
            Training data (monthly time series with Period index)
        test : pd.Series
            Test data (for calculating RMSE)
        forecast_horizon : int
            Number of months to forecast (default: 12)

        Returns:
        --------
        Tuple[np.ndarray, float]
            (forecast_array, rmse)
            - forecast_array: Array of forecast values (length = forecast_horizon)
            - rmse: Root Mean Square Error on test set
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
