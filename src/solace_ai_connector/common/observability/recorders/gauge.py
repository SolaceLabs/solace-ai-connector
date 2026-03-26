"""Gauge recorder for point-in-time values."""

import logging
from typing import Dict, List, Set
from opentelemetry.metrics import UpDownCounter

from .base import MetricRecorder

logger = logging.getLogger(__name__)


class GaugeRecorder(MetricRecorder):
    """
    Recorder for push-style gauge metrics (values that can go up or down).

    Uses OpenTelemetry UpDownCounter for tracking values that can increase or decrease.
    Examples: cache size, queue depth, active connections.
    """

    def __init__(self, gauge: UpDownCounter, excluded_labels: List[str]):
        """
        Initialize gauge recorder.

        Args:
            gauge: OpenTelemetry UpDownCounter instrument
            excluded_labels: Labels to exclude from recording
        """
        self._gauge = gauge
        self._excluded_labels: Set[str] = set(excluded_labels)

    def record(self, value: int, labels: Dict[str, str]):
        """
        Record gauge value (can be positive or negative).

        Args:
            value: Amount to add (positive for increment, negative for decrement)
            labels: Label key-value pairs
        """
        try:
            # Filter excluded labels
            filtered_labels = {
                k: v for k, v in labels.items()
                if k not in self._excluded_labels
            }

            # Record to OpenTelemetry gauge
            self._gauge.add(value, attributes=filtered_labels)
        except Exception as e:
            logger.warning("Failed to record gauge: %s", e)