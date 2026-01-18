"""
Database write operations.
Writes forecasts and accuracy to PostgreSQL with transaction safety.
"""
import logging
import pandas as pd
from typing import List, Dict
from datetime import datetime
from sqlalchemy import text

from forecasting_engine.db import get_session
from forecasting_engine.config import settings

logger = logging.getLogger(__name__)


def write_forecasts_to_db(
    df_forecasts: pd.DataFrame,
    forecast_generated_at: datetime = None
) -> int:
    """
    Write forecasts to PostgreSQL database.

    Uses UPSERT logic to update existing forecasts (supersede old active forecasts).

    Parameters:
    -----------
    df_forecasts : pd.DataFrame
        Forecast results from run_tournament()
    forecast_generated_at : datetime
        Timestamp for this forecast run (default: now)

    Returns:
    --------
    int
        Number of forecasts written
    """
    if df_forecasts.empty:
        logger.warning("No forecasts to write")
        return 0

    if forecast_generated_at is None:
        forecast_generated_at = datetime.now()

    # Filter out failed forecasts
    df_success = df_forecasts[df_forecasts['winning_model'].notna()].copy()

    if df_success.empty:
        logger.warning("No successful forecasts to write")
        return 0

    # Build INSERT query
    insert_query = text("""
        INSERT INTO forecasts (
            item_code,
            forecast_generated_at,
            winning_model,
            forecast_horizon,
            forecast_confidence_pct,
            history_months,
            train_months,
            test_months,
            avg_monthly_demand,
            demand_cv,
            forecast_month_1,
            forecast_month_2,
            forecast_month_3,
            forecast_month_4,
            forecast_month_5,
            forecast_month_6,
            forecast_month_7,
            forecast_month_8,
            forecast_month_9,
            forecast_month_10,
            forecast_month_11,
            forecast_month_12,
            rmse_sma,
            rmse_holt_winters,
            rmse_prophet,
            rmse_arima,
            rmse_sarimax,
            rmse_theta,
            forecast_period_start,
            status,
            created_at
        ) VALUES (
            :item_code,
            :forecast_generated_at,
            :winning_model,
            :forecast_horizon,
            :forecast_confidence_pct,
            :history_months,
            :train_months,
            :test_months,
            :avg_monthly_demand,
            :demand_cv,
            :forecast_month_1,
            :forecast_month_2,
            :forecast_month_3,
            :forecast_month_4,
            :forecast_month_5,
            :forecast_month_6,
            :forecast_month_7,
            :forecast_month_8,
            :forecast_month_9,
            :forecast_month_10,
            :forecast_month_11,
            :forecast_month_12,
            :rmse_sma,
            :rmse_holt_winters,
            :rmse_prophet,
            :rmse_arima,
            :rmse_sarimax,
            :rmse_theta,
            :forecast_period_start,
            'Active',
            NOW()
        )
    """)

    # Build supersede query
    supersede_query = text("""
        UPDATE forecasts
        SET status = 'Superseded',
            updated_at = NOW()
        WHERE item_code = :item_code
          AND status = 'Active'
    """)

    count = 0
    errors = []

    try:
        with get_session() as session:
            for _, row in df_success.iterrows():
                try:
                    # First, supersede existing active forecast
                    session.execute(supersede_query, {"item_code": row['item_code']})

                    # Then insert new forecast
                    session.execute(insert_query, {
                        "item_code": row['item_code'],
                        "forecast_generated_at": forecast_generated_at,
                        "winning_model": row['winning_model'],
                        "forecast_horizon": int(row.get('forecast_horizon', settings.forecast_horizon)),
                        "forecast_confidence_pct": row.get('forecast_confidence_pct'),
                        "history_months": int(row.get('history_months', 0)) if pd.notna(row.get('history_months')) else None,
                        "train_months": int(row.get('train_months', 0)) if pd.notna(row.get('train_months')) else None,
                        "test_months": int(row.get('test_months', 0)) if pd.notna(row.get('test_months')) else None,
                        "avg_monthly_demand": row.get('avg_monthly_demand'),
                        "demand_cv": row.get('demand_cv'),
                        "forecast_month_1": row.get('forecast_month_1'),
                        "forecast_month_2": row.get('forecast_month_2'),
                        "forecast_month_3": row.get('forecast_month_3'),
                        "forecast_month_4": row.get('forecast_month_4'),
                        "forecast_month_5": row.get('forecast_month_5'),
                        "forecast_month_6": row.get('forecast_month_6'),
                        "forecast_month_7": row.get('forecast_month_7'),
                        "forecast_month_8": row.get('forecast_month_8'),
                        "forecast_month_9": row.get('forecast_month_9'),
                        "forecast_month_10": row.get('forecast_month_10'),
                        "forecast_month_11": row.get('forecast_month_11'),
                        "forecast_month_12": row.get('forecast_month_12'),
                        "rmse_sma": row.get('rmse_sma'),
                        "rmse_holt_winters": row.get('rmse_holt-winters') if 'rmse_holt-winters' in row else row.get('rmse_holt_winters'),
                        "rmse_prophet": row.get('rmse_prophet'),
                        "rmse_arima": row.get('rmse_arima'),
                        "rmse_sarimax": row.get('rmse_sarima') if 'rmse_sarima' in row else row.get('rmse_sarimax'),
                        "rmse_theta": row.get('rmse_theta'),
                        "forecast_period_start": row.get('forecast_period_start')
                    })
                    count += 1
                except Exception as e:
                    error_msg = f"Error writing forecast for {row['item_code']}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            session.commit()

        logger.info(f"Wrote {count} forecasts to database")
        if errors:
            logger.warning(f"Encountered {len(errors)} errors during write")

        return count

    except Exception as e:
        logger.error(f"Fatal error writing forecasts: {e}")
        raise


