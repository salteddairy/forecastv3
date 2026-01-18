"""
Command-line interface for forecasting engine.

Provides commands for running forecasts, checking health, validating config.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List

from forecasting_engine.orchestrator import (
    run_forecast_job,
    validate_job_config,
    get_job_summary,
    monitor_job_progress
)
from forecasting_engine.db import test_connection, get_database_version
from forecasting_engine.config import settings
from forecasting_engine import __version__


def setup_logging(verbose: bool = False):
    """
    Configure logging based on verbosity level.

    Parameters:
    -----------
    verbose : bool
        If True, set logging to DEBUG level
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def cmd_forecast(args: argparse.Namespace):
    """
    Execute forecast job.

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("FORECASTING ENGINE - CLI")
    logger.info(f"Version: {__version__}")
    logger.info("=" * 60)

    # Parse item codes if provided
    item_codes = None
    if args.item_codes:
        item_codes = [code.strip() for code in args.item_codes.split(',')]
        logger.info(f"Item codes specified: {len(item_codes)} items")

    # Parse warehouse
    if args.warehouse:
        logger.info(f"Warehouse filter: {args.warehouse}")

    # Validate configuration if requested
    if args.validate:
        logger.info("\nValidating job configuration...")
        validation = validate_job_config(
            item_codes=item_codes,
            min_months_history=args.min_months
        )

        print("\n" + "=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)
        print(f"Configuration valid: {validation['valid']}")
        print(f"Item count: {validation['item_count']}")

        if validation['warnings']:
            print(f"\nWarnings ({len(validation['warnings'])}):")
            for warning in validation['warnings']:
                print(f"  - {warning}")

        if validation['recommendations']:
            print(f"\nRecommendations ({len(validation['recommendations'])}):")
            for rec in validation['recommendations']:
                print(f"  - {rec}")

        print("=" * 60)

        # Ask for confirmation
        if not args.auto_confirm:
            response = input("\nContinue with forecast? [y/N]: ")
            if response.lower() != 'y':
                print("Forecast cancelled.")
                sys.exit(0)

    # Run the forecast job
    print("\n" + "=" * 60)
    print("RUNNING FORECAST JOB")
    print("=" * 60)
    print(f"Source: {args.source}")
    print(f"Dry run: {args.dry_run}")
    print(f"Advanced models: {args.advanced_models}")
    print(f"Parallel processing: {args.parallel}")
    print("=" * 60 + "\n")

    try:
        results = run_forecast_job(
            item_codes=item_codes,
            warehouse=args.warehouse,
            min_months_history=args.min_months,
            use_advanced_models=args.advanced_models,
            dry_run=args.dry_run,
            parallel=args.parallel,
            source=args.source
        )

        # Print summary
        print("\n" + get_job_summary(results))

        # Monitor metrics
        metrics = monitor_job_progress(results)

        print("\nMONITORING METRICS")
        print("=" * 60)
        print(f"Success rate: {metrics['success_rate']:.1%}")
        print(f"Error count: {metrics['error_count']}")
        print(f"Duration per item: {metrics['duration_per_item']:.2f} seconds")
        print(f"Has warnings: {metrics['has_warnings']}")

        if results.get('forecasts_generated') == 0:
            print("\nWARNING: No forecasts were generated")
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Forecast job failed: {e}")
        sys.exit(1)


def cmd_health(args: argparse.Namespace):
    """
    Check system health.

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    setup_logging(args.verbose)

    print("=" * 60)
    print("FORECASTING ENGINE - HEALTH CHECK")
    print("=" * 60)

    # Check configuration
    print("\n1. Configuration:")
    print(f"   Version: {__version__}")
    print(f"   Min months history: {settings.min_months_history}")
    print(f"   Forecast horizon: {settings.forecast_horizon} months")
    print(f"   Advanced models enabled: {settings.use_advanced_models}")

    # Check database
    print("\n2. Database:")
    if settings.database_url:
        try:
            db_ok = test_connection()
            if db_ok:
                print("   Status: CONNECTED")
                version = get_database_version()
                if version:
                    print(f"   Version: {version.split(',')[0] if ',' in version else version}")
            else:
                print("   Status: CONNECTION FAILED")
                sys.exit(1)
        except Exception as e:
            print(f"   Status: ERROR - {e}")
            sys.exit(1)
    else:
        print("   Status: NOT CONFIGURED (DATABASE_URL not set)")

    # Check models
    print("\n3. Forecasting Models:")
    from forecasting_engine.models import MODEL_REGISTRY
    print(f"   Registered models: {len(MODEL_REGISTRY)}")
    for model_name in MODEL_REGISTRY.keys():
        print(f"   - {model_name}")

    # Check data directory
    print("\n4. Data Directory:")
    data_dir = Path("data/raw")
    if data_dir.exists():
        sales_file = data_dir / "sales.tsv"
        if sales_file.exists():
            print(f"   Status: OK")
            print(f"   Sales file: {sales_file} ({sales_file.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"   Status: OK (directory exists)")
            print(f"   Sales file: Not found")
    else:
        print(f"   Status: NOT FOUND")
        print(f"   Path: {data_dir.absolute()}")

    print("\n" + "=" * 60)
    print("HEALTH CHECK PASSED")
    print("=" * 60)

    sys.exit(0)


def cmd_validate(args: argparse.Namespace):
    """
    Validate job configuration.

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    setup_logging(args.verbose)

    # Parse item codes if provided
    item_codes = None
    if args.item_codes:
        item_codes = [code.strip() for code in args.item_codes.split(',')]

    print("=" * 60)
    print("JOB CONFIGURATION VALIDATION")
    print("=" * 60)

    validation = validate_job_config(
        item_codes=item_codes,
        min_months_history=args.min_months
    )

    print(f"\nValid: {validation['valid']}")
    print(f"Item count: {validation['item_count']}")

    if validation['warnings']:
        print(f"\nWarnings ({len(validation['warnings'])}):")
        for warning in validation['warnings']:
            print(f"  - {warning}")

    if validation['recommendations']:
        print(f"\nRecommendations ({len(validation['recommendations'])}):")
        for rec in validation['recommendations']:
            print(f"  - {rec}")

    print("\n" + "=" * 60)

    sys.exit(0 if validation['valid'] else 1)


def cmd_config(args: argparse.Namespace):
    """
    Show current configuration.

    Parameters:
    -----------
    args : argparse.Namespace
        Parsed command-line arguments
    """
    print("=" * 60)
    print("FORECASTING ENGINE - CONFIGURATION")
    print("=" * 60)

    print("\nDatabase:")
    print(f"  URL: {settings.database_url or 'Not configured'}")

    print("\nData Requirements:")
    print(f"  Min months history: {settings.min_months_history}")
    print(f"  Max months history: {settings.max_months_history}")
    print(f"  Min orders: {settings.min_orders}")

    print("\nForecasting:")
    print(f"  Forecast horizon: {settings.forecast_horizon} months")

    print("\nAdvanced Models:")
    print(f"  Use advanced models: {settings.use_advanced_models}")
    print(f"  Prophet min months: {settings.prophet_min_months}")
    print(f"  SARIMA min months: {settings.sarima_min_months}")
    print(f"  ARIMA min months: {settings.arima_min_months}")

    print("\nProphet Settings:")
    print(f"  Yearly seasonality: {settings.prophet_yearly_seasonality}")
    print(f"  Weekly seasonality: {settings.prophet_weekly_seasonality}")
    print(f"  Daily seasonality: {settings.prophet_daily_seasonality}")
    print(f"  Interval width: {settings.prophet_interval_width}")

    print("\nProcessing:")
    print(f"  Parallel threshold: {settings.parallel_threshold} items")
    print(f"  Number of jobs: {settings.n_jobs} (-1 = all CPUs)")

    print("\n" + "=" * 60)

    sys.exit(0)


def main():
    """
    Main CLI entry point.
    """
    parser = argparse.ArgumentParser(
        prog='forecast-engine',
        description='SAP B1 Inventory Forecasting Engine - Tournament-based demand forecasting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run forecast with local data (dry run)
  python -m forecasting_engine.cli forecast --source local --dry-run

  # Run forecast with database
  python -m forecasting_engine.cli forecast --source database --advanced-models

  # Run forecast for specific items
  python -m forecasting_engine.cli forecast --item-codes "ITEM001,ITEM002,ITEM003"

  # Run forecast for specific warehouse
  python -m forecasting_engine.cli forecast --warehouse "01"

  # Run forecast with verbose output
  python -m forecasting_engine.cli forecast --verbose

  # Check system health
  python -m forecasting_engine.cli health

  # Show configuration
  python -m forecasting_engine.cli config

  # Validate job configuration
  python -m forecasting_engine.cli validate --item-codes "ITEM001,ITEM002"

For more information, see: FORECASTING_ENGINE_PROGRESS.md
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    subparsers = parser.add_subparsers(
        dest='command',
        title='Available Commands',
        description='Use "forecast-engine <command> --help" for command-specific help'
    )

    # Forecast command
    forecast_parser = subparsers.add_parser(
        'forecast',
        help='Run forecasting job',
        description='Run complete forecasting job with tournament approach'
    )

    forecast_parser.add_argument(
        '--item-codes',
        type=str,
        help='Comma-separated list of item codes to forecast (default: auto-detect)'
    )

    forecast_parser.add_argument(
        '--warehouse',
        type=str,
        help='Filter by warehouse code'
    )

    forecast_parser.add_argument(
        '--min-months',
        type=int,
        default=None,
        help='Minimum months of history required (default: 6)'
    )

    forecast_parser.add_argument(
        '--source',
        type=str,
        choices=['database', 'local'],
        default='database',
        help='Data source: "database" (default) or "local"'
    )

    forecast_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Skip database writes (for testing)'
    )

    forecast_parser.add_argument(
        '--advanced-models',
        action='store_true',
        default=True,
        help='Use advanced models (Prophet, SARIMA, ARIMA, Theta)'
    )

    forecast_parser.add_argument(
        '--no-advanced-models',
        dest='advanced_models',
        action='store_false',
        help='Disable advanced models (use only SMA, Holt-Winters, Croston)'
    )

    forecast_parser.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        help='Use parallel processing (default: True)'
    )

    forecast_parser.add_argument(
        '--no-parallel',
        dest='parallel',
        action='store_false',
        help='Use sequential processing'
    )

    forecast_parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration before running'
    )

    forecast_parser.add_argument(
        '--auto-confirm',
        action='store_true',
        help='Skip confirmation prompt (useful for automation)'
    )

    forecast_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    forecast_parser.set_defaults(func=cmd_forecast)

    # Health command
    health_parser = subparsers.add_parser(
        'health',
        help='Check system health',
        description='Check database connection, models, and data directory'
    )

    health_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    health_parser.set_defaults(func=cmd_health)

    # Validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate job configuration',
        description='Validate job configuration without running'
    )

    validate_parser.add_argument(
        '--item-codes',
        type=str,
        help='Comma-separated list of item codes to validate'
    )

    validate_parser.add_argument(
        '--min-months',
        type=int,
        default=None,
        help='Minimum months of history required'
    )

    validate_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    validate_parser.set_defaults(func=cmd_validate)

    # Config command
    config_parser = subparsers.add_parser(
        'config',
        help='Show current configuration',
        description='Display all configuration settings'
    )

    config_parser.set_defaults(func=cmd_config)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()
