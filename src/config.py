"""
Configuration module for SAP B1 Inventory & Forecast Analyzer.

Centralizes all configuration constants to avoid magic numbers and improve maintainability.
"""
from pathlib import Path


class DataConfig:
    """Data file paths and directories"""
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data" / "raw"
    CACHE_DIR = PROJECT_ROOT / "data" / "cache"
    LOGS_DIR = PROJECT_ROOT / "data" / "logs"
    QUERIES_DIR = PROJECT_ROOT / "queries"

    @classmethod
    def get_data_file(cls, filename: str) -> Path:
        """Get a data file path with validation"""
        filepath = cls.DATA_DIR / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        return filepath


class ForecastConfig:
    """Forecast model configuration"""
    # Minimum months required for different forecasting models
    MIN_HISTORY_SMA = 3
    MIN_HISTORY_HOLT_WINTERS = 6
    MIN_HISTORY_PROPHET = 18

    # Default forecast horizon (1 year = 12 months)
    DEFAULT_FORECAST_HORIZON = 12
    MIN_FORECAST_HORIZON = 1
    MAX_FORECAST_HORIZON = 12

    # Dynamic forecast horizon thresholds
    HIGH_VELOCITY_THRESHOLD = 100  # Average monthly demand
    MEDIUM_VELOCITY_THRESHOLD = 20

    # Coefficient of Variation thresholds
    CV_THRESHOLD_SMOOTH = 0.5
    CV_THRESHOLD_INTERMITTENT = 1.0


class CleaningConfig:
    """Data cleaning configuration"""
    # Z-score threshold for outlier detection
    OUTLIER_Z_THRESHOLD = 3.0

    # Maximum lead time (in days) before considered outlier
    MAX_LEAD_TIME_DAYS = 365

    # Minimum data points for vendor statistics
    MIN_VENDOR_DATA_POINTS = 3


class OptimizationConfig:
    """Inventory optimization configuration"""
    # Carrying cost rate (annual)
    DEFAULT_CARRYING_RATE = 0.25

    # Freight costs as percentages
    STANDARD_FREIGHT_PCT = 0.05
    SPECIAL_ORDER_SURCHARGE_PCT = 0.10
    EXPEDITED_FREIGHT_PCT = 0.08

    # Service level targets
    TARGET_SERVICE_LEVEL = 0.95
    MIN_SERVICE_LEVEL = 0.80

    # TCO recommendation thresholds
    TCO_SAVINGS_THRESHOLD = 100  # Minimum annual savings to recommend switching


class CacheConfig:
    """Cache configuration"""
    DEFAULT_CACHE_DIR = Path("data/cache")
    DEFAULT_MAX_AGE_HOURS = 24.0

    # Cache file names
    FORECASTS_FILE = "forecasts.parquet"
    SIGNATURES_FILE = "signatures.json"


class UIConfig:
    """UI configuration"""
    # Inactive item threshold (months without sales)
    INACTIVE_MONTHS_THRESHOLD = 12

    # Stockout urgency thresholds (in days)
    URGENCY_CRITICAL = 30
    URGENCY_HIGH = 60
    URGENCY_MEDIUM = 90

    # Default filter values
    DEFAULT_SAMPLE_SIZE = None  # None = use all data


class LoggingConfig:
    """Logging configuration"""
    DEFAULT_LEVEL = 20  # INFO level
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Log file names
    APP_LOG_FILE = "app.log"
    ERROR_LOG_FILE = "errors.log"


# Configuration instance for easy import
config = type('Config', (), {
    'data': DataConfig,
    'forecast': ForecastConfig,
    'cleaning': CleaningConfig,
    'optimization': OptimizationConfig,
    'cache': CacheConfig,
    'ui': UIConfig,
    'logging': LoggingConfig,
})()
