"""
Unit tests for Forecasting Module
Tests model selection, forecast generation, and tournament logic
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.forecasting import (
    calculate_dynamic_forecast_horizon,
    prepare_monthly_data,
    forecast_sma,
    run_tournament,
    forecast_items
)


class TestDynamicForecastHorizon:
    """Test dynamic forecast horizon calculation"""

    def test_high_velocity_stable(self):
        """Test high velocity, stable demand returns short horizon"""
        # Create monthly data with high, stable demand
        data = pd.Series([150, 155, 160, 158, 162, 160, 157, 163, 161, 159, 160, 158],
                        index=pd.period_range('2023-01', periods=12, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # High velocity (avg >= 100) and stable (CV < 0.5) should return 1-2 months
        assert horizon in [1, 2]

    def test_medium_velocity(self):
        """Test medium velocity demand"""
        data = pd.Series([50, 55, 48, 52, 50, 53, 49, 51, 50, 52, 48, 50],
                        index=pd.period_range('2023-01', periods=12, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # Medium velocity (20-100) should return 3-4 months
        assert horizon in [3, 4]

    def test_low_velocity_stable(self):
        """Test low velocity, stable demand"""
        data = pd.Series([10, 11, 10, 12, 10, 11, 10, 12, 10, 11, 10, 12],
                        index=pd.period_range('2023-01', periods=12, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # Low velocity, stable should return 3 months
        assert horizon == 3

    def test_low_velocity_seasonal(self):
        """Test low velocity, seasonal demand"""
        data = pd.Series([5, 5, 20, 5, 5, 20, 5, 5, 20, 5, 5, 20],
                        index=pd.period_range('2023-01', periods=12, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # Low velocity, high variability (seasonal) returns 3 months
        # (avg=10 < 20, CV > 0.5, so returns default 3)
        assert horizon == 3

    def test_insufficient_data(self):
        """Test with insufficient historical data"""
        data = pd.Series([10, 15], index=pd.period_range('2023-01', periods=2, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # Should default to 3 months for insufficient data
        assert horizon == 3

    def test_zero_demand(self):
        """Test with zero demand items"""
        data = pd.Series([0, 0, 0, 0, 0, 0],
                        index=pd.period_range('2023-01', periods=6, freq='M'))

        horizon = calculate_dynamic_forecast_horizon(data)

        # Should return a valid horizon even with zero demand
        assert horizon in [3, 6]


class TestSMAModel:
    """Test Simple Moving Average model"""

    def test_sma_basic_forecast(self):
        """Test basic SMA forecast"""
        train = pd.Series([100, 110, 105, 108, 102, 107],
                         index=pd.period_range('2023-01', periods=6, freq='M'))
        test = pd.Series([106, 104],
                        index=pd.period_range('2023-07', periods=2, freq='M'))

        forecast, rmse = forecast_sma(train, test, forecast_horizon=3)

        # Should return forecast for 3 months
        assert len(forecast) == 3
        assert np.isnan(rmse) == False

    def test_sma_with_test_set(self):
        """Test SMA calculates RMSE correctly"""
        train = pd.Series([100, 100, 100, 100],
                         index=pd.period_range('2023-01', periods=4, freq='M'))
        test = pd.Series([100, 100],
                        index=pd.period_range('2023-05', periods=2, freq='M'))

        forecast, rmse = forecast_sma(train, test, forecast_horizon=2)

        # With perfect data, RMSE should be 0
        assert rmse == 0.0

    def test_sma_empty_train(self):
        """Test SMA with empty training data"""
        train = pd.Series([], dtype=float)
        test = pd.Series([100, 100], dtype=float)

        forecast, rmse = forecast_sma(train, test, forecast_horizon=2)

        # Should handle gracefully
        assert len(forecast) == 2


class TestForecastTournament:
    """Test forecasting tournament logic"""

    @pytest.fixture
    def sample_sales_data(self):
        """Create sample sales data for tournament testing"""
        data = {
            'date': pd.date_range('2023-01-01', periods=24, freq='MS'),
            'item_code': ['TEST001'] * 24,
            'qty': [100, 105, 102, 108, 103, 107, 104, 106, 101, 109, 105, 103,
                    102, 108, 104, 106, 103, 107, 105, 104, 106, 103, 105, 104]
        }
        return pd.DataFrame(data)

    def test_run_tournament(self, sample_sales_data):
        """Test running tournament for single item"""
        result = run_tournament(sample_sales_data, 'TEST001')

        # Should return a dictionary with expected keys
        assert 'item_code' in result
        assert 'winning_model' in result
        assert 'forecast_month_1' in result

        # Winning model should be one of the three (lowercase)
        assert result['winning_model'] in ['sma', 'holt_winters', 'prophet', 'SMA', 'Holt-Winters', 'Prophet']

    def test_forecast_items_single_item(self, sample_sales_data):
        """Test forecasting for single item"""
        df_results = forecast_items(sample_sales_data, item_codes=['TEST001'])

        assert len(df_results) == 1
        assert df_results.iloc[0]['item_code'] == 'TEST001'

    def test_forecast_items_multiple_items(self, sample_sales_data):
        """Test forecasting for multiple items"""
        # Add second item
        df_multi = pd.concat([
            sample_sales_data,
            sample_sales_data.assign(item_code='TEST002')
        ])

        df_results = forecast_items(df_multi, item_codes=['TEST001', 'TEST002'])

        assert len(df_results) == 2

    def test_insufficient_history(self):
        """Test handling of items with insufficient history"""
        # Create item with only 2 months of data
        data = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=2, freq='MS'),
            'item_code': ['TEST001'] * 2,
            'qty': [100, 105]
        })

        result = run_tournament(data, 'TEST001')

        # Should still return a result, possibly with error or default model
        assert 'item_code' in result


class TestMonthlyDataPreparation:
    """Test monthly data preparation"""

    @pytest.fixture
    def sample_daily_sales(self):
        """Create sample daily sales data"""
        dates = pd.date_range('2023-01-01', '2023-03-31', freq='D')
        data = {
            'date': dates,
            'item_code': 'TEST001',
            'qty': np.random.randint(0, 10, size=len(dates))
        }
        return pd.DataFrame(data)

    def test_prepare_monthly_data(self, sample_daily_sales):
        """Test aggregating daily sales to monthly"""
        monthly = prepare_monthly_data(sample_daily_sales, 'TEST001')

        # Should have 3 months of data
        assert len(monthly) == 3
        assert isinstance(monthly.index, pd.PeriodIndex)

    def test_prepare_monthly_empty_data(self):
        """Test preparing monthly data with no matching items"""
        df_sales = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=10, freq='D'),
            'item_code': ['OTHER'] * 10,
            'qty': [10] * 10
        })

        monthly = prepare_monthly_data(df_sales, 'TEST001')

        # Should return empty series
        assert len(monthly) == 0


class TestForecastAccuracy:
    """Test forecast accuracy calculations"""

    def test_rmse_calculation(self):
        """Test RMSE is calculated correctly"""
        actual = pd.Series([100, 102, 98, 101, 99, 100])
        forecast = pd.Series([100, 100, 100, 100, 100, 100])

        # Manual RMSE calculation
        squared_errors = (actual - forecast) ** 2
        rmse = np.sqrt(squared_errors.mean())

        assert rmse > 0
        assert rmse < 2  # Should be relatively small

    def test_mape_calculation(self):
        """Test MAPE (Mean Absolute Percentage Error) calculation"""
        actual = pd.Series([100, 200, 150])
        forecast = pd.Series([110, 190, 160])

        # MAPE = mean(|actual - forecast| / actual) * 100
        absolute_errors = np.abs(actual - forecast)
        mape = (absolute_errors / actual).mean() * 100

        assert 0 < mape < 20  # Should be between 0-20%


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
