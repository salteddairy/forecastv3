"""
Data Cleaning Module
Implements Z-score based outlier detection and item segmentation
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
from src.utils import safe_divide


def detect_and_replace_outliers_zscore(df_history: pd.DataFrame,
                                        z_threshold: float = 3.0) -> pd.DataFrame:
    """
    Detect outliers in lead times using Z-score method and replace with vendor median.
    Outlier = If lead time is > z_threshold standard deviations from vendor's median.

    Parameters:
    -----------
    df_history : pd.DataFrame
        Supply history dataframe with vendor_code and lead_time_days columns
    z_threshold : float
        Number of standard deviations from median to flag as outlier (default: 3.0)

    Returns:
    --------
    pd.DataFrame
        Dataframe with outliers replaced by vendor medians
    """
    print("\n[Z-Score Outlier Detection]")
    print(f"  Z-threshold: {z_threshold} sigmas")

    df_cleaned = df_history.copy()
    outliers_replaced = 0
    outliers_by_vendor = {}

    # Process each vendor separately
    for vendor in df_history['vendor_code'].unique():
        vendor_mask = df_history['vendor_code'] == vendor
        vendor_data = df_history[vendor_mask]['lead_time_days'].dropna()

        if len(vendor_data) < 3:
            # Skip vendors with insufficient data
            continue

        # Calculate vendor statistics
        vendor_median = vendor_data.median()
        vendor_std = vendor_data.std()

        if vendor_std == 0:
            # No variance, all values are the same
            continue

        # Calculate Z-scores
        z_scores = np.abs((vendor_data - vendor_median) / vendor_std)

        # Find outliers
        outlier_mask = z_scores > z_threshold
        outlier_indices = vendor_data[outlier_mask].index

        if len(outlier_indices) > 0:
            outliers_by_vendor[vendor] = len(outlier_indices)
            # Replace outliers with vendor median
            df_cleaned.loc[outlier_indices, 'lead_time_days'] = vendor_median
            outliers_replaced += len(outlier_indices)

    print(f"  - Vendors processed: {df_history['vendor_code'].nunique()}")
    print(f"  - Outliers replaced: {outliers_replaced}")
    print(f"  - Vendors with outliers: {len(outliers_by_vendor)}")

    if outliers_by_vendor:
        print(f"  - Top 5 vendors with most outliers:")
        sorted_vendors = sorted(outliers_by_vendor.items(),
                               key=lambda x: x[1], reverse=True)[:5]
        for vendor, count in sorted_vendors:
            print(f"    * {vendor}: {count} outliers")

    return df_cleaned


def calculate_demand_cv(df_sales: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Coefficient of Variation (CV) for each item's demand.
    CV = Standard Deviation / Mean

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe with item_code, date, qty columns

    Returns:
    --------
    pd.DataFrame
        DataFrame with item_code, mean_demand, std_demand, cv, and demand_months
    """
    print("\n[Demand CV Calculation]")

    # Aggregate demand by item and month
    df_sales['year_month'] = df_sales['date'].dt.to_period('M')

    # Calculate monthly demand per item
    monthly_demand = df_sales.groupby(['item_code', 'year_month'])['qty'].sum().reset_index()

    # Calculate statistics per item
    item_stats = monthly_demand.groupby('item_code').agg({
        'qty': ['mean', 'std', 'count']
    }).reset_index()

    item_stats.columns = ['item_code', 'mean_demand', 'std_demand', 'demand_months']

    # Calculate CV (coefficient of variation) - use safe_divide to handle zero mean demand
    item_stats['cv'] = safe_divide(item_stats['std_demand'], item_stats['mean_demand'], 0.0)

    print(f"  - Unique items analyzed: {len(item_stats)}")
    print(f"  - Average demand months per item: {item_stats['demand_months'].mean():.1f}")
    print(f"  - CV range: {item_stats['cv'].min():.2f} to {item_stats['cv'].max():.2f}")

    return item_stats


