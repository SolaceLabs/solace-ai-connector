"""Counter recorder for event counting."""

import logging
from typing import Dict, List, Set
from opentelemetry.metrics import Counter

from .base import MetricRecorder

logger = logging.getLogger(__name__)


class CounterRecorder(MetricRecorder):
    """
    Recorder for counter metrics (monotonically increasing values).

    Examples: request count, cache hits, errors.
    """

    def __init__(self, counter: Counter, excluded_labels: List[str]):
        """
        Initialize counter recorder.

        Args:
            counter: OpenTelemetry Counter instrument
            excluded_labels: Labels to exclude from recording
        """
        self._counter = counter
        self._excluded_labels: Set[str] = set(excluded_labels)

    def record(self, value: int, labels: Dict[str, str]):
        """
        Increment counter.

        Args:
            value: Amount to increment (typically 1)
            labels: Label key-value pairs
        """
        try:
            # Filter excluded labels
            filtered_labels = {
                k: v for k, v in labels.items()
                if k not in self._excluded_labels
            }

            # Record to OpenTelemetry counter
            self._counter.add(value, attributes=filtered_labels)
        except Exception as e:
            logger.warning("Failed to record counter: %s", e)