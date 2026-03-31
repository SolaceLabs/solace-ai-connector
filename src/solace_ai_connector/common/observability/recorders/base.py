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


class NoOpObservableGauge:
    """
    Silent no-op observable gauge returned when observability is disabled.

    Mimics OpenTelemetry ObservableGauge interface but does nothing.
    Allows consistent Null Object pattern across all metric creation methods.
    """
    pass  # Observable gauges are callback-based - no methods to implement