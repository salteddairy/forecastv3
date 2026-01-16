"""
Centralized logging configuration for the forecast application.

Provides consistent logging format across all modules.
Log files are written to data/logs/ directory.
"""
import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path = Path("data/logs"), level: int = logging.INFO) -> None:
    """
    Configure logging for the application.

    Parameters:
    -----------
    log_dir : Path
        Directory to store log files (default: data/logs)
    level : int
        Logging level (default: INFO)
    """
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler for all logs
    file_handler = logging.FileHandler(log_dir / 'app.log', encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # File handler for errors only (using a custom filter)
    class ErrorFilter(logging.Filter):
        def filter(self, record):
            return record.levelno >= logging.ERROR

    error_handler = logging.FileHandler(log_dir / 'errors.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # Set specific levels for noisy modules
    logging.getLogger('prophet').setLevel(logging.WARNING)
    logging.getLogger('cmdstanpy').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Parameters:
    -----------
    name : str
        Logger name (typically __name__ from calling module)

    Returns:
    --------
    logging.Logger
        Logger instance
    """
    return logging.getLogger(name)


# Setup logging when module is imported
setup_logging()
