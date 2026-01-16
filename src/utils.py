"""
Utility functions for input validation and error handling.

Provides standardized validation and error handling across the application.
"""
import pandas as pd
import logging
import re
from pathlib import Path
from typing import Optional, Tuple, Any, Union
from src.config import DataConfig

logger = logging.getLogger(__name__)


def validate_file_exists(filepath: Path, file_description: str = "File") -> Path:
    """
    Validate that a file exists and return it.

    Parameters:
    -----------
    filepath : Path
        Path to the file to validate
    file_description : str
        Description of the file for error messages

    Returns:
    --------
    Path
        The validated filepath

    Raises:
    -------
    FileNotFoundError
        If the file does not exist
    """
    if not filepath.exists():
        raise FileNotFoundError(
            f"{file_description} not found: {filepath}\n"
            f"Please ensure the data files are in: {DataConfig.DATA_DIR}"
        )
    return filepath


def validate_file_format(filepath: Path, allowed_extensions: Tuple[str, ...] = ('.tsv', '.csv')) -> Path:
    """
    Validate file format/extension.

    Parameters:
    -----------
    filepath : Path
        Path to the file to validate
    allowed_extensions : Tuple[str, ...]
        Allowed file extensions (default: .tsv, .csv)

    Raises:
    -------
    ValueError
        If file extension is not allowed
    """
    if filepath.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"Invalid file format: {filepath.suffix}\n"
            f"Allowed formats: {', '.join(allowed_extensions)}"
        )
    return filepath


def safe_divide(numerator: Any, denominator: Any, default: float = 0.0) -> float:
    """
    Perform safe division to avoid division by zero.

    Parameters:
    -----------
    numerator : Any
        Numerator (will be converted to float)
    denominator : Any
        Denominator (will be converted to float)
    default : float
        Default value if denominator is zero (default: 0.0)

    Returns:
    --------
    float
        Result of division or default value
    """
    try:
        num = float(numerator)
        denom = float(denominator)
        if denom == 0:
            return default
        return num / denom
    except (ValueError, TypeError):
        return default


def safe_percentage_change(old_value: Any, new_value: Any, default: float = 0.0) -> float:
    """
    Calculate safe percentage change.

    Parameters:
    -----------
    old_value : Any
        Old value (will be converted to float)
    new_value : Any
        New value (will be converted to float)
    default : float
        Default value if old_value is zero (default: 0.0)

    Returns:
    --------
    float
        Percentage change or default value
    """
    try:
        old = float(old_value)
        new = float(new_value)
        if old == 0:
            return default
        return ((new - old) / old) * 100
    except (ValueError, TypeError):
        return default


def validate_dataframe_columns(df: pd.DataFrame, required_columns: list,
                                df_name: str = "DataFrame") -> None:
    """
    Validate that a DataFrame contains required columns.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to validate
    required_columns : list
        List of required column names
    df_name : str
        Name of the DataFrame for error messages

    Raises:
    -------
    ValueError
        If required columns are missing
    """
    missing_cols = set(required_columns) - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"{df_name} is missing required columns: {missing_cols}\n"
            f"Available columns: {list(df.columns)}"
        )


def safe_numeric_conversion(df: pd.DataFrame, columns: list,
                            fill_value: float = 0.0) -> pd.DataFrame:
    """
    Safely convert columns to numeric, handling errors gracefully.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to process
    columns : list
        List of column names to convert
    fill_value : float
        Value to use for conversion failures (default: 0.0)

    Returns:
    --------
    pd.DataFrame
        DataFrame with converted columns
    """
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(fill_value)
    return df


def validate_positive_number(value: Any, name: str = "Value",
                            allow_zero: bool = True) -> float:
    """
    Validate that a value is a positive number.

    Parameters:
    -----------
    value : Any
        Value to validate
    name : str
        Name of the value for error messages
    allow_zero : bool
        Whether to allow zero (default: True)

    Returns:
    --------
    float
        Validated value as float

    Raises:
    -------
    ValueError
        If value is not positive
    """
    try:
        num_value = float(value)
        if num_value < 0:
            raise ValueError(f"{name} cannot be negative: {value}")
        if not allow_zero and num_value == 0:
            raise ValueError(f"{name} cannot be zero: {value}")
        return num_value
    except (ValueError, TypeError) as e:
        raise ValueError(f"{name} must be a number: {value}") from e


def log_dataframe_info(df: pd.DataFrame, df_name: str = "DataFrame") -> None:
    """
    Log information about a DataFrame for debugging.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to log info about
    df_name : str
        Name of the DataFrame
    """
    logger.debug(f"{df_name} shape: {df.shape}")
    logger.debug(f"{df_name} columns: {list(df.columns)}")
    logger.debug(f"{df_name} dtypes:\n{df.dtypes}")
    logger.debug(f"{df_name} memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")


def get_safe_cache_dir(cache_dir: Optional[Path] = None) -> Path:
    """
    Get cache directory with safety validation.

    Parameters:
    -----------
    cache_dir : Path, optional
        Custom cache directory

    Returns:
    --------
    Path
        Validated cache directory

    Raises:
    -------
    ValueError
        If cache directory name is not 'cache'
    """
    if cache_dir is None:
        cache_dir = DataConfig.CACHE_DIR

    # Security check: ensure directory name is 'cache'
    if cache_dir.name != "cache":
        raise ValueError(f"Invalid cache directory name: {cache_dir.name}")

    return cache_dir


