import pytest
import time
import json
import socket
import urllib.request
from unittest.mock import Mock, patch
from io import BytesIO
from solace_ai_connector.common.health_check import HealthChecker


class TestHealthChecker:
    def test_health_checker_initialization(self):
        """Test HealthChecker initializes with correct default state"""
        mock_connector = Mock()
        checker = HealthChecker(mock_connector, readiness_check_period_seconds=5, startup_check_period_seconds=10)

        assert checker.connector is mock_connector
        assert checker.readiness_check_period_seconds == 5
        assert checker.startup_check_period_seconds == 10
        assert checker.is_ready() is False
        assert checker.is_startup_complete() is False
        assert checker.readiness_monitor_thread is None
        assert checker.startup_monitor_thread is None
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

    def test_startup_complete_set_when_mark_ready_succeeds(self):
        """Test _startup_complete is set to True when mark_ready succeeds"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]
        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        assert checker.is_startup_complete() is False

        checker.mark_ready()

        assert checker.is_startup_complete() is True

    def test_startup_complete_latches_when_readiness_degrades(self):
        """Test _startup_complete stays True even when readiness becomes False"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]
        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        checker.mark_ready()

        assert checker.is_startup_complete() is True
        assert checker.is_ready() is True

        # Simulate thread death - readiness should degrade but startup stays True
        mock_thread.is_alive.return_value = False

        # Manually trigger health check (simulating monitoring loop)
        checker._ready = not checker._check_all_threads_alive()
        with checker._lock:
            checker._ready = False

        assert checker.is_ready() is False
        assert checker.is_startup_complete() is True  # Latched!

    def test_start_monitoring_creates_daemon_threads(self):
        """Test start_monitoring creates and starts daemon threads"""
        mock_connector = Mock()
        mock_connector.apps = []

        checker = HealthChecker(mock_connector)
        checker.start_monitoring()

        assert checker.readiness_monitor_thread is not None
        assert checker.readiness_monitor_thread.daemon is True
        assert checker.readiness_monitor_thread.is_alive() is True
        # Startup monitor thread should also be started since startup not complete
        assert checker.startup_monitor_thread is not None
        assert checker.startup_monitor_thread.daemon is True

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

        checker = HealthChecker(mock_connector, readiness_check_period_seconds=1)

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
        """Test stop method halts the monitoring threads"""
        mock_connector = Mock()
        mock_connector.apps = []

        checker = HealthChecker(mock_connector)
        checker.start_monitoring()

        assert checker.readiness_monitor_thread.is_alive() is True

        checker.stop()

        assert checker.stop_event.is_set() is True

    def test_check_all_threads_alive_with_app_callback_ready(self):
        """Test _check_all_threads_alive calls app is_ready() callback when available"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_ready.return_value = True  # App reports ready

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_threads_alive()

        assert result is True
        mock_app.is_ready.assert_called_once()

    def test_check_all_threads_alive_with_app_callback_not_ready(self):
        """Test _check_all_threads_alive returns False when app callback reports not ready"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True  # Thread is alive
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_ready.return_value = False  # But app reports not ready

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_threads_alive()

        assert result is False
        mock_app.is_ready.assert_called_once()

    def test_check_all_threads_alive_without_app_callback(self):
        """Test _check_all_threads_alive works when app doesn't have is_ready callback"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock(spec=['flows'])  # App without is_ready method
        mock_app.flows = [mock_flow]

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_threads_alive()

        # Should still work, just checking threads
        assert result is True

    def test_check_all_threads_alive_multiple_apps_mixed_readiness(self):
        """Test _check_all_threads_alive with multiple apps, some with callbacks"""
        mock_connector = Mock()

        # App 1: Has callback, reports ready
        mock_thread1 = Mock()
        mock_thread1.is_alive.return_value = True
        mock_flow1 = Mock()
        mock_flow1.threads = [mock_thread1]
        mock_app1 = Mock()
        mock_app1.flows = [mock_flow1]
        mock_app1.is_ready.return_value = True

        # App 2: No callback
        mock_thread2 = Mock()
        mock_thread2.is_alive.return_value = True
        mock_flow2 = Mock()
        mock_flow2.threads = [mock_thread2]
        mock_app2 = Mock(spec=['flows'])
        mock_app2.flows = [mock_flow2]

        mock_connector.apps = [mock_app1, mock_app2]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_threads_alive()

        assert result is True
        mock_app1.is_ready.assert_called_once()

    def test_check_all_apps_startup_complete_with_callback_complete(self):
        """Test _check_all_apps_startup_complete when app callback reports complete"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_startup_complete.return_value = True

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_apps_startup_complete()

        assert result is True
        mock_app.is_startup_complete.assert_called_once()

    def test_check_all_apps_startup_complete_with_callback_not_complete(self):
        """Test _check_all_apps_startup_complete when app callback reports not complete"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_startup_complete.return_value = False

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_apps_startup_complete()

        assert result is False
        mock_app.is_startup_complete.assert_called_once()

    def test_check_all_apps_startup_complete_without_callback(self):
        """Test _check_all_apps_startup_complete when app has no is_startup_complete method"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        # App without is_startup_complete method
        mock_app = Mock(spec=['flows'])
        mock_app.flows = [mock_flow]

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        result = checker._check_all_apps_startup_complete()

        # Should return True (assume complete if no callback)
        assert result is True

    def test_mark_ready_checks_app_startup_complete(self):
        """Test mark_ready only sets startup complete when apps report complete"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_ready.return_value = True
        mock_app.is_startup_complete.return_value = False  # Not complete yet

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        checker.mark_ready()

        # Should NOT be startup complete because app says not complete
        assert checker.is_startup_complete() is False
        # But readiness can still be True (threads alive, is_ready True)
        assert checker.is_ready() is True

    def test_mark_ready_sets_startup_complete_when_apps_complete(self):
        """Test mark_ready sets startup complete when all apps report complete"""
        mock_connector = Mock()

        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        mock_flow = Mock()
        mock_flow.threads = [mock_thread]

        mock_app = Mock()
        mock_app.flows = [mock_flow]
        mock_app.is_ready.return_value = True
        mock_app.is_startup_complete.return_value = True  # Complete!

        mock_connector.apps = [mock_app]

        checker = HealthChecker(mock_connector)
        checker.mark_ready()

        # Both should be True
        assert checker.is_startup_complete() is True
        assert checker.is_ready() is True


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

    def test_startup_endpoint_returns_503_before_startup(self):
        """Test startup endpoint returns 503 before startup complete"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        mock_health_checker = Mock()
        mock_health_checker.is_startup_complete.return_value = False
        HealthCheckRequestHandler.health_checker = mock_health_checker

        handler = Mock(spec=HealthCheckRequestHandler)
        handler.health_checker = mock_health_checker
        handler.wfile = BytesIO()

        HealthCheckRequestHandler._handle_startup(handler)

        handler.send_response.assert_called_once_with(503)

    def test_startup_endpoint_returns_200_after_startup(self):
        """Test startup endpoint returns 200 after startup complete"""
        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        mock_health_checker = Mock()
        mock_health_checker.is_startup_complete.return_value = True
        HealthCheckRequestHandler.health_checker = mock_health_checker

        handler = Mock(spec=HealthCheckRequestHandler)
        handler.health_checker = mock_health_checker
        handler.wfile = BytesIO()

        HealthCheckRequestHandler._handle_startup(handler)

        handler.send_response.assert_called_once_with(200)


