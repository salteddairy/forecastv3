"""
Unit tests for UOM Conversion (SAP B1)
Tests edge cases, data quality, and conversion accuracy
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.uom_conversion_sap import convert_stock_to_sales_uom_sap, validate_sap_uom_data


class TestUOMConversion:
    """Test UOM conversion functionality"""

    @pytest.fixture
    def sample_items(self):
        """Create sample items data for testing"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004', 'ITEM005'],
            'Item Description': ['Test Item 1', 'Test Item 2', 'Test Item 3', 'Test Item 4', 'Test Item 5'],
            'BaseUoM': ['Litre', 'Litre', 'kg', 'Litre', 'Litre'],
            'SalesUoM': ['Pail', 'Drum', 'Pail', 'Pail', 'Pail'],
            'QtyPerSalesUoM': [18.9, 200.0, 20.0, 0.0, 15.0],
            'CurrentStock': [189.0, 2000.0, 100.0, 50.0, 150.0],
            'IncomingStock': [0.0, 0.0, 0.0, 0.0, 0.0],
            'Warehouse': ['REG', 'REG', 'REG', 'REG', 'REG']
        }
        return pd.DataFrame(data)

    def test_basic_conversion(self, sample_items):
        """Test basic UOM conversion"""
        result = convert_stock_to_sales_uom_sap(sample_items)

        # ITEM001: 189.0 Litres / 18.9 = 10 Pails
        item001 = result[result['Item No.'] == 'ITEM001'].iloc[0]
        assert item001['CurrentStock_SalesUOM'] == pytest.approx(10.0, rel=0.01)
        assert item001['SalesUOM'] == 'Pail'
        assert item001['ConversionFactor'] == 18.9

    def test_drum_conversion(self, sample_items):
        """Test conversion to larger units (Drums)"""
        result = convert_stock_to_sales_uom_sap(sample_items)

        # ITEM002: 2000.0 Litres / 200.0 = 10 Drums
        item002 = result[result['Item No.'] == 'ITEM002'].iloc[0]
        assert item002['CurrentStock_SalesUOM'] == pytest.approx(10.0, rel=0.01)
        assert item002['SalesUOM'] == 'Drum'

    def test_kg_conversion(self, sample_items):
        """Test conversion from kg to Pail"""
        result = convert_stock_to_sales_uom_sap(sample_items)

        # ITEM003: 100.0 kg / 20.0 = 5 Pails
        item003 = result[result['Item No.'] == 'ITEM003'].iloc[0]
        assert item003['CurrentStock_SalesUOM'] == pytest.approx(5.0, rel=0.01)
        assert item003['BaseUoM'] == 'kg'

    def test_zero_conversion_factor(self, sample_items):
        """Test handling of zero conversion factor"""
        result = convert_stock_to_sales_uom_sap(sample_items)

        # ITEM004: Has 0 conversion factor, should be marked as invalid (NaN)
        item004 = result[result['Item No.'] == 'ITEM004'].iloc[0]
        # With conversion factor of 0, it should be set to NaN with error flag
        assert pd.isna(item004['ConversionFactor'])
        assert item004['ConversionError'] == 'Invalid QtyPerSalesUoM'

    def test_incoming_stock_conversion(self, sample_items):
        """Test conversion of incoming stock"""
        sample_items.loc[sample_items['Item No.'] == 'ITEM001', 'IncomingStock'] = 189.0
        result = convert_stock_to_sales_uom_sap(sample_items)

        item001 = result[result['Item No.'] == 'ITEM001'].iloc[0]
        assert item001['IncomingStock_SalesUOM'] == pytest.approx(10.0, rel=0.01)

    def test_missing_uom_columns(self):
        """Test handling of missing UOM columns"""
        data = {
            'Item No.': ['ITEM001'],
            'CurrentStock': [100.0],
            'IncomingStock': [0.0]
        }
        df = pd.DataFrame(data)
        result = convert_stock_to_sales_uom_sap(df)

        # Should return original dataframe if columns missing
        assert 'CurrentStock_SalesUOM' not in result.columns


