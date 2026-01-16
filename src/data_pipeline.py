"""
Data Pipeline Module - Modular Processing with Caching and Progress Tracking
Separates data loading, forecasting, and report generation for better performance
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime
import hashlib
import json
from functools import lru_cache
import threading
import time
from functools import wraps

logger = logging.getLogger(__name__)


# ============================================================================
# TIMING UTILITIES - Embedded to avoid import issues
# ============================================================================

# Dictionary to store timing statistics
_timings = {}

def reset_timings():
    """Clear all timing statistics."""
    global _timings
    _timings = {}

def get_timings():
    """Get all timing statistics."""
    return _timings.copy()

class Timer:
    """
    Context manager for timing code blocks.

    Usage:
        with Timer("Data Loading"):
            # ... code ...
            pass
    """
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        logger.info(f"[TIMING] {self.operation_name}: Starting...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start

        # Store timing
        if self.operation_name not in _timings:
            _timings[self.operation_name] = []
        _timings[self.operation_name].append(duration)

        # Log timing
        if exc_type is not None:
            logger.error(f"[TIMING] {self.operation_name}: FAILED after {duration:.2f}s")
        else:
            if duration < 1:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration*1000:.0f}ms")
            elif duration < 60:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration:.2f}s")
            else:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration/60:.1f}min")

        return False  # Don't suppress exceptions

def print_timing_summary():
    """Print a summary of all timing statistics."""
    global _timings

    if not _timings:
        logger.info("[TIMING] No timing statistics available")
        return

    logger.info("=" * 60)
    logger.info("PERFORMANCE TIMING SUMMARY")
    logger.info("=" * 60)

    total_time = 0
    for op_name, durations in sorted(_timings.items()):
        count = len(durations)
        total = sum(durations)
        avg = total / count
        total_time += total

        # Format time appropriately
        if avg < 1:
            time_str = f"{avg*1000:.0f}ms avg"
        elif avg < 60:
            time_str = f"{avg:.2f}s avg"
        else:
            time_str = f"{avg/60:.1f}min avg"

        logger.info(f"  {op_name}:")
        logger.info(f"    Runs: {count}, Total: {total:.2f}s, {time_str}")

    logger.info("-" * 60)

    if total_time < 60:
        logger.info(f"Total Pipeline Time: {total_time:.2f}s")
    else:
        logger.info(f"Total Pipeline Time: {total_time/60:.1f} minutes")

    logger.info("=" * 60)


# ============================================================================
# END TIMING UTILITIES
# ============================================================================


class DataPipeline:
    """
    Modular data pipeline with caching and progress tracking.

    Separates processing into stages:
    1. Load raw data (fast)
    2. Generate forecasts (slow, cached)
    3. Generate reports (medium speed)
    4. Combine results (fast)

    Each stage can be run independently or combined.
    """

    def __init__(self, cache_dir: Path = Path("data/cache")):
        """
        Initialize data pipeline.

        Parameters:
        -----------
        cache_dir : Path
            Directory for cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Thread lock for cache operations (prevents race conditions)
        self._cache_lock = threading.Lock()

        # In-memory cache for dimensions
        self._dimension_cache = {}
        self._capacity_cache = None

        # Data storage
        self.raw_data = {}
        self.forecasts = None
        self.reports = {}

        logger.info(f"DataPipeline initialized with cache dir: {cache_dir}")

    def get_data_hash(self, filepath: Path) -> str:
        """
        Generate hash of file for cache validation.

        Parameters:
        -----------
        filepath : Path
            File to hash

        Returns:
        --------
        str
            MD5 hash of file size + modification time
        """
        if not filepath.exists():
            return ""

        stat = filepath.stat()
        hash_str = f"{filepath.name}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.md5(hash_str.encode()).hexdigest()

    def get_cache_path(self, cache_type: str) -> Path:
        """Get cache file path for a given type."""
        return self.cache_dir / f"{cache_type}.parquet"

    def load_raw_data(self, data_dir: Path, progress_callback=None) -> Dict:
        """
        Stage 1: Load raw data from TSV files (FAST).

        Parameters:
        -----------
        data_dir : Path
            Directory containing raw data files
        progress_callback : callable, optional
            Callback for progress updates

        Returns:
        --------
        Dict
            Dictionary with raw data DataFrames
        """
        logger.info("Stage 1: Loading raw data...")
        if progress_callback:
            progress_callback(0, "Loading raw data...")

        from src.ingestion import load_sales_orders, load_supply_chain, load_items
        from src.cleaning import clean_supply_data
        from src.uom_conversion_sap import convert_stock_to_sales_uom_sap

        # Load raw data (20%)
        with Timer("Load Sales Orders"):
            df_sales = load_sales_orders(data_dir / "sales.tsv")
        if progress_callback:
            progress_callback(20, "Loading sales data...")

        with Timer("Load Supply Chain"):
            df_history, df_schedule = load_supply_chain(data_dir / "supply.tsv")
        if progress_callback:
            progress_callback(40, "Loading supply data...")

        with Timer("Load Items"):
            df_items = load_items(data_dir / "items.tsv")
        if progress_callback:
            progress_callback(60, "Loading items data...")

        # Filter out inactive items (if ValidFor column exists)
        initial_count = len(df_items)
        if 'ValidFor' in df_items.columns:
            df_items = df_items[df_items['ValidFor'] == 'Y'].copy()
            filtered_count = initial_count - len(df_items)
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} inactive items (ValidFor='N')")
        if 'Frozen' in df_items.columns:
            df_items = df_items[df_items['Frozen'] != 'Y'].copy()
            frozen_count = initial_count - len(df_items)
            if frozen_count > 0:
                logger.info(f"Filtered out {frozen_count} frozen items")

        # UOM conversion (20%)
        with Timer("UoM Conversion"):
            df_items = convert_stock_to_sales_uom_sap(df_items)
        if progress_callback:
            progress_callback(80, "Converting units of measure...")

        # Log conversion results
        if 'CurrentStock_SalesUOM' in df_items.columns:
            converted_count = df_items['CurrentStock_SalesUOM'].notna().sum()
            logger.info(f"[OK] UoM conversion completed: {converted_count}/{len(df_items)} items converted to Sales UoM")
        else:
            logger.warning("[WARNING] UoM conversion did not create CurrentStock_SalesUOM column")

        # Clean supply data (20%)
        with Timer("Clean Supply Data"):
            df_history_clean, df_schedule_clean = clean_supply_data(df_history, df_schedule)

        # Calculate last sale date for inactive filtering
        df_sales['date'] = pd.to_datetime(df_sales['date'], errors='coerce')
        last_sale_dates = df_sales.groupby('item_code')['date'].max().reset_index()
        last_sale_dates.columns = ['Item No.', 'last_sale_date']

        self.raw_data = {
            'sales': df_sales,
            'history': df_history_clean,
            'schedule': df_schedule_clean,
            'items': df_items,
            'last_sale_dates': last_sale_dates
        }

        if progress_callback:
            progress_callback(100, "Raw data loaded!")

        logger.info(f"Loaded {len(df_sales)} sales, {len(df_items)} items")
        return self.raw_data

    def generate_forecasts(self, n_samples: Optional[int] = None,
                          use_cache: bool = True,
                          force_refresh: bool = False,
                          progress_callback=None) -> pd.DataFrame:
        """
        Stage 2: Generate forecasts (SLOW, cached).

        Parameters:
        -----------
        n_samples : int, optional
            Number of items to forecast (None = all)
        use_cache : bool
            Whether to use cached forecasts
        force_refresh : bool
            Force regeneration even if cache exists
        progress_callback : callable, optional
            Callback for progress updates

        Returns:
        --------
        pd.DataFrame
            Forecast results
        """
        logger.info("Stage 2: Generating forecasts...")

        # Check cache - use combined hash of all data files AND n_samples
        cache_path = self.get_cache_path("forecasts")
        data_dir = Path("data/raw")
        # Combine hashes of all input files for proper cache invalidation
        sales_hash = self.get_data_hash(data_dir / "sales.tsv")
        items_hash = self.get_data_hash(data_dir / "items.tsv")
        supply_hash = self.get_data_hash(data_dir / "supply.tsv")
        # Include n_samples in cache key to ensure different sample sizes are cached separately
        samples_key = str(n_samples) if n_samples is not None else "all"
        data_hash = f"{sales_hash}_{items_hash}_{supply_hash}_{samples_key}"

        # Thread-safe cache loading with lock
        if use_cache and not force_refresh and cache_path.exists():
            # Acquire lock before accessing cache (prevents race conditions)
            with self._cache_lock:
                # Double-check pattern inside lock
                if not cache_path.exists():
                    logger.info("Cache file disappeared while waiting for lock - regenerating")
                else:
                    try:
                        cached = pd.read_parquet(cache_path)
                        cache_meta_path = self.cache_dir / "forecasts_meta.json"
                        if cache_meta_path.exists():
                            with open(cache_meta_path) as f:
                                meta = json.load(f)
                                if meta.get('data_hash') == data_hash and meta.get('n_samples') == n_samples:
                                    # Ensure forecast_horizon column exists (for backward compatibility)
                                    if 'forecast_horizon' not in cached.columns:
                                        logger.warning("Old cache format detected - adding forecast_horizon column")
                                        cached['forecast_horizon'] = 6  # Default to 6 months
                                    logger.info(f"Loaded {len(cached)} forecasts from cache")
                                    self.forecasts = cached
                                    if progress_callback:
                                        progress_callback(100, "Forecasts loaded from cache!")
                                    return cached
                                else:
                                    logger.info(f"Cache hash or n_samples mismatch - regenerating forecasts (cached: {meta.get('n_samples')}, requested: {n_samples})")
                        else:
                            logger.info("Cache metadata missing - regenerating forecasts")
                    except Exception as e:
                        logger.warning(f"Failed to load cache: {e}")

        if progress_callback:
            progress_callback(10, "Running forecasting tournament...")

        # Run forecasting tournament
        from src.forecasting import forecast_items

        df_sales = self.raw_data['sales']

        if n_samples:
            df_forecasts = forecast_items(df_sales, n_samples=n_samples)
        else:
            df_forecasts = forecast_items(df_sales)

        if progress_callback:
            progress_callback(90, "Caching forecasts...")

        # Save to cache (thread-safe with lock)
        try:
            # Acquire lock before writing to cache
            with self._cache_lock:
                df_forecasts.to_parquet(cache_path, index=False)
                # Save metadata
                cache_meta_path = self.cache_dir / "forecasts_meta.json"
                with open(cache_meta_path, 'w') as f:
                    json.dump({
                        'data_hash': data_hash,
                        'n_samples': n_samples,
                        'timestamp': datetime.now().isoformat(),
                        'item_count': len(df_forecasts)
                    }, f)
                logger.info(f"Cached {len(df_forecasts)} forecasts")
        except Exception as e:
            logger.warning(f"Failed to cache forecasts: {e}")

        # Save forecast snapshot for accuracy tracking
        try:
            from src.forecast_accuracy import save_forecast_snapshot
            snapshot_id = save_forecast_snapshot(df_forecasts, self.cache_dir)
            logger.info(f"Saved forecast snapshot {snapshot_id} for accuracy tracking")
        except Exception as e:
            logger.warning(f"Failed to save forecast snapshot: {e}")

        self.forecasts = df_forecasts

        if progress_callback:
            progress_callback(100, f"Generated {len(df_forecasts)} forecasts!")

        return df_forecasts

    def generate_inventory_health(self, use_cache: bool = True) -> Dict:
        """
        Generate inventory health report (dead stock, shelf life risk).

        Parameters:
        -----------
        use_cache : bool
            Whether to use cached inventory health data

        Returns:
        --------
        Dict
            Inventory health report with dead_stock, shelf_life_risk, summary
        """
        from src.inventory_health import (
            generate_inventory_health_report,
            save_inventory_health_report,
            load_inventory_health_report
        )

        # Try loading from cache
        if use_cache:
            cached = load_inventory_health_report(self.cache_dir)
            if cached is not None:
                logger.info("Using cached inventory health report")
                return cached

        # Generate fresh
        logger.info("Generating inventory health report...")
        health_report = generate_inventory_health_report(
            self.raw_data['items'],
            self.raw_data['sales'],
            self.forecasts,
            self.raw_data.get('history')
        )

        # Save to cache
        save_inventory_health_report(health_report, self.cache_dir)

        return health_report

    def generate_reports(self, config: Optional[Dict] = None,
                        progress_callback=None) -> Tuple[pd.DataFrame, pd.DataFrame, Dict, Dict]:
        """
        Stage 3: Generate shortage and TCO reports (MEDIUM speed).

        Parameters:
        -----------
        config : Dict, optional
            Configuration for optimization
        progress_callback : callable, optional
            Callback for progress updates

        Returns:
        --------
        Tuple[pd.DataFrame, pd.DataFrame, Dict, Dict]
            (stockout_report, tco_report, vendor_data, inventory_health)
        """
        logger.info("Stage 3: Generating reports...")

        if progress_callback:
            progress_callback(10, "Running optimization analysis...")

        from src.optimization import optimize_inventory, load_config

        # Load config
        if config is None:
            config = load_config()

        if progress_callback:
            progress_callback(30, "Calculating stockouts...")

        # Run optimization
        with Timer("Optimization Analysis"):
            df_stockout, df_tco = optimize_inventory(
                self.raw_data['items'],
                self.forecasts,
                self.raw_data['schedule'],
                config
            )

        if progress_callback:
            progress_callback(50, "Analyzing vendor performance...")

        # Generate vendor performance data
        with Timer("Vendor Performance Analysis"):
            vendor_data = self.generate_vendor_performance()

        if progress_callback:
            progress_callback(70, "Merging lead time data...")

        # Merge fastest vendor lead time into stockout report (with validation)
        if vendor_data and 'fastest_vendors' in vendor_data and not vendor_data['fastest_vendors'].empty:
            df_vendor_merge = vendor_data['fastest_vendors'][
                ['ItemCode', 'VendorCode', 'effective_mean_lead_time']
            ]
            df_stockout = df_stockout.merge(
                df_vendor_merge,
                left_on='Item No.',
                right_on='ItemCode',
                how='left',
                validate='many_to_one'
            )
            # Rename for clarity
            df_stockout = df_stockout.rename(columns={
                'VendorCode': 'FastestVendor',
                'effective_mean_lead_time': 'VendorLeadTimeDays'
            })

            # Log merge success
            matched = df_stockout['FastestVendor'].notna().sum()
            logger.info(f"Vendor lead times merged for {matched}/{len(df_stockout)} items")
        else:
            logger.warning("No vendor performance data available")
            df_stockout['FastestVendor'] = None
            df_stockout['VendorLeadTimeDays'] = None

        if progress_callback:
            progress_callback(85, "Analyzing inventory health...")

        # Generate inventory health report
        with Timer("Inventory Health Analysis"):
            inventory_health = self.generate_inventory_health()

        # Add shelf life warnings to stockout report for FG-RE items
        if 'shelf_life_risk' in inventory_health and not inventory_health['shelf_life_risk'].empty:
            df_shelf_risk = inventory_health['shelf_life_risk'][
                ['Item No.', 'expiry_risk', 'ordering_recommendation', 'months_of_stock']
            ]
            df_stockout = df_stockout.merge(
                df_shelf_risk,
                on='Item No.',
                how='left'
            )

        if progress_callback:
            progress_callback(95, "Finalizing reports...")

        # Merge last sale date for inactive filtering
        with Timer("Merge Final Data"):
            last_sale_dates = self.raw_data['last_sale_dates']
            df_stockout = df_stockout.merge(last_sale_dates, on='Item No.', how='left')
            df_tco = df_tco.merge(last_sale_dates, on='Item No.', how='left')

        self.reports = {
            'stockout': df_stockout,
            'tco': df_tco,
            'vendor': vendor_data,
            'inventory_health': inventory_health
        }

        if progress_callback:
            progress_callback(100, "Reports generated!")

        logger.info(f"Generated {len(df_stockout)} stockout alerts, {len(df_tco)} TCO analyses")
        return df_stockout, df_tco, vendor_data, inventory_health

    def generate_vendor_performance(self, use_cache: bool = True) -> Dict:
        """
        Generate vendor performance analytics.

        Parameters:
        -----------
        use_cache : bool
            Whether to use cached vendor data

        Returns:
        --------
        Dict
            Dictionary with vendor performance DataFrames
        """
        from src.vendor_performance import (
            calculate_item_vendor_lead_times,
            identify_fastest_vendors,
            calculate_vendor_performance_scores,
            load_vendor_performance_data,
            save_vendor_performance_data
        )

        # Try loading from cache
        if use_cache:
            cached = load_vendor_performance_data(self.cache_dir)
            if all(df is not None for df in cached):
                logger.info("Using cached vendor performance data")
                item_vendor_stats, vendor_stats, fastest_vendors, vendor_perf = cached
                return {
                    'item_vendor_stats': item_vendor_stats,
                    'vendor_stats': vendor_stats,
                    'fastest_vendors': fastest_vendors,
                    'vendor_perf': vendor_perf
                }

        # Calculate fresh
        logger.info("Calculating vendor performance metrics...")
        with Timer("Calculate Item-Vendor Lead Times"):
            item_vendor_stats, vendor_stats = calculate_item_vendor_lead_times(
                self.raw_data['history']
            )

        if item_vendor_stats.empty:
            logger.warning("No vendor performance data available")
            return {}

        with Timer("Identify Fastest Vendors"):
            fastest_vendors = identify_fastest_vendors(item_vendor_stats)

        with Timer("Calculate Vendor Scores"):
            vendor_perf = calculate_vendor_performance_scores(vendor_stats, item_vendor_stats)

        # Save to cache
        save_vendor_performance_data(
            item_vendor_stats,
            vendor_stats,
            fastest_vendors,
            vendor_perf,
            self.cache_dir
        )

        return {
            'item_vendor_stats': item_vendor_stats,
            'vendor_stats': vendor_stats,
            'fastest_vendors': fastest_vendors,
            'vendor_perf': vendor_perf
        }

    def combine_all(self, progress_callback=None) -> Dict:
        """
        Stage 4: Combine all results into final output (FAST).

        Parameters:
        -----------
        progress_callback : callable, optional
            Callback for progress updates

        Returns:
        --------
        Dict
            Combined data with all results
        """
        logger.info("Stage 4: Combining results...")

        if progress_callback:
            progress_callback(100, "Combining results...")

        from src.optimization import load_config

        result = {
            **self.raw_data,
            'forecasts': self.forecasts,
            'stockout': self.reports.get('stockout'),
            'tco': self.reports.get('tco'),
            'vendor': self.reports.get('vendor', {}),
            'inventory_health': self.reports.get('inventory_health', {}),
            'config': load_config()
        }

        logger.info("Results combined!")
        return result

    def run_full_pipeline(self, data_dir: Path,
                         n_samples: Optional[int] = None,
                         use_cache: bool = True,
                         progress_callback=None) -> Dict:
        """
        Run complete pipeline (all stages).

        Parameters:
        -----------
        data_dir : Path
            Directory containing raw data files
        n_samples : int, optional
            Number of items to forecast (None = all)
        use_cache : bool
            Whether to use cached forecasts
        progress_callback : callable, optional
            Callback for progress updates (0-100)

        Returns:
        --------
        Dict
            Combined data with all results
        """
        logger.info("=" * 60)
        logger.info("RUNNING FULL DATA PIPELINE")
        logger.info("=" * 60)

        with Timer("Full Pipeline Execution"):
            # Stage 1: Load data (0-20%)
            with Timer("Stage 1: Load Raw Data"):
                self.load_raw_data(data_dir,
                                  progress_callback=lambda p, msg: (
                                      progress_callback(int(p * 0.2), msg) if progress_callback else None
                                  ))

            # Stage 2: Generate forecasts (20-80%)
            with Timer("Stage 2: Generate Forecasts"):
                self.generate_forecasts(n_samples=n_samples, use_cache=use_cache,
                                       progress_callback=lambda p, msg: (
                                           progress_callback(int(20 + p * 0.6), msg) if progress_callback else None
                                       ))

            # Stage 3: Generate reports (80-95%)
            with Timer("Stage 3: Generate Reports"):
                self.generate_reports(progress_callback=lambda p, msg: (
                    progress_callback(int(80 + p * 0.15), msg) if progress_callback else None
                ))

            # Stage 4: Combine (95-100%)
            with Timer("Stage 4: Combine Results"):
                result = self.combine_all(progress_callback=lambda p, msg: (
                    progress_callback(int(95 + p * 0.05), msg) if progress_callback else None
                ))

        # Print timing summary
        print_timing_summary()

        if progress_callback:
            progress_callback(100, "Pipeline complete!")

        return result

    def get_pipeline_status(self) -> Dict:
        """
        Get current status of pipeline stages.

        Returns:
        --------
        Dict
            Status information for each stage
        """
        status = {
            'raw_data_loaded': len(self.raw_data) > 0,
            'forecasts_generated': self.forecasts is not None,
            'reports_generated': len(self.reports) > 0,
            'cache_info': {}
        }

        # Check cache status
        forecast_cache = self.get_cache_path("forecasts")
        if forecast_cache.exists():
            status['cache_info']['forecasts'] = {
                'exists': True,
                'items': len(pd.read_parquet(forecast_cache))
            }
        else:
            status['cache_info']['forecasts'] = {'exists': False}

        return status

    def clear_cache(self):
        """Clear all cached data."""
        logger.info("Clearing cache...")
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cache cleared!")