class TestHealthCheckHttpServer:
    def test_server_initialization(self):
        """Test HealthCheckHttpServer initializes correctly"""
        from solace_ai_connector.common.health_check import HealthCheckHttpServer

        mock_health_checker = Mock()
        server = HealthCheckHttpServer(
            mock_health_checker,
            port=8080,
            liveness_path="/healthz",
            readiness_path="/readyz",
            startup_path="/startup"
        )

        assert server.health_checker is mock_health_checker
        assert server.port == 8080
        assert server.liveness_path == "/healthz"
        assert server.readiness_path == "/readyz"
        assert server.startup_path == "/startup"
        assert server.httpd is None
        assert server.server_thread is None

    def test_server_starts_and_stops(self):
        """Test server starts and stops correctly"""
        from solace_ai_connector.common.health_check import HealthCheckHttpServer

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HealthCheckHttpServer(
            mock_health_checker,
            port=port,
            liveness_path="/healthz",
            readiness_path="/readyz",
            startup_path="/startup"
        )

        server.start()

        assert server.httpd is not None
        assert server.server_thread is not None
        assert server.server_thread.is_alive() is True
        assert server.server_thread.daemon is True

        # Clean up
        server.stop()

        # Verify stopped
        time.sleep(0.1)
        assert server.server_thread.is_alive() is False

    def test_server_serves_requests(self):
        """Test server actually serves HTTP requests"""
        from solace_ai_connector.common.health_check import HealthCheckHttpServer

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HealthCheckHttpServer(
            mock_health_checker,
            port=port,
            liveness_path="/healthz",
            readiness_path="/readyz",
            startup_path="/startup"
        )

        server.start()
        time.sleep(0.1)  # Give server time to start

        try:
            # Test liveness endpoint
            response = urllib.request.urlopen(f"http://localhost:{port}/healthz")
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data["status"] == "ok"

            # Test readiness endpoint
            response = urllib.request.urlopen(f"http://localhost:{port}/readyz")
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data["status"] == "ok"
        finally:
            server.stop()
