"""
Cache Manager - Disk-based caching for forecast results
Stores forecasts to disk for instant loading on subsequent runs

Security: Uses Parquet and JSON instead of pickle for safe serialization
Performance: Parquet is ~10x faster than pickle for DataFrames
"""
import pandas as pd
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict
import time
import logging

logger = logging.getLogger(__name__)


def get_file_hash(filepath: Path) -> str:
    """
    Calculate MD5 hash of a file to detect changes.

    Parameters:
    -----------
    filepath : Path
        Path to file

    Returns:
    --------
    str
        MD5 hash of file contents
    """
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_data_signature(data_dir: Path = Path("data/raw")) -> dict:
    """
    Get signatures of all data files to detect changes.

    Parameters:
    -----------
    data_dir : Path
        Path to data directory

    Returns:
    --------
    dict
        Dictionary with file hashes and timestamps
    """
    signatures = {}

    for file in ["sales.tsv", "supply.tsv", "items.tsv"]:
        filepath = data_dir / file
        if filepath.exists():
            signatures[file] = {
                'hash': get_file_hash(filepath),
                'modified': filepath.stat().st_mtime
            }

    return signatures


def load_cached_forecasts(cache_dir: Path = Path("data/cache")) -> Optional[pd.DataFrame]:
    """
    Load cached forecasts from disk.

    Parameters:
    -----------
    cache_dir : Path
        Path to cache directory

    Returns:
    --------
    pd.DataFrame or None
        Cached forecast dataframe, or None if not found
    """
    cache_file = cache_dir / "forecasts.parquet"
    sig_file = cache_dir / "signatures.json"

    if not cache_file.exists() or not sig_file.exists():
        return None

    try:
        # Load signatures (JSON is safe from code execution)
        with open(sig_file, 'r') as f:
            cached_sigs = json.load(f)

        # Get current data signatures
        current_sigs = get_data_signature()

        # Check if data has changed
        if cached_sigs != current_sigs:
            logger.info("Data has changed, cache invalid")
            return None

        # Load forecasts (Parquet is safe and fast)
        df_forecasts = pd.read_parquet(cache_file)

        # Ensure forecast_horizon column exists (for backward compatibility)
        if 'forecast_horizon' not in df_forecasts.columns:
            logger.warning("Old cache format detected - adding forecast_horizon column")
            df_forecasts['forecast_horizon'] = 6  # Default to 6 months

        cache_time = cache_file.stat().st_mtime
        age_hours = (time.time() - cache_time) / 3600

        logger.info(f"Loaded {len(df_forecasts)} cached forecasts (age: {age_hours:.1f} hours)")
        return df_forecasts

    except Exception as e:
        logger.warning(f"Error loading cache: {e}")
        return None


def save_forecasts_to_cache(df_forecasts: pd.DataFrame,
                            cache_dir: Path = Path("data/cache")) -> None:
    """
    Save forecasts to disk cache.

    Parameters:
    -----------
    df_forecasts : pd.DataFrame
        Forecast dataframe to cache
    cache_dir : Path
        Path to cache directory
    """
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / "forecasts.parquet"
    sig_file = cache_dir / "signatures.json"

    try:
        # Save forecasts (Parquet is safe and fast)
        df_forecasts.to_parquet(cache_file, index=False)

        # Save data signatures (JSON is safe)
        signatures = get_data_signature()
        with open(sig_file, 'w') as f:
            json.dump(signatures, f)

        logger.info(f"Cached {len(df_forecasts)} forecasts to disk")
        logger.info(f"Cache location: {cache_file}")

    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def clear_cache(cache_dir: Path = Path("data/cache")) -> None:
    """
    Clear cached forecasts with safety validation.

    Parameters:
    -----------
    cache_dir : Path
        Path to cache directory
    """
    import shutil
    from src.utils import get_safe_cache_dir

    # Validate cache directory is safe
    try:
        cache_dir = get_safe_cache_dir(cache_dir)
    except ValueError as e:
        logger.error(f"Cache validation failed: {e}")
        return

    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    else:
        logger.info("No cache to clear")


def should_refresh_cache(cache_dir: Path = Path("data/cache"),
                         max_age_hours: float = 24.0) -> bool:
    """
    Check if cached forecasts should be refreshed.

    Parameters:
    -----------
    cache_dir : Path
        Path to cache directory
    max_age_hours : float
        Maximum age of cache in hours (default: 24)

    Returns:
    --------
    bool
        True if cache should be refreshed
    """
    cache_file = cache_dir / "forecasts.parquet"

    if not cache_file.exists():
        return True

    # Check cache age
    cache_time = cache_file.stat().st_mtime
    age_hours = (time.time() - cache_time) / 3600

    if age_hours > max_age_hours:
        logger.info(f"Cache is {age_hours:.1f} hours old (max: {max_age_hours} hours)")
        return True

    # Check if data has changed
    sig_file = cache_dir / "signatures.json"
    if sig_file.exists():
        try:
            with open(sig_file, 'r') as f:
                cached_sigs = json.load(f)

            current_sigs = get_data_signature()

            if cached_sigs != current_sigs:
                logger.info("Data files have changed, cache invalid")
                return True
        except Exception as e:
            logger.warning(f"Error checking cache validity: {e}")
            return True

    return False


def get_cache_info(cache_dir: Path = Path("data/cache")) -> dict:
    """
    Get information about cached forecasts.

    Parameters:
    -----------
    cache_dir : Path
        Path to cache directory

    Returns:
    --------
    dict
        Cache information including age, item count, validity
    """
    cache_file = cache_dir / "forecasts.parquet"
    sig_file = cache_dir / "signatures.json"

    info = {
        'exists': cache_file.exists(),
        'item_count': 0,
        'age_hours': None,
        'valid': False
    }

    if cache_file.exists():
        try:
            # Get cache age
            cache_time = cache_file.stat().st_mtime
            info['age_hours'] = (time.time() - cache_time) / 3600

            # Get item count (Parquet is fast)
            df = pd.read_parquet(cache_file)
            info['item_count'] = len(df)

            # Ensure forecast_horizon column exists (for backward compatibility)
            if 'forecast_horizon' not in df.columns:
                df['forecast_horizon'] = 6  # Default to 6 months (don't save, just for info)

            # Check validity
            if sig_file.exists():
                with open(sig_file, 'r') as f:
                    cached_sigs = json.load(f)
                current_sigs = get_data_signature()
                info['valid'] = (cached_sigs == current_sigs)

        except Exception as e:
            info['error'] = str(e)

    return info
