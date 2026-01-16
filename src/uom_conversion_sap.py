"""
UOM (Unit of Measure) Conversion Module - SAP B1 Version
Uses SAP B1 native UOM fields for accurate conversion
"""
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_stock_to_sales_uom_sap(df_items: pd.DataFrame) -> pd.DataFrame:
    """
    Convert stock from SAP Base UOM (Litres/kg) to Sales UOM (Pails/Drums)
    using SAP B1's native UOM conversion fields.

    SAP B1 Fields:
    - BaseUoM: Inventory UOM (e.g., 'L', 'kg') - stock is ALWAYS in this
    - SalesUoM: Sales UOM (e.g., 'Pail', 'Drum')
    - QtyPerSalesUoM: Conversion factor (e.g., 18.9 Litres per Pail)

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe from SAP B1 with UOM fields

    Returns:
    --------
    pd.DataFrame
        Items dataframe with stock converted to sales UOM
    """
    df_converted = df_items.copy()

    # Check if required UOM columns exist
    required_cols = ['BaseUoM', 'SalesUoM', 'QtyPerSalesUoM']
    missing_cols = [col for col in required_cols if col not in df_items.columns]

    if missing_cols:
        logger.error(f"Missing required UOM columns: {missing_cols}")
        logger.error("Please update items.tsv export from Query 3 to include UOM fields")
        logger.error("Required columns: BaseUoM, SalesUoM, QtyPerSalesUoM")
        return df_items

    # VECTORIZED CONVERSION - 100-1000x faster than iterrows loop
    conversion_log = []

    # Ensure numeric types (vectorized) - use normalized column names
    df_converted['QtyPerSalesUoM'] = pd.to_numeric(df_converted['QtyPerSalesUoM'], errors='coerce')
    df_converted['current_stock'] = pd.to_numeric(df_converted['current_stock'], errors='coerce').fillna(0)
    df_converted['incoming_stock'] = pd.to_numeric(df_converted['incoming_stock'], errors='coerce').fillna(0)

    # Find rows where conversion is needed (SalesUoM != BaseUoM)
    needs_conversion = (df_converted['SalesUoM'].notna()) & \
                       (df_converted['SalesUoM'] != df_converted['BaseUoM'])

    if not needs_conversion.any():
        logger.info("No items require UoM conversion")
        return df_items

    # Validate conversion factors (vectorized)
    invalid_mask = (df_converted['QtyPerSalesUoM'].isna()) | \
                   (df_converted['QtyPerSalesUoM'] <= 0)

    if invalid_mask.any():
        invalid_count = invalid_mask.sum()
        invalid_items = df_converted.loc[invalid_mask, 'item_code'].head(10).tolist()
        logger.error(f"[ERROR] {invalid_count} items have invalid QtyPerSalesUoM: {invalid_items}...")

        # Set converted values to NaN for invalid items
        df_converted.loc[invalid_mask, 'current_stock_SalesUOM'] = np.nan
        df_converted.loc[invalid_mask, 'incoming_stock_SalesUOM'] = np.nan
        df_converted.loc[invalid_mask, 'ConversionFactor'] = np.nan
        df_converted.loc[invalid_mask, 'ConversionError'] = 'Invalid QtyPerSalesUoM'

        # Exclude invalid items from conversion
        valid_mask = ~invalid_mask
    else:
        valid_mask = pd.Series([True] * len(df_converted), index=df_converted.index)

    # Vectorized conversion (much faster!) - use normalized column names
    if valid_mask.any():
        df_converted.loc[valid_mask, 'current_stock_SalesUOM'] = \
            df_converted.loc[valid_mask, 'current_stock'] / df_converted.loc[valid_mask, 'QtyPerSalesUoM']

        df_converted.loc[valid_mask, 'incoming_stock_SalesUOM'] = \
            df_converted.loc[valid_mask, 'incoming_stock'] / df_converted.loc[valid_mask, 'QtyPerSalesUoM']

        df_converted.loc[valid_mask, 'ConversionFactor'] = df_converted.loc[valid_mask, 'QtyPerSalesUoM']

    # Copy string columns (vectorized) - use SalesUOM for test compatibility
    df_converted['SalesUOM'] = df_converted['SalesUoM']
    df_converted['BaseUoM_Copy'] = df_converted['BaseUoM']

    # Build conversion log (only for first 1000 to avoid memory issues) - use normalized column names
    sample_conversions = df_converted[valid_mask & (df_converted['QtyPerSalesUoM'] != 1.0)].head(1000)
    if len(sample_conversions) > 0:
        conversion_log = [
            {
                'Item Code': row['item_code'],
                'Base UOM': row['BaseUoM'],
                'Sales UOM': row['SalesUoM'],
                'QtyPerSalesUoM': row['ConversionFactor'],
                'Original Stock': f"{row['current_stock']:.2f} {row['BaseUoM']}",
                'Converted Stock': f"{row['current_stock_SalesUOM']:.2f} {row['SalesUoM']}"
            }
            for _, row in sample_conversions.iterrows()
        ]

    # Post-conversion validation - use normalized column names
    converted_count = df_converted['current_stock_SalesUOM'].notna().sum()
    error_count = df_converted['ConversionError'].notna().sum() if 'ConversionError' in df_converted.columns else 0
    total_converted = valid_mask.sum()

    if total_converted > 0:
        logger.info(f"[PERF] UoM conversion: {converted_count}/{len(df_converted)} successful (vectorized)")
        if error_count > 0:
            logger.warning(f"[WARNING] {error_count} items failed conversion (invalid QtyPerSalesUoM)")
        if conversion_log:
            df_log = pd.DataFrame(conversion_log)
            logger.info(f"\nSample conversions:\n{df_log.head(10).to_string()}")
    else:
        logger.warning("No UOM conversions applied - check if QtyPerSalesUoM field has data")

    return df_converted


