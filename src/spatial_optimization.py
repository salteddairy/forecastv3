"""
Spatial Constraints & Vendor Optimization Module

Implements warehouse capacity management and shipping efficiency optimization:
- Skid space calculations per warehouse location
- Item dimension tracking (from SAP or manual)
- Space-constrained order optimization
- Vendor grouping for shipping efficiency

PERFORMANCE OPTIMIZATIONS:
- Persistent dimension caching to disk
- Pre-computed pattern matching
- LRU cache for dimension lookups
"""
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from src.config import DataConfig
from functools import lru_cache
import pickle
import json

logger = logging.getLogger(__name__)


@dataclass
class ItemDimensions:
    """Physical dimensions of an item"""
    length_cm: float  # Length in centimeters
    width_cm: float   # Width in centimeters
    height_cm: float  # Height in centimeters
    weight_kg: float  # Weight in kilograms
    units_per_skid: int = 1  # How many units fit on a standard skid
    stacking_allowed: bool = True  # Can skids be stacked


@dataclass
class SkidSpace:
    """Warehouse skid space capacity"""
    location: str  # Warehouse location code
    total_skids: int  # Total skid spaces available
    used_skids: int = 0  # Currently used
    skid_length_cm: float = 120.0  # Standard skid length (cm)
    skid_width_cm: float = 100.0   # Standard skid width (cm)
    max_height_cm: float = 150.0   # Max stacking height (cm)

    @property
    def available_skids(self) -> int:
        return max(0, self.total_skids - self.used_skids)

    @property
    def utilization_pct(self) -> float:
        if self.total_skids == 0:
            return 0.0
        return (self.used_skids / self.total_skids) * 100


@dataclass
class VendorGroupOrder:
    """Optimized order grouped by vendor"""
    vendor_code: str
    vendor_name: str
    items: List[Dict[str, Any]]  # List of items to order from this vendor
    total_units: int
    total_skids_required: float
    estimated_shipping_cost: float
    space_constraint_met: bool = True
    space_shortage_skids: float = 0.0


