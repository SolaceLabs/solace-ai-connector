"""Unit tests for observability monitor factory methods."""

import pytest
from solace_ai_connector.common.observability.monitors.base import MonitorInstance
from solace_ai_connector.common.observability.monitors.remote import (
    RemoteRequestMonitor,
    BrokerMonitor
)
from solace_ai_connector.common.observability.monitors.db import DBMonitor
from solace_ai_connector.common.observability.monitors.genai import (
    GenAIMonitor,
    GenAITTFTMonitor
)
from solace_ai_connector.common.observability.monitors.operation import OperationMonitor
from solace_ai_connector.common.observability.monitors.gateway import (
    GatewayMonitor,
    GatewayTTFBMonitor
)


class TestBrokerMonitor:
    """Test BrokerMonitor factory methods."""

    def test_publish_returns_monitor_instance(self):
        """Test publish() returns correct MonitorInstance."""
        instance = BrokerMonitor.publish()

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "outbound.request.duration"
        assert instance.labels == {
            "service.peer.name": "solace_broker",
            "operation.name": "publish"
        }
        assert instance.error_parser == BrokerMonitor.parse_error

    def test_broker_monitor_inherits_from_remote_request(self):
        """Test BrokerMonitor inherits from RemoteRequestMonitor."""
        assert issubclass(BrokerMonitor, RemoteRequestMonitor)
        assert BrokerMonitor.monitor_type == "outbound.request.duration"


class TestDBMonitor:
    """Test DBMonitor factory methods."""

    def test_query_returns_monitor_instance(self):
        """Test query() returns correct MonitorInstance."""
        instance = DBMonitor.query("users")

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "db.duration"
        assert instance.labels == {
            "db.collection.name": "users",
            "db.operation.name": "query"
        }
        assert instance.error_parser == DBMonitor.parse_error

    def test_insert_returns_monitor_instance(self):
        """Test insert() returns correct MonitorInstance."""
        instance = DBMonitor.insert("orders")

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "db.duration"
        assert instance.labels == {
            "db.collection.name": "orders",
            "db.operation.name": "insert"
        }
        assert instance.error_parser == DBMonitor.parse_error

    def test_update_returns_monitor_instance(self):
        """Test update() returns correct MonitorInstance."""
        instance = DBMonitor.update("products")

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "db.duration"
        assert instance.labels == {
            "db.collection.name": "products",
            "db.operation.name": "update"
        }
        assert instance.error_parser == DBMonitor.parse_error

    def test_delete_returns_monitor_instance(self):
        """Test delete() returns correct MonitorInstance."""
        instance = DBMonitor.delete("sessions")

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "db.duration"
        assert instance.labels == {
            "db.collection.name": "sessions",
            "db.operation.name": "delete"
        }
        assert instance.error_parser == DBMonitor.parse_error


class TestGenAIMonitor:
    """Test GenAIMonitor factory methods."""

    def test_instance_returns_monitor_instance(self):
        """Test instance() returns correct MonitorInstance."""
        instance = GenAIMonitor.create("gpt-4", 1500)

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "gen_ai.client.operation.duration"
        assert instance.labels == {
            "gen_ai.request.model": "gpt-4",
            "tokens": "5000"  # Bucketized
        }
        assert instance.error_parser == GenAIMonitor.parse_error

    def test_instance_bucketizes_tokens(self):
        """Test instance() bucketizes token counts."""
        # Test different bucket ranges
        test_cases = [
            (500, "1000"),
            (1000, "1000"),
            (2000, "5000"),
            (5000, "5000"),
            (7500, "10000"),
            (10000, "10000"),
            (25000, "50000"),
            (50000, "50000"),
            (75000, "100000"),
            (100000, "100000"),
            (150000, "200000"),
            (250000, "200000")
        ]

        for tokens, expected_bucket in test_cases:
            instance = GenAIMonitor.create("claude-sonnet-3.5", tokens)
            assert instance.labels["tokens"] == expected_bucket


