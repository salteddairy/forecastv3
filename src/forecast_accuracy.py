"""
Forecast Accuracy Tracking Module

Tracks forecast accuracy over time by comparing previous forecasts to actual sales.
Provides metrics like MAPE, RMSE, and bias detection.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import json
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ForecastAccuracyTracker:
    """
    Tracks and analyzes forecast accuracy over time.

    Stores historical forecasts and compares them to actual sales
    to calculate accuracy metrics like MAPE, RMSE, and bias.
    """

    def __init__(self, cache_dir: Path = Path("data/cache")):
        """
        Initialize the accuracy tracker.

        Parameters:
        -----------
        cache_dir : Path
            Directory to store accuracy tracking data
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.accuracy_file = self.cache_dir / "forecast_accuracy.parquet"
        self.history_file = self.cache_dir / "forecast_history.json"

    def save_forecast_snapshot(self, df_forecasts: pd.DataFrame,
                              snapshot_date: Optional[datetime] = None) -> None:
        """
        Save a snapshot of current forecasts for later accuracy comparison.

        Parameters:
        -----------
        df_forecasts : pd.DataFrame
            Current forecast results with item_code, forecast_month_1-12, winning_model
        snapshot_date : datetime, optional
            Date of this forecast snapshot (default: now)
        """
        if snapshot_date is None:
            snapshot_date = datetime.now()

        snapshot_id = snapshot_date.strftime("%Y%m%d_%H%M%S")

        # Create snapshot record
        snapshot = {
            'snapshot_id': snapshot_id,
            'snapshot_date': snapshot_date.isoformat(),
            'item_count': len(df_forecasts),
            'items': {}
        }

        # Save forecast data for each item
        for _, row in df_forecasts.iterrows():
            item_code = row['item_code']
            snapshot['items'][item_code] = {
                'winning_model': row.get('winning_model'),
                'forecast_horizon': row.get('forecast_horizon', 12),
                'forecast_confidence_pct': row.get('forecast_confidence_pct'),
                'forecasts': {f'month_{i+1}': row.get(f'forecast_month_{i+1}')
                             for i in range(12)}
            }

        # Load existing history and append
        history = self._load_history()
        history.append(snapshot)

        # Save updated history
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

        logger.info(f"Saved forecast snapshot {snapshot_id} with {len(df_forecasts)} items")

    def calculate_accuracy_metrics(self, df_sales: pd.DataFrame,
                                   snapshot_id: Optional[str] = None) -> pd.DataFrame:
        """
        Calculate accuracy metrics by comparing previous forecasts to actual sales.

        Parameters:
        -----------
        df_sales : pd.DataFrame
            Actual sales data with item_code, date, qty
        snapshot_id : str, optional
            Specific snapshot to compare against (default: most recent)

        Returns:
        --------
        pd.DataFrame
            Accuracy metrics per item (MAPE, RMSE, bias, etc.)
        """
        # Load forecast history
        history = self._load_history()

        if not history:
            logger.warning("No forecast history found for accuracy calculation")
            return pd.DataFrame()

        # Get the snapshot to compare (most recent or specific)
        if snapshot_id:
            snapshot = next((s for s in history if s['snapshot_id'] == snapshot_id), None)
            if not snapshot:
                logger.error(f"Snapshot {snapshot_id} not found")
                return pd.DataFrame()
        else:
            # Use most recent snapshot (that's at least 1 month old)
            snapshot = None
            for s in reversed(history):
                snapshot_date = datetime.fromisoformat(s['snapshot_date'])
                age_months = (datetime.now() - snapshot_date).days / 30
                if age_months >= 1:
                    snapshot = s
                    break

            if not snapshot:
                logger.warning("No sufficiently old forecast snapshot found (need at least 1 month)")
                return pd.DataFrame()

        snapshot_date = datetime.fromisoformat(snapshot['snapshot_date'])
        logger.info(f"Calculating accuracy against snapshot from {snapshot_date.strftime('%Y-%m-%d')}")

        # Aggregate actual sales by month since snapshot
        df_sales['date'] = pd.to_datetime(df_sales['date'])
        df_sales_monthly = df_sales[df_sales['date'] >= snapshot_date].copy()
        df_sales_monthly['year_month'] = df_sales_monthly['date'].dt.to_period('M')
        actuals = df_sales_monthly.groupby(['item_code', 'year_month'])['qty'].sum().reset_index()
        actuals['month_offset'] = (
            (actuals['year_month'].dt.year - snapshot_date.year) * 12 +
            actuals['year_month'].dt.month - snapshot_date.month
        )

        # Calculate accuracy for each item
        accuracy_records = []

        for item_code in snapshot['items'].keys():
            forecast_data = snapshot['items'][item_code]
            item_actuals = actuals[actuals['item_code'] == item_code]

            if len(item_actuals) == 0:
                continue

            # Compare forecast to actual for each month
            forecast_values = []
            actual_values = []

            for _, actual_row in item_actuals.iterrows():
                month_offset = int(actual_row['month_offset'])
                if month_offset < 1 or month_offset > 12:
                    continue

                forecast_key = f'month_{month_offset}'
                forecast_value = forecast_data['forecasts'].get(forecast_key)

                if forecast_value is not None and not np.isnan(forecast_value):
                    forecast_values.append(forecast_value)
                    actual_values.append(actual_row['qty'])

            if len(forecast_values) == 0:
                continue

            # Calculate metrics
            forecast_arr = np.array(forecast_values)
            actual_arr = np.array(actual_values)

            # MAPE (Mean Absolute Percentage Error)
            non_zero_mask = actual_arr != 0
            if non_zero_mask.any():
                mape = np.mean(np.abs((actual_arr[non_zero_mask] - forecast_arr[non_zero_mask]) /
                                     actual_arr[non_zero_mask])) * 100
            else:
                mape = np.nan

            # RMSE (Root Mean Square Error)
            rmse = np.sqrt(np.mean((actual_arr - forecast_arr) ** 2))

            # Bias (mean forecast error)
            bias = np.mean(forecast_arr - actual_arr)

            # Mean Absolute Error (MAE)
            mae = np.mean(np.abs(actual_arr - forecast_arr))

            # Tracking Signal (cumulative forecast error / MAD)
            cumulative_error = np.sum(forecast_arr - actual_arr)
            mad = mae
            tracking_signal = cumulative_error / mad if mad > 0 else np.nan

            accuracy_records.append({
                'item_code': item_code,
                'snapshot_id': snapshot['snapshot_id'],
                'snapshot_date': snapshot_date,
                'months_compared': len(forecast_values),
                'winning_model': forecast_data['winning_model'],
                'mape': mape,
                'rmse': rmse,
                'bias': bias,
                'mae': mae,
                'tracking_signal': tracking_signal,
                'forecast_confidence_pct': forecast_data.get('forecast_confidence_pct'),
                'total_actual': np.sum(actual_arr),
                'total_forecast': np.sum(forecast_arr)
            })

        if accuracy_records:
            df_accuracy = pd.DataFrame(accuracy_records)
            # Save to cache
            df_accuracy.to_parquet(self.accuracy_file, index=False)
            logger.info(f"Calculated accuracy for {len(df_accuracy)} items")
            return df_accuracy
        else:
            logger.warning("No accuracy data could be calculated")
            return pd.DataFrame()

    def load_accuracy_metrics(self) -> pd.DataFrame:
        """
        Load previously calculated accuracy metrics from cache.

        Returns:
        --------
        pd.DataFrame
            Accuracy metrics or empty DataFrame if not available
        """
        if self.accuracy_file.exists():
            try:
                df_accuracy = pd.read_parquet(self.accuracy_file)
                logger.info(f"Loaded accuracy metrics for {len(df_accuracy)} items")
                return df_accuracy
            except Exception as e:
                logger.warning(f"Failed to load accuracy metrics: {e}")
                return pd.DataFrame()
        else:
            logger.info("No cached accuracy metrics found")
            return pd.DataFrame()

    def get_accuracy_summary(self, df_accuracy: pd.DataFrame) -> Dict:
        """
        Generate summary statistics from accuracy metrics.

        Parameters:
        -----------
        df_accuracy : pd.DataFrame
            Accuracy metrics DataFrame

        Returns:
        --------
        Dict
            Summary statistics
        """
        if df_accuracy.empty:
            return {}

        summary = {
            'total_items': len(df_accuracy),
            'avg_mape': df_accuracy['mape'].mean(),
            'median_mape': df_accuracy['mape'].median(),
            'avg_rmse': df_accuracy['rmse'].mean(),
            'avg_bias': df_accuracy['bias'].mean(),
            'model_distribution': df_accuracy['winning_model'].value_counts().to_dict(),
            'accuracy_categories': {
                'excellent': ((df_accuracy['mape'] < 10) & (df_accuracy['mape'].notna())).sum(),
                'good': ((df_accuracy['mape'] >= 10) & (df_accuracy['mape'] < 20)).sum(),
                'fair': ((df_accuracy['mape'] >= 20) & (df_accuracy['mape'] < 30)).sum(),
                'poor': (df_accuracy['mape'] >= 30).sum()
            }
        }

        return summary

    def _load_history(self) -> list:
        """Load forecast history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load forecast history: {e}")
                return []
        else:
            return []

    def get_available_snapshots(self) -> pd.DataFrame:
        """
        Get list of available forecast snapshots.

        Returns:
        --------
        pd.DataFrame
            Available snapshots with metadata
        """
        history = self._load_history()

        if not history:
            return pd.DataFrame()

        snapshots = []
        for s in history:
            snapshot_date = datetime.fromisoformat(s['snapshot_date'])
            age_days = (datetime.now() - snapshot_date).days
            snapshots.append({
                'snapshot_id': s['snapshot_id'],
                'snapshot_date': snapshot_date,
                'item_count': s['item_count'],
                'age_days': age_days,
                'can_compare': age_days >= 30
            })

        return pd.DataFrame(snapshots)


# Convenience functions for backward compatibility
def save_forecast_snapshot(df_forecasts: pd.DataFrame,
                          cache_dir: Path = Path("data/cache"),
                          snapshot_date: Optional[datetime] = None) -> str:
    """
    Save a snapshot of current forecasts.

    Returns:
    --------
    str
        Snapshot ID
    """
    tracker = ForecastAccuracyTracker(cache_dir)
    tracker.save_forecast_snapshot(df_forecasts, snapshot_date)
    return tracker._load_history()[-1]['snapshot_id']


def calculate_forecast_accuracy(df_sales: pd.DataFrame,
                                cache_dir: Path = Path("data/cache"),
                                snapshot_id: Optional[str] = None) -> pd.DataFrame:
    """
    Calculate forecast accuracy by comparing to actual sales.

    Returns:
    --------
    pd.DataFrame
        Accuracy metrics
    """
    tracker = ForecastAccuracyTracker(cache_dir)
    return tracker.calculate_accuracy_metrics(df_sales, snapshot_id)


def get_accuracy_metrics(cache_dir: Path = Path("data/cache")) -> pd.DataFrame:
    """Load cached accuracy metrics."""
    tracker = ForecastAccuracyTracker(cache_dir)
    return tracker.load_accuracy_metrics()
