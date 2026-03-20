"""Instrumentation API for observability."""

import time
import asyncio
import functools
import logging
from typing import Optional

from .monitors.base import MonitorInstance
from .registry import MetricRegistry

logger = logging.getLogger(__name__)


class MonitorLatency:
    """
    Context manager for latency tracking.

    Overhead: < 10μs for typical operation

    Supports:
    - Decorator usage: @MonitorLatency(service=...)
    - Sync context: with MonitorLatency(service=...)
    - Async context: async with MonitorLatency(service=...)
    - Manual: monitor.start() / monitor.stop()
    """

    def __init__(self, service: MonitorInstance):
        self._instance = service
        self._registry = MetricRegistry.get_instance()
        self._start_time: Optional[float] = None

    def __enter__(self):
        self._start_time = time.perf_counter()  # ~50ns
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            duration = time.perf_counter() - self._start_time

            # Fast path: check if recorder exists
            recorder = self._registry.get_recorder(self._instance.monitor_type)
            if recorder is None:
                return  # Skip recording - zero overhead
            # Add error label if exception occurred
            labels = self._instance.labels.copy()
            if exc_type is not None:
                try:
                    labels['error.type'] = self._instance.error_parser(exc_val)
                except Exception as parse_err:
                    logger.warning("Error parser failed: %s", parse_err)
                    labels['error.type'] = 'error'
            else:
                labels['error.type'] = 'none'
            try:
                recorder.record(duration, labels)
            except Exception as record_err:
                logger.warning("Failed to record metric: %s", record_err)
        except Exception as e:
            logger.error("MonitorLatency.__exit__ failed: %s", e)
        # Don't suppress original exception
        return False

    async def __aenter__(self):
        self._start_time = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Same logic as __exit__
        return self.__exit__(exc_type, exc_val, exc_tb)

    def __call__(self, func):
        """Decorator support."""
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with self:
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)
            return sync_wrapper

    def start(self):
        """Manual start."""
        self._start_time = time.perf_counter()
        return self

    def stop(self):
        """Manual stop - records metric with error.type='none' (success)."""
        self.__exit__(None, None, None)

    def error(self, exc: Exception):
        """
        Manual stop with error - records metric with error.type from exception.

        Args:
            exc: The exception that occurred

        Usage:
            monitor = MonitorLatency(service)
            monitor.start()
            try:
                risky_operation()
                monitor.stop()
            except Exception as e:
                monitor.error(e)
                raise
        """
        self.__exit__(type(exc), exc, exc.__traceback__)