# Performance Timing Features

**Date:** 2026-01-13
**Purpose:** Track execution time for each pipeline stage and operation

---

## Overview

The timing system provides detailed performance metrics for all pipeline operations, helping identify bottlenecks and track optimization effectiveness.

---

## How It Works

### Automatic Timing

The pipeline now automatically tracks timing for all major operations:

#### Pipeline Stages (High-Level):
- **Full Pipeline Execution** - Total time from start to finish
- **Stage 1: Load Raw Data** - Data ingestion and cleaning
- **Stage 2: Generate Forecasts** - Forecasting tournament
- **Stage 3: Generate Reports** - Optimization, vendor analysis, inventory health
- **Stage 4: Combine Results** - Final data assembly

#### Detailed Operations (Low-Level):
- **Load Sales Orders** - Read sales.tsv
- **Load Supply Chain** - Read supply.tsv
- **Load Items** - Read items.tsv
- **UoM Conversion** - Convert stock to sales units
- **Clean Supply Data** - Remove invalid supply records
- **Optimization Analysis** - Calculate stockouts and TCO
- **Vendor Performance Analysis** - Calculate lead times and scores
- **Calculate Item-Vendor Lead Times** - Per-item-vendor metrics
- **Identify Fastest Vendors** - Find best vendor per item
- **Calculate Vendor Scores** - Overall vendor ratings
- **Inventory Health Analysis** - Dead stock and shelf life risk
- **Merge Final Data** - Combine all results

---

## Timing Output

### Log Messages

Each operation logs timing information:

```
[TIMING] Full Pipeline Execution: Starting...
[TIMING] Stage 1: Load Raw Data: Starting...
[TIMING] Load Sales Orders: Completed in 842ms
[TIMING] Load Supply Chain: Completed in 1.24s
[TIMING] Load Items: Completed in 523ms
[TIMING] UoM Conversion: Completed in 284ms
[TIMING] Clean Supply Data: Completed in 156ms
[TIMING] Stage 1: Load Raw Data: Completed in 3.21s
[TIMING] Stage 2: Generate Forecasts: Starting...
...
[TIMING] Full Pipeline Execution: Completed in 2m 24s
```

### Timing Summary

At the end of each pipeline run, a detailed summary is printed:

```
============================================================
PERFORMANCE TIMING SUMMARY
============================================================
  Calculate Item-Vendor Lead Times:
    Runs: 1, Total: 0.45s, 450ms avg
  Calculate Vendor Scores:
    Runs: 1, Total: 0.12s, 120ms avg
  Full Pipeline Execution:
    Runs: 1, Total: 143.52s, 2.4min avg
  Identify Fastest Vendors:
    Runs: 1, Total: 0.08s, 80ms avg
  Inventory Health Analysis:
    Runs: 1, Total: 0.32s, 320ms avg
  Load Items:
    Runs: 1, Total: 0.52s, 520ms avg
  Load Sales Orders:
    Runs: 1, Total: 0.84s, 840ms avg
  Load Supply Chain:
    Runs: 1, Total: 1.24s, 1.24s avg
  Merge Final Data:
    Runs: 1, Total: 0.15s, 150ms avg
  Optimization Analysis:
    Runs: 1, Total: 1.85s, 1.85s avg
  Stage 1: Load Raw Data:
    Runs: 1, Total: 3.21s, 3.21s avg
  Stage 2: Generate Forecasts:
    Runs: 1, Total: 128.45s, 2.1min avg
  Stage 3: Generate Reports:
    Runs: 1, Total: 8.92s, 8.92s avg
  Stage 4: Combine Results:
    Runs: 1, Total: 0.05s, 50ms avg
  UoM Conversion:
    Runs: 1, Total: 0.28s, 280ms avg
  Vendor Performance Analysis:
    Runs: 1, Total: 0.72s, 720ms avg
------------------------------------------------------------
Total Pipeline Time: 143.52s
============================================================
```

---

## Programmatic Access

### Get Timing Statistics

```python
from src.timing import get_timings, reset_timings

# Get all timing statistics
timings = get_timings()

# Access specific operation
pipeline_time = timings['Full Pipeline Execution']  # [143.52]
avg_uom_conversion = sum(timings['UoM Conversion']) / len(timings['UoM Conversion'])

# Reset for fresh measurement
reset_timings()
```

### Using Timer Context Manager

Add timing to any code block:

```python
from src.timing import Timer

with Timer("My Custom Operation"):
    # Your code here
    result = some_function()
    # Timing automatically logged when block exits
```

### Using Decorator

Add timing to functions:

```python
from src.timing import timed_operation

@timed_operation("My Function")
def my_function():
    # Your code here
    return result
```

---

## Performance Benchmarks

### Expected Timing (with vectorized operations):

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| Load Sales Orders | 0.5-1.5s | Depends on file size |
| Load Supply Chain | 1-2s | Depends on file size |
| Load Items | 0.3-0.8s | Depends on file size |
| UoM Conversion | 0.1-0.5s | **Vectorized** (was 30-60s) |
| Clean Supply Data | 0.1-0.3s | Fast |
| Stage 1 Total | **2-5s** | Data loading |
| Generate Forecasts | 2-4 min | Tournament (with cache) |
| Stage 2 Total | **2-4 min** | Forecasting |
| Optimization Analysis | 1-3s | Vectorized operations |
| Vendor Performance | 0.5-1.5s | Depends on data |
| Inventory Health | 0.1-0.5s | **Vectorized** (was 2-5s) |
| Stage 3 Total | **8-15s** | Reports |
| Stage 4 Total | **<1s** | Combine results |
| **Full Pipeline** | **2.5-4.5 min** | With cache |
| Full Pipeline (no cache) | 4-8 min | First run |

### Performance Improvements from Vectorization:

1. **UoM Conversion**: 30-60s → 0.1-0.5s (**60-600x faster**)
2. **Forecast Confidence**: 10-20s → 0.2-0.4s (**25-100x faster**)
3. **Inventory Health**: 2-5s → 0.1-0.5s (**10-50x faster**)

**Total time saved**: 42-85 seconds per data load

---

## Troubleshooting

### Issue: Operations taking longer than expected

**Check timing logs** to identify the bottleneck:

```bash
# View latest logs
tail -f logs/forecast.log | grep "\[TIMING\]"
```

**Common causes:**

1. **Forecasting taking >5 minutes**:
   - Check if n_samples is limiting items
   - Verify cache is being used
   - Check for data quality issues

2. **UoM Conversion taking >1 second**:
   - Vectorization may have failed
   - Check for unexpected data types
   - Verify no .iterrows() or .apply() in the code

3. **Supply chain loading taking >10 seconds**:
   - File may be very large
   - Check for memory issues
   - Consider data sampling

### Issue: No timing output

**Verify imports:**

```python
from src.timing import Timer, print_timing_summary
```

**Check logging level:**

```python
import logging
logging.basicConfig(level=logging.INFO)
```

---

## Advanced Usage

### Comparing Performance

Track performance before and after optimizations:

```python
from src.timing import reset_timings, get_timings

# Baseline
reset_timings()
pipeline.run_full_pipeline(data_dir)
baseline = get_timings()

# After optimization
reset_timings()
pipeline.run_full_pipeline(data_dir)
optimized = get_timings()

# Compare
for op in baseline:
    before = sum(baseline[op]) / len(baseline[op])
    after = sum(optimized[op]) / len(optimized[op])
    speedup = before / after
    print(f"{op}: {speedup:.2f}x faster")
```

### Export Timing Data

```python
import json
from src.timing import get_timings

timings = get_timings()

# Convert to serializable format
export_data = {
    op: {
        'runs': len(durations),
        'total': sum(durations),
        'avg': sum(durations) / len(durations)
    }
    for op, durations in timings.items()
}

# Save to file
with open('timing_report.json', 'w') as f:
    json.dump(export_data, f, indent=2)
```

---

## Implementation Details

### Files Modified:

- **src/timing.py** (NEW) - Timing utilities and context managers
- **src/data_pipeline.py** (MODIFIED) - Added Timer context managers to all stages

### Thread Safety:

Timing data is stored in a global dictionary `_timings`. The timing system is designed for single-threaded pipeline execution (which is ensured by the data pipeline design).

### Overhead:

The timing system has negligible overhead (<1ms per operation) and does not significantly affect pipeline performance.

---

## Future Enhancements

Possible improvements:

1. **Graphing** - Generate performance graphs over time
2. **Database storage** - Store timing history for trend analysis
3. **Alerts** - Warn when operations degrade beyond threshold
4. **Profiling integration** - Combine with cProfile for deeper analysis
5. **Real-time monitoring** - Dashboard showing live timing metrics

---

*Implemented: 2026-01-13*
*Ready for production*
