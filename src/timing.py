"""
Performance timing utilities for tracking operation durations.
"""
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


# Dictionary to store timing statistics
_timings = {}

def reset_timings():
    """Clear all timing statistics."""
    global _timings
    _timings = {}


def get_timings():
    """Get all timing statistics."""
    return _timings.copy()


def timed_operation(operation_name):
    """
    Decorator to time function execution and log results.

    Usage:
        @timed_operation("My Operation")
        def my_function():
            # ... code ...
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start

                # Store timing
                if operation_name not in _timings:
                    _timings[operation_name] = []
                _timings[operation_name].append(duration)

                # Log timing
                if duration < 1:
                    logger.info(f"[TIMING] {operation_name}: {duration*1000:.0f}ms")
                elif duration < 60:
                    logger.info(f"[TIMING] {operation_name}: {duration:.2f}s")
                else:
                    logger.info(f"[TIMING] {operation_name}: {duration/60:.1f}min")

                return result
            except Exception as e:
                duration = time.time() - start
                logger.error(f"[TIMING] {operation_name}: FAILED after {duration:.2f}s - {e}")
                raise
        return wrapper
    return decorator


class Timer:
    """
    Context manager for timing code blocks.

    Usage:
        with Timer("Data Loading"):
            # ... code ...
            pass
    """
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        logger.info(f"[TIMING] {self.operation_name}: Starting...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start

        # Store timing
        if self.operation_name not in _timings:
            _timings[self.operation_name] = []
        _timings[self.operation_name].append(duration)

        # Log timing
        if exc_type is not None:
            logger.error(f"[TIMING] {self.operation_name}: FAILED after {duration:.2f}s")
        else:
            if duration < 1:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration*1000:.0f}ms")
            elif duration < 60:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration:.2f}s")
            else:
                logger.info(f"[TIMING] {self.operation_name}: Completed in {duration/60:.1f}min")

        return False  # Don't suppress exceptions


def print_timing_summary():
    """Print a summary of all timing statistics."""
    global _timings

    if not _timings:
        logger.info("[TIMING] No timing statistics available")
        return

    logger.info("=" * 60)
    logger.info("PERFORMANCE TIMING SUMMARY")
    logger.info("=" * 60)

    total_time = 0
    for op_name, durations in sorted(_timings.items()):
        count = len(durations)
        total = sum(durations)
        avg = total / count
        total_time += total

        # Format time appropriately
        if avg < 1:
            time_str = f"{avg*1000:.0f}ms avg"
        elif avg < 60:
            time_str = f"{avg:.2f}s avg"
        else:
            time_str = f"{avg/60:.1f}min avg"

        logger.info(f"  {op_name}:")
        logger.info(f"    Runs: {count}, Total: {total:.2f}s, {time_str}")

    logger.info("-" * 60)

    if total_time < 60:
        logger.info(f"Total Pipeline Time: {total_time:.2f}s")
    else:
        logger.info(f"Total Pipeline Time: {total_time/60:.1f} minutes")

    logger.info("=" * 60)