# Convenience functions for backward compatibility
def load_all_data(data_dir: Path = Path("data/raw"),
                 n_samples: Optional[int] = None,
                 use_cache: bool = True,
                 progress_callback=None) -> Dict:
    """
    Convenience function to load all data using the pipeline.

    Maintains compatibility with existing code.
    """
    pipeline = DataPipeline()
    return pipeline.run_full_pipeline(data_dir, n_samples, use_cache, progress_callback)


def load_data_only(data_dir: Path = Path("data/raw"),
                   progress_callback=None) -> Dict:
    """
    Fast load of raw data only (no forecasting).

    Use this for quick data exploration.
    """
    pipeline = DataPipeline()
    return pipeline.load_raw_data(data_dir, progress_callback)


def generate_forecasts_only(raw_data: Dict,
                           n_samples: Optional[int] = None,
                           use_cache: bool = True,
                           progress_callback=None) -> pd.DataFrame:
    """
    Generate forecasts from already-loaded raw data.

    Use this to regenerate forecasts without reloading data.
    """
    pipeline = DataPipeline()
    pipeline.raw_data = raw_data
    return pipeline.generate_forecasts(n_samples, use_cache, progress_callback=progress_callback)


def generate_reports_only(raw_data: Dict,
                         forecasts: pd.DataFrame,
                         config: Optional[Dict] = None,
                         progress_callback=None) -> Tuple[pd.DataFrame, pd.DataFrame, Dict, Dict]:
    """
    Generate reports from already-loaded data and forecasts.

    Use this to regenerate reports without re-forecasting.

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame, Dict, Dict]
        (stockout_report, tco_report, vendor_data, inventory_health)
    """
    pipeline = DataPipeline()
    pipeline.raw_data = raw_data
    pipeline.forecasts = forecasts
    return pipeline.generate_reports(config, progress_callback)
