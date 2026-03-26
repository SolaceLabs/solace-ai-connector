"""Monitors for GenAI operations."""

from .base import Monitor, MonitorInstance


class GenAIMonitorInstance(MonitorInstance):
    """
    Specialized monitor instance for GenAI operations.

    Provides typed method for updating prompt token count.
    """

    def set_prompt_tokens(self, token_count: int) -> None:
        """
        Update the tokens label with actual prompt token count from LLM API response.

        This is the ONLY authorized way to set token count after monitor creation.

        Args:
            token_count: Actual prompt_tokens from LLM API response (response.usage.prompt_tokens)

        Token buckets (numeric strings for Datadog/Prometheus compatibility):
            - "1000" for tokens <= 1000
            - "5000" for tokens <= 5000
            - "10000" for tokens <= 10000
            - "50000" for tokens <= 50000
            - "100000" for tokens <= 100000
            - "200000" for tokens > 100000
        """
        # Bucketize using numeric strings (industry standard)
        if token_count <= 1000:
            bucket = "1000"
        elif token_count <= 5000:
            bucket = "5000"
        elif token_count <= 10000:
            bucket = "10000"
        elif token_count <= 50000:
            bucket = "50000"
        elif token_count <= 100000:
            bucket = "100000"
        else:
            bucket = "200000"

        # Update label through protected method
        self._update_label("tokens", bucket)


class GenAIMonitor(Monitor):
    """
    Monitor for GenAI operation duration.

    Maps to: gen_ai.client.operation.duration histogram
    Labels: gen_ai.request.model, tokens (prompt tokens), error.type

    Note: tokens label is excluded by default in config to reduce cardinality.
    """

    monitor_type = "gen_ai.client.operation.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """Categorize AI-specific errors."""
        if isinstance(exc, TimeoutError):
            return "timeout"
        if hasattr(exc, 'status_code'):
            code = exc.status_code
            if 400 <= code < 500:
                return "4xx_error"
            if 500 <= code < 600:
                return "5xx_error"
            return f"api_error_{code}"

        exc_str = str(exc).lower()
        if "rate_limit" in exc_str or "rate limit" in exc_str:
            return "rate_limit"
        if "context_length" in exc_str or "context length" in exc_str:
            return "context_length_exceeded"

        return exc.__class__.__name__

    @classmethod
    def create(cls, model: str, tokens: int = None) -> GenAIMonitorInstance:
        """
        Create GenAI monitor instance for tracking LLM operation latency.

        Args:
            model: Model name from configuration (e.g., "gpt-4", "claude-sonnet-3.5")
            tokens: amount of tokens

        Returns:
            GenAIMonitorInstance with set_prompt_tokens() method

        Usage:
            monitor = GenAIMonitor.create(model="gpt-4")
            with MonitorLatency(monitor):
                response = llm.call()
                monitor.set_prompt_tokens(response.usage.prompt_tokens)
        """
        monitor = GenAIMonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "gen_ai.request.model": model,
                "tokens": "none"
            },
            error_parser=cls.parse_error
        )
        if tokens:
           monitor.set_prompt_tokens(tokens)

        return monitor



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
    def create(cls, model: str) -> MonitorInstance:
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