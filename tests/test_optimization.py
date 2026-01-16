"""
Unit tests for Optimization Module
Tests TCO calculations, stockout predictions, and inventory optimization
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization import (
    calculate_tco_metrics,
    calculate_stockout_predictions,
    optimize_inventory
)


class TestTCOCalculations:
    """Test Total Cost of Ownership calculations"""

    @pytest.fixture
    def sample_items(self):
        """Create sample items data"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Item Description': ['Item 1', 'Item 2', 'Item 3'],
            'CurrentStock': [100, 50, 200],
            'IncomingStock': [0, 25, 0],
            'UnitCost': [50.0, 100.0, 25.0],
            'Region': ['REG', 'WPG', 'REG'],
            'Warehouse': ['REG', 'WPG', 'REG']
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def sample_forecasts(self):
        """Create sample forecast data"""
        data = {
            'item_code': ['ITEM001', 'ITEM002', 'ITEM003'],
            'forecast_month_1': [50, 25, 10],
            'forecast_month_2': [50, 25, 10],
            'forecast_month_3': [50, 25, 10],
            'forecast_month_4': [50, 25, 10],
            'forecast_month_5': [50, 25, 10],
            'forecast_month_6': [50, 25, 10],
            'winning_model': ['sma', 'sma', 'sma'],
            'forecast_horizon': [6, 6, 6]
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def default_config(self):
        """Default configuration for TCO calculations"""
        return {
            'carrying_cost': {
                'cost_of_capital_percent': 0.08,
                'storage_percent': 0.10,
                'service_percent': 0.02,
                'risk_percent': 0.05
            },
            'shipping': {
                'standard_freight_percent': 0.05,
                'special_order_freight_percent': 0.15,
                'special_order_fixed_surcharge': 50.0
            }
        }

    def test_calculate_tco_metrics(self, sample_items, sample_forecasts, default_config):
        """Test TCO metric calculations"""
        df_tco = calculate_tco_metrics(sample_items, sample_forecasts, default_config)

        assert len(df_tco) == 3
        assert 'cost_to_stock_annual' in df_tco.columns
        assert 'cost_to_special_annual' in df_tco.columns
        assert 'recommendation' in df_tco.columns

    def test_annual_demand_calculation(self, sample_items, sample_forecasts, default_config):
        """Test annual demand is calculated from forecasts"""
        df_tco = calculate_tco_metrics(sample_items, sample_forecasts, default_config)

        # ITEM001: 6 months * 50 = 300, annualized to 600
        item001_tco = df_tco[df_tco['Item No.'] == 'ITEM001'].iloc[0]
        assert item001_tco['annual_demand'] == 600

    def test_recommendation_logic(self, sample_items, sample_forecasts, default_config):
        """Test that TCO recommendation makes sense"""
        df_tco = calculate_tco_metrics(sample_items, sample_forecasts, default_config)

        # Should have a recommendation column
        assert 'recommendation' in df_tco.columns

        # Recommendation should be one of the valid options
        valid_recommendations = ['STOCK', 'SPECIAL ORDER']
        assert all(df_tco['recommendation'].isin(valid_recommendations))


class TestStockoutPredictions:
    """Test stockout prediction calculations"""

    @pytest.fixture
    def sample_stock_items(self):
        """Create items that will stockout"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'Region': ['REG', 'WPG', 'REG', 'CGY'],
            'Warehouse': ['REG', 'WPG', 'REG', 'CGY'],
            'CurrentStock': [50, 20, 200, 10],
            'IncomingStock': [0, 0, 0, 0]
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def sample_forecasts(self):
        """Create forecasts that will cause stockouts"""
        data = {
            'item_code': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'forecast_month_1': [20, 10, 15, 8],
            'forecast_month_2': [20, 10, 15, 8],
            'forecast_month_3': [20, 10, 15, 8],
            'forecast_month_4': [0, 0, 0, 0],
            'forecast_month_5': [0, 0, 0, 0],
            'forecast_month_6': [0, 0, 0, 0],
            'forecast_horizon': [3, 3, 3, 3]
        }
        return pd.DataFrame(data)

    def test_stockout_detection(self, sample_stock_items, sample_forecasts):
        """Test that stockouts are detected"""
        df_stockout = calculate_stockout_predictions(sample_stock_items, sample_forecasts)

        # ITEM001: 50 stock, 60 demand = will stockout
        item001 = df_stockout[df_stockout['Item No.'] == 'ITEM001'].iloc[0]
        assert item001['will_stockout'] == True

        # ITEM003: 200 stock, 45 demand = no stockout
        item003 = df_stockout[df_stockout['Item No.'] == 'ITEM003'].iloc[0]
        assert item003['will_stockout'] == False

    def test_shortage_quantity(self, sample_stock_items, sample_forecasts):
        """Test shortage quantity calculation"""
        df_stockout = calculate_stockout_predictions(sample_stock_items, sample_forecasts)

        # ITEM001: 50 available, 60 demand = 10 shortage
        item001 = df_stockout[df_stockout['Item No.'] == 'ITEM001'].iloc[0]
        assert item001['shortage_qty'] == 10

    def test_days_until_stockout(self, sample_stock_items, sample_forecasts):
        """Test days until stockout calculation"""
        df_stockout = calculate_stockout_predictions(sample_stock_items, sample_forecasts)

        # ITEM001: 50 stock, 20/month demand = 2.5 months = ~75 days
        item001 = df_stockout[df_stockout['Item No.'] == 'ITEM001'].iloc[0]
        assert 60 < item001['days_until_stockout'] < 90

    def test_urgency_categorization(self, sample_stock_items, sample_forecasts):
        """Test urgency categorization"""
        df_stockout = calculate_stockout_predictions(sample_stock_items, sample_forecasts)

        # Should have urgency column
        assert 'urgency' in df_stockout.columns

    def test_no_stockout_items(self, sample_stock_items, sample_forecasts):
        """Test items that won't stockout"""
        df_stockout = calculate_stockout_predictions(sample_stock_items, sample_forecasts)

        # Should have days_until_stockout = 999 for non-stockout items
        no_stockout = df_stockout[df_stockout['will_stockout'] == False]
        assert all(no_stockout['days_until_stockout'] == 999)


class TestIncomingStock:
    """Test handling of incoming/purchase orders"""

    def test_incoming_stock_prevents_stockout(self):
        """Test that incoming stock is considered"""
        items = pd.DataFrame({
            'Item No.': ['ITEM001'],
            'Region': ['REG'],
            'Warehouse': ['REG'],
            'CurrentStock': [50],
            'IncomingStock': [50]  # Incoming stock
        })

        forecasts = pd.DataFrame({
            'item_code': ['ITEM001'],
            'forecast_month_1': [30],
            'forecast_month_2': [30],
            'forecast_month_3': [30],
            'forecast_month_4': [0],
            'forecast_month_5': [0],
            'forecast_month_6': [0],
            'forecast_horizon': [3]
        })

        df_stockout = calculate_stockout_predictions(items, forecasts)

        # Should have 100 total available (50 + 50)
        item001 = df_stockout.iloc[0]
        assert item001['total_available'] == 100

        # Should NOT stockout (100 >= 90 demand)
        assert item001['will_stockout'] == False


class TestOptimizationIntegration:
    """Test full optimization workflow"""

    @pytest.fixture
    def optimization_data(self):
        """Create complete dataset for optimization"""
        items = pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002'],
            'Region': ['REG', 'WPG'],
            'Warehouse': ['REG', 'WPG'],
            'CurrentStock': [100, 50],
            'IncomingStock': [0, 0],
            'UnitCost': [50.0, 100.0]
        })

        forecasts = pd.DataFrame({
            'item_code': ['ITEM001', 'ITEM002'],
            'forecast_month_1': [40, 20],
            'forecast_month_2': [40, 20],
            'forecast_month_3': [40, 20],
            'forecast_month_4': [40, 20],
            'forecast_month_5': [40, 20],
            'forecast_month_6': [40, 20],
            'winning_model': ['sma', 'sma'],
            'forecast_horizon': [6, 6]
        })

        return items, forecasts

    def test_optimize_inventory(self, optimization_data):
        """Test complete optimization function"""
        items, forecasts = optimization_data

        df_stockout, df_tco = optimize_inventory(items, forecasts)

        # Should return both dataframes
        assert len(df_stockout) == 2
        assert len(df_tco) == 2

        # Stockout dataframe should have expected columns
        assert 'will_stockout' in df_stockout.columns
        assert 'shortage_qty' in df_stockout.columns

        # TCO dataframe should have expected columns
        assert 'recommendation' in df_tco.columns
        assert 'annual_savings' in df_tco.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
