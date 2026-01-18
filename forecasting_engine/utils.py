"""
Utility functions for forecasting engine.
"""
import logging
import pandas as pd
import numpy as np
from typing import Any

logger = logging.getLogger(__name__)


def safe_divide(numerator: float, denominator: float, default: float = 0) -> float:
    """
    Safely divide two numbers, returning default if division by zero.

    Parameters:
    -----------
    numerator : float
        Numerator
    denominator : float
        Denominator
    default : float
        Default value if division by zero

    Returns:
    --------
    float
        Result of division or default
    """
    try:
        if denominator == 0 or pd.isna(denominator):
            return default
        return numerator / denominator
    except Exception:
        return default


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to a range.

    Parameters:
    -----------
    value : float
        Value to clamp
    min_val : float
        Minimum value
    max_val : float
        Maximum value

    Returns:
    --------
    float
        Clamped value
    """
    return max(min_val, min(max_val, value))


def format_number(value: Any, decimals: int = 2) -> str:
    """
    Format a number for display.

    Parameters:
    -----------
    value : Any
        Value to format
    decimals : int
        Number of decimal places

    Returns:
    --------
    str
        Formatted number
    """
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def validate_dataframe(df: pd.DataFrame, required_columns: list) -> bool:
    """
    Validate that DataFrame has required columns.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to validate
    required_columns : list
        List of required column names

    Returns:
    --------
    bool
        True if all columns present
    """
    missing = set(required_columns) - set(df.columns)
    if missing:
        logger.error(f"Missing required columns: {missing}")
        return False
    return True
