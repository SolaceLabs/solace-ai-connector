"""Histogram recorder for duration metrics."""

import logging
from typing import Dict, List, Set
from opentelemetry.metrics import Histogram

from .base import MetricRecorder

log = logging.getLogger(__name__)


class HistogramRecorder(MetricRecorder):
    """
    Recorder for histogram metrics (duration distributions).

    Wraps OpenTelemetry Histogram and applies label filtering.
    """

    def __init__(self, histogram: Histogram, buckets: List[float], excluded_labels: List[str]):
        """
        Initialize histogram recorder.

        Args:
            histogram: OpenTelemetry Histogram instrument
            buckets: Bucket boundaries (for validation/documentation)
            excluded_labels: Labels to exclude from recording
        """
        self._histogram = histogram
        self._buckets = buckets
        self._excluded_labels: Set[str] = set(excluded_labels)

    def record(self, value: float, labels: Dict[str, str]):
        """
        Record duration value with labels.

        Args:
            value: Duration in seconds
            labels: Label key-value pairs
        """
        try:
            # Filter excluded labels
            filtered_labels = {
                k: v for k, v in labels.items()
                if k not in self._excluded_labels
            }

            # Record to OpenTelemetry histogram
            self._histogram.record(value, attributes=filtered_labels)

        except Exception as e:
            # Never crash application due to metrics
            log.warning(f"Failed to record histogram: {e}")