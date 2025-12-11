import pytest
from unittest.mock import Mock
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
