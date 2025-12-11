import pytest
import time
import json
from unittest.mock import Mock, patch
from io import BytesIO
from solace_ai_connector.common.health_check import HealthChecker


class TestHealthChecker:
    def test_health_checker_initialization(self):
        """Test HealthChecker initializes with correct default state"""
        mock_connector = Mock()
        checker = HealthChecker(mock_connector, check_interval_seconds=5)

        assert checker.connector is mock_connector
        assert checker.check_interval_seconds == 5
        assert checker.is_ready() is False
        assert checker.monitor_thread is None
        assert checker.stop_event.is_set() is False

    def test_check_all_threads_alive_with_alive_threads(self):
        """Test _check_all_threads_alive returns True when all threads alive"""
        mock_connector = Mock()

        # Create mock structure: connector.apps[].flows[].threads[]
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = True
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = True

        mock_flow1 = Mock()
        mock_flow1.threads = [mock_thread1, mock_thread2]

        mock_app = Mock()
        mock_app.flows = [mock_flow1]

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        assert checker._check_all_threads_alive() is True

    def test_check_all_threads_alive_with_dead_thread(self):
        """Test _check_all_threads_alive returns False when any thread is dead"""
        mock_connector = Mock()

        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = True
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = False  # Dead thread

        mock_flow1 = Mock()
        mock_flow1.threads = [mock_thread1, mock_thread2]

        mock_app = Mock()
        mock_app.flows = [mock_flow1]

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        assert checker._check_all_threads_alive() is False

    def test_check_all_threads_alive_with_no_apps(self):
        """Test _check_all_threads_alive returns True when no apps exist"""
        mock_connector = Mock()
        mock_connector.apps = []

        checker = HealthChecker(mock_connector)
        assert checker._check_all_threads_alive() is True

    def test_mark_ready_when_threads_alive(self):
        """Test mark_ready sets ready state when all threads alive"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]
        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        assert checker.is_ready() is False

        checker.mark_ready()

        assert checker.is_ready() is True

    def test_mark_ready_when_threads_dead(self):
        """Test mark_ready does not set ready when threads are dead"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = False
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]
        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        checker.mark_ready()

        assert checker.is_ready() is False

    def test_start_monitoring_creates_daemon_thread(self):
        """Test start_monitoring creates and starts a daemon thread"""
        mock_connector = Mock()
        mock_connector.apps = []

        checker = HealthChecker(mock_connector)
        checker.start_monitoring()

        assert checker.monitor_thread is not None
        assert checker.monitor_thread.daemon is True
        assert checker.monitor_thread.is_alive() is True

        # Clean up
        checker.stop()

    def test_monitoring_detects_thread_death(self):
        """Test monitoring loop detects when threads die"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True  # Initially alive
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]
        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector, check_interval_seconds=1)

        # Mark as ready
        checker.mark_ready()
        assert checker.is_ready() is True

        # Start monitoring
        checker.start_monitoring()

        # Simulate thread death
        mock_thread.is_alive.return_value = False

        # Wait for monitoring loop to detect it
        time.sleep(1.5)

        assert checker.is_ready() is False

        # Clean up
        checker.stop()

    def test_stop_halts_monitoring(self):
        """Test stop method halts the monitoring thread"""
        mock_connector = Mock()
        mock_connector.apps = []

        checker = HealthChecker(mock_connector)
        checker.start_monitoring()

        assert checker.monitor_thread.is_alive() is True

        checker.stop()

        assert checker.stop_event.is_set() is True


class TestHealthCheckRequestHandler:
    def test_liveness_endpoint_returns_ok(self):
        """Test liveness endpoint always returns 200 OK"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        mock_health_checker = Mock()
        HealthCheckRequestHandler.health_checker = mock_health_checker
        HealthCheckRequestHandler.liveness_path = "/healthz"
        HealthCheckRequestHandler.readiness_path = "/readyz"

        # Create a mock handler instance
        handler = Mock(spec=HealthCheckRequestHandler)
        handler.health_checker = mock_health_checker
        handler.liveness_path = "/healthz"
        handler.readiness_path = "/readyz"
        handler.path = "/healthz"
        handler.wfile = BytesIO()

        # Call the actual method
        HealthCheckRequestHandler._handle_liveness(handler)

        # Verify 200 was sent
        handler.send_response.assert_called_once_with(200)

    def test_readiness_endpoint_ready(self):
        """Test readiness endpoint returns 200 when ready"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True
        HealthCheckRequestHandler.health_checker = mock_health_checker
        HealthCheckRequestHandler.liveness_path = "/healthz"
        HealthCheckRequestHandler.readiness_path = "/readyz"

        handler = Mock(spec=HealthCheckRequestHandler)
        handler.health_checker = mock_health_checker
        handler.wfile = BytesIO()

        HealthCheckRequestHandler._handle_readiness(handler)

        handler.send_response.assert_called_once_with(200)

    def test_readiness_endpoint_not_ready(self):
        """Test readiness endpoint returns 503 when not ready"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = False
        HealthCheckRequestHandler.health_checker = mock_health_checker

        handler = Mock(spec=HealthCheckRequestHandler)
        handler.health_checker = mock_health_checker
        handler.wfile = BytesIO()

        HealthCheckRequestHandler._handle_readiness(handler)

        handler.send_response.assert_called_once_with(503)

    def test_unknown_path_returns_404(self):
        """Test unknown paths return 404"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        handler = Mock(spec=HealthCheckRequestHandler)
        handler.wfile = BytesIO()

        HealthCheckRequestHandler._handle_not_found(handler)

        handler.send_response.assert_called_once_with(404)
