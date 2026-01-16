"""
Performance Benchmarking Suite for SR&ED Substantiation
Measures accuracy improvements from advanced forecasting models
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from typing import Dict, List, Tuple
import json
from datetime import datetime

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


class PerformanceBenchmark:
    """Benchmarking suite for forecasting model comparison"""

    def __init__(self):
        self.results = {
            'baseline_models': {},
            'advanced_models': {},
            'ensemble_models': {},
            'improvements': {},
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'test_scenarios': []
            }
        }

    def generate_test_data(self, pattern: str, n_months: int = 36) -> pd.DataFrame:
        """
        Generate synthetic test data with specific patterns

        Parameters:
        -----------
        pattern : str
            Type of pattern: 'stable', 'trending', 'seasonal', 'intermittent'
        n_months : int
            Number of months of data to generate

        Returns:
        --------
        pd.DataFrame
            Test sales data with date, item_code, qty columns
        """
        dates = pd.date_range('2021-01-01', periods=n_months, freq='MS')

        if pattern == 'stable':
            # Stable demand around 100 with small noise
            base = 100
            noise = np.random.normal(0, 5, n_months)
            qty = base + noise
            qty = np.maximum(qty, 0)  # No negative values

        elif pattern == 'trending':
            # Linear upward trend
            trend = np.linspace(80, 150, n_months)
            noise = np.random.normal(0, 8, n_months)
            qty = trend + noise
            qty = np.maximum(qty, 0)

        elif pattern == 'seasonal':
            # Seasonal pattern (annual cycle)
            base = 100
            seasonal = 30 * np.sin(2 * np.pi * np.arange(n_months) / 12)
            noise = np.random.normal(0, 5, n_months)
            qty = base + seasonal + noise
            qty = np.maximum(qty, 0)

        elif pattern == 'intermittent':
            # Intermittent demand (many zeros)
            base_qty = np.random.poisson(20, n_months)
            # 60% zeros (intermittent)
            zeros = np.random.choice([0, 1], size=n_months, p=[0.6, 0.4])
            qty = base_qty * zeros

        else:
            raise ValueError(f"Unknown pattern: {pattern}")

        df = pd.DataFrame({
            'date': dates,
            'item_code': f'TEST_{pattern.upper()}',
            'qty': qty.astype(int)
        })

        return df

    def split_train_test(self, df: pd.DataFrame, train_size: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data into training and test sets"""
        n = len(df)
        split_idx = int(n * train_size)
        train = df.iloc[:split_idx].copy()
        test = df.iloc[split_idx:].copy()
        return train, test

    def prepare_series(self, df: pd.DataFrame, item_code: str) -> pd.Series:
        """Prepare monthly time series from DataFrame"""
        return prepare_monthly_data(df, item_code)

    def calculate_metrics(self, actual: pd.Series, forecast: np.array) -> Dict[str, float]:
        """Calculate RMSE and MAPE metrics"""
        # Align lengths
        min_len = min(len(actual), len(forecast))
        actual_aligned = actual.iloc[:min_len]
        forecast_aligned = forecast[:min_len]

        rmse = calculate_rmse(actual_aligned, forecast_aligned)
        mape = calculate_mape(actual_aligned, forecast_aligned)

        return {'rmse': rmse, 'mape': mape}

    def evaluate_model(self, model_func, train_series: pd.Series, test_series: pd.Series,
                      model_name: str, forecast_horizon: int = 6) -> Dict:
        """Evaluate a single model's performance"""
        try:
            forecast, rmse = model_func(train_series, test_series, forecast_horizon)

            # Calculate MAPE if we have test data
            mape = np.nan
            if len(test_series) > 0:
                min_len = min(len(test_series), len(forecast))
                if min_len > 0 and test_series.iloc[:min_len].sum() > 0:
                    mape = calculate_mape(test_series.iloc[:min_len], forecast[:min_len])

            return {
                'forecast': forecast.tolist(),
                'rmse': float(rmse) if not np.isnan(rmse) else None,
                'mape': float(mape) if not np.isnan(mape) else None,
                'status': 'success'
            }
        except Exception as e:
            return {
                'forecast': None,
                'rmse': None,
                'mape': None,
                'status': f'error: {str(e)}'
            }

    def benchmark_pattern(self, pattern: str) -> Dict:
        """Benchmark all models on a specific data pattern"""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {pattern.upper()} PATTERN")
        print(f"{'='*60}")

        # Generate test data
        df = self.generate_test_data(pattern, n_months=36)
        train_df, test_df = self.split_train_test(df, train_size=0.8)

        # Prepare series
        train_series = self.prepare_series(train_df, f'TEST_{pattern.upper()}')
        test_series = self.prepare_series(test_df, f'TEST_{pattern.upper()}')

        forecast_horizon = 6
        results = {
            'pattern': pattern,
            'train_size': len(train_series),
            'test_size': len(test_series),
            'models': {}
        }

        # Baseline Models
        print("\n--- BASELINE MODELS ---")
        baseline_models = {
            'SMA': lambda t, s, h: forecast_sma(t, s, h),
            'Holt-Winters': lambda t, s, h: forecast_holt_winters(t, s, h)
        }

        for name, model_func in baseline_models.items():
            print(f"Evaluating {name}...")
            result = self.evaluate_model(model_func, train_series, test_series, name, forecast_horizon)
            results['models'][name] = result
            if result['status'] == 'success':
                print(f"  RMSE: {result['rmse']:.2f}, MAPE: {result['mape']:.2f}%")

        # Advanced Models (requires sufficient history)
        print("\n--- ADVANCED MODELS ---")
        if len(train_series) >= 12:
            advanced_models = {
                'Theta': forecast_theta,
                'ARIMA': forecast_arima
            }

            for name, model_func in advanced_models.items():
                print(f"Evaluating {name}...")
                result = self.evaluate_model(model_func, train_series, test_series, name, forecast_horizon)
                results['models'][name] = result
                if result['status'] == 'success':
                    print(f"  RMSE: {result['rmse']:.2f}, MAPE: {result['mape']:.2f}%")

        if len(train_series) >= 24:
            print(f"Evaluating SARIMA...")
            result = self.evaluate_model(forecast_sarima, train_series, test_series, 'SARIMA', forecast_horizon)
            results['models']['SARIMA'] = result
            if result['status'] == 'success':
                print(f"  RMSE: {result['rmse']:.2f}, MAPE: {result['mape']:.2f}%")

        # Croston's Method (for intermittent)
        if pattern == 'intermittent':
            print(f"Evaluating Croston's Method...")
            result = self.evaluate_model(forecast_croston, train_series, test_series, 'Croston', forecast_horizon)
            results['models']['Croston'] = result
            if result['status'] == 'success':
                print(f"  RMSE: {result['rmse']:.2f}, MAPE: {result['mape']:.2f}%")

        # Ensemble Models
        print("\n--- ENSEMBLE MODELS ---")
        # Build results dict for ensembles
        ensemble_results = {}
        for model_name, model_result in results['models'].items():
            if model_result['status'] == 'success' and model_result['forecast'] is not None:
                ensemble_results[model_name.lower().replace('-', '_')] = {
                    'forecast': np.array(model_result['forecast']),
                    'rmse': model_result['rmse'] if model_result['rmse'] is not None else np.nan
                }

        if ensemble_results:
            # Simple Ensemble
            print("Evaluating Simple Ensemble (Mean)...")
            try:
                forecast, rmse = forecast_ensemble_simple(ensemble_results, forecast_horizon, method='mean')
                mape = np.nan
                if len(test_series) > 0:
                    min_len = min(len(test_series), len(forecast))
                    if min_len > 0 and test_series.iloc[:min_len].sum() > 0:
                        mape = calculate_mape(test_series.iloc[:min_len], forecast[:min_len])

                results['models']['Ensemble-Simple'] = {
                    'forecast': forecast.tolist(),
                    'rmse': float(rmse) if not np.isnan(rmse) else None,
                    'mape': float(mape) if not np.isnan(mape) else None,
                    'status': 'success'
                }
                print(f"  RMSE: {results['models']['Ensemble-Simple']['rmse']:.2f}, "
                      f"MAPE: {results['models']['Ensemble-Simple']['mape']:.2f}%")
            except Exception as e:
                results['models']['Ensemble-Simple'] = {
                    'forecast': None, 'rmse': None, 'mape': None, 'status': f'error: {str(e)}'
                }

            # Weighted Ensemble
            print("Evaluating Weighted Ensemble (RMSE)...")
            try:
                forecast, rmse = forecast_ensemble_weighted(ensemble_results, forecast_horizon)
                mape = np.nan
                if len(test_series) > 0:
                    min_len = min(len(test_series), len(forecast))
                    if min_len > 0 and test_series.iloc[:min_len].sum() > 0:
                        mape = calculate_mape(test_series.iloc[:min_len], forecast[:min_len])

                results['models']['Ensemble-Weighted'] = {
                    'forecast': forecast.tolist(),
                    'rmse': float(rmse) if not np.isnan(rmse) else None,
                    'mape': float(mape) if not np.isnan(mape) else None,
                    'status': 'success'
                }
                print(f"  RMSE: {results['models']['Ensemble-Weighted']['rmse']:.2f}, "
                      f"MAPE: {results['models']['Ensemble-Weighted']['mape']:.2f}%")
            except Exception as e:
                results['models']['Ensemble-Weighted'] = {
                    'forecast': None, 'rmse': None, 'mape': None, 'status': f'error: {str(e)}'
                }

        # Calculate improvements
        results['improvements'] = self.calculate_improvements(results['models'])

        return results

    def calculate_improvements(self, models: Dict) -> Dict:
        """Calculate improvements over baseline (SMA)"""
        improvements = {}

        if 'SMA' not in models or models['SMA']['rmse'] is None:
            return improvements

        baseline_rmse = models['SMA']['rmse']
        baseline_mape = models['SMA']['mape']

        for model_name, model_data in models.items():
            if model_name == 'SMA' or model_data.get('rmse') is None:
                continue

            rmse_improvement = ((baseline_rmse - model_data['rmse']) / baseline_rmse) * 100
            mape_improvement = ((baseline_mape - model_data['mape']) / baseline_mape) * 100 if baseline_mape else 0

            improvements[model_name] = {
                'rmse_improvement_pct': round(rmse_improvement, 2),
                'mape_improvement_pct': round(mape_improvement, 2)
            }

        return improvements

    def run_full_benchmark(self) -> Dict:
        """Run comprehensive benchmark across all patterns"""
        patterns = ['stable', 'trending', 'seasonal', 'intermittent']

        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARKING SUITE")
        print("SR&ED Experimental Development - Accuracy Validation")
        print("="*60)

        all_results = {}
        summary = {
            'best_model_by_pattern': {},
            'overall_improvements': {}
        }

        for pattern in patterns:
            self.results['metadata']['test_scenarios'].append(pattern)
            pattern_result = self.benchmark_pattern(pattern)
            all_results[pattern] = pattern_result

            # Find best model for this pattern
            best_model = min(
                [(name, data) for name, data in pattern_result['models'].items()
                 if data.get('rmse') is not None],
                key=lambda x: x[1]['rmse']
            )
            summary['best_model_by_pattern'][pattern] = {
                'model': best_model[0],
                'rmse': best_model[1]['rmse'],
                'mape': best_model[1]['mape']
            }

        self.results['all_patterns'] = all_results
        self.results['summary'] = summary

        # Calculate overall improvements
        self.results['overall_improvements'] = self.calculate_overall_improvements()

        return self.results

    def calculate_overall_improvements(self) -> Dict:
        """Calculate average improvements across all patterns"""
        overall = {}

        # Collect all improvements
        all_improvements = {}
        for pattern, pattern_data in self.results.get('all_patterns', {}).items():
            for model, improvement in pattern_data.get('improvements', {}).items():
                if model not in all_improvements:
                    all_improvements[model] = []
                all_improvements[model].append(improvement)

        # Calculate averages
        for model, improvements in all_improvements.items():
            avg_rmse_imp = np.mean([imp['rmse_improvement_pct'] for imp in improvements])
            avg_mape_imp = np.mean([imp['mape_improvement_pct'] for imp in improvements])
            overall[model] = {
                'avg_rmse_improvement_pct': round(avg_rmse_imp, 2),
                'avg_mape_improvement_pct': round(avg_mape_imp, 2),
                'patterns_tested': len(improvements)
            }

        return overall

    def save_results(self, filepath: str = None):
        """Save benchmark results to JSON file"""
        if filepath is None:
            filepath = Path(__file__).parent.parent / 'benchmark_results.json'

        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\nResults saved to: {filepath}")
        return filepath

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*80)
        print("BENCHMARK SUMMARY")
        print("="*80)

        print("\n--- BEST MODEL BY PATTERN ---")
        for pattern, best in self.results['summary']['best_model_by_pattern'].items():
            print(f"{pattern.upper():15} -> {best['model']:20} (RMSE: {best['rmse']:.2f}, MAPE: {best['mape']:.2f}%)")

        print("\n--- OVERALL IMPROVEMENTS (vs SMA Baseline) ---")
        if self.results.get('overall_improvements'):
            for model, imp in sorted(self.results['overall_improvements'].items(),
                                   key=lambda x: x[1]['avg_rmse_improvement_pct'],
                                   reverse=True):
                print(f"{model:20} -> RMSE: {imp['avg_rmse_improvement_pct']:+6.2f}%, "
                      f"MAPE: {imp['avg_mape_improvement_pct']:+6.2f}% "
                      f"({imp['patterns_tested']} patterns)")

        print("\n" + "="*80)