def validate_sap_uom_data(df_items: pd.DataFrame) -> Dict:
    """
    Validate SAP B1 UOM data completeness and accuracy.

    Parameters:
    -----------
    df_items : pd.DataFrame
        Items dataframe from SAP B1

    Returns:
    --------
    Dict
        Validation results with issues found
    """
    issues = {
        'missing_uom_fields': [],
        'invalid_conversion_factors': [],
        'zero_conversion_factor': [],
        'extreme_conversion_factors': []
    }

    # Check for required UOM fields
    required_uom_cols = ['BaseUoM', 'SalesUoM', 'QtyPerSalesUoM']
    missing_uom_cols = [col for col in required_uom_cols if col not in df_items.columns]

    if missing_uom_cols:
        issues['missing_uom_fields'] = missing_uom_cols
        logger.error(f"Missing UOM columns: {missing_uom_cols}")

    # Check conversion factors - use normalized column names
    if 'QtyPerSalesUoM' in df_items.columns:
        for idx, row in df_items.iterrows():
            item_code = row['item_code']
            conversion_factor = pd.to_numeric(row.get('QtyPerSalesUoM', 1), errors='coerce')

            if pd.isna(conversion_factor):
                issues['invalid_conversion_factors'].append(item_code)

            elif conversion_factor == 0:
                issues['zero_conversion_factor'].append(item_code)

            elif conversion_factor < 0.01:
                issues['extreme_conversion_factors'].append({
                    'Item Code': item_code,
                    'Factor': conversion_factor,
                    'Issue': 'Conversion factor too small (<0.01)'
                })

            elif conversion_factor > 10000:
                issues['extreme_conversion_factors'].append({
                    'Item Code': item_code,
                    'Factor': conversion_factor,
                    'Issue': 'Conversion factor too large (>10000)'
                })

    # Summary
    total_issues = sum(len(v) if isinstance(v, list) else len(v) if isinstance(v, dict) else 0
                        for v in issues.values())

    logger.info(f"UOM Validation Complete: {total_issues} issues found")

    for issue_type, issue_list in issues.items():
        if issue_list:
            logger.warning(f"{issue_type}: {len(issue_list)} items")
            if isinstance(issue_list, list) and len(issue_list) <= 5:
                logger.warning(f"  Examples: {issue_list[:5]}")

    return issues


if __name__ == "__main__":
    # Test with current data
    from src.ingestion import load_items
    from pathlib import Path

    print("Testing SAP UOM Conversion...")
    df_items = load_items(Path("data/raw/items.tsv"))

    # Validate current data
    print("\n=== Validating Current Data ===")
    validation = validate_sap_uom_data(df_items)

    if validation['missing_uom_fields']:
        print("\n[ERROR] MISSING UOM FIELDS DETECTED!")
        print(f"Missing columns: {validation['missing_uom_fields']}")
        print("\n[ACTION REQUIRED]:")
        print("1. Run the updated query: queries/items_with_uom.txt")
        print("2. Export to data/raw/items.tsv")
        print("3. Reload the application")
    else:
        print("\n[OK] UOM fields present - testing conversion...")
        df_converted = convert_stock_to_sales_uom_sap(df_items)

        # Show example - use normalized column names
        test_item = df_converted[df_converted['item_code'] == '30555C-DEL']
        if len(test_item) > 0:
            item = test_item.iloc[0]
            print(f"\n=== 30555C-DEL Conversion ===")
            print(f"Base UOM: {item['BaseUoM']}")
            print(f"Sales UOM: {item['SalesUoM']}")
            print(f"QtyPerSalesUoM: {item['ConversionFactor']}")
            print(f"Current Stock: {item['current_stock']} {item['BaseUoM']}")
            print(f"Converted Stock: {item['current_stock_SalesUOM']:.2f} {item['SalesUoM']}")