def write_accuracy_to_db(
    item_code: str,
    forecast_generated_at: datetime,
    winning_model: str,
    forecast_confidence_pct: float,
    metrics: Dict,
    months_compared: int,
    forecast_horizon: int = 12
) -> bool:
    """
    Write accuracy metrics to database.

    Parameters:
    -----------
    item_code : str
        Item code
    forecast_generated_at : datetime
        When forecast was generated
    winning_model : str
        Which model won the tournament
    forecast_confidence_pct : float
        Forecast confidence percentage
    metrics : Dict
        Accuracy metrics (mape, rmse, bias, mae)
    months_compared : int
        Number of months compared
    forecast_horizon : int
        Forecast horizon in months

    Returns:
    --------
    bool
        True if write successful
    """
    query = text("""
        INSERT INTO forecast_accuracy (
            item_code,
            forecast_generated_at,
            winning_model,
            forecast_confidence_pct,
            months_compared,
            forecast_horizon,
            mape,
            rmse,
            bias,
            mae,
            total_forecast,
            total_actual,
            created_at
        ) VALUES (
            :item_code,
            :forecast_generated_at,
            :winning_model,
            :forecast_confidence_pct,
            :months_compared,
            :forecast_horizon,
            :mape,
            :rmse,
            :bias,
            :mae,
            :total_forecast,
            :total_actual,
            NOW()
        )
    """)

    try:
        with get_session() as session:
            session.execute(query, {
                "item_code": item_code,
                "forecast_generated_at": forecast_generated_at,
                "winning_model": winning_model,
                "forecast_confidence_pct": forecast_confidence_pct,
                "months_compared": months_compared,
                "forecast_horizon": forecast_horizon,
                "mape": metrics.get('mape'),
                "rmse": metrics.get('rmse'),
                "bias": metrics.get('bias'),
                "mae": metrics.get('mae'),
                "total_forecast": 0,  # Will update when comparing to actuals
                "total_actual": 0
            })
            session.commit()

        logger.debug(f"Wrote accuracy metrics for {item_code}")
        return True

    except Exception as e:
        logger.error(f"Failed to write accuracy metrics for {item_code}: {e}")
        return False


def batch_write_accuracy(
    df_accuracy: pd.DataFrame,
    forecast_generated_at: datetime = None
) -> int:
    """
    Batch write accuracy metrics to database.

    Parameters:
    -----------
    df_accuracy : pd.DataFrame
        Accuracy metrics DataFrame from batch_calculate_accuracy()
    forecast_generated_at : datetime
        When forecast was generated

    Returns:
    --------
    int
        Number of accuracy records written
    """
    if df_accuracy.empty:
        logger.warning("No accuracy metrics to write")
        return 0

    if forecast_generated_at is None:
        forecast_generated_at = datetime.now()

    count = 0
    for _, row in df_accuracy.iterrows():
        success = write_accuracy_to_db(
            item_code=row['item_code'],
            forecast_generated_at=forecast_generated_at,
            winning_model=row['winning_model'],
            forecast_confidence_pct=row.get('forecast_confidence_pct'),
            metrics={
                'mape': row.get('mape'),
                'rmse': row.get('rmse'),
                'bias': row.get('bias'),
                'mae': row.get('mae')
            },
            months_compared=int(row['months_compared']),
            forecast_horizon=int(row.get('forecast_horizon', 12))
        )
        if success:
            count += 1

    logger.info(f"Wrote {count} accuracy records to database")
    return count


