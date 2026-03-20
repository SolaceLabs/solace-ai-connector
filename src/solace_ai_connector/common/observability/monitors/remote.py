"""Monitors for remote service requests."""

from .base import Monitor, MonitorInstance


class RemoteRequestMonitor(Monitor):
    """
    Abstract monitor for outbound remote service calls.

    Maps to: outbound.request.duration histogram
    Labels: service.peer.name, operation.name, error.type

    Concrete implementations (S3Monitor, OAuthMonitor, Broker, etc.) provided by downstream repos.
    """

    monitor_type = "outbound.request.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Map exceptions to HTTP-style error categories."""
        if isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, ConnectionError):
            return "connection_error"
        if hasattr(exc, 'status_code'):
            code = exc.status_code
            if 400 <= code < 500:
                return f"4xx_error"
            if 500 <= code < 600:
                return f"5xx_error"
        return exc.__class__.__name__


class BrokerMonitor(RemoteRequestMonitor):
    """
    Monitor for Solace broker connections.

    Concrete implementation provided by solace-ai-connector for broker operations.
    """
    @classmethod
    def publish(cls) -> MonitorInstance:
        """Create monitor instance for broker publish operation."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "service.peer.name": "solace_broker",
                "operation.name": "publish"
            },
            error_parser=cls.parse_error
        )