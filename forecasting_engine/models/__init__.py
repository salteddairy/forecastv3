"""
Forecasting models - Tournament approach.
All models follow the same interface for competition.
"""

from forecasting_engine.models.base import ForecastModel
from forecasting_engine.models.prophet_model import ProphetModel
from forecasting_engine.models.sarima_model import SARIMAModel
from forecasting_engine.models.arima_model import ARIMAModel
from forecasting_engine.models.theta_model import ThetaModel
from forecasting_engine.models.holt_winters_model import HoltWintersModel
from forecasting_engine.models.croston_model import CrostonModel
from forecasting_engine.models.sma_model import SMAModel

# Model registry for tournament
MODEL_REGISTRY = {
    "Prophet": ProphetModel,
    "SARIMA": SARIMAModel,
    "ARIMA": ARIMAModel,
    "Theta": ThetaModel,
    "Holt-Winters": HoltWintersModel,
    "Croston": CrostonModel,
    "SMA": SMAModel,
}

__all__ = [
    "ForecastModel",
    "ProphetModel",
    "SARIMAModel",
    "ARIMAModel",
    "ThetaModel",
    "HoltWintersModel",
    "CrostonModel",
    "SMAModel",
    "MODEL_REGISTRY",
]