class DimensionManager:
    """Manages item dimension data from SAP or manual entry"""

    # Standard conversion factors
    INCH_TO_CM = 2.54
    LB_TO_KG = 0.453592

    def __init__(self, cache_dir: Path = None):
        self.dimensions_cache: Dict[str, ItemDimensions] = {}
        self._cache_dir = cache_dir or (DataConfig.DATA_DIR.parent / 'cache')
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Pre-compute pattern matching cache for descriptions
        self._pattern_cache: Dict[str, Optional[str]] = {}

        # Try to load from persistent cache
        self._load_from_cache()

    def load_from_sap(self, df_items: pd.DataFrame) -> Dict[str, ItemDimensions]:
        """
        Load item dimensions from SAP B1 data

        Expected columns in df_items:
        - Item No.: Item code
        - Length: Length in specified unit
        - Width: Width in specified unit
        - Height: Height in specified unit
        - Weight: Weight in specified unit
        - UoM: Unit of measure for dimensions (CM, INCH, etc.)
        """
        dimensions = {}

        for _, row in df_items.iterrows():
            item_code = row.get('Item No.')

            if pd.isna(item_code):
                continue

            # Try to extract dimensions from SAP data
            try:
                # Check if dimension data exists
                has_dimensions = all(col in df_items.columns for col in ['Length', 'Width', 'Height'])

                if has_dimensions:
                    length = self._parse_dimension(row.get('Length', 0))
                    width = self._parse_dimension(row.get('Width', 0))
                    height = self._parse_dimension(row.get('Height', 0))
                    weight = self._parse_dimension(row.get('Weight', 0))

                    # Skip if all dimensions are zero (no data available)
                    if length == 0 and width == 0 and height == 0:
                        continue

                    # Estimate units per skid based on dimensions
                    units_per_skid = self._estimate_units_per_skid(length, width, height)

                    dimensions[item_code] = ItemDimensions(
                        length_cm=length,
                        width_cm=width,
                        height_cm=height,
                        weight_kg=weight,
                        units_per_skid=units_per_skid,
                        stacking_allowed=True
                    )

            except Exception as e:
                logger.debug(f"Could not parse dimensions for {item_code}: {e}")
                continue

        logger.info(f"Loaded dimensions for {len(dimensions)} items from SAP")
        self.dimensions_cache.update(dimensions)
        return dimensions

    def load_manual_dimensions(self, filepath: Path) -> Dict[str, ItemDimensions]:
        """
        Load manually entered dimensions from CSV/TSV file

        Expected columns:
        - Item No.: Item code
        - Length_cm: Length in cm
        - Width_cm: Width in cm
        - Height_cm: Height in cm
        - Weight_kg: Weight in kg
        - Units_Per_Skid: How many fit on a skid (optional)
        - Stacking_Allowed: Can skids be stacked (optional, default: True)
        """
        try:
            df = pd.read_csv(filepath, sep='\t')

            dimensions = {}
            for _, row in df.iterrows():
                item_code = row.get('Item No.')

                if pd.isna(item_code):
                    continue

                dimensions[item_code] = ItemDimensions(
                    length_cm=float(row.get('Length_cm', 0)),
                    width_cm=float(row.get('Width_cm', 0)),
                    height_cm=float(row.get('Height_cm', 0)),
                    weight_kg=float(row.get('Weight_kg', 0)),
                    units_per_skid=int(row.get('Units_Per_Skid', 1)),
                    stacking_allowed=str(row.get('Stacking_Allowed', 'True')).upper() == 'TRUE'
                )

            logger.info(f"Loaded {len(dimensions)} manual dimension entries")
            self.dimensions_cache.update(dimensions)
            return dimensions

        except Exception as e:
            logger.error(f"Error loading manual dimensions: {e}")
            return {}

    def get_dimensions(self, item_code: str) -> Optional[ItemDimensions]:
        """Get dimensions for an item, return None if not available"""
        return self.dimensions_cache.get(item_code)

    def auto_populate_from_description(self, df_items: pd.DataFrame) -> Dict[str, ItemDimensions]:
        """
        Auto-populate dimensions based on item description keywords

        Rules:
        - "pail" in description: 36 pails per pallet
        - "drum" in description: 4 drums per pallet
        - "tote" in description: 1 tote per pallet

        Standard pallet dimensions: 120x100 cm
        """
        auto_dimensions = {}

        for _, row in df_items.iterrows():
            item_code = row.get('Item No.')
            description = str(row.get('Item Description', '')).lower()

            if pd.isna(item_code):
                continue

            # Skip if already has dimensions
            if item_code in self.dimensions_cache:
                continue

            # Auto-populate based on description
            units_per_skid = None
            length_cm = None
            width_cm = None
            height_cm = None
            weight_kg = 10.0  # Default weight

            if 'pail' in description:
                units_per_skid = 36
                # Standard pail: ~20L pail, approximate dimensions
                length_cm = 30
                width_cm = 30
                height_cm = 40
                weight_kg = 20.0  # Approx 20kg when full
            elif 'drum' in description:
                units_per_skid = 4
                # Standard 55-gallon drum
                length_cm = 60
                width_cm = 60
                height_cm = 90
                weight_kg = 200.0  # Approx 200kg when full
            elif 'tote' in description:
                units_per_skid = 1
                # Standard tote/bin
                length_cm = 120
                width_cm = 100
                height_cm = 100
                weight_kg = 500.0  # Large tote

            if units_per_skid is not None:
                auto_dimensions[item_code] = ItemDimensions(
                    length_cm=length_cm or 30,
                    width_cm=width_cm or 30,
                    height_cm=height_cm or 40,
                    weight_kg=weight_kg,
                    units_per_skid=units_per_skid,
                    stacking_allowed=True
                )

        logger.info(f"Auto-populated dimensions for {len(auto_dimensions)} items based on description")
        self.dimensions_cache.update(auto_dimensions)
        return auto_dimensions

    def generate_default_dimensions(self, df_items: pd.DataFrame) -> Dict[str, ItemDimensions]:
        """
        Generate default/fallback dimensions for items without dimension data

        Uses heuristics based on item characteristics:
        - Item code patterns
        - Description keywords
        - Default conservative estimates

        Returns:
        --------
        Dict[str, ItemDimensions]
            Default dimensions for items that don't have dimension data
        """
        default_dimensions = {}

        for _, row in df_items.iterrows():
            item_code = row.get('Item No.')

            if pd.isna(item_code):
                continue

            # Skip if already has dimensions
            if item_code in self.dimensions_cache:
                continue

            description = str(row.get('Item Description', '')).lower()
            item_code_str = str(item_code).upper()

            # Try to categorize and assign defaults
            dims = self._get_fallback_dimensions(item_code_str, description)

            if dims:
                default_dimensions[item_code] = dims

        if default_dimensions:
            logger.warning(f"Using DEFAULT/FALLBACK dimensions for {len(default_dimensions)} items "
                         f"(no SAP data and no keyword match)")
            self.dimensions_cache.update(default_dimensions)

        return default_dimensions

    def _get_fallback_dimensions(self, item_code: str, description: str) -> Optional[ItemDimensions]:
        """
        Get fallback dimensions based on item code and description patterns

        Returns:
        --------
        ItemDimensions or None
        """
        # Pattern-based fallback rules
        fallback_rules = [
            # Liquids and bulk materials
            {
                'patterns': ['liquid', 'oil', 'fluid', 'solution', 'chemical'],
                'units_per_skid': 4,
                'length_cm': 40,
                'width_cm': 40,
                'height_cm': 50,
                'weight_kg': 50,
                'reason': 'Liquid/chemical'
            },
            # Boxes/cartons
            {
                'patterns': ['box', 'carton', 'case', 'pack'],
                'units_per_skid': 50,
                'length_cm': 40,
                'width_cm': 30,
                'height_cm': 30,
                'weight_kg': 15,
                'reason': 'Box/carton'
            },
            # Bags
            {
                'patterns': ['bag', 'sack', 'pouch'],
                'units_per_skid': 25,
                'length_cm': 50,
                'width_cm': 40,
                'height_cm': 30,
                'weight_kg': 25,
                'reason': 'Bag'
            },
            # Sheets/pads
            {
                'patterns': ['sheet', 'pad', 'wipe', 'cloth'],
                'units_per_skid': 100,
                'length_cm': 30,
                'width_cm': 20,
                'height_cm': 20,
                'weight_kg': 5,
                'reason': 'Sheet/pad'
            },
            # Small parts/fasteners
            {
                'patterns': ['screw', 'bolt', 'nut', 'nail', 'fastener', 'clip'],
                'units_per_skid': 200,
                'length_cm': 20,
                'width_cm': 20,
                'height_cm': 20,
                'weight_kg': 10,
                'reason': 'Small parts'
            },
            # Tools/equipment
            {
                'patterns': ['tool', 'wrench', 'hammer', 'plier', 'equipment'],
                'units_per_skid': 10,
                'length_cm': 60,
                'width_cm': 40,
                'height_cm': 40,
                'weight_kg': 30,
                'reason': 'Tool'
            },
        ]

        # Check patterns against description and item code
        for rule in fallback_rules:
            for pattern in rule['patterns']:
                if pattern in description or pattern in item_code:
                    logger.debug(f"Item {item_code}: Using fallback rule '{rule['reason']}'")
                    return ItemDimensions(
                        length_cm=rule['length_cm'],
                        width_cm=rule['width_cm'],
                        height_cm=rule['height_cm'],
                        weight_kg=rule['weight_kg'],
                        units_per_skid=rule['units_per_skid'],
                        stacking_allowed=True
                    )

        # Ultra-conservative default if no patterns match
        # Assume 1 unit per skid, standard skid size
        logger.debug(f"Item {item_code}: Using ultra-conservative default (1 unit/skid)")
        return ItemDimensions(
            length_cm=60.0,
            width_cm=40.0,
            height_cm=40.0,
            weight_kg=20.0,
            units_per_skid=1,
            stacking_allowed=True
        )

    def get_dimensions_with_fallback(self, item_code: str, df_items: pd.DataFrame = None) -> ItemDimensions:
        """
        Get dimensions for an item with automatic fallback

        Parameters:
        -----------
        item_code : str
            Item code to look up
        df_items : pd.DataFrame, optional
            Full items dataframe for fallback generation

        Returns:
        --------
        ItemDimensions
            Dimensions (from cache, SAP, manual, auto-populated, or fallback)
        """
        # Check cache first
        if item_code in self.dimensions_cache:
            return self.dimensions_cache[item_code]

        # Try to generate fallback if items data provided
        if df_items is not None:
            self.generate_default_dimensions(df_items)

            # Check cache again
            if item_code in self.dimensions_cache:
                logger.warning(f"Item {item_code}: Using FALLBACK dimensions (no dimension data available)")
                return self.dimensions_cache[item_code]

        # Ultimate fallback - return conservative default
        logger.warning(f"Item {item_code}: Using ULTIMATE FALLBACK (1 unit/skid, no specific data)")
        return ItemDimensions(
            length_cm=60.0,
            width_cm=40.0,
            height_cm=40.0,
            weight_kg=20.0,
            units_per_skid=1,
            stacking_allowed=True
        )

    def get_fallback_statistics(self) -> Dict[str, int]:
        """
        Get statistics on dimension sources

        Returns:
        --------
        Dict with counts by source type
        """
        stats = {
            'sap_data': 0,
            'manual_entry': 0,
            'auto_populated': 0,
            'fallback_pattern': 0,
            'fallback_default': 0
        }

        # Count sources (would need to track source with each dimension)
        # For now, just return total count
        stats['total'] = len(self.dimensions_cache)

        return stats

    def _parse_dimension(self, value: Any) -> float:
        """Parse dimension value, handling various formats"""
        if pd.isna(value):
            return 0.0

        try:
            # If it's a string, remove non-numeric characters (except decimal point and minus)
            if isinstance(value, str):
                value = float(value)
            else:
                value = float(value)

            return max(0, value)  # Ensure non-negative

        except (ValueError, TypeError):
            return 0.0

    def _estimate_units_per_skid(self, length_cm: float, width_cm: float,
                                height_cm: float) -> int:
        """
        Estimate how many units fit on a standard skid (120x100 cm)

        Formula: floor(skid_length / item_length) * floor(skid_width / item_width)
        Also considers height constraints
        """
        if length_cm == 0 or width_cm == 0 or height_cm == 0:
            return 1

        # Standard skid dimensions
        skid_length = 120.0  # cm
        skid_width = 100.0   # cm
        max_height = 150.0   # cm

        # Calculate how many fit on base layer
        units_per_layer = int((skid_length / length_cm) * (skid_width / width_cm))

        # Calculate how many layers can be stacked
        if height_cm > 0:
            max_layers = int(max_height / height_cm)
            if max_layers < 1:
                max_layers = 1
        else:
            max_layers = 1

        # Total units per skid
        total_units = max(1, units_per_layer * max_layers)

        return total_units

    def _load_from_cache(self):
        """Load dimensions from persistent cache file"""
        cache_file = self._cache_dir / 'dimensions_cache.pkl'

        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                # Load dimensions cache
                self.dimensions_cache = cached_data.get('dimensions', {})

                # Load pattern cache
                self._pattern_cache = cached_data.get('patterns', {})

                logger.info(f"Loaded {len(self.dimensions_cache)} dimensions from cache")
            except Exception as e:
                logger.warning(f"Failed to load dimension cache: {e}")
                self.dimensions_cache = {}
                self._pattern_cache = {}

    def _save_to_cache(self):
        """Save dimensions to persistent cache file"""
        cache_file = self._cache_dir / 'dimensions_cache.pkl'

        try:
            cached_data = {
                'dimensions': self.dimensions_cache,
                'patterns': self._pattern_cache,
                'timestamp': pd.Timestamp.now().isoformat()
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(cached_data, f)

            logger.debug(f"Saved {len(self.dimensions_cache)} dimensions to cache")
        except Exception as e:
            logger.warning(f"Failed to save dimension cache: {e}")

    def invalidate_cache(self):
        """Clear the persistent cache file"""
        cache_file = self._cache_dir / 'dimensions_cache.pkl'

        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.info("Dimension cache cleared")
            except Exception as e:
                logger.warning(f"Failed to clear cache: {e}")

    @lru_cache(maxsize=1000)
    def _match_pattern_cached(self, description_lower: str, item_code_upper: str) -> Optional[str]:
        """
        Cached pattern matching for descriptions

        Returns the matched pattern name or None
        """
        # Auto-population patterns (highest priority)
        if 'pail' in description_lower:
            return 'auto_pail'
        elif 'drum' in description_lower:
            return 'auto_drum'
        elif 'tote' in description_lower:
            return 'auto_tote'

        # Fallback patterns
        patterns = {
            'liquid': 'liquid',
            'oil': 'liquid',
            'fluid': 'liquid',
            'solution': 'liquid',
            'chemical': 'liquid',
            'box': 'box',
            'carton': 'box',
            'case': 'box',
            'pack': 'box',
            'bag': 'bag',
            'sack': 'bag',
            'pouch': 'bag',
            'sheet': 'sheet',
            'pad': 'sheet',
            'wipe': 'sheet',
            'cloth': 'sheet',
            'screw': 'fastener',
            'bolt': 'fastener',
            'nut': 'fastener',
            'nail': 'fastener',
            'fastener': 'fastener',
            'clip': 'fastener',
            'tool': 'tool',
            'wrench': 'tool',
            'hammer': 'tool',
            'plier': 'tool',
            'equipment': 'tool',
        }

        for keyword, pattern in patterns.items():
            if keyword in description_lower or keyword in item_code_upper:
                return pattern

        return None

    def get_dimensions_optimized(self, item_code: str, description: str = None) -> ItemDimensions:
        """
        Optimized dimension lookup with caching

        Parameters:
        -----------
        item_code : str
            Item code to look up
        description : str, optional
            Item description for pattern matching

        Returns:
        --------
        ItemDimensions
            Cached or newly computed dimensions
        """
        # Check cache first (fastest)
        if item_code in self.dimensions_cache:
            return self.dimensions_cache[item_code]

        # No cached dimensions, need to compute
        if description is None:
            # Return conservative default if no description available
            return ItemDimensions(
                length_cm=60.0,
                width_cm=40.0,
                height_cm=40.0,
                weight_kg=20.0,
                units_per_skid=1,
                stacking_allowed=True
            )

        # Use cached pattern matching
        description_lower = str(description).lower()
        item_code_upper = str(item_code).upper()

        pattern = self._match_pattern_cached(description_lower, item_code_upper)

        # Generate dimensions based on pattern
        if pattern == 'auto_pail':
            dims = ItemDimensions(
                length_cm=30, width_cm=30, height_cm=40,
                weight_kg=20.0, units_per_skid=36, stacking_allowed=True
            )
        elif pattern == 'auto_drum':
            dims = ItemDimensions(
                length_cm=60, width_cm=60, height_cm=90,
                weight_kg=200.0, units_per_skid=4, stacking_allowed=True
            )
        elif pattern == 'auto_tote':
            dims = ItemDimensions(
                length_cm=120, width_cm=100, height_cm=100,
                weight_kg=500.0, units_per_skid=1, stacking_allowed=True
            )
        elif pattern == 'liquid':
            dims = ItemDimensions(
                length_cm=40, width_cm=40, height_cm=50,
                weight_kg=50, units_per_skid=4, stacking_allowed=True
            )
        elif pattern == 'box':
            dims = ItemDimensions(
                length_cm=40, width_cm=30, height_cm=30,
                weight_kg=15, units_per_skid=50, stacking_allowed=True
            )
        elif pattern == 'bag':
            dims = ItemDimensions(
                length_cm=50, width_cm=40, height_cm=30,
                weight_kg=25, units_per_skid=25, stacking_allowed=True
            )
        elif pattern == 'sheet':
            dims = ItemDimensions(
                length_cm=30, width_cm=20, height_cm=20,
                weight_kg=5, units_per_skid=100, stacking_allowed=True
            )
        elif pattern == 'fastener':
            dims = ItemDimensions(
                length_cm=20, width_cm=20, height_cm=20,
                weight_kg=10, units_per_skid=200, stacking_allowed=True
            )
        elif pattern == 'tool':
            dims = ItemDimensions(
                length_cm=60, width_cm=40, height_cm=40,
                weight_kg=30, units_per_skid=10, stacking_allowed=True
            )
        else:
            # Ultimate fallback
            dims = ItemDimensions(
                length_cm=60.0, width_cm=40.0, height_cm=40.0,
                weight_kg=20.0, units_per_skid=1, stacking_allowed=True
            )

        # Cache the result
        self.dimensions_cache[item_code] = dims

        # Periodically save to disk (every 100 new items)
        if len(self.dimensions_cache) % 100 == 0:
            self._save_to_cache()

        return dims


class WarehouseCapacityManager:
    """Manages warehouse capacity and space constraints"""

    def __init__(self, dimension_manager: DimensionManager):
        self.dimension_manager = dimension_manager
        self.location_capacities: Dict[str, SkidSpace] = {}
        self.current_stock: Dict[str, Dict[str, int]] = {}  # location -> item_code -> qty

    def load_warehouse_capacities(self, filepath: Path = None) -> Dict[str, SkidSpace]:
        """
        Load warehouse skid space capacities from file

        Expected columns:
        - Location: Warehouse location code
        - Total_Skids: Total skid spaces available
        - Used_Skids: Currently used (optional)
        - Skid_Length_cm: Skid length (optional, default 120)
        - Skid_Width_cm: Skid width (optional, default 100)
        - Max_Height_cm: Max stacking height (optional, default 150)
        """
        if filepath is None:
            filepath = DataConfig.DATA_DIR / 'warehouse_capacities.tsv'

        capacities = {}

        try:
            if filepath.exists():
                df = pd.read_csv(filepath, sep='\t')

                for _, row in df.iterrows():
                    location = row.get('Location')

                    if pd.isna(location):
                        continue

                    capacities[location] = SkidSpace(
                        location=str(location),
                        total_skids=int(row.get('Total_Skids', 100)),
                        used_skids=int(row.get('Used_Skids', 0)),
                        skid_length_cm=float(row.get('Skid_Length_cm', 120.0)),
                        skid_width_cm=float(row.get('Skid_Width_cm', 100.0)),
                        max_height_cm=float(row.get('Max_Height_cm', 150.0))
                    )

                logger.info(f"Loaded warehouse capacities for {len(capacities)} locations")
            else:
                # Use default capacities if file doesn't exist
                logger.warning(f"Warehouse capacity file not found: {filepath}")
                logger.info("Using default warehouse capacities")

                # Create default capacity for each region
                for region in ['CGY', 'TOR', 'EDM', 'VAN', 'WIN']:
                    capacities[region] = SkidSpace(
                        location=region,
                        total_skids=100,  # Default capacity
                        used_skids=0
                    )

        except Exception as e:
            logger.error(f"Error loading warehouse capacities: {e}")
            # Return default capacities
            for region in ['CGY', 'TOR', 'EDM', 'VAN', 'WIN']:
                capacities[region] = SkidSpace(
                    location=region,
                    total_skids=100,
                    used_skids=0
                )

        self.location_capacities = capacities
        return capacities

    def load_current_stock(self, df_items: pd.DataFrame):
        """
        Load current stock levels by location

        Parameters:
        -----------
        df_items : pd.DataFrame
            Items data with current stock and location/warehouse
        """
        self.current_stock = {}

        for _, row in df_items.iterrows():
            item_code = row.get('Item No.')

            if pd.isna(item_code):
                continue

            # Extract location from item code or warehouse column
            location = self._extract_location(row)

            if location not in self.current_stock:
                self.current_stock[location] = {}

            # Get current stock in Sales UOM
            current_stock = row.get('CurrentStock_SalesUOM', 0)
            if pd.isna(current_stock):
                current_stock = 0

            self.current_stock[location][item_code] = int(current_stock)

        logger.info(f"Loaded current stock for {len(self.current_stock)} locations")

    def _extract_location(self, row: pd.Series) -> str:
        """
        Extract location code from item row

        Tries multiple sources:
        1. 'Region' column
        2. 'Warehouse' column
        3. Item code suffix (e.g., XXX-CGY, TOR-XXX)

        Returns:
        --------
        str
            Location code (CGY, TOR, EDM, VAN, WIN, etc.)
        """
        # Try Region column first
        if 'Region' in row and pd.notna(row['Region']):
            return str(row['Region'])

        # Try Warehouse column
        if 'Warehouse' in row and pd.notna(row['Warehouse']):
            return str(row['Warehouse'])

        # Try to extract from item code
        item_code = str(row.get('Item No.', ''))

        # Check common suffixes
        for loc in ['CGY', 'TOR', 'EDM', 'VAN', 'WIN', 'MON', 'OTT']:
            if item_code.endswith(f'-{loc}'):
                return loc
            if item_code.startswith(f'{loc}-'):
                return loc

        # Default: Use a general warehouse code
        return 'GENERIC'

    def calculate_space_required(self, item_code: str, quantity: int,
                               df_items: pd.DataFrame = None) -> float:
        """
        Calculate skid spaces required for a quantity of items

        Uses fallback system if no dimension data available

        Parameters:
        -----------
        item_code : str
            Item to calculate space for
        quantity : int
            Quantity of items
        df_items : pd.DataFrame, optional
            Items dataframe for fallback dimension generation

        Returns:
        --------
        float
            Number of skids required (can be fractional for partial skids)
        """
        # Use fallback system to get dimensions
        dimensions = self.dimension_manager.get_dimensions_with_fallback(
            item_code, df_items
        )

        if dimensions.units_per_skid > 0:
            skids_required = quantity / dimensions.units_per_skid
        else:
            # Fallback to 1 unit per skid
            skids_required = float(quantity)

        return skids_required

    def calculate_current_space_usage(self, location: str) -> float:
        """
        Calculate current skid usage for a location

        Returns:
        --------
        float
            Current skids used in this location
        """
        if location not in self.current_stock:
            return 0.0

        total_skids = 0.0

        for item_code, quantity in self.current_stock[location].items():
            skids = self.calculate_space_required(item_code, quantity)
            total_skids += skids

        return total_skids

    def check_capacity_constraint(self, location: str, additional_items: Dict[str, int]) -> Tuple[bool, float]:
        """
        Check if location has capacity for additional items

        Parameters:
        -----------
        location : str
            Warehouse location code
        additional_items : Dict[str, int]
            Dictionary of item_code -> quantity to add

        Returns:
        --------
        Tuple[bool, float]
            (has_capacity, shortage_skids)
        """
        if location not in self.location_capacities:
            logger.warning(f"Unknown location: {location}, assuming unlimited capacity")
            return True, 0.0

        capacity = self.location_capacities[location]

        # Calculate current space usage
        current_usage = self.calculate_current_space_usage(location)

        # Calculate space required for additional items
        additional_space = 0.0
        for item_code, quantity in additional_items.items():
            additional_space += self.calculate_space_required(item_code, quantity)

        total_required = current_usage + additional_space

        has_capacity = total_required <= capacity.total_skids
        shortage = max(0, total_required - capacity.total_skids)

        return has_capacity, shortage

    def get_location_capacity_status(self) -> pd.DataFrame:
        """
        Get capacity status for all locations

        Returns:
        --------
        pd.DataFrame
            Capacity status by location
        """
        status_data = []

        for location, capacity in self.location_capacities.items():
            current_usage = self.calculate_current_space_usage(location)

            status_data.append({
                'Location': location,
                'Total_Skids': capacity.total_skids,
                'Current_Usage_Skids': round(current_usage, 2),
                'Available_Skids': round(capacity.available_skids, 2),
                'Utilization_Pct': round((current_usage / capacity.total_skids * 100) if capacity.total_skids > 0 else 0, 2)
            })

        return pd.DataFrame(status_data)


class VendorGroupOptimizer:
    """Optimizes orders by vendor for shipping efficiency"""

    def __init__(self, df_items: pd.DataFrame):
        self.df_items = df_items

    def group_items_by_vendor(self, items_to_order: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Group items to order by their vendor

        Parameters:
        -----------
        items_to_order : pd.DataFrame
            Items that need to be ordered with recommended quantities
            Expected columns: Item No., Vendor, Recommended_Order_Qty

        Returns:
        --------
        Dict[str, pd.DataFrame]
            Dictionary mapping vendor_code to DataFrame of items
        """
        vendor_groups = {}

        # Group by vendor
        for vendor_code, group in items_to_order.groupby('TargetVendor'):
            vendor_groups[vendor_code] = group.copy()

        logger.info(f"Grouped {len(items_to_order)} items across {len(vendor_groups)} vendors")
        return vendor_groups

    def calculate_vendor_group_metrics(self, vendor_group: pd.DataFrame,
                                      capacity_manager: WarehouseCapacityManager) -> Dict[str, Any]:
        """
        Calculate metrics for a vendor group

        Returns:
        --------
        Dict with:
        - total_units: Total units to order
        - total_skids: Total skids required
        - estimated_weight_kg: Total weight
        - estimated_shipping_cost: Estimated shipping cost
        """
        total_units = 0
        total_skids = 0.0
        total_weight = 0.0

        for _, row in vendor_group.iterrows():
            item_code = row.get('Item No.')
            order_qty = row.get('Recommended_Order_Qty', 0)

            if pd.isna(order_qty):
                order_qty = 0

            total_units += int(order_qty)

            # Calculate space requirements
            skids = capacity_manager.calculate_space_required(item_code, int(order_qty))
            total_skids += skids

            # Add weight
            dimensions = capacity_manager.dimension_manager.get_dimensions(item_code)
            if dimensions:
                total_weight += dimensions.weight_kg * int(order_qty)

        # Estimate shipping cost (simple model: $50 base + $10 per skid + $0.01 per kg)
        estimated_shipping_cost = 50.0 + (total_skids * 10.0) + (total_weight * 0.01)

        return {
            'total_units': total_units,
            'total_skids': round(total_skids, 2),
            'total_weight_kg': round(total_weight, 2),
            'estimated_shipping_cost': round(estimated_shipping_cost, 2)
        }


class SpatialOrderOptimizer:
    """Optimizes orders considering spatial constraints and vendor grouping"""

    def __init__(self, df_items: pd.DataFrame, df_stockout: pd.DataFrame):
        self.df_items = df_items
        self.df_stockout = df_stockout
        self.dimension_manager = DimensionManager()
        self.capacity_manager = WarehouseCapacityManager(self.dimension_manager)
        self.vendor_optimizer = VendorGroupOptimizer(df_items)

        # Load data
        self._initialize()

    def _initialize(self):
        """Initialize dimension and capacity data with fallback system"""
        # Load dimensions from SAP
        self.dimension_manager.load_from_sap(self.df_items)

        # Auto-populate dimensions from item descriptions (pail, drum, tote)
        self.dimension_manager.auto_populate_from_description(self.df_items)

        # Try to load manual dimensions
        manual_dim_file = DataConfig.DATA_DIR / 'manual_dimensions.tsv'
        if manual_dim_file.exists():
            self.dimension_manager.load_manual_dimensions(manual_dim_file)

        # Generate fallback dimensions for remaining items (pattern-based heuristics)
        fallback_dims = self.dimension_manager.generate_default_dimensions(self.df_items)
        if fallback_dims:
            logger.info(f"Generated fallback dimensions for {len(fallback_dims)} items using pattern heuristics")

        # Load warehouse capacities (with defaults if no file)
        self.capacity_manager.load_warehouse_capacities()

        # Load current stock
        self.capacity_manager.load_current_stock(self.df_items)

        # Log dimension coverage
        total_items = len(self.df_items)
        items_with_dims = len(self.dimension_manager.dimensions_cache)
        coverage_pct = (items_with_dims / total_items * 100) if total_items > 0 else 0
        logger.info(f"Dimension coverage: {items_with_dims}/{total_items} ({coverage_pct:.1f}%)")

    def optimize_orders_with_constraints(self, max_capacity_utilization: float = 0.90) -> pd.DataFrame:
        """
        Optimize orders considering:
        1. Spatial constraints (don't exceed warehouse capacity)
        2. Vendor grouping (consolidate orders by vendor)

        Parameters:
        -----------
        max_capacity_utilization : float
            Maximum warehouse capacity to use (0.0-1.0)
            Default 0.90 means keep 10% buffer

        Returns:
        --------
        pd.DataFrame
            Optimized order recommendations with vendor grouping and space info
        """
        logger.info("Starting spatial order optimization...")

        # Start with items that need ordering (shortage items)
        items_to_order = self.df_stockout[self.df_stockout['will_stockout'] == True].copy()

        if len(items_to_order) == 0:
            logger.warning("No items need ordering")
            return pd.DataFrame()

        # Add recommended order quantity (shortage + safety stock buffer)
        items_to_order['Recommended_Order_Qty'] = items_to_order['shortage_qty'] * 1.2

        # Group by vendor
        vendor_groups = self.vendor_optimizer.group_items_by_vendor(items_to_order)

        # Optimize each vendor group considering spatial constraints
        optimized_orders = []

        for vendor_code, vendor_items in vendor_groups.items():
            vendor_name = vendor_items['TargetVendorName'].iloc[0] if 'TargetVendorName' in vendor_items.columns else vendor_code

            # Calculate space requirements for this vendor group
            total_skids = 0.0
            for _, row in vendor_items.iterrows():
                item_code = row['Item No.']
                qty = int(row['Recommended_Order_Qty'])
                skids = self.capacity_manager.calculate_space_required(item_code, qty)
                total_skids += skids

            # Check if vendor items are in multiple locations
            location_summary = vendor_items.groupby('Region').agg({
                'Item No.': 'count',
                'Recommended_Order_Qty': 'sum'
            }).rename(columns={'Item No.': 'item_count', 'Recommended_Order_Qty': 'total_qty'})

            # Check capacity for each location
            all_constraints_met = True
            constraint_details = []

            for location, location_data in location_summary.iterrows():
                location_items = vendor_items[vendor_items['Region'] == location]

                # Build items dict for this location
                location_order_dict = {
                    row['Item No.']: int(row['Recommended_Order_Qty'])
                    for _, row in location_items.iterrows()
                }

                has_capacity, shortage = self.capacity_manager.check_capacity_constraint(
                    location, location_order_dict
                )

                if not has_capacity:
                    all_constraints_met = False
                    constraint_details.append(f"{location}: {shortage:.1f} skids shortage")
                else:
                    constraint_details.append(f"{location}: OK")

            # Calculate vendor metrics
            metrics = self.vendor_optimizer.calculate_vendor_group_metrics(
                vendor_items, self.capacity_manager
            )

            optimized_orders.append({
                'Vendor': vendor_code,
                'Vendor_Name': vendor_name,
                'Item_Count': len(vendor_items),
                'Total_Units': metrics['total_units'],
                'Total_Skids_Required': metrics['total_skids'],
                'Estimated_Shipping_Cost': metrics['estimated_shipping_cost'],
                'Space_Constraint_Met': all_constraints_met,
                'Constraint_Details': '; '.join(constraint_details),
                'Items': vendor_items['Item No.'].tolist()
            })

        result_df = pd.DataFrame(optimized_orders)

        # Sort by shipping cost efficiency
        result_df = result_df.sort_values('Estimated_Shipping_Cost', ascending=True)

        logger.info(f"Optimization complete: {len(result_df)} vendor groups")

        return result_df

    def generate_order_recommendations(self, optimized_orders: pd.DataFrame) -> pd.DataFrame:
        """
        Generate detailed order recommendations with line items

        Returns:
        --------
        pd.DataFrame with:
        - Vendor, Vendor_Name, Item No., Description, Order_Qty, Location, Skids_Required
        """
        order_lines = []

        for _, order_group in optimized_orders.iterrows():
            vendor = order_group['Vendor']
            vendor_name = order_group['Vendor_Name']

            # Get items for this vendor
            vendor_items = self.df_stockout[
                (self.df_stockout['will_stockout'] == True) &
                (self.df_stockout['TargetVendor'] == vendor)
            ].copy()

            for _, item_row in vendor_items.iterrows():
                item_code = item_row['Item No.']
                order_qty = int(item_row['shortage_qty'] * 1.2)  # 20% safety buffer
                location = item_row['Region']

                # Calculate skids required
                skids = self.capacity_manager.calculate_space_required(item_code, order_qty)

                # Get description if available
                description = item_row.get('Item Description', item_code)

                order_lines.append({
                    'Vendor': vendor,
                    'Vendor_Name': vendor_name,
                    'Item_No.': item_code,
                    'Description': description,
                    'Order_Qty': order_qty,
                    'Location': location,
                    'Skids_Required': round(skids, 2)
                })

        return pd.DataFrame(order_lines)

    def get_capacity_report(self) -> pd.DataFrame:
        """
        Generate warehouse capacity report

        Returns:
        --------
        pd.DataFrame with capacity status by location
        """
        return self.capacity_manager.get_location_capacity_status()