def handle_common_errors(error: Exception, context: str = "Operation") -> str:
    """
    Common error handling with user-friendly messages.

    Parameters:
    -----------
    error : Exception
        The exception that occurred
    context : str
        Context where the error occurred

    Returns:
    --------
    str
        User-friendly error message
    """
    error_type = type(error).__name__
    error_msg = str(error)

    logger.error(f"{context} failed: {error_type}: {error_msg}")

    # Create user-friendly message
    user_messages = {
        'FileNotFoundError': "Required file not found. Please check your data files.",
        'ValueError': "Invalid data format. Please check your input data.",
        'KeyError': "Missing expected data column. Please verify data structure.",
        'AttributeError': "Data format issue detected. Please check data consistency.",
    }

    return user_messages.get(error_type, f"An error occurred: {error_msg}")


# ===== Security Utilities =====

def sanitize_string(input_string: Any, max_length: int = 1000,
                   allow_special_chars: bool = False) -> str:
    """
    Sanitize string input to prevent injection attacks.

    Parameters:
    -----------
    input_string : Any
        Input to sanitize (will be converted to string)
    max_length : int
        Maximum allowed length (default: 1000)
    allow_special_chars : bool
        Whether to allow special characters (default: False)

    Returns:
    --------
    str
        Sanitized string
    """
    if input_string is None:
        return ""

    # Convert to string
    sanitized = str(input_string)

    # Truncate to max length
    sanitized = sanitized[:max_length]

    # Remove potential SQL injection and XSS patterns first
    dangerous_patterns = [
        (r'--', ''),  # SQL comments
        (r';--', ''),
        (r'/\*', ''),  # Multi-line comments
        (r'\*/', ''),
        (r'<script.*?>', '', True),  # Script tags
        (r'on\w+\s*=', '', True),  # Event handlers (onclick=, onload=, etc.)
        (r'javascript:', '', True),  # JavaScript protocol
        (r'(union|select|insert|update|delete|drop|exec|execute)', '', True),  # SQL keywords
    ]

    for pattern in dangerous_patterns:
        flags = re.IGNORECASE if len(pattern) > 2 and pattern[2] else 0
        sanitized = re.sub(pattern[0], pattern[1], sanitized, flags=flags)

    if not allow_special_chars:
        # Remove potentially dangerous characters
        # Keep only alphanumeric, spaces, and basic punctuation
        sanitized = re.sub(r'[^\w\s\-.,;:]', '', sanitized)

    return sanitized.strip()


def validate_path_safe(filepath: Path, allowed_dir: Path = None) -> Path:
    """
    Validate that a filepath is safe and doesn't escape allowed directory.

    Parameters:
    -----------
    filepath : Path
        Path to validate
    allowed_dir : Path, optional
        Directory that filepath must be within (default: DATA_DIR)

    Returns:
    --------
    Path
        Validated path

    Raises:
    -------
    ValueError
        If path escapes allowed directory
    """
    if allowed_dir is None:
        allowed_dir = DataConfig.DATA_DIR

    # Resolve to absolute paths
    filepath = filepath.resolve()
    allowed_dir = allowed_dir.resolve()

    # Check if filepath is within allowed directory
    try:
        filepath.relative_to(allowed_dir)
    except ValueError:
        raise ValueError(
            f"Path outside allowed directory: {filepath}\n"
            f"Must be within: {allowed_dir}"
        )

    return filepath


def sanitize_dataframe(df: pd.DataFrame, max_string_length: int = 1000) -> pd.DataFrame:
    """
    Sanitize string columns in a DataFrame.

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to sanitize
    max_string_length : int
        Maximum length for string columns

    Returns:
    --------
    pd.DataFrame
        Sanitized DataFrame
    """
    df_sanitized = df.copy()

    for col in df_sanitized.columns:
        if df_sanitized[col].dtype == 'object':
            # Sanitize string columns
            df_sanitized[col] = df_sanitized[col].apply(
                lambda x: sanitize_string(x, max_string_length) if pd.notna(x) else x
            )

    return df_sanitized


def validate_numeric_range(value: Any, name: str = "Value",
                          min_value: Optional[float] = None,
                          max_value: Optional[float] = None) -> float:
    """
    Validate that a numeric value is within specified range.

    Parameters:
    -----------
    value : Any
        Value to validate (will be converted to float)
    name : str
        Name of the value for error messages
    min_value : float, optional
        Minimum allowed value
    max_value : float, optional
        Maximum allowed value

    Returns:
    --------
    float
        Validated value as float

    Raises:
    -------
    ValueError
        If value is out of range or not a number
    """
    try:
        num_value = float(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"{name} must be a number: {value}") from e

    if min_value is not None and num_value < min_value:
        raise ValueError(f"{name} must be >= {min_value}: {num_value}")

    if max_value is not None and num_value > max_value:
        raise ValueError(f"{name} must be <= {max_value}: {num_value}")

    return num_value


def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Create a safe filename by removing dangerous characters.

    Parameters:
    -----------
    filename : str
        Original filename
    max_length : int
        Maximum filename length

    Returns:
    --------
    str
        Safe filename
    """
    # Remove path components
    filename = Path(filename).name

    # Remove dangerous characters (keep alphanumeric, underscore, hyphen, dot)
    filename = re.sub(r'[^\w\-.]', '_', filename)

    # Truncate to max length
    filename = filename[:max_length]

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    return filename or "unnamed"