class TestGenAITTFTMonitor:
    """Test GenAITTFTMonitor factory methods."""

    def test_instance_returns_monitor_instance(self):
        """Test instance() returns correct MonitorInstance."""
        instance = GenAITTFTMonitor.create("claude-opus-4")

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "gen_ai.client.operation.ttft.duration"
        assert instance.labels == {
            "gen_ai.request.model": "claude-opus-4"
        }
        assert instance.error_parser == GenAITTFTMonitor.parse_error

    def test_ttft_uses_genai_error_parser(self):
        """Test TTFT monitor delegates to GenAI error parser."""
        # Test that they produce the same results
        test_error = TimeoutError("test")
        assert GenAITTFTMonitor.parse_error(test_error) == GenAIMonitor.parse_error(test_error)

        class APIError(Exception):
            status_code = 429
        api_error = APIError("rate limited")
        assert GenAITTFTMonitor.parse_error(api_error) == GenAIMonitor.parse_error(api_error)


class TestOperationMonitor:
    """Test OperationMonitor factory methods."""

    def test_instance_returns_monitor_instance(self):
        """Test instance() returns correct MonitorInstance."""
        instance = OperationMonitor.instance(
            component_type="orchestrator",
            component_name="AgentOrchestrator",
            operation="execute"
        )

        assert isinstance(instance, MonitorInstance)
        assert instance.monitor_type == "operation.duration"
        assert instance.labels == {
            "type": "orchestrator",
            "component.name": "AgentOrchestrator",
            "operation.name": "execute"
        }
        assert instance.error_parser == OperationMonitor.parse_error


class TestGatewayMonitors:
    """Test GatewayMonitor and GatewayTTFBMonitor."""

    def test_gateway_monitor_type(self):
        """Test GatewayMonitor has correct monitor_type."""
        assert GatewayMonitor.monitor_type == "gateway.duration"

    def test_gateway_ttfb_monitor_type(self):
        """Test GatewayTTFBMonitor has correct monitor_type."""
        assert GatewayTTFBMonitor.monitor_type == "gateway.ttfb.duration"

    def test_gateway_ttfb_uses_gateway_error_parser(self):
        """Test TTFB monitor delegates to Gateway error parser."""
        # Test that they produce the same results
        test_error = ValueError("test")
        assert GatewayTTFBMonitor.parse_error(test_error) == GatewayMonitor.parse_error(test_error)

        class HTTPError(Exception):
            status_code = 500
        http_error = HTTPError("server error")
        assert GatewayTTFBMonitor.parse_error(http_error) == GatewayMonitor.parse_error(http_error)


