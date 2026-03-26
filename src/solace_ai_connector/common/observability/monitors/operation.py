"""Monitor for generic internal operations."""

from .base import Monitor, MonitorInstance


class OperationMonitor(Monitor):
    """
    Monitor for internal operation duration.

    Maps to: operation.duration histogram
    Labels: type, component.name, operation.name, error.type

    The 'type' label allows grouping similar components for querying.
    """

    monitor_type = "operation.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Generic error categorization."""
        if isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, ValueError):
            return "validation_error"
        return exc.__class__.__name__

    @classmethod
    def instance(cls, component_type: str, component_name: str, operation: str) -> MonitorInstance:
        """
        Create operation monitor instance.

        Args:
            component_type: Grouping category (e.g., "orchestrator", "agent", "connector")
            component_name: Specific component (e.g., "AgentOrchestrator", "SolaceConnector")
            operation: Operation name (e.g., "execute", "process_message")
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "type": component_type,
                "component.name": component_name,
                "operation.name": operation
            },
            error_parser=cls.parse_error
        )