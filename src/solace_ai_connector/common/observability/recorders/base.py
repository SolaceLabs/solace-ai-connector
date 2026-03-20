"""Base class for metric recorders."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class MetricRecorder(ABC):
    """Abstract base for metric recorders."""

    @abstractmethod
    def record(self, value: Any, labels: Dict[str, str]):
        """Record a metric value with labels."""
        pass


class NoOpRecorder(MetricRecorder):
    """Silent no-op recorder returned when observability is disabled."""

    def record(self, value: Any, labels: Dict[str, str]):
        """Record a metric value with labels (no-op)."""
        pass