class TestBenchmarking:
    """Pytest tests for benchmarking"""

    def test_benchmark_stable_pattern(self):
        """Test benchmarking on stable demand pattern"""
        bm = PerformanceBenchmark()
        results = bm.benchmark_pattern('stable')

        assert 'models' in results
        assert 'SMA' in results['models']
        assert results['models']['SMA']['status'] == 'success'
        assert results['models']['SMA']['rmse'] is not None

    def test_benchmark_trending_pattern(self):
        """Test benchmarking on trending demand pattern"""
        bm = PerformanceBenchmark()
        results = bm.benchmark_pattern('trending')

        assert 'models' in results
        assert 'improvements' in results
        # Some model should improve over SMA for trending data
        has_improvement = any(imp['rmse_improvement_pct'] > 0
                            for imp in results['improvements'].values())
        assert has_improvement, "Expected at least one model to improve over SMA for trending data"

    def test_benchmark_seasonal_pattern(self):
        """Test benchmarking on seasonal demand pattern"""
        bm = PerformanceBenchmark()
        results = bm.benchmark_pattern('seasonal')

        assert 'models' in results
        # Theta or SARIMA should be available for seasonal data
        assert 'Theta' in results['models'] or 'SARIMA' in results['models']

    def test_benchmark_intermittent_pattern(self):
        """Test benchmarking on intermittent demand pattern"""
        bm = PerformanceBenchmark()
        results = bm.benchmark_pattern('intermittent')

        assert 'models' in results
        assert 'Croston' in results['models']
        # Croston should be available for intermittent data
        assert results['models']['Croston']['status'] == 'success'

    def test_full_benchmark_suite(self):
        """Test complete benchmark suite"""
        bm = PerformanceBenchmark()
        results = bm.run_full_benchmark()

        assert 'metadata' in results
        assert 'all_patterns' in results
        assert 'summary' in results
        assert 'overall_improvements' in results

        # Should have tested all 4 patterns
        assert len(results['metadata']['test_scenarios']) == 4

    def test_improvement_calculation(self):
        """Test improvement calculation is correct"""
        bm = PerformanceBenchmark()

        # Test data
        models = {
            'SMA': {'rmse': 100.0, 'mape': 25.0},
            'Model_A': {'rmse': 80.0, 'mape': 20.0},
            'Model_B': {'rmse': 120.0, 'mape': 30.0}
        }

        improvements = bm.calculate_improvements(models)

        # Model_A: 20% improvement in RMSE ((100-80)/100*100)
        assert improvements['Model_A']['rmse_improvement_pct'] == 20.0
        assert improvements['Model_A']['mape_improvement_pct'] == 20.0

        # Model_B: -20% (worse) in RMSE ((100-120)/100*100)
        assert improvements['Model_B']['rmse_improvement_pct'] == -20.0
        assert improvements['Model_B']['mape_improvement_pct'] == -20.0


def main():
    """Run benchmark and generate report"""
    bm = PerformanceBenchmark()
    results = bm.run_full_benchmark()
    bm.save_results()
    bm.print_summary()


if __name__ == '__main__':
    main()
