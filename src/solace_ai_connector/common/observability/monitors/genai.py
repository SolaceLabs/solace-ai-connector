"""Monitors for GenAI operations."""

from .base import Monitor, MonitorInstance


class GenAIMonitor(Monitor):
    """
    Monitor for GenAI operation duration.

    Maps to: gen_ai.client.operation.duration histogram
    Labels: gen_ai.request.model, tokens, error.type

    Note: tokens label is excluded by default in config to reduce cardinality.
    """

    monitor_type = "gen_ai.client.operation.duration"

    @staticmethod
    def _bucketize_tokens(tokens: int) -> str:
        """
        Bucket tokens to control cardinality.

        Buckets: 1000, 5000, 10000, 50000, 100000, 200000
        """
        if tokens <= 1000:
            return "1000"
        if tokens <= 5000:
            return "5000"
        if tokens <= 10000:
            return "10000"
        if tokens <= 50000:
            return "50000"
        if tokens <= 100000:
            return "100000"
        return "200000"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Categorize AI-specific errors."""
        if isinstance(exc, TimeoutError):
            return "timeout"
        if hasattr(exc, 'status_code'):
            return f"api_error_{exc.status_code}"

        exc_str = str(exc).lower()
        if "rate_limit" in exc_str or "rate limit" in exc_str:
            return "rate_limit"
        if "context_length" in exc_str or "context length" in exc_str:
            return "context_length_exceeded"

        return exc.__class__.__name__

    @classmethod
    def instance(cls, model: str, tokens: int):
        """
        Create GenAI monitor instance.

        Args:
            model: Model name from configuration (e.g., "gpt-4", "claude-sonnet-3.5")
            tokens: Total tokens (input + output) for bucketization
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "gen_ai.request.model": model,
                "tokens": cls._bucketize_tokens(tokens)
            },
            error_parser=cls.parse_error
        )


class GenAITTFTMonitor(Monitor):
    """
    Monitor for GenAI Time-To-First-Token duration.

    Maps to: gen_ai.client.operation.ttft.duration histogram
    Labels: gen_ai.request.model, error.type
    """

    monitor_type = "gen_ai.client.operation.ttft.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Same error categorization as GenAIMonitor."""
        return GenAIMonitor.parse_error(exc)

    @classmethod
    def instance(cls, model: str):
        """
        Create GenAI TTFT monitor instance.

        Args:
            model: Model name from configuration
        """
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={"gen_ai.request.model": model},
            error_parser=cls.parse_error
        )