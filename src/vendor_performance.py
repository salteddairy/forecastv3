"""
Vendor Performance Module - Lead Time Analysis by Item and Vendor
Calculates per-item-per-vendor lead times with vendor fallback
Identifies fastest vendors and provides vendor performance metrics
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_item_vendor_lead_times(df_history: pd.DataFrame,
                                     min_sample_size: int = 3) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate lead time statistics by item-vendor combination with vendor fallback.

    Primary calculation: Item-vendor specific averages
    Fallback: Vendor average if item-vendor data insufficient (< min_sample_size)

    Parameters:
    -----------
    df_history : pd.DataFrame
        Supply history with columns: ItemCode, VendorCode, lead_time_days
    min_sample_size : int
        Minimum number of observations required for item-vendor calculation (default: 3)

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        (item_vendor_stats, vendor_stats)
        - item_vendor_stats: Lead time metrics per item-vendor pair
        - vendor_stats: Overall vendor performance metrics
    """
    logger.info("Calculating item-vendor lead time statistics...")

    # Filter to valid lead times only
    df_valid = df_history[
        df_history['lead_time_days'].notna() &
        (df_history['lead_time_days'] > 0)
    ].copy()

    if len(df_valid) == 0:
        logger.warning("No valid lead time data found")
        return pd.DataFrame(), pd.DataFrame()

    # Import safe_divide for CV calculations
    from src.utils import safe_divide

    # Calculate vendor-level stats (for fallback)
    vendor_stats = df_valid.groupby('VendorCode')['lead_time_days'].agg([
        ('mean_lead_time', 'mean'),
        ('median_lead_time', 'median'),
        ('min_lead_time', 'min'),
        ('max_lead_time', 'max'),
        ('std_lead_time', 'std'),
        ('count', 'count'),
        ('cv', lambda x: safe_divide(x.std(), x.mean(), 0.0))  # Coefficient of variation
    ]).reset_index()

    vendor_stats = vendor_stats.round(2)
    logger.info(f"Calculated vendor stats for {len(vendor_stats)} vendors")

    # Calculate item-vendor level stats
    item_vendor_stats = df_valid.groupby(['ItemCode', 'VendorCode'])['lead_time_days'].agg([
        ('mean_lead_time', 'mean'),
        ('median_lead_time', 'median'),
        ('min_lead_time', 'min'),
        ('max_lead_time', 'max'),
        ('std_lead_time', 'std'),
        ('count', 'count'),
        ('cv', lambda x: safe_divide(x.std(), x.mean(), 0.0))
    ]).reset_index()

    item_vendor_stats = item_vendor_stats.round(2)

    # Determine if we should use item-vendor or vendor fallback
    # Add vendor averages for fallback
    item_vendor_stats = item_vendor_stats.merge(
        vendor_stats[['VendorCode', 'mean_lead_time', 'median_lead_time']],
        on='VendorCode',
        suffixes=('', '_vendor')
    )

    # Flag items with insufficient data
    item_vendor_stats['use_fallback'] = item_vendor_stats['count'] < min_sample_size

    # Add effective lead time (item-vendor if enough data, else vendor)
    item_vendor_stats['effective_mean_lead_time'] = item_vendor_stats.apply(
        lambda row: row['mean_lead_time_vendor'] if row['use_fallback'] else row['mean_lead_time'],
        axis=1
    )

    # Calculate reliability score (higher = more reliable)
    # Factors: low CV (consistency), high count (data volume)
    item_vendor_stats['reliability_score'] = (
        (1 - item_vendor_stats['cv'].clip(0, 1)) * 0.5 +  # Consistency (50%)
        (item_vendor_stats['count'] / item_vendor_stats['count'].max()) * 0.5  # Data volume (50%)
    ) * 100

    logger.info(f"Calculated item-vendor stats for {len(item_vendor_stats)} item-vendor pairs")
    logger.info(f"  - Using item-vendor specific: {(~item_vendor_stats['use_fallback']).sum()}")
    logger.info(f"  - Using vendor fallback: {item_vendor_stats['use_fallback'].sum()}")

    return item_vendor_stats, vendor_stats