class TestUOMValidation:
    """Test UOM data validation"""

    @pytest.fixture
    def valid_items(self):
        """Create valid items data"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'BaseUoM': ['Litre', 'kg', 'Litre'],
            'SalesUoM': ['Pail', 'Pail', 'Drum'],
            'QtyPerSalesUoM': [18.9, 20.0, 200.0],
            'CurrentStock': [189.0, 100.0, 2000.0],
            'IncomingStock': [0.0, 0.0, 0.0]
        }
        return pd.DataFrame(data)

    @pytest.fixture
    def invalid_items(self):
        """Create items with validation issues"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'BaseUoM': ['Litre', 'kg', 'Litre', 'Litre'],
            'SalesUoM': ['Pail', 'Pail', 'Drum', 'Pail'],
            'QtyPerSalesUoM': [18.9, np.nan, 0.0, 0.005],  # Valid, NaN, zero, too small
            'CurrentStock': [189.0, 100.0, 2000.0, 100.0],
            'IncomingStock': [0.0, 0.0, 0.0, 0.0]
        }
        return pd.DataFrame(data)

    def test_valid_data_passes(self, valid_items):
        """Test that valid data passes validation"""
        result = validate_sap_uom_data(valid_items)

        assert result['invalid_conversion_factors'] == []
        assert result['zero_conversion_factor'] == []

    def test_detects_nan_conversion_factor(self, invalid_items):
        """Test detection of NaN conversion factors"""
        result = validate_sap_uom_data(invalid_items)

        assert 'ITEM002' in result['invalid_conversion_factors']

    def test_detects_zero_conversion_factor(self, invalid_items):
        """Test detection of zero conversion factors"""
        result = validate_sap_uom_data(invalid_items)

        assert 'ITEM003' in result['zero_conversion_factor']

    def test_detects_extreme_conversion_factors(self, invalid_items):
        """Test detection of extreme conversion factors"""
        result = validate_sap_uom_data(invalid_items)

        extreme_items = [x['Item Code'] for x in result['extreme_conversion_factors']]
        assert 'ITEM004' in extreme_items

    def test_missing_uom_columns(self):
        """Test detection of missing UOM columns"""
        data = {
            'Item No.': ['ITEM001'],
            'CurrentStock': [100.0]
        }
        df = pd.DataFrame(data)
        result = validate_sap_uom_data(df)

        assert 'BaseUoM' in result['missing_uom_fields']
        assert 'SalesUoM' in result['missing_uom_fields']
        assert 'QtyPerSalesUoM' in result['missing_uom_fields']


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_negative_stock(self):
        """Test handling of negative stock values"""
        data = {
            'Item No.': ['ITEM001'],
            'BaseUoM': ['Litre'],
            'SalesUoM': ['Pail'],
            'QtyPerSalesUoM': [18.9],
            'CurrentStock': [-50.0],
            'IncomingStock': [0.0]
        }
        df = pd.DataFrame(data)
        result = convert_stock_to_sales_uom_sap(df)

        item = result.iloc[0]
        assert item['CurrentStock_SalesUOM'] < 0

    def test_very_large_conversion_factor(self):
        """Test handling of very large conversion factors"""
        data = {
            'Item No.': ['ITEM001'],
            'BaseUoM': ['Litre'],
            'SalesUoM': ['Tank'],
            'QtyPerSalesUoM': [50000.0],  # Very large
            'CurrentStock': [100000.0],
            'IncomingStock': [0.0]
        }
        df = pd.DataFrame(data)
        result = convert_stock_to_sales_uom_sap(df)

        item = result.iloc[0]
        assert item['CurrentStock_SalesUOM'] == pytest.approx(2.0, rel=0.01)

    def test_string_in_numeric_fields(self):
        """Test handling of strings in numeric fields"""
        data = {
            'Item No.': ['ITEM001', 'ITEM002'],
            'BaseUoM': ['Litre', 'kg'],
            'SalesUoM': ['Pail', 'Pail'],
            'QtyPerSalesUoM': ['18.9', 'invalid'],  # One valid, one invalid
            'CurrentStock': [189.0, 100.0],
            'IncomingStock': [0.0, 0.0]
        }
        df = pd.DataFrame(data)
        result = convert_stock_to_sales_uom_sap(df)

        # First item should convert correctly
        item001 = result[result['Item No.'] == 'ITEM001'].iloc[0]
        assert item001['CurrentStock_SalesUOM'] == pytest.approx(10.0, rel=0.01)

        # Second item should be marked as invalid (NaN with error flag)
        item002 = result[result['Item No.'] == 'ITEM002'].iloc[0]
        assert pd.isna(item002['ConversionFactor'])
        assert item002['ConversionError'] == 'Invalid QtyPerSalesUoM'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
