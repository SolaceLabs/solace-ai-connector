"""Base classes for observability monitors."""

from abc import ABC, abstractmethod
from typing import Dict, Callable
from dataclasses import dataclass


@dataclass
class MonitorInstance:
    """
    Monitor instance returned by monitor factory methods.

    Attributes:
        monitor_type: Histogram family identifier (e.g., 'remote_request', 'gen_ai')
        labels: Label key-value pairs for this metric instance
        error_parser: Function to categorize exceptions into error label values
    """
    monitor_type: str
    labels: Dict[str, str]
    error_parser: Callable[[Exception], str]


class Monitor(ABC):
    """
    Abstract base class for all monitors.

    Each monitor class maps to one histogram family and defines:
    - The monitor_type identifier
    - Error parsing logic for that domain
    - Factory methods that return MonitorInstance objects
    """

    @property
    @abstractmethod
    def monitor_type(self) -> str:
        """Histogram family identifier (e.g., 'remote_request', 'gen_ai')."""
        pass

    @staticmethod
    @abstractmethod
    def parse_error(exc: Exception) -> str:
        """
        Convert exception to error label value.

        Each monitor subclass implements domain-specific error categorization.
        """
        pass