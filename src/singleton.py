"""
Singleton pattern to prevent concurrent pipeline execution.
Ensures only one pipeline runs at a time across all threads/processes.
"""
import threading
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Global lock for pipeline execution
_pipeline_lock = threading.Lock()
_pipeline_running = False
_pipeline_start_time = None

def acquire_pipeline_lock(timeout=300):
    """
    Acquire exclusive lock for pipeline execution.

    Parameters:
    -----------
    timeout : int
        Maximum time to wait for lock (seconds). Default 5 minutes.

    Returns:
    --------
    bool
        True if lock acquired, False if timeout
    """
    global _pipeline_running, _pipeline_start_time

    acquired = _pipeline_lock.acquire(blocking=True, timeout=timeout)

    if acquired:
        _pipeline_running = True
        _pipeline_start_time = time.time()
        logger.info("[LOCK] Pipeline lock acquired")
    else:
        logger.warning(f"[LOCK] Failed to acquire pipeline lock after {timeout}s")

    return acquired

def release_pipeline_lock():
    """Release pipeline execution lock."""
    global _pipeline_running, _pipeline_start_time

    if _pipeline_running:
        duration = time.time() - _pipeline_start_time
        logger.info(f"[LOCK] Pipeline lock released after {duration:.2f}s")

    _pipeline_running = False
    _pipeline_start_time = None
    _pipeline_lock.release()

def is_pipeline_running():
    """Check if pipeline is currently running."""
    return _pipeline_running

def get_pipeline_runtime():
    """Get how long the current pipeline has been running."""
    global _pipeline_start_time

    if _pipeline_start_time:
        return time.time() - _pipeline_start_time
    return 0
