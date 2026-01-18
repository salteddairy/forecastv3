"""
Forecasting Engine - Tournament Approach
Background service for generating demand forecasts using 7 competing models.
"""

__version__ = "1.0.0"
__author__ = "Claude (AI Assistant)"

from forecasting_engine.config import settings
from forecasting_engine.db import get_engine, get_session, test_connection
from forecasting_engine.models import MODEL_REGISTRY

__all__ = [
    "settings",
    "get_engine",
    "get_session",
    "test_connection",
    "MODEL_REGISTRY",
]
