"""Monitor for GenAI token usage tracking."""

from .base import Monitor, MonitorInstance


class GenAITokenMonitor(Monitor):
    """
    Monitor for GenAI token usage.

    Maps to: gen_ai.tokens.used counter
    Labels: gen_ai.request.model, component.name, owner.id, gen_ai.token.type

    Label usage:
    - SAM/SAMe: component.name=agent_id, owner.id=user_id
    - Connector: component.name=flow_name, owner.id="none"

    Note: This monitor does not use error_parser (counters are not wrapped in error handling).
    """

    monitor_type = "gen_ai.tokens.used"

    @classmethod
    def create(cls, model: str, component_name: str, owner_id: str, token_type: str) -> MonitorInstance:
        """Create token usage monitor instance.

        Args:
            model: Model name (e.g., "gpt-4", "claude-sonnet-3.5")
            component_name: SAM: agent identifier, Connector: flow name
            owner_id: SAM: user identifier, Connector: "none"
            token_type: "input" or "output"
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "gen_ai.request.model": model,
                "component.name": component_name,
                "owner.id": owner_id,
                "gen_ai.token.type": token_type
            },
            error_parser=None  # Counters don't use error handling
        )