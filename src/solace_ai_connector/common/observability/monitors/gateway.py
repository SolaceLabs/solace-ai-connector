"""Monitors for gateway operations."""

from .base import Monitor, MonitorInstance


class GatewayMonitor(Monitor):
    """
    Abstract monitor for gateway request duration.

    Maps to: gateway.duration histogram
    Labels: gateway.name, operation.name, error.type

    Concrete implementations provided by downstream repos (SAM/SAMe).
    """

    monitor_type = "gateway.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Categorize as client vs server errors."""
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return "client_error"
        if isinstance(exc, (RuntimeError, OSError)):
            return "server_error"
        if hasattr(exc, 'status_code'):
            code = exc.status_code
            if 400 <= code < 500:
                return "4xx_error"
            if 500 <= code < 600:
                return "5xx_error"
            return f"http_{code}"
        return exc.__class__.__name__


class GatewayTTFBMonitor(Monitor):
    """
    Abstract monitor for gateway Time-To-First-Byte duration.

    Maps to: gateway.ttfb.duration histogram
    Labels: gateway.name, operation.name, error.type

    Concrete implementations provided by downstream repos (SAM/SAMe).
    """

    monitor_type = "gateway.ttfb.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Same error categorization as GatewayMonitor."""
        return GatewayMonitor.parse_error(exc)