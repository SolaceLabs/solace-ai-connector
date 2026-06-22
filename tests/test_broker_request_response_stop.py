"""
Tests for BrokerRequestResponse.stop_component() timeout behavior.

Verifies that stop_component doesn't hang indefinitely if the response thread
doesn't exit cleanly.
"""

import threading
import time
import pytest
from unittest.mock import MagicMock, patch


class TestStopComponentTimeout:
    """Test stop_component timeout behavior without full component setup."""

    def test_thread_join_with_timeout_normal_exit(self):
        """Verify thread.join(timeout) works when thread exits quickly."""
        exit_event = threading.Event()

        def quick_thread():
            exit_event.wait(timeout=0.1)

        thread = threading.Thread(target=quick_thread, daemon=True)
        thread.start()

        start = time.time()
        thread.join(timeout=2.0)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Join took {elapsed}s, expected < 0.5s"
        assert not thread.is_alive()

    def test_thread_join_with_timeout_slow_exit(self):
        """Verify thread.join(timeout) returns after timeout even if thread is slow."""
        slow_event = threading.Event()

        def slow_thread():
            slow_event.wait(timeout=10.0)  # Would take 10s

        thread = threading.Thread(target=slow_thread, daemon=True)
        thread.start()

        start = time.time()
        thread.join(timeout=2.0)  # Should return after 2s
        elapsed = time.time() - start

        # Should return around 2s, not 10s
        assert 1.5 < elapsed < 3.0, f"Join took {elapsed}s, expected ~2s"
        assert thread.is_alive()  # Thread still running

        # Cleanup
        slow_event.set()
        thread.join(timeout=1.0)

    def test_stop_component_pattern(self):
        """Test the exact pattern used in stop_component."""
        from solace_ai_connector.components.inputs_outputs.broker_request_response import (
            BrokerRequestResponse,
        )

        # Get the actual stop_component method and verify it has timeout
        import inspect
        source = inspect.getsource(BrokerRequestResponse.stop_component)

        # Verify timeout is in the join call
        assert "join(timeout=" in source, "stop_component should use join with timeout"
        assert "timeout=2.0" in source, "timeout should be 2.0 seconds"

    def test_daemon_thread_behavior(self):
        """Verify daemon threads don't prevent process exit."""
        event = threading.Event()

        def daemon_thread():
            event.wait()  # Wait forever

        thread = threading.Thread(target=daemon_thread, daemon=True)
        thread.start()

        # Daemon thread is alive but won't prevent test process from exiting
        assert thread.is_alive()
        assert thread.daemon is True

        # Process would exit here normally, daemon thread would be killed
        # For test cleanup, we signal it
        event.set()
        thread.join(timeout=1.0)


class TestStopComponentIntegration:
    """Integration test with mocked component."""

    def test_stop_component_calls_join_with_timeout(self):
        """Verify stop_component uses join with timeout."""
        from solace_ai_connector.components.inputs_outputs.broker_request_response import (
            BrokerRequestResponse,
        )

        # Create a minimal mock that simulates the component's structure
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = False  # Thread exits cleanly

        # Create a mock component with just the attributes needed
        mock_component = MagicMock(spec=BrokerRequestResponse)
        mock_component.response_thread = mock_thread
        mock_component._local_stop_signal = MagicMock()

        # Call the actual stop_component method
        BrokerRequestResponse.stop_component(mock_component)

        # Verify join was called with timeout
        mock_thread.join.assert_called_once_with(timeout=2.0)
        mock_component._local_stop_signal.set.assert_called_once()

    def test_stop_component_logs_warning_on_timeout(self):
        """Verify warning is logged when thread doesn't exit."""
        from solace_ai_connector.components.inputs_outputs.broker_request_response import (
            BrokerRequestResponse,
        )

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True  # Thread still alive after join

        mock_component = MagicMock(spec=BrokerRequestResponse)
        mock_component.response_thread = mock_thread
        mock_component._local_stop_signal = MagicMock()

        with patch(
            "solace_ai_connector.components.inputs_outputs.broker_request_response.log"
        ) as mock_log:
            BrokerRequestResponse.stop_component(mock_component)

            # Should log warning
            mock_log.warning.assert_called_once()
            warning_msg = mock_log.warning.call_args[0][0]
            assert "timeout" in warning_msg.lower()
