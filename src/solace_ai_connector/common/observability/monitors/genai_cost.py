"""Monitor for GenAI cost tracking."""

from .base import Monitor, MonitorInstance


class GenAICostMonitor(Monitor):
    """
    Monitor for GenAI cost tracking.
    """
    monitor_type = "gen_ai.cost.total"
    @classmethod
    def create(cls, model: str, component_name: str, owner_id: str) -> MonitorInstance:
        """Create cost tracking monitor instance.

        Args:
            model: Model name (e.g., "gpt-4", "claude-sonnet-3.5")
            component_name: SAM: agent identifier, Connector: flow name
            owner_id: SAM: user identifier, Connector: "none"
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "gen_ai.request.model": model,
                "component.name": component_name,
                "owner.id": owner_id
            },
            error_parser=None
        )