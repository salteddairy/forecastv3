"""
UOM (Unit of Measure) Conversion Module
Handles conversion from purchase UOM to sales UOM for accurate inventory calculations
"""
import pandas as pd
import re
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_uom_mapping(config_path: Path = Path("uom_mapping.yaml")) -> dict:
    """
    Load UOM conversion mapping from YAML config.

    Parameters:
    -----------
    config_path : Path
        Path to UOM mapping configuration file

    Returns:
    --------
    dict
        UOM conversion configuration
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded UOM mapping from {config_path}")
        return config
    except FileNotFoundError:
        logger.warning(f"UOM mapping file not found: {config_path}")
        return {'conversions': [], 'manual_mappings': [], 'default_conversion': {'factor': 1.0}}
    except Exception as e:
        logger.error(f"Error loading UOM mapping: {e}")
        return {'conversions': [], 'manual_mappings': [], 'default_conversion': {'factor': 1.0}}


def get_conversion_factor(item_code: str, item_description: str,
                          uom_config: dict) -> Tuple[float, Optional[str]]:
    """
    Get conversion factor for an item based on description patterns or manual mapping.

    Parameters:
    -----------
    item_code : str
        Item code
    item_description : str
        Item description
    uom_config : dict
        UOM configuration dictionary

    Returns:
    --------
    Tuple[float, Optional[str]]
        (conversion_factor, sales_uom)
    """
    # Check manual mappings first (highest priority)
    for mapping in uom_config.get('manual_mappings', []):
        if mapping['item_code'] == item_code:
            factor = mapping['conversion_factor']
            sales_uom = mapping.get('sales_uom', 'unit')
            logger.debug(f"{item_code}: Using manual conversion factor {factor}")
            return factor, sales_uom

    # Check pattern-based conversions
    desc_lower = item_description.lower()
    for conversion in uom_config.get('conversions', []):
        pattern = conversion.get('pattern', '')
        if re.search(pattern, desc_lower, re.IGNORECASE):
            factor = conversion['conversion_factor']
            sales_uom = conversion['sales_uom']
            logger.debug(f"{item_code}: Matched pattern '{pattern}', conversion factor {factor}")
            return factor, sales_uom

    # Use default if no match found
    default = uom_config.get('default_conversion', {})
    factor = default.get('factor', 1.0)
    logger.warning(f"{item_code}: No UOM pattern matched, using default factor {factor}")
    return factor, None


def convert_stock_to_sales_uom(df_items: pd.DataFrame,
                                uom_config_path: Path = Path("uom_mapping.yaml")) -> pd.DataFrame:
    """
    Convert CurrentStock and IncomingStock from purchase UOM to sales UOM.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe with CurrentStock and IncomingStock in purchase UOM
    uom_config_path : Path
        Path to UOM configuration file

    Returns:
    --------
    pd.DataFrame
        Items dataframe with stock converted to sales UOM
    """
    df_converted = df_items.copy()
    uom_config = load_uom_mapping(uom_config_path)

    conversion_log = []

    for idx, row in df_items.iterrows():
        item_code = row['Item No.']
        description = str(row.get('Item Description', ''))

        # Get conversion factor
        factor, sales_uom = get_conversion_factor(item_code, description, uom_config)

        # Convert stock quantities
        original_stock = pd.to_numeric(row['CurrentStock'], errors='coerce')
        if pd.isna(original_stock):
            original_stock = 0
        original_incoming = pd.to_numeric(row['IncomingStock'], errors='coerce')
        if pd.isna(original_incoming):
            original_incoming = 0

        converted_stock = original_stock / factor if factor > 0 else original_stock
        converted_incoming = original_incoming / factor if factor > 0 else original_incoming

        # Store converted values
        df_converted.loc[idx, 'CurrentStock_SalesUOM'] = converted_stock
        df_converted.loc[idx, 'IncomingStock_SalesUOM'] = converted_incoming
        df_converted.loc[idx, 'ConversionFactor'] = factor
        df_converted.loc[idx, 'SalesUOM'] = sales_uom or 'unknown'

        # Log significant conversions for validation
        if factor != 1.0:
            conversion_log.append({
                'Item Code': item_code,
                'Description': description[:50],
                'Original Stock': f"{original_stock:.2f}",
                'Converted Stock': f"{converted_stock:.2f}",
                'Factor': factor,
                'Sales UOM': sales_uom
            })

    if conversion_log:
        df_log = pd.DataFrame(conversion_log)
        logger.info(f"Converted {len(conversion_log)} items to sales UOM")
        logger.info(f"\nSample conversions:\n{df_log.head(10).to_string()}")

    return df_converted


def validate_uom_conversions(df_items: pd.DataFrame,
                             uom_config_path: Path = Path("uom_mapping.yaml")) -> pd.DataFrame:
    """
    Validate UOM conversions and flag potential issues.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe with converted stock values
    uom_config_path : Path
        Path to UOM configuration file

    Returns:
    --------
    pd.DataFrame
        Validation report with flagged issues
    """
    uom_config = load_uom_mapping(uom_config_path)
    validation_rules = uom_config.get('validation', {})

    issues = []

    for idx, row in df_items.iterrows():
        item_code = row['Item No.']
        original_stock = pd.to_numeric(row['CurrentStock'], errors='coerce')
        if pd.isna(original_stock):
            original_stock = 0
        converted_stock = row.get('CurrentStock_SalesUOM', 0)
        if pd.isna(converted_stock):
            converted_stock = 0
        factor = row.get('ConversionFactor', 1.0)
        if pd.isna(factor):
            factor = 1.0

        # Check for suspiciously large conversion factors
        max_factor = validation_rules.get('max_conversion_factor', 10000)
        if factor > max_factor:
            issues.append({
                'Item Code': item_code,
                'Issue': 'Conversion factor too large',
                'Details': f'Factor {factor} exceeds maximum {max_factor}',
                'Severity': 'ERROR'
            })

        # Check for very low stock after conversion (possible misconfiguration)
        min_stock = validation_rules.get('min_stock_after_conversion', 0.01)
        if original_stock > 100 and converted_stock < min_stock:
            issues.append({
                'Item Code': item_code,
                'Issue': 'Stock too low after conversion',
                'Details': f'Original: {original_stock:.2f}, Converted: {converted_stock:.4f}',
                'Severity': 'WARNING'
            })

        # Check for large discrepancies (possible wrong UOM assignment)
        warn_threshold = validation_rules.get('warn_large_discrepancy', 100)
        if original_stock > 0 and (original_stock / converted_stock) > warn_threshold:
            issues.append({
                'Item Code': item_code,
                'Issue': 'Large purchase/sales quantity discrepancy',
                'Details': f'Original {original_stock:.2f} / Converted {converted_stock:.2f} = {original_stock/converted_stock:.0f}x',
                'Severity': 'WARNING'
            })

    if issues:
        df_issues = pd.DataFrame(issues)
        logger.warning(f"Found {len(issues)} UOM validation issues")
        return df_issues
    else:
        logger.info("No UOM validation issues found")
        return pd.DataFrame()


if __name__ == "__main__":
    # Test the UOM conversion
    from src.ingestion import load_items
    from pathlib import Path

    print("Testing UOM Conversion...")
    df_items = load_items(Path("data/raw/items.tsv"))

    # Convert stock
    df_converted = convert_stock_to_sales_uom(df_items)

    # Show conversion examples
    print("\n=== Conversion Examples ===")
    sample_items = ['30555C-DEL', '30071C-TOR', 'BX010007-CGY']

    for item_code in sample_items:
        item = df_converted[df_converted['Item No.'] == item_code]
        if len(item) > 0:
            item = item.iloc[0]
            print(f"\n{item_code}:")
            print(f"  Description: {item['Item Description'][:60]}...")
            print(f"  Original Stock: {item['CurrentStock']:.2f}")
            print(f"  Converted Stock: {item['CurrentStock_SalesUOM']:.2f} {item['SalesUOM']}")
            print(f"  Conversion Factor: {item['ConversionFactor']}")

    # Validate conversions
    print("\n=== Validation ===")
    df_issues = validate_uom_conversions(df_converted)
    if len(df_issues) > 0:
        print(df_issues.to_string())
    else:
        print("No issues found")