def classify_items(df_sales: pd.DataFrame,
                   cv_threshold: float = 0.5,
                   zero_months_threshold: int = 3) -> pd.DataFrame:
    """
    Classify items based on demand pattern:
    - 'Smooth': CV < cv_threshold (steady demand)
    - 'Intermittent': CV >= cv_threshold (variable demand)
    - 'Lumpy': Many zero-demand months (zero_months_threshold or more)

    Parameters:
    -----------
    df_sales : pd.DataFrame
        Sales orders dataframe with item_code, date, qty columns
    cv_threshold : float
        CV threshold for Smooth vs Intermittent classification (default: 0.5)
    zero_months_threshold : int
        Number of zero-demand months to classify as 'Lumpy' (default: 3)

    Returns:
    --------
    pd.DataFrame
        DataFrame with item_code, classification, cv, and supporting metrics
    """
    print("\n[Item Segmentation]")

    # Ensure qty is numeric
    df_sales_clean = df_sales.copy()
    df_sales_clean['qty'] = pd.to_numeric(df_sales_clean['qty'], errors='coerce')

    # Remove rows with invalid quantities
    initial_rows = len(df_sales_clean)
    df_sales_clean = df_sales_clean.dropna(subset=['qty'])
    print(f"  - Removed {initial_rows - len(df_sales_clean)} rows with invalid quantities")

    # Aggregate demand by item and month
    df_sales_clean['year_month'] = df_sales_clean['date'].dt.to_period('M')

    # Calculate monthly demand per item
    monthly_demand = df_sales_clean.groupby(['item_code', 'year_month'])['qty'].sum().reset_index()

    # Count zero-demand months per item
    zero_demand_counts = monthly_demand[monthly_demand['qty'] == 0].groupby('item_code').size()
    total_months = monthly_demand.groupby('item_code').size()

    # Calculate statistics per item
    item_stats = monthly_demand.groupby('item_code').agg({
        'qty': ['mean', 'std', 'count']
    }).reset_index()
    item_stats.columns = ['item_code', 'mean_demand', 'std_demand', 'active_months']

    # Calculate CV - use safe_divide to handle zero mean demand
    item_stats['cv'] = safe_divide(item_stats['std_demand'], item_stats['mean_demand'], 0.0)

    # Add zero-demand month counts
    item_stats['zero_demand_months'] = item_stats['item_code'].map(zero_demand_counts).fillna(0).astype(int)
    item_stats['total_months'] = item_stats['item_code'].map(total_months).fillna(0).astype(int)

    # Classify items
    def classify_item(row):
        # Lumpy: many zero-demand months
        if row['zero_demand_months'] >= zero_months_threshold:
            return 'Lumpy'
        # Smooth: low coefficient of variation
        elif row['cv'] < cv_threshold:
            return 'Smooth'
        # Intermittent: high coefficient of variation
        else:
            return 'Intermittent'

    item_stats['classification'] = item_stats.apply(classify_item, axis=1)

    # Summary statistics
    classification_counts = item_stats['classification'].value_counts()
    print(f"  - Total items classified: {len(item_stats)}")
    print(f"  - Classification breakdown:")
    for cls, count in classification_counts.items():
        pct = (count / len(item_stats)) * 100
        print(f"    * {cls}: {count} ({pct:.1f}%)")

    return item_stats[['item_code', 'classification', 'cv', 'mean_demand',
                       'std_demand', 'active_months', 'zero_demand_months', 'total_months']]