def refresh_materialized_views() -> bool:
    """
    Refresh materialized views after forecasts are updated.

    Returns:
    --------
    bool
        True if all views refreshed successfully
    """
    views = [
        'mv_forecast_summary',
        'mv_forecast_accuracy_summary',
        'mv_latest_costs',
        'mv_latest_pricing',
        'mv_vendor_lead_times'
    ]

    success_count = 0
    for view in views:
        try:
            with get_session() as session:
                # Use CONCURRENTLY to allow reads during refresh
                session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
                session.commit()
                logger.info(f"Refreshed materialized view: {view}")
                success_count += 1
        except Exception as e:
            logger.error(f"Error refreshing view {view}: {e}")
            # Continue with other views

    if success_count == len(views):
        logger.info("All materialized views refreshed successfully")
        return True
    else:
        logger.warning(f"Refreshed {success_count}/{len(views)} materialized views")
        return False


def write_and_refresh(
    df_forecasts: pd.DataFrame,
    df_accuracy: pd.DataFrame = None,
    forecast_generated_at: datetime = None
) -> Dict:
    """
    Write forecasts and accuracy to database and refresh views in one transaction.

    Parameters:
    -----------
    df_forecasts : pd.DataFrame
        Forecast results
    df_accuracy : pd.DataFrame, optional
        Accuracy metrics
    forecast_generated_at : datetime
        Timestamp for forecast run

    Returns:
    --------
    Dict
        Results with counts and any errors
        {
            'forecasts_written': int,
            'accuracy_written': int,
            'views_refreshed': bool,
            'errors': list
        }
    """
    results = {
        'forecasts_written': 0,
        'accuracy_written': 0,
        'views_refreshed': False,
        'errors': []
    }

    try:
        # Write forecasts
        results['forecasts_written'] = write_forecasts_to_db(df_forecasts, forecast_generated_at)

        # Write accuracy if provided
        if df_accuracy is not None and not df_accuracy.empty:
            results['accuracy_written'] = batch_write_accuracy(df_accuracy, forecast_generated_at)

        # Refresh views
        results['views_refreshed'] = refresh_materialized_views()

    except Exception as e:
        error_msg = f"Fatal error in write_and_refresh: {e}"
        logger.error(error_msg)
        results['errors'].append(error_msg)

    return results


def test_database_write() -> bool:
    """
    Test database write operations with sample data.

    Returns:
    --------
    bool
        True if test successful
    """
    logger.info("Testing database write operations...")

    try:
        with get_session() as session:
            # Test query
            result = session.execute(text("SELECT COUNT(*) FROM forecasts")).scalar()
            logger.info(f"Current forecasts in database: {result}")

            result = session.execute(text("SELECT COUNT(*) FROM forecast_accuracy")).scalar()
            logger.info(f"Current accuracy records in database: {result}")

            result = session.execute(text(
                "SELECT COUNT(*) FROM forecasts WHERE status = 'Active'"
            )).scalar()
            logger.info(f"Active forecasts: {result}")

        return True

    except Exception as e:
        logger.error(f"Database write test failed: {e}")
        return False


def get_active_forecasts() -> pd.DataFrame:
    """
    Get all active forecasts from database.

    Returns:
    --------
    pd.DataFrame
        Active forecasts
    """
    query = text("""
        SELECT * FROM forecasts
        WHERE status = 'Active'
        ORDER BY item_code
    """)

    try:
        with get_session() as session:
            result = session.execute(query)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df
    except Exception as e:
        logger.error(f"Failed to get active forecasts: {e}")
        return pd.DataFrame()


def get_latest_forecast_for_item(item_code: str) -> Dict:
    """
    Get the latest active forecast for a specific item.

    Parameters:
    -----------
    item_code : str
        Item code

    Returns:
    --------
    Dict
        Forecast data or empty dict if not found
    """
    query = text("""
        SELECT * FROM forecasts
        WHERE item_code = :item_code
          AND status = 'Active'
        ORDER BY forecast_generated_at DESC
        LIMIT 1
    """)

    try:
        with get_session() as session:
            result = session.execute(query, {"item_code": item_code})
            row = result.fetchone()

            if row:
                return dict(row._asdict())
            else:
                return {}

    except Exception as e:
        logger.error(f"Failed to get forecast for {item_code}: {e}")
        return {}