class TestErrorParsers:
    """Test error parsing logic for each monitor type."""

    def test_remote_request_timeout_error(self):
        """Test RemoteRequestMonitor parses TimeoutError."""
        error = TimeoutError("Connection timed out")
        result = RemoteRequestMonitor.parse_error(error)
        assert result == "timeout"

    def test_remote_request_connection_error(self):
        """Test RemoteRequestMonitor parses ConnectionError."""
        error = ConnectionError("Connection refused")
        result = RemoteRequestMonitor.parse_error(error)
        assert result == "connection_error"

    def test_remote_request_http_4xx_error(self):
        """Test RemoteRequestMonitor parses 4xx status codes."""
        class HTTPError(Exception):
            status_code = 404

        error = HTTPError("Not found")
        result = RemoteRequestMonitor.parse_error(error)
        assert result == "4xx_error"

    def test_remote_request_http_5xx_error(self):
        """Test RemoteRequestMonitor parses 5xx status codes."""
        class HTTPError(Exception):
            status_code = 503

        error = HTTPError("Service unavailable")
        result = RemoteRequestMonitor.parse_error(error)
        assert result == "5xx_error"

    def test_remote_request_generic_error(self):
        """Test RemoteRequestMonitor returns class name for unknown errors."""
        error = ValueError("Invalid value")
        result = RemoteRequestMonitor.parse_error(error)
        assert result == "ValueError"

    def test_db_timeout_error(self):
        """Test DBMonitor detects timeout in error chain."""
        root_cause = Exception("connection timeout")
        error = Exception("Database operation failed")
        error.__cause__ = root_cause

        result = DBMonitor.parse_error(error)
        assert result == "db_timeout"

    def test_db_connection_error(self):
        """Test DBMonitor detects connection errors."""
        root_cause = Exception("connection refused")
        error = Exception("Query failed")
        error.__cause__ = root_cause

        result = DBMonitor.parse_error(error)
        assert result == "db_connection_error"

    def test_db_deadlock_error(self):
        """Test DBMonitor detects deadlocks."""
        root_cause = Exception("deadlock detected")
        error = Exception("Transaction failed")
        error.__cause__ = root_cause

        result = DBMonitor.parse_error(error)
        assert result == "db_deadlock"

    def test_db_constraint_violation(self):
        """Test DBMonitor detects constraint violations."""
        root_cause = Exception("unique constraint violation")
        error = Exception("Insert failed")
        error.__cause__ = root_cause

        result = DBMonitor.parse_error(error)
        assert result == "db_constraint_violation"

    def test_db_generic_error(self):
        """Test DBMonitor returns root cause class name."""
        root_cause = ValueError("Invalid data")
        error = Exception("Operation failed")
        error.__cause__ = root_cause

        result = DBMonitor.parse_error(error)
        assert result == "ValueError"

    def test_genai_rate_limit_error(self):
        """Test GenAIMonitor detects rate limit errors."""
        error = Exception("rate_limit exceeded")
        result = GenAIMonitor.parse_error(error)
        assert result == "rate_limit"

        error2 = Exception("rate limit reached")
        result2 = GenAIMonitor.parse_error(error2)
        assert result2 == "rate_limit"

    def test_genai_context_length_error(self):
        """Test GenAIMonitor detects context length errors."""
        error = Exception("context_length exceeded")
        result = GenAIMonitor.parse_error(error)
        assert result == "context_length_exceeded"

        error2 = Exception("context length too large")
        result2 = GenAIMonitor.parse_error(error2)
        assert result2 == "context_length_exceeded"

    def test_genai_timeout_error(self):
        """Test GenAIMonitor parses TimeoutError."""
        error = TimeoutError("Request timeout")
        result = GenAIMonitor.parse_error(error)
        assert result == "timeout"

    def test_genai_status_code_error(self):
        """Test GenAIMonitor parses status code errors."""
        class APIError(Exception):
            status_code = 429

        error = APIError("Too many requests")
        result = GenAIMonitor.parse_error(error)
        assert result == "4xx_error"

    def test_operation_timeout_error(self):
        """Test OperationMonitor parses TimeoutError."""
        error = TimeoutError("Operation timeout")
        result = OperationMonitor.parse_error(error)
        assert result == "timeout"

    def test_operation_validation_error(self):
        """Test OperationMonitor parses ValueError."""
        error = ValueError("Invalid input")
        result = OperationMonitor.parse_error(error)
        assert result == "validation_error"

    def test_operation_generic_error(self):
        """Test OperationMonitor returns class name for other errors."""
        error = RuntimeError("Something went wrong")
        result = OperationMonitor.parse_error(error)
        assert result == "RuntimeError"

    def test_gateway_client_error(self):
        """Test GatewayMonitor categorizes client errors."""
        error = ValueError("Bad request")
        result = GatewayMonitor.parse_error(error)
        assert result == "client_error"

        error2 = TypeError("Type mismatch")
        result2 = GatewayMonitor.parse_error(error2)
        assert result2 == "client_error"

        error3 = KeyError("Missing key")
        result3 = GatewayMonitor.parse_error(error3)
        assert result3 == "client_error"

    def test_gateway_server_error(self):
        """Test GatewayMonitor categorizes server errors."""
        error = RuntimeError("Internal error")
        result = GatewayMonitor.parse_error(error)
        assert result == "server_error"

        error2 = OSError("System error")
        result2 = GatewayMonitor.parse_error(error2)
        assert result2 == "server_error"

    def test_gateway_http_status_error(self):
        """Test GatewayMonitor parses HTTP status codes."""
        class HTTPError(Exception):
            status_code = 500

        error = HTTPError("Internal server error")
        result = GatewayMonitor.parse_error(error)
        assert result == "5xx_error"