def impute_missing_lead_times(df_history: pd.DataFrame,
                               df_schedule: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Impute missing lead times using vendor median.

    Parameters:
    -----------
    df_history : pd.DataFrame
        Supply history dataframe
    df_schedule : pd.DataFrame
        Supply schedule dataframe (Open POs)

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        Updated history and schedule dataframes with imputed lead times
    """
    print("\n[Lead Time Imputation]")

    # Calculate vendor medians
    vendor_medians = df_history.groupby('vendor_code')['lead_time_days'].median()
    overall_median = df_history['lead_time_days'].median()

    # Track missing values before imputation
    history_missing_before = df_history['lead_time_days'].isna().sum()
    schedule_missing_before = df_schedule['lead_time_days'].isna().sum()

    # Impute for History
    df_history_imputed = df_history.copy()
    mask_missing = df_history_imputed['lead_time_days'].isna()

    for idx in df_history_imputed[mask_missing].index:
        vendor = df_history_imputed.loc[idx, 'vendor_code']
        if vendor in vendor_medians:
            df_history_imputed.loc[idx, 'lead_time_days'] = vendor_medians[vendor]
        else:
            df_history_imputed.loc[idx, 'lead_time_days'] = overall_median

    # Impute for Schedule
    df_schedule_imputed = df_schedule.copy()
    mask_missing_schedule = df_schedule_imputed['lead_time_days'].isna()

    for idx in df_schedule_imputed[mask_missing_schedule].index:
        vendor = df_schedule_imputed.loc[idx, 'vendor_code']
        if vendor in vendor_medians:
            df_schedule_imputed.loc[idx, 'lead_time_days'] = vendor_medians[vendor]
        else:
            df_schedule_imputed.loc[idx, 'lead_time_days'] = overall_median

    history_missing_after = df_history_imputed['lead_time_days'].isna().sum()
    schedule_missing_after = df_schedule_imputed['lead_time_days'].isna().sum()

    print(f"  History:")
    print(f"    - Missing before: {history_missing_before}")
    print(f"    - Missing after: {history_missing_after}")
    print(f"    - Imputed: {history_missing_before - history_missing_after}")
    print(f"  Schedule:")
    print(f"    - Missing before: {schedule_missing_before}")
    print(f"    - Missing after: {schedule_missing_after}")
    print(f"    - Imputed: {schedule_missing_before - schedule_missing_after}")

    return df_history_imputed, df_schedule_imputed


def clean_supply_data(df_history: pd.DataFrame,
                      df_schedule: pd.DataFrame,
                      z_threshold: float = 3.0) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Complete cleaning pipeline for supply data:
    1. Detect and replace outliers using Z-score method
    2. Impute missing lead times using vendor median

    Parameters:
    -----------
    df_history : pd.DataFrame
        Supply history dataframe
    df_schedule : pd.DataFrame
        Supply schedule dataframe (Open POs)
    z_threshold : float
        Z-score threshold for outlier detection (default: 3.0)

    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        Cleaned history and schedule dataframes
    """
    print("\n" + "=" * 60)
    print("SUPPLY DATA CLEANING PIPELINE")
    print("=" * 60)

    # Step 1: Detect and replace outliers using Z-score
    df_history_clean = detect_and_replace_outliers_zscore(df_history, z_threshold)

    # Step 2: Impute missing lead times
    df_history_final, df_schedule_final = impute_missing_lead_times(
        df_history_clean, df_schedule
    )

    print("\n" + "=" * 60)
    print("SUPPLY CLEANING COMPLETE")
    print("=" * 60)

    return df_history_final, df_schedule_final


def test_cleaning_pipeline():
    """
    Test function to run the cleaning pipeline on loaded data and print results.
    """
    print("\n" + "=" * 60)
    print("TESTING CLEANING PIPELINE")
    print("=" * 60)

    from src.ingestion import load_sales_orders, load_supply_chain

    # Load data
    data_dir = Path("data/raw")

    print("\n[Loading Data]")
    df_sales = load_sales_orders(data_dir / "sales.tsv")
    df_history, df_schedule = load_supply_chain(data_dir / "supply.tsv")

    print(f"  - Sales orders: {len(df_sales)} rows")
    print(f"  - Supply history: {len(df_history)} rows")
    print(f"  - Supply schedule: {len(df_schedule)} rows")

    # Clean supply data
    df_history_clean, df_schedule_clean = clean_supply_data(
        df_history, df_schedule, z_threshold=3.0
    )

    # Classify items
    df_classified = classify_items(df_sales,
                                   cv_threshold=0.5,
                                   zero_months_threshold=3)

    # Print sample of classified items
    print("\n" + "=" * 60)
    print("SAMPLE CLASSIFIED ITEMS (Top 20)")
    print("=" * 60)

    sample_items = df_classified.head(20)
    for idx, row in sample_items.iterrows():
        print(f"\nItem: {row['item_code']}")
        print(f"  Classification: {row['classification']}")
        print(f"  CV: {row['cv']:.3f}")
        print(f"  Mean Demand: {row['mean_demand']:.2f}")
        print(f"  Active Months: {row['active_months']}")
        print(f"  Zero-Demand Months: {row['zero_demand_months']}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    print("\n[Supply Data - After Cleaning]")
    print(f"  History rows: {len(df_history_clean)}")
    print(f"  Schedule rows: {len(df_schedule_clean)}")
    print(f"  History lead time - Mean: {df_history_clean['lead_time_days'].mean():.1f} days")
    print(f"  History lead time - Median: {df_history_clean['lead_time_days'].median():.1f} days")
    print(f"  History lead time - Std: {df_history_clean['lead_time_days'].std():.1f} days")
    print(f"  History lead time - Range: {df_history_clean['lead_time_days'].min():.0f} to {df_history_clean['lead_time_days'].max():.0f} days")

    print("\n[Item Classification Summary]")
    for classification in ['Smooth', 'Intermittent', 'Lumpy']:
        items = df_classified[df_classified['classification'] == classification]
        print(f"  {classification}:")
        print(f"    - Count: {len(items)}")
        if len(items) > 0:
            print(f"    - Avg CV: {items['cv'].mean():.3f}")
            print(f"    - Avg Mean Demand: {items['mean_demand'].mean():.2f}")

    return df_history_clean, df_schedule_clean, df_classified


if __name__ == "__main__":
    test_cleaning_pipeline()
