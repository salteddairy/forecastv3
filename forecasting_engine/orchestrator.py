"""
Pipeline orchestrator - coordinates the entire forecasting process.
Extracts data, runs tournament, calculates accuracy, writes to database.
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
import time
from pathlib import Path

from forecasting_engine.extract import extract_sales_data, extract_items_with_sufficient_history
from forecasting_engine.forecast import run_tournament
from forecasting_engine.accuracy import batch_calculate_accuracy
from forecasting_engine.load import write_and_refresh, test_database_write
from forecasting_engine.db import test_connection, get_database_version
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


def run_forecast_job(
    item_codes: Optional[List[str]] = None,
    warehouse: Optional[str] = None,
    min_months_history: int = None,
    use_advanced_models: bool = True,
    dry_run: bool = False,
    parallel: bool = True,
    source: str = "local"
) -> Dict:
    """
    Run the complete forecasting job.

    Coordinates:
    1. Database connection test
    2. Data extraction
    3. Tournament execution
    4. Accuracy calculation
    5. Database write
    6. Materialized view refresh

    Parameters:
    -----------
    item_codes : List[str], optional
        Specific items to forecast (None = auto-detect)
    warehouse : str, optional
        Filter by warehouse code
    min_months_history : int, optional
        Minimum months of history required
    use_advanced_models : bool
        Whether to use advanced models (Prophet, SARIMA, etc.)
    dry_run : bool
        If True, skip database writes
    parallel : bool
        Whether to use parallel processing
    source : str
        Data source: "database" (default) or "local"

    Returns:
    --------
    Dict
        Job results with statistics
        {
            'start_time': datetime,
            'end_time': datetime,
            'duration_seconds': float,
            'database_test': bool,
            'items_processed': int,
            'forecasts_generated': int,
            'forecasts_written': int,
            'accuracy_written': int,
            'views_refreshed': bool,
            'model_distribution': dict,
            'accuracy_summary': dict,
            'errors': list
        }
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("FORECASTING JOB STARTED")
    logger.info("=" * 60)
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Data source: {source}")

    results = {
        'start_time': start_time,
        'end_time': None,
        'duration_seconds': 0,
        'database_test': False,
        'source': source,
        'items_processed': 0,
        'forecasts_generated': 0,
        'forecasts_written': 0,
        'accuracy_written': 0,
        'views_refreshed': False,
        'model_distribution': {},
        'accuracy_summary': {},
        'errors': []
    }

    # Step 1: Test database connection (only if not dry-run)
    if source == "database" and not dry_run:
        logger.info("Step 1: Testing database connection...")
        results['database_test'] = test_connection()
        if not results['database_test']:
            raise ConnectionError("Database connection test failed")

        db_version = get_database_version()
        logger.info(f"Connected to: {db_version.split(',')[0] if db_version else 'Unknown'}")
    else:
        logger.info("Step 1: Skipping database test (dry-run or local source)")
        results['database_test'] = None

    # Step 2: Get items to forecast
    logger.info("Step 2: Getting items with sufficient history...")

    if item_codes is None:
        item_codes = extract_items_with_sufficient_history(
            min_months=min_months_history or settings.min_months_history,
            min_orders=settings.min_orders,
            source=source
        )

    if not item_codes:
        logger.warning("No items found with sufficient history")
        results['end_time'] = datetime.now()
        results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
        return results

    results['items_processed'] = len(item_codes)
    logger.info(f"Found {len(item_codes)} items with sufficient history")

    # Step 3: Extract sales data
    logger.info("Step 3: Extracting sales data...")

    data_dir = None
    if source == "local":
        data_dir = Path("data/raw")  # Default local data directory

    df_sales = extract_sales_data(
        item_codes=item_codes,
        warehouse=warehouse,
        months_history=settings.max_months_history,
        source=source,
        data_dir=data_dir
    )

    if df_sales.empty:
        logger.warning("No sales data found")
        results['end_time'] = datetime.now()
        results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
        return results

    logger.info(f"Extracted {len(df_sales)} sales records")

    # Step 4: Run tournament
    logger.info("Step 4: Running forecasting tournament...")
    logger.info(f"Advanced models: {use_advanced_models}")
    logger.info(f"Parallel processing: {parallel and source != 'local'}")  # Force sequential for local

    tournament_start = time.time()

    df_forecasts = run_tournament(
        df_sales=df_sales,
        item_codes=item_codes,
        use_advanced_models=use_advanced_models,
        parallel=parallel  # Will be False for local source
    )

    tournament_duration = time.time() - tournament_start
    logger.info(f"Tournament completed in {tournament_duration:.1f} seconds")

    # Count successful forecasts
    successful = df_forecasts[df_forecasts['winning_model'].notna()]
    failed = df_forecasts[df_forecasts['winning_model'].isna()]

    results['forecasts_generated'] = len(successful)
    logger.info(f"Generated {len(successful)} forecasts")
    logger.info(f"Failed: {len(failed)} items")

    if len(successful) > 0:
        # Model distribution
        model_dist = successful['winning_model'].value_counts().to_dict()
        results['model_distribution'] = model_dist
        logger.info(f"Model distribution: {model_dist}")

    # Step 5: Calculate accuracy
    logger.info("Step 5: Calculating accuracy metrics...")
    df_accuracy = batch_calculate_accuracy(df_forecasts, df_sales)
    logger.info(f"Calculated accuracy for {len(df_accuracy)} items")

    # Accuracy summary
    if not df_accuracy.empty and 'mape' in df_accuracy.columns:
        valid_mape = df_accuracy[df_accuracy['mape'].notna()]
        results['accuracy_summary'] = {
            'avg_mape': float(valid_mape['mape'].mean()) if len(valid_mape) > 0 else None,
            'median_mape': float(valid_mape['mape'].median()) if len(valid_mape) > 0 else None,
            'min_mape': float(valid_mape['mape'].min()) if len(valid_mape) > 0 else None,
            'max_mape': float(valid_mape['mape'].max()) if len(valid_mape) > 0 else None,
        }
        logger.info(f"Average MAPE: {results['accuracy_summary']['avg_mape']:.2f}%")

    # Step 6: Write to database
    if not dry_run and source == "database":
        logger.info("Step 6: Writing to database...")

        write_results = write_and_refresh(
            df_forecasts=successful,
            df_accuracy=df_accuracy,
            forecast_generated_at=start_time
        )

        results['forecasts_written'] = write_results['forecasts_written']
        results['accuracy_written'] = write_results.get('accuracy_written', 0)
        results['views_refreshed'] = write_results['views_refreshed']
        results['errors'].extend(write_results.get('errors', []))

        logger.info(f"Wrote {results['forecasts_written']} forecasts")
        logger.info(f"Wrote {results['accuracy_written']} accuracy records")
        logger.info(f"Views refreshed: {results['views_refreshed']}")
    else:
        logger.info("Step 6: DRY RUN - skipping database write")
        logger.info(f"Would write {len(successful)} forecasts to database")
        logger.info(f"Would write {len(df_accuracy)} accuracy records")

    # Finalize
    end_time = datetime.now()
    results['end_time'] = end_time
    results['duration_seconds'] = (end_time - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("FORECASTING JOB COMPLETED")
    logger.info(f"End time: {end_time.isoformat()}")
    logger.info(f"Duration: {results['duration_seconds']:.1f} seconds")
    logger.info(f"Items processed: {results['items_processed']}")
    logger.info(f"Forecasts generated: {results['forecasts_generated']}")
    logger.info(f"Forecasts written: {results['forecasts_written']}")
    logger.info(f"Errors: {len(results['errors'])}")
    logger.info("=" * 60)

    return results


def run_batch_jobs(
    item_batches: List[List[str]],
    warehouse: Optional[str] = None,
    use_advanced_models: bool = True,
    dry_run: bool = False,
    source: str = "local"
) -> List[Dict]:
    """
    Run multiple forecasting jobs in batches.

    Useful for processing large item lists in chunks.

    Parameters:
    -----------
    item_batches : List[List[str]]
        List of item code batches
    warehouse : str, optional
        Filter by warehouse
    use_advanced_models : bool
        Use advanced models
    dry_run : bool
        Dry run mode
    source : str
        Data source

    Returns:
    --------
    List[Dict]
        Results for each batch
    """
    all_results = []

    for i, batch in enumerate(item_batches, 1):
        logger.info(f"Processing batch {i}/{len(item_batches)} ({len(batch)} items)")

        result = run_forecast_job(
            item_codes=batch,
            warehouse=warehouse,
            use_advanced_models=use_advanced_models,
            dry_run=dry_run,
            source=source
        )

        all_results.append(result)

        # Log batch summary
        logger.info(f"Batch {i} complete: {result['forecasts_generated']} forecasts")

    return all_results


def get_job_summary(results: Dict) -> str:
    """
    Generate a human-readable summary of job results.

    Parameters:
    -----------
    results : Dict
        Results from run_forecast_job()

    Returns:
    --------
    str
        Formatted summary
    """
    lines = [
        "=" * 60,
        "FORECASTING JOB SUMMARY",
        "=" * 60,
        f"Start Time:      {results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"End Time:        {results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration:        {results['duration_seconds']:.1f} seconds",
        f"Items Processed: {results['items_processed']}",
        f"Forecasts Gen:   {results['forecasts_generated']}",
        f"Forecasts Write: {results['forecasts_written']}",
        f"Database Test:   {results.get('database_test', 'N/A')}",
        "",
    ]

    if results.get('model_distribution'):
        lines.append("Model Distribution:")
        for model, count in results['model_distribution'].items():
            lines.append(f"  {model}: {count} items")
        lines.append("")

    if results.get('accuracy_summary'):
        summary = results['accuracy_summary']
        lines.append("Accuracy Summary:")
        lines.append(f"  Average MAPE: {summary.get('avg_mape', 'N/A')}")
        lines.append(f"  Median MAPE:  {summary.get('median_mape', 'N/A')}")
        lines.append(f"  Range:        {summary.get('min_mape', 'N/A')} - {summary.get('max_mape', 'N/A')}")
        lines.append("")

    if results['errors']:
        lines.append(f"Errors ({len(results['errors'])}):")
        for error in results['errors'][:5]:
            lines.append(f"  - {error}")
        if len(results['errors']) > 5:
            lines.append(f"  ... and {len(results['errors']) - 5} more")

    lines.append("=" * 60)

    return "\n".join(lines)


def validate_job_config(
    item_codes: Optional[List[str]] = None,
    min_months_history: int = None
) -> Dict[str, any]:
    """
    Validate job configuration before running.

    Parameters:
    -----------
    item_codes : List[str], optional
        Item codes to validate
    min_months_history : int, optional
        Minimum months threshold

    Returns:
    --------
    Dict
        Validation results
        {
            'valid': bool,
            'item_count': int,
            'warnings': list,
            'recommendations': list
        }
    """
    validation = {
        'valid': True,
        'item_count': 0,
        'warnings': [],
        'recommendations': []
    }

    # Check minimum months configuration
    min_months = min_months_history or settings.min_months_history
    if min_months < 3:
        validation['warnings'].append(f"Minimum months ({min_months}) is below recommended 3")
        validation['recommendations'].append("Increase min_months_history to at least 3")

    if min_months < 6:
        validation['recommendations'].append("For best results, use min_months_history=6 or higher")

    # Check item codes
    if item_codes:
        validation['item_count'] = len(item_codes)
        if len(item_codes) > 1000:
            validation['warnings'].append(f"Large item count ({len(item_codes)}) may take significant time")
            validation['recommendations'].append("Consider processing in batches or using parallel=True")

    # Check parallel processing
    if not settings.use_advanced_models:
        validation['recommendations'].append("Enable use_advanced_models=True for better accuracy (slower)")

    return validation


def monitor_job_progress(results: Dict) -> Dict:
    """
    Extract key metrics for monitoring and alerting.

    Parameters:
    -----------
    results : Dict
        Job results

    Returns:
    --------
    Dict
        Monitoring metrics
    """
    return {
        'success_rate': results['forecasts_generated'] / results['items_processed'] if results['items_processed'] > 0 else 0,
        'error_count': len(results['errors']),
        'duration_per_item': results['duration_seconds'] / results['items_processed'] if results['items_processed'] > 0 else 0,
        'has_warnings': results['forecasts_generated'] < results['items_processed'],
        'database_write_failed': results['forecasts_written'] < results['forecasts_generated'] if results.get('database_test') else None
    }
