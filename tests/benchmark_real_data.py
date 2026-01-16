"""
Real SAP B1 Data Benchmarking
Validates forecasting models on actual sales data
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple
import json
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.forecasting import (
    forecast_sma,
    forecast_holt_winters,
    forecast_theta,
    forecast_arima,
    forecast_sarima,
    forecast_croston,
    forecast_ensemble_simple,
    forecast_ensemble_weighted,
    calculate_rmse,
    calculate_mape,
    prepare_monthly_data,
    run_tournament
)
from src.ingestion import load_sales_orders, load_supply_chain, load_items
from src.config import DataConfig


class RealDataBenchmark:
    """Benchmarking on real SAP B1 sales data"""

    def __init__(self):
        self.results = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'data_source': 'SAP B1 Production Data',
                'items_tested': 0
            },
            'items': {},
            'summary': {
                'by_pattern': {},
                'best_models': {},
                'business_impact': {}
            }
        }

    def load_real_data(self):
        """Load real SAP B1 sales data"""
        print("Loading SAP B1 sales data...")
        sales_file = DataConfig.DATA_DIR / 'sales.tsv'

        if not sales_file.exists():
            raise FileNotFoundError(f"Sales data not found: {sales_file}")

        df_sales = load_sales_orders(sales_file)
        print(f"Loaded {len(df_sales)} sales records")

        # Convert date column to datetime
        df_sales['date'] = pd.to_datetime(df_sales['date'], errors='coerce')
        print(f"Date range: {df_sales['date'].min()} to {df_sales['date'].max()}")

        return df_sales

    def categorize_demand_pattern(self, monthly_series: pd.Series) -> Dict:
        """
        Categorize item demand pattern based on statistical properties

        Returns dict with pattern type and metrics
        """
        if len(monthly_series) < 12:
            return {'pattern': 'insufficient_data', 'metrics': {}}

        values = monthly_series.values

        # Calculate metrics
        mean_val = np.mean(values)
        std_val = np.std(values)
        cv = std_val / mean_val if mean_val > 0 else np.inf

        # Zero ratio (for intermittent detection)
        zero_ratio = np.sum(values == 0) / len(values)

        # Trend detection (linear regression slope)
        x = np.arange(len(values))
        if len(values) > 1:
            slope = np.polyfit(x, values, 1)[0]
            slope_pct = (slope / mean_val) * 100 if mean_val > 0 else 0
        else:
            slope_pct = 0

        # Seasonality detection (simple autocorrelation at lag 12)
        has_seasonality = False
        if len(values) >= 24:
            # Detrend
            if abs(slope_pct) > 1:
                detrended = values - np.polyval(np.polyfit(x, values, 1), x)
            else:
                detrended = values - mean_val

            # Autocorrelation at seasonal lags
            acf_lag12 = np.corrcoef(detrended[:-12], detrended[12:])[0, 1]
            has_seasonality = abs(acf_lag12) > 0.3

        # Pattern classification
        pattern = 'stable'
        confidence = 'medium'

        if zero_ratio > 0.3:
            pattern = 'intermittent'
            confidence = 'high'
        elif has_seasonality:
            pattern = 'seasonal'
            confidence = 'high'
        elif abs(slope_pct) > 5:
            pattern = 'trending'
            confidence = 'high'
        elif cv > 0.5:
            pattern = 'volatile'
            confidence = 'medium'

        return {
            'pattern': pattern,
            'confidence': confidence,
            'metrics': {
                'mean_demand': float(mean_val),
                'std_demand': float(std_val),
                'cv': float(cv),
                'zero_ratio': float(zero_ratio),
                'slope_pct': float(slope_pct),
                'has_seasonality': has_seasonality,
                'n_months': len(values)
            }
        }

    def sample_items_by_pattern(self, df_sales: pd.DataFrame, n_per_pattern: int = 5) -> Dict[str, List[str]]:
        """Sample items from each demand pattern"""
        print("\nCategorizing items by demand pattern...")

        # Get all item codes
        all_items = df_sales['item_code'].unique()
        print(f"Total unique items: {len(all_items)}")

        # Categorize each item
        pattern_items = defaultdict(list)
        pattern_stats = defaultdict(list)

        for item_code in all_items:
            try:
                monthly_data = prepare_monthly_data(df_sales, item_code)

                if len(monthly_data) < 12:
                    continue

                categorization = self.categorize_demand_pattern(monthly_data)
                pattern = categorization['pattern']

                if pattern != 'insufficient_data':
                    pattern_items[pattern].append({
                        'item_code': item_code,
                        'metrics': categorization['metrics'],
                        'confidence': categorization['confidence']
                    })
                    pattern_stats[pattern].append(categorization['metrics'])

            except Exception as e:
                continue

        # Print summary
        print("\nDemand Pattern Distribution:")
        for pattern, items in sorted(pattern_items.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {pattern.capitalize():15} : {len(items):4} items")

        # Sample items from each pattern
        sampled = {}
        for pattern, items in pattern_items.items():
            # Sort by confidence (high first) then sample
            high_conf = [i for i in items if i['confidence'] == 'high']
            med_conf = [i for i in items if i['confidence'] == 'medium']

            selected = high_conf[:n_per_pattern]
            if len(selected) < n_per_pattern:
                selected.extend(med_conf[:n_per_pattern - len(selected)])

            sampled[pattern] = [i['item_code'] for i in selected]
            print(f"  Selected {len(selected)} {pattern} items for testing")

        return sampled

    def benchmark_item(self, df_sales: pd.DataFrame, item_code: str) -> Dict:
        """Run full benchmark on single item"""
        try:
            # Prepare data
            monthly_data = prepare_monthly_data(df_sales, item_code)

            if len(monthly_data) < 12:
                return {'error': 'Insufficient data'}

            # Categorize pattern
            pattern_info = self.categorize_demand_pattern(monthly_data)
            pattern = pattern_info['pattern']

            # Train/test split (80/20)
            split_idx = int(len(monthly_data) * 0.8)
            train = monthly_data.iloc[:split_idx]
            test = monthly_data.iloc[split_idx:]

            forecast_horizon = 6

            # Run tournament to get winning model
            tournament_result = run_tournament(df_sales, item_code, use_advanced_models=True)

            # Evaluate individual models
            models = {}

            # Baseline models
            forecast, rmse = forecast_sma(train, test, forecast_horizon)
            mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
            models['SMA'] = {'rmse': rmse, 'mape': mape}

            forecast, rmse = forecast_holt_winters(train, test, forecast_horizon)
            mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
            models['Holt-Winters'] = {'rmse': rmse, 'mape': mape}

            # Advanced models (if sufficient data)
            if len(train) >= 12:
                forecast, rmse = forecast_theta(train, test, forecast_horizon)
                mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
                models['Theta'] = {'rmse': rmse, 'mape': mape}

                forecast, rmse = forecast_arima(train, test, forecast_horizon)
                mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
                models['ARIMA'] = {'rmse': rmse, 'mape': mape}

            if len(train) >= 24:
                forecast, rmse = forecast_sarima(train, test, forecast_horizon)
                mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
                models['SARIMA'] = {'rmse': rmse, 'mape': mape}

            # Croston for intermittent
            if pattern_info['metrics']['zero_ratio'] > 0.3:
                forecast, rmse = forecast_croston(train, test, forecast_horizon)
                mape = calculate_mape(test, forecast) if len(test) > 0 else np.nan
                models['Croston'] = {'rmse': rmse, 'mape': mape}

            # Calculate improvements vs SMA
            baseline_rmse = models['SMA']['rmse']
            baseline_mape = models['SMA']['mape']

            improvements = {}
            for model_name, model_metrics in models.items():
                if model_name == 'SMA':
                    continue
                if model_metrics['rmse'] is not None and baseline_rmse > 0:
                    rmse_imp = ((baseline_rmse - model_metrics['rmse']) / baseline_rmse) * 100
                    mape_imp = 0
                    if model_metrics['mape'] is not None and baseline_mape is not None and baseline_mape > 0:
                        mape_imp = ((baseline_mape - model_metrics['mape']) / baseline_mape) * 100

                    improvements[model_name] = {
                        'rmse_improvement_pct': round(rmse_imp, 2),
                        'mape_improvement_pct': round(mape_imp, 2)
                    }

            return {
                'item_code': item_code,
                'pattern': pattern,
                'metrics': pattern_info['metrics'],
                'confidence': pattern_info['confidence'],
                'models': models,
                'improvements': improvements,
                'winning_model': tournament_result.get('winning_model', 'unknown'),
                'train_size': len(train),
                'test_size': len(test)
            }

        except Exception as e:
            return {'error': str(e), 'item_code': item_code}

    def run_real_data_benchmark(self, max_items_per_pattern: int = 10):
        """Run comprehensive benchmark on real SAP B1 data"""
        print("\n" + "="*80)
        print("REAL SAP B1 DATA BENCHMARK")
        print("="*80)

        # Load data
        df_sales = self.load_real_data()

        # Sample items by pattern
        sampled_items = self.sample_items_by_pattern(df_sales, max_items_per_pattern)

        # Benchmark each item
        all_results = []

        for pattern, item_codes in sampled_items.items():
            print(f"\n{'='*60}")
            print(f"Testing {pattern.upper()} pattern ({len(item_codes)} items)")
            print(f"{'='*60}")

            for i, item_code in enumerate(item_codes, 1):
                print(f"\n[{i}/{len(item_codes)}] Testing item: {item_code}")
                result = self.benchmark_item(df_sales, item_code)

                if 'error' not in result:
                    all_results.append(result)
                    self.results['items'][item_code] = result

                    # Print summary
                    print(f"  Pattern: {result['pattern']} (confidence: {result['confidence']})")
                    print(f"  Winning Model: {result['winning_model']}")

                    # Show best improvement
                    if result['improvements']:
                        best_model = max(result['improvements'].items(),
                                       key=lambda x: x[1]['rmse_improvement_pct'])
                        print(f"  Best Improvement: {best_model[0]} +{best_model[1]['rmse_improvement_pct']:.2f}% RMSE")
                else:
                    print(f"  Error: {result['error']}")

        self.results['metadata']['items_tested'] = len(all_results)

        # Calculate summary statistics
        self.calculate_summary_statistics(all_results)

        return self.results

    def calculate_summary_statistics(self, all_results: List[Dict]):
        """Calculate summary statistics across all tested items"""

        # Group by pattern
        by_pattern = defaultdict(lambda: {'items': [], 'improvements': defaultdict(list)})

        for result in all_results:
            pattern = result['pattern']
            by_pattern[pattern]['items'].append(result)

            # Collect improvements
            for model, imp in result['improvements'].items():
                by_pattern[pattern]['improvements'][model].append(imp['rmse_improvement_pct'])

        # Calculate average improvements per pattern
        for pattern, data in by_pattern.items():
            avg_improvements = {}
            for model, improvements in data['improvements'].items():
                if improvements:
                    avg_improvements[model] = round(np.mean(improvements), 2)

            self.results['summary']['by_pattern'][pattern] = {
                'n_items': len(data['items']),
                'avg_improvements': avg_improvements
            }

        # Overall best models
        all_improvements = defaultdict(list)
        for result in all_results:
            for model, imp in result['improvements'].items():
                all_improvements[model].append(imp['rmse_improvement_pct'])

        overall_avg = {}
        for model, improvements in all_improvements.items():
            if improvements:
                overall_avg[model] = round(np.mean(improvements), 2)

        self.results['summary']['best_models'] = {
            'overall_average_improvements': overall_avg
        }

        # Calculate business impact
        self.calculate_business_impact(all_results)

    def calculate_business_impact(self, all_results: List[Dict]):
        """Calculate business impact metrics"""

        total_items = len(all_results)
        items_with_improvement = 0

        # Count items where best model improves over SMA
        total_improvement = 0
        best_model_counts = defaultdict(int)

        for result in all_results:
            if result['improvements']:
                best_model = max(result['improvements'].items(),
                               key=lambda x: x[1]['rmse_improvement_pct'])

                if best_model[1]['rmse_improvement_pct'] > 0:
                    items_with_improvement += 1
                    total_improvement += best_model[1]['rmse_improvement_pct']
                    best_model_counts[best_model[0]] += 1

        self.results['summary']['business_impact'] = {
            'total_items_tested': total_items,
            'items_with_improvement': items_with_improvement,
            'pct_items_improved': round((items_with_improvement / total_items * 100) if total_items > 0 else 0, 2),
            'avg_improvement_per_item': round(total_improvement / items_with_improvement, 2) if items_with_improvement > 0 else 0,
            'best_model_distribution': dict(best_model_counts)
        }

    def print_summary(self):
        """Print real data benchmark summary"""
        print("\n" + "="*80)
        print("REAL DATA BENCHMARK SUMMARY")
        print("="*80)

        print(f"\nItems Tested: {self.results['metadata']['items_tested']}")

        print("\n--- PERFORMANCE BY DEMAND PATTERN ---")
        for pattern, data in self.results['summary']['by_pattern'].items():
            print(f"\n{pattern.upper()} ({data['n_items']} items):")
            if data['avg_improvements']:
                # Sort by improvement
                sorted_models = sorted(data['avg_improvements'].items(),
                                     key=lambda x: x[1], reverse=True)
                for model, imp in sorted_models[:3]:
                    print(f"  {model:20} -> +{imp:6.2f}% avg RMSE improvement")

        print("\n--- OVERALL BEST MODELS ---")
        if self.results['summary']['best_models']['overall_average_improvements']:
            sorted_models = sorted(
                self.results['summary']['best_models']['overall_average_improvements'].items(),
                key=lambda x: x[1], reverse=True
            )
            for model, imp in sorted_models[:5]:
                print(f"  {model:20} -> +{imp:6.2f}% avg RMSE improvement")

        print("\n--- BUSINESS IMPACT ---")
        impact = self.results['summary']['business_impact']
        print(f"  Items with improvement: {impact['items_with_improvement']}/{impact['total_items_tested']} ({impact['pct_items_improved']}%)")
        print(f"  Avg improvement per item: +{impact['avg_improvement_per_item']}%")
        print(f"\n  Best Model Distribution:")
        for model, count in sorted(impact['best_model_distribution'].items(),
                                   key=lambda x: x[1], reverse=True):
            print(f"    {model:20} : {count:2} items")

        print("\n" + "="*80)

    def save_results(self, filepath: str = None):
        """Save results to JSON"""
        if filepath is None:
            filepath = Path(__file__).parent.parent / 'real_data_benchmark_results.json'

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\nResults saved to: {filepath}")
        return filepath


def main():
    """Run real data benchmark"""
    bm = RealDataBenchmark()
    results = bm.run_real_data_benchmark(max_items_per_pattern=10)
    bm.save_results()
    bm.print_summary()


if __name__ == '__main__':
    main()
