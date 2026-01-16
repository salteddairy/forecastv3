"""
Unit tests for Spatial Optimization Module
Tests warehouse capacity management and vendor grouping
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spatial_optimization import (
    ItemDimensions,
    SkidSpace,
    DimensionManager,
    WarehouseCapacityManager,
    VendorGroupOptimizer,
    SpatialOrderOptimizer
)


class TestItemDimensions:
    """Test ItemDimensions dataclass"""

    def test_create_dimensions(self):
        """Test creating item dimensions"""
        dims = ItemDimensions(
            length_cm=50.0,
            width_cm=40.0,
            height_cm=30.0,
            weight_kg=5.0,
            units_per_skid=24,
            stacking_allowed=True
        )

        assert dims.length_cm == 50.0
        assert dims.width_cm == 40.0
        assert dims.height_cm == 30.0
        assert dims.weight_kg == 5.0
        assert dims.units_per_skid == 24
        assert dims.stacking_allowed is True


class TestSkidSpace:
    """Test SkidSpace dataclass"""

    def test_skid_space_calculation(self):
        """Test skid space calculations"""
        space = SkidSpace(
            location='CGY',
            total_skids=100,
            used_skids=60
        )

        assert space.available_skids == 40
        assert space.utilization_pct == 60.0

    def test_full_capacity(self):
        """Test at full capacity"""
        space = SkidSpace(
            location='TOR',
            total_skids=100,
            used_skids=100
        )

        assert space.available_skids == 0
        assert space.utilization_pct == 100.0

    def test_empty_capacity(self):
        """Test empty warehouse"""
        space = SkidSpace(
            location='EDM',
            total_skids=100,
            used_skids=0
        )

        assert space.available_skids == 100
        assert space.utilization_pct == 0.0


class TestDimensionManager:
    """Test dimension management"""

    def test_parse_dimension_valid(self):
        """Test parsing valid dimension"""
        dm = DimensionManager()
        result = dm._parse_dimension(50.5)
        assert result == 50.5

    def test_parse_dimension_string(self):
        """Test parsing dimension from string"""
        dm = DimensionManager()
        result = dm._parse_dimension("50.5")
        assert result == 50.5

    def test_parse_dimension_zero(self):
        """Test parsing zero dimension"""
        dm = DimensionManager()
        result = dm._parse_dimension(0)
        assert result == 0.0

    def test_parse_dimension_nan(self):
        """Test parsing NaN dimension"""
        dm = DimensionManager()
        result = dm._parse_dimension(np.nan)
        assert result == 0.0

    def test_estimate_units_per_skid(self):
        """Test estimating units per skid"""
        dm = DimensionManager()

        # Small items: 30x20x15 cm
        # Should fit many on 120x100 cm skid
        units = dm._estimate_units_per_skid(30.0, 20.0, 15.0)
        assert units > 1

        # Large item: same size as skid
        units = dm._estimate_units_per_skid(120.0, 100.0, 150.0)
        assert units == 1

    def test_load_from_sap(self):
        """Test loading dimensions from SAP data"""
        dm = DimensionManager()

        # Create mock SAP data
        df_items = pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Length': [50.0, 30.0, 0.0],
            'Width': [40.0, 20.0, 0.0],
            'Height': [30.0, 15.0, 0.0],
            'Weight': [5.0, 2.0, 1.0]
        })

        dimensions = dm.load_from_sap(df_items)

        # Should load 2 items (ITEM003 has no dimensions)
        assert len(dimensions) == 2
        assert 'ITEM001' in dimensions
        assert 'ITEM002' in dimensions
        assert 'ITEM003' not in dimensions

        # Check dimensions
        assert dimensions['ITEM001'].length_cm == 50.0
        assert dimensions['ITEM001'].units_per_skid > 1

    def test_get_dimensions(self):
        """Test retrieving dimensions"""
        dm = DimensionManager()

        # Add some dimensions
        dm.dimensions_cache['TEST001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=24
        )

        # Get existing
        dims = dm.get_dimensions('TEST001')
        assert dims is not None
        assert dims.length_cm == 50.0

        # Get non-existing
        dims = dm.get_dimensions('NONEXISTENT')
        assert dims is None


class TestWarehouseCapacityManager:
    """Test warehouse capacity management"""

    @pytest.fixture
    def sample_items(self):
        """Create sample items data"""
        return pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Warehouse': ['CGY', 'TOR', 'CGY'],
            'CurrentStock_SalesUOM': [100, 200, 150]
        })

    @pytest.fixture
    def manager(self, sample_items):
        """Create manager with sample data"""
        dm = DimensionManager()
        manager = WarehouseCapacityManager(dm)
        manager.load_current_stock(sample_items)
        return manager

    def test_load_current_stock(self, manager):
        """Test loading current stock"""
        assert 'CGY' in manager.current_stock
        assert 'TOR' in manager.current_stock

        assert manager.current_stock['CGY']['ITEM001'] == 100
        assert manager.current_stock['CGY']['ITEM003'] == 150
        assert manager.current_stock['TOR']['ITEM002'] == 200

    def test_calculate_space_required_no_dimensions(self, manager):
        """Test space calculation when no dimensions available"""
        # No dimensions loaded, should assume 1 unit per skid
        skids = manager.calculate_space_required('NONEXISTENT', 100)
        assert skids == 100.0

    def test_calculate_space_required_with_dimensions(self, manager):
        """Test space calculation with dimensions"""
        # Add dimensions
        manager.dimension_manager.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=10
        )

        # 100 units / 10 units per skid = 10 skids
        skids = manager.calculate_space_required('ITEM001', 100)
        assert skids == 10.0

    def test_calculate_current_space_usage(self, manager):
        """Test calculating current space usage"""
        # Add dimensions
        manager.dimension_manager.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=10
        )
        manager.dimension_manager.dimensions_cache['ITEM003'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=20
        )

        # CGY: ITEM001 (100 units) + ITEM003 (150 units)
        # 100/10 + 150/20 = 10 + 7.5 = 17.5 skids
        usage = manager.calculate_current_space_usage('CGY')
        assert usage == 17.5

    def test_check_capacity_constraint_sufficient(self, manager):
        """Test capacity check with sufficient space"""
        # Clear current stock to start fresh
        manager.current_stock = {}

        # Add capacity
        manager.location_capacities['CGY'] = SkidSpace(
            location='CGY',
            total_skids=100,
            used_skids=0
        )

        # Add dimensions
        manager.dimension_manager.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=10
        )

        # Order 50 units = 5 skids
        has_capacity, shortage = manager.check_capacity_constraint('CGY', {'ITEM001': 50})

        assert has_capacity is True
        assert shortage == 0.0

    def test_check_capacity_constraint_insufficient(self, manager):
        """Test capacity check with insufficient space"""
        # Clear current stock to start fresh
        manager.current_stock = {}

        # Add small capacity
        manager.location_capacities['CGY'] = SkidSpace(
            location='CGY',
            total_skids=5,
            used_skids=0
        )

        # Add dimensions
        manager.dimension_manager.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=10
        )

        # Order 100 units = 10 skids, but only 5 available
        has_capacity, shortage = manager.check_capacity_constraint('CGY', {'ITEM001': 100})

        assert has_capacity is False
        assert shortage == 5.0

    def test_get_location_capacity_status(self, manager):
        """Test capacity status report"""
        # Add capacities
        manager.location_capacities['CGY'] = SkidSpace(
            location='CGY',
            total_skids=100,
            used_skids=0
        )
        manager.location_capacities['TOR'] = SkidSpace(
            location='TOR',
            total_skids=200,
            used_skids=50
        )

        # Add dimensions for space calculation
        manager.dimension_manager.dimensions_cache['ITEM002'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=20
        )

        status = manager.get_location_capacity_status()

        assert len(status) == 2
        assert 'CGY' in status['Location'].values
        assert 'TOR' in status['Location'].values

        # TOR should have some usage from ITEM002
        tor_row = status[status['Location'] == 'TOR'].iloc[0]
        assert tor_row['Current_Usage_Skids'] == 10.0  # 200 units / 20 per skid


class TestVendorGroupOptimizer:
    """Test vendor grouping optimization"""

    @pytest.fixture
    def sample_items(self):
        """Create sample items to order"""
        return pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003', 'ITEM004'],
            'TargetVendor': ['VEND001', 'VEND001', 'VEND002', 'VEND002'],
            'TargetVendorName': ['Vendor A', 'Vendor A', 'Vendor B', 'Vendor B'],
            'Recommended_Order_Qty': [100, 200, 150, 50]
        })

    @pytest.fixture
    def optimizer(self, sample_items):
        """Create optimizer with sample data"""
        return VendorGroupOptimizer(sample_items)

    def test_group_items_by_vendor(self, optimizer):
        """Test grouping items by vendor"""
        groups = optimizer.group_items_by_vendor(optimizer.df_items)

        assert len(groups) == 2
        assert 'VEND001' in groups
        assert 'VEND002' in groups

        # Check VEND001 has 2 items
        assert len(groups['VEND001']) == 2
        assert set(groups['VEND001']['Item No.']) == {'ITEM001', 'ITEM002'}

    def test_calculate_vendor_group_metrics(self, optimizer):
        """Test calculating vendor group metrics"""
        # Add dimension manager
        from src.spatial_optimization import WarehouseCapacityManager
        dm = DimensionManager()
        dm.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50.0, width_cm=40.0, height_cm=30.0,
            weight_kg=5.0, units_per_skid=10
        )
        cm = WarehouseCapacityManager(dm)

        vendor_group = optimizer.df_items[
            optimizer.df_items['TargetVendor'] == 'VEND001'
        ]

        metrics = optimizer.calculate_vendor_group_metrics(vendor_group, cm)

        assert metrics['total_units'] == 300  # 100 + 200
        assert metrics['total_skids'] > 0
        assert metrics['estimated_shipping_cost'] > 0


class TestSpatialOrderOptimizer:
    """Test integrated spatial order optimization"""

    @pytest.fixture
    def sample_stockout(self):
        """Create sample stockout data"""
        return pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Region': ['CGY', 'TOR', 'CGY'],
            'shortage_qty': [100, 200, 150],
            'will_stockout': [True, True, True],
            'TargetVendor': ['VEND001', 'VEND002', 'VEND001'],
            'Item Description': ['Item 1', 'Item 2', 'Item 3']
        })

    @pytest.fixture
    def sample_items(self):
        """Create sample items data"""
        return pd.DataFrame({
            'Item No.': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Warehouse': ['CGY', 'TOR', 'CGY'],
            'CurrentStock_SalesUOM': [50, 100, 25],
            'TargetVendorName': ['Vendor A', 'Vendor B', 'Vendor A']
        })

    def test_optimize_orders_with_constraints(self, sample_items, sample_stockout):
        """Test order optimization with spatial constraints"""
        optimizer = SpatialOrderOptimizer(sample_items, sample_stockout)

        # Add default capacities
        optimizer.capacity_manager.location_capacities['CGY'] = SkidSpace(
            location='CGY', total_skids=100, used_skids=0
        )
        optimizer.capacity_manager.location_capacities['TOR'] = SkidSpace(
            location='TOR', total_skids=100, used_skids=0
        )

        result = optimizer.optimize_orders_with_constraints()

        assert len(result) > 0
        assert 'Vendor' in result.columns
        assert 'Total_Units' in result.columns
        assert 'Total_Skids_Required' in result.columns
        assert 'Estimated_Shipping_Cost' in result.columns
        assert 'Space_Constraint_Met' in result.columns

    def test_generate_order_recommendations(self, sample_items, sample_stockout):
        """Test generating detailed order recommendations"""
        optimizer = SpatialOrderOptimizer(sample_items, sample_stockout)

        # Add capacities
        for location in ['CGY', 'TOR']:
            optimizer.capacity_manager.location_capacities[location] = SkidSpace(
                location=location, total_skids=100, used_skids=0
            )

        optimized = optimizer.optimize_orders_with_constraints()
        recommendations = optimizer.generate_order_recommendations(optimized)

        if len(recommendations) > 0:
            assert 'Vendor' in recommendations.columns
            assert 'Item_No.' in recommendations.columns
            assert 'Order_Qty' in recommendations.columns
            assert 'Location' in recommendations.columns
            assert 'Skids_Required' in recommendations.columns

    def test_get_capacity_report(self, sample_items, sample_stockout):
        """Test capacity report generation"""
        optimizer = SpatialOrderOptimizer(sample_items, sample_stockout)

        # Add capacities
        optimizer.capacity_manager.location_capacities['CGY'] = SkidSpace(
            location='CGY', total_skids=100, used_skids=0
        )

        report = optimizer.get_capacity_report()

        assert len(report) > 0
        assert 'Location' in report.columns
        assert 'Total_Skids' in report.columns
        assert 'Available_Skids' in report.columns
        assert 'Utilization_Pct' in report.columns


class TestFallbackSystem:
    """Test fallback system for missing data"""

    def test_fallback_dimensions_liquids(self):
        """Test fallback dimensions for liquid items"""
        dm = DimensionManager()

        df_items = pd.DataFrame({
            'Item No.': ['LIQUID001', 'OIL-002', 'CHEM-003'],
            'Item Description': ['Industrial liquid solvent', 'Motor oil 5W30', 'Cleaning solution']
        })

        fallback_dims = dm.generate_default_dimensions(df_items)

        # Should generate fallback for all items
        assert len(fallback_dims) == 3
        assert all(d.units_per_skid == 4 for d in fallback_dims.values())

    def test_fallback_dimensions_boxes(self):
        """Test fallback dimensions for boxed items"""
        dm = DimensionManager()

        df_items = pd.DataFrame({
            'Item No.': ['BOX001', 'CARTON-A', 'CASE-X'],
            'Item Description': ['Cardboard box set', 'Carton of parts', 'Case of units']
        })

        fallback_dims = dm.generate_default_dimensions(df_items)

        assert len(fallback_dims) == 3
        assert all(d.units_per_skid == 50 for d in fallback_dims.values())

    def test_fallback_dimensions_small_parts(self):
        """Test fallback dimensions for small parts"""
        dm = DimensionManager()

        df_items = pd.DataFrame({
            'Item No.': ['SCREW-01', 'BOLT-A', 'NUT-X'],
            'Item Description': ['Steel screw 1in', 'Hex bolt', 'Locking nut']
        })

        fallback_dims = dm.generate_default_dimensions(df_items)

        assert len(fallback_dims) == 3
        # Small parts have high units per skid
        assert all(d.units_per_skid >= 100 for d in fallback_dims.values())

    def test_get_dimensions_with_fallback_from_cache(self):
        """Test getting dimensions when already cached"""
        dm = DimensionManager()

        # Add cached dimensions
        dm.dimensions_cache['CACHED001'] = ItemDimensions(
            length_cm=40, width_cm=30, height_cm=30,
            weight_kg=10, units_per_skid=50
        )

        # Should return cached version
        dims = dm.get_dimensions_with_fallback('CACHED001')
        assert dims.units_per_skid == 50

    def test_get_dimensions_with_fallback_pattern(self):
        """Test getting dimensions with pattern-based fallback"""
        dm = DimensionManager()

        df_items = pd.DataFrame({
            'Item No.': ['LIQUID-NO-DATA'],
            'Item Description': ['Chemical liquid']
        })

        # Not in cache, should generate fallback
        dims = dm.get_dimensions_with_fallback('LIQUID-NO-DATA', df_items)
        assert dims is not None
        assert dims.units_per_skid == 4  # Liquid pattern

    def test_get_dimensions_with_fallback_ultimate(self):
        """Test ultimate fallback when no pattern matches"""
        dm = DimensionManager()

        df_items = pd.DataFrame({
            'Item No.': ['UNKNOWN-ITEM'],
            'Item Description': ['Unknown item description']
        })

        # No pattern match, should use ultimate fallback (1 unit/skid)
        dims = dm.get_dimensions_with_fallback('UNKNOWN-ITEM', df_items)
        assert dims is not None
        assert dims.units_per_skid == 1  # Ultimate fallback

    def test_fallback_statistics(self):
        """Test fallback statistics reporting"""
        dm = DimensionManager()

        # Add some dimensions
        dm.dimensions_cache['ITEM001'] = ItemDimensions(
            length_cm=50, width_cm=40, height_cm=30,
            weight_kg=5, units_per_skid=10
        )

        stats = dm.get_fallback_statistics()
        assert 'total' in stats
        assert stats['total'] == 1

    def test_warehouse_capacity_default_fallback(self):
        """Test warehouse capacity uses defaults when file missing"""
        from src.spatial_optimization import WarehouseCapacityManager

        dm = DimensionManager()
        manager = WarehouseCapacityManager(dm)

        # Load capacities (file doesn't exist, should use defaults)
        capacities = manager.load_warehouse_capacities()

        # Should have default capacities for standard regions
        assert 'CGY' in capacities
        assert 'TOR' in capacities
        assert 'EDM' in capacities

        # All should have 100 skids (default)
        assert all(c.total_skids == 100 for c in capacities.values())

    def test_space_calculation_with_fallback(self):
        """Test space calculation uses fallback dimensions"""
        from src.spatial_optimization import WarehouseCapacityManager

        dm = DimensionManager()
        manager = WarehouseCapacityManager(dm)

        df_items = pd.DataFrame({
            'Item No.': ['UNKNOWN-ITEM'],
            'Item Description': ['Unknown item']
        })

        # Should use fallback dimensions
        skids = manager.calculate_space_required('UNKNOWN-ITEM', 100, df_items)

        # Fallback is 1 unit/skid, so 100 units = 100 skids
        assert skids == 100.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
