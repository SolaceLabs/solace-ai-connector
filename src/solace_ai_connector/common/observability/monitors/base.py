"""Base classes for observability monitors."""

from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional
from dataclasses import dataclass


@dataclass
class MonitorInstance:
    """
    Monitor instance returned by monitor factory methods.

    Attributes:
        monitor_type: Metric identifier (e.g., 'gen_ai.client.operation.duration', 'gen_ai.tokens.used')
        labels: Label key-value pairs for this metric instance
        error_parser: Optional function to categorize exceptions into error label values.
                     Used by histogram monitors wrapped in MonitorLatency context manager.
                     Counters/gauges set this to None as they don't use error handling.
    """
    monitor_type: str
    labels: Dict[str, str]
    error_parser: Optional[Callable[[Exception], str]] = None

    def _update_label(self, key: str, value: str) -> None:
        """
        Internal method to update a label value.

        Should only be called by specialized monitor subclasses via their typed methods.
        NOT to be called directly by user code.
        """
        self.labels[key] = value


class Monitor(ABC):
    """
    Abstract base class for all monitors.

    Each monitor class maps to one metric and defines:
    - The monitor_type identifier
    - Factory methods that return MonitorInstance objects
    - Optional: Error parsing logic (for histogram monitors)
    """

    @property
    @abstractmethod
    def monitor_type(self) -> str:
        """Metric identifier (e.g., 'gen_ai.client.operation.duration', 'gen_ai.tokens.used')."""
        pass

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """
        Optional: Override in monitors that need error categorization.

        Default implementation for monitors that don't use error parsing (counters, gauges).
        Histogram monitors should override this with domain-specific error categorization.
        """
        return exc.__class__.__name__