def identify_fastest_vendors(item_vendor_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Identify the fastest vendor for each item based on mean lead time.

    Parameters:
    -----------
    item_vendor_stats : pd.DataFrame
        Item-vendor lead time statistics from calculate_item_vendor_lead_times()

    Returns:
    --------
    pd.DataFrame
        Fastest vendor for each item with comparison to alternatives
    """
    if item_vendor_stats.empty:
        logger.warning("No item-vendor stats available for fastest vendor identification")
        return pd.DataFrame()

    logger.info("Identifying fastest vendors for each item...")

    # For each item, find the vendor with lowest mean lead time
    fastest_vendors = item_vendor_stats.loc[
        item_vendor_stats.groupby('ItemCode')['effective_mean_lead_time'].idxmin()
    ].copy()

    fastest_vendors = fastest_vendors.sort_values('ItemCode').reset_index(drop=True)

    # Calculate alternative vendor count for each item
    alt_vendor_counts = item_vendor_stats.groupby('ItemCode').size().reset_index(name='vendor_options')
    fastest_vendors = fastest_vendors.merge(alt_vendor_counts, on='ItemCode')

    logger.info(f"Identified fastest vendors for {len(fastest_vendors)} items")
    logger.info(f"  - Items with multiple vendors: {(fastest_vendors['vendor_options'] > 1).sum()}")

    return fastest_vendors


def calculate_vendor_performance_scores(vendor_stats: pd.DataFrame,
                                        item_vendor_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate overall vendor performance scores.

    Scoring factors:
    - Speed (40%): Lower median lead time = better
    - Consistency (30%): Lower coefficient of variation = better
    - Volume (20%): More transactions = more reliable
    - Coverage (10%): More unique items supplied = better

    Parameters:
    -----------
    vendor_stats : pd.DataFrame
        Vendor-level statistics
    item_vendor_stats : pd.DataFrame
        Item-vendor level statistics

    Returns:
    --------
    pd.DataFrame
        Vendor performance metrics with overall score
    """
    if vendor_stats.empty:
        logger.warning("No vendor stats available for performance scoring")
        return pd.DataFrame()

    logger.info("Calculating vendor performance scores...")

    # Calculate item coverage per vendor
    item_coverage = item_vendor_stats.groupby('VendorCode')['ItemCode'].nunique().reset_index()
    item_coverage.columns = ['VendorCode', 'unique_items']

    # Merge coverage into vendor stats
    vendor_perf = vendor_stats.merge(item_coverage, on='VendorCode', how='left')

    # Normalize metrics (0-100 scale, higher is better)
    # Speed: Lower lead time = higher score (inverse)
    max_lead_time = vendor_perf['median_lead_time'].max()
    vendor_perf['speed_score'] = (1 - vendor_perf['median_lead_time'] / max_lead_time) * 100

    # Consistency: Lower CV = higher score (inverse, already 0-1)
    vendor_perf['consistency_score'] = (1 - vendor_perf['cv'].clip(0, 1)) * 100

    # Volume: More transactions = higher score
    max_count = vendor_perf['count'].max()
    vendor_perf['volume_score'] = (vendor_perf['count'] / max_count) * 100

    # Coverage: More unique items = higher score
    max_items = vendor_perf['unique_items'].max()
    vendor_perf['coverage_score'] = (vendor_perf['unique_items'] / max_items) * 100 if max_items > 0 else 0

    # Calculate overall score (weighted)
    vendor_perf['overall_score'] = (
        vendor_perf['speed_score'] * 0.40 +
        vendor_perf['consistency_score'] * 0.30 +
        vendor_perf['volume_score'] * 0.20 +
        vendor_perf['coverage_score'] * 0.10
    ).round(2)

    # Rank vendors (handle NaN values by filling with 0 before ranking)
    vendor_perf['rank'] = vendor_perf['overall_score'].fillna(0).rank(ascending=False).astype(int)

    # Sort by rank
    vendor_perf = vendor_perf.sort_values('rank').reset_index(drop=True)

    logger.info(f"Calculated performance scores for {len(vendor_perf)} vendors")
    logger.info(f"  - Top vendor: {vendor_perf.iloc[0]['VendorCode'] if len(vendor_perf) > 0 else 'N/A'}")

    return vendor_perf


def get_item_lead_time_with_fallback(item_code: str,
                                     df_history: pd.DataFrame,
                                     item_vendor_stats: pd.DataFrame = None,
                                     vendor_stats: pd.DataFrame = None) -> Dict:
    """
    Get lead time information for a specific item with fallback logic.

    Priority:
    1. Item-vendor specific mean (if sufficient data)
    2. Vendor average mean
    3. Overall median lead time

    Parameters:
    -----------
    item_code : str
        Item code to look up
    df_history : pd.DataFrame
        Supply history data
    item_vendor_stats : pd.DataFrame, optional
        Pre-calculated item-vendor stats (will calculate if not provided)
    vendor_stats : pd.DataFrame, optional
        Pre-calculated vendor stats (will calculate if not provided)

    Returns:
    --------
    Dict
        Lead time information with source and vendors
    """
    # Calculate stats if not provided
    if item_vendor_stats is None or vendor_stats is None:
        item_vendor_stats, vendor_stats = calculate_item_vendor_lead_times(df_history)

    # Filter for this item
    item_data = item_vendor_stats[item_vendor_stats['ItemCode'] == item_code].copy()

    if item_data.empty:
        # No data for this item
        overall_median = df_history['lead_time_days'].median()
        return {
            'item_code': item_code,
            'lead_time_days': overall_median if pd.notna(overall_median) else 21,  # Default 21 days
            'source': 'overall_fallback',
            'vendors': []
        }

    # Find fastest vendor
    fastest = item_data.loc[item_data['effective_mean_lead_time'].idxmin()]

    # Get all vendors for this item
    vendors = []
    for _, row in item_data.sort_values('effective_mean_lead_time').iterrows():
        vendors.append({
            'vendor_code': row['VendorCode'],
            'lead_time_days': row['effective_mean_lead_time'],
            'is_fastest': row['VendorCode'] == fastest['VendorCode'],
            'using_fallback': bool(row['use_fallback']),
            'sample_count': int(row['count'])
        })

    return {
        'item_code': item_code,
        'lead_time_days': fastest['effective_mean_lead_time'],
        'fastest_vendor': fastest['VendorCode'],
        'source': 'item_vendor_specific' if not fastest['use_fallback'] else 'vendor_fallback',
        'vendors': vendors
    }


def save_vendor_performance_data(item_vendor_stats: pd.DataFrame,
                                  vendor_stats: pd.DataFrame,
                                  fastest_vendors: pd.DataFrame,
                                  vendor_perf: pd.DataFrame,
                                  output_dir: Path = Path("data/cache")) -> None:
    """
    Save vendor performance data to cache for quick loading.

    Parameters:
    -----------
    item_vendor_stats : pd.DataFrame
        Item-vendor lead time statistics
    vendor_stats : pd.DataFrame
        Vendor-level statistics
    fastest_vendors : pd.DataFrame
        Fastest vendor per item
    vendor_perf : pd.DataFrame
        Vendor performance scores
    output_dir : Path
        Directory to save cache files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Saving vendor performance data to cache...")

    try:
        item_vendor_stats.to_parquet(output_dir / "item_vendor_stats.parquet", index=False)
        vendor_stats.to_parquet(output_dir / "vendor_stats.parquet", index=False)
        fastest_vendors.to_parquet(output_dir / "fastest_vendors.parquet", index=False)
        vendor_perf.to_parquet(output_dir / "vendor_perf.parquet", index=False)

        logger.info("[OK] Vendor performance data cached successfully")
    except Exception as e:
        logger.error(f"Failed to cache vendor performance data: {e}")


def load_vendor_performance_data(cache_dir: Path = Path("data/cache")) -> Tuple[Optional[pd.DataFrame], ...]:
    """
    Load vendor performance data from cache.

    Parameters:
    -----------
    cache_dir : Path
        Directory containing cache files

    Returns:
    --------
    Tuple of DataFrames or None
        (item_vendor_stats, vendor_stats, fastest_vendors, vendor_perf)
    """
    logger.info("Loading vendor performance data from cache...")

    try:
        item_vendor_stats = pd.read_parquet(cache_dir / "item_vendor_stats.parquet")
        vendor_stats = pd.read_parquet(cache_dir / "vendor_stats.parquet")
        fastest_vendors = pd.read_parquet(cache_dir / "fastest_vendors.parquet")
        vendor_perf = pd.read_parquet(cache_dir / "vendor_perf.parquet")

        logger.info("[OK] Vendor performance data loaded from cache")
        return item_vendor_stats, vendor_stats, fastest_vendors, vendor_perf
    except Exception as e:
        logger.warning(f"Failed to load vendor performance cache: {e}")
        return None, None, None, None
