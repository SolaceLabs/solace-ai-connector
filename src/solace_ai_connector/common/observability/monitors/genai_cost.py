"""Monitor for GenAI cost tracking."""

from .base import Monitor, MonitorInstance


class GenAICostMonitor(Monitor):
    """
    Monitor for GenAI cost tracking.

    Maps to: gen_ai.cost.total counter
    Labels: gen_ai.request.model, component.name, owner.id

    Label usage:
    - SAM/SAMe: component.name=agent_id, owner.id=user_id
    - Connector: component.name=flow_name, owner.id="none"

    Note: This monitor does not use error_parser (counters are not wrapped in error handling).
    """

    monitor_type = "gen_ai.cost.total"

    @classmethod
    def create(cls, model: str, component_name: str, owner_id: str) -> MonitorInstance:
        """
        Create cost tracking monitor instance.

        Args:
            model: Model name (e.g., "gpt-4", "claude-sonnet-3.5")
            component_name: SAM: agent identifier, Connector: flow name
            owner_id: SAM: user identifier, Connector: "none"

        Returns:
            MonitorInstance for cost tracking

        Usage:
            # In SAM:
            monitor = GenAICostMonitor.create(
                model="gpt-4",
                component_name="OrchestratorAgent",
                owner_id="user@example.com"
            )

            # In Connector:
            monitor = GenAICostMonitor.create(
                model="gpt-4",
                component_name="test_flow",
                owner_id="none"
            )

            registry.record_counter_from_monitor(monitor, cost_usd)
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "gen_ai.request.model": model,
                "component.name": component_name,
                "owner.id": owner_id
            },
            error_parser=None  # Counters don't use error handling
        )