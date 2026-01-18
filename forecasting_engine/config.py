"""
Configuration management for forecasting engine.
Loads settings from environment variables with sensible defaults.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: Optional[str] = None  # Required for operations, but allow import

    # Logging
    log_level: str = "INFO"

    # Forecasting parameters
    min_months_history: int = 6
    min_orders: int = 10
    max_months_history: int = 24
    forecast_horizon: int = 12  # Always 12 months

    # Tournament settings
    use_advanced_models: bool = True
    parallel_threshold: int = 10
    n_jobs: int = -1  # -1 = all CPUs

    # Prophet settings
    prophet_yearly_seasonality: bool = True
    prophet_weekly_seasonality: bool = False
    prophet_daily_seasonality: bool = False
    prophet_interval_width: float = 0.95

    # Model minimum data requirements
    prophet_min_months: int = 18
    sarima_min_months: int = 24
    arima_min_months: int = 12
    theta_min_months: int = 12

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Create singleton instance
def _load_settings() -> Settings:
    """Load settings from environment."""
    try:
        return Settings()
    except Exception as e:
        # Log but don't fail - allow import for testing
        import logging
        logging.warning(f"Could not load all settings: {e}")
        # Return default settings
        return Settings()


settings = _load_settings()
