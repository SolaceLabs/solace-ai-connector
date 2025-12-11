import pytest
from unittest.mock import Mock, patch, MagicMock
from solace_ai_connector.solace_ai_connector import SolaceAiConnector


class TestSolaceAiConnectorHealth:
    @patch('solace_ai_connector.solace_ai_connector.HealthCheckServer')
    @patch('solace_ai_connector.solace_ai_connector.HealthChecker')
    def test_health_check_disabled_by_default(self, mock_health_checker_class, mock_health_server_class):
        """Test health check is not started when disabled"""
        config = {
            "apps": [{"name": "test", "flows": []}]
        }

        with patch('solace_ai_connector.solace_ai_connector.setup_log'), \
             patch('solace_ai_connector.solace_ai_connector.resolve_config_values'), \
             patch('solace_ai_connector.solace_ai_connector.TimerManager'), \
             patch('solace_ai_connector.solace_ai_connector.CacheService'), \
             patch('solace_ai_connector.solace_ai_connector.create_storage_backend'), \
             patch('solace_ai_connector.solace_ai_connector.Monitoring'):

            sac = SolaceAiConnector(config)

            assert sac.health_checker is None
            assert sac.health_server is None
            mock_health_checker_class.assert_not_called()
            mock_health_server_class.assert_not_called()


    @patch('solace_ai_connector.solace_ai_connector.HealthCheckServer')
    @patch('solace_ai_connector.solace_ai_connector.HealthChecker')
    def test_health_check_enabled_in_config(self, mock_health_checker_class, mock_health_server_class):
        """Test health check is started when enabled in config"""
        mock_health_checker = Mock()
        mock_health_server = Mock()
        mock_health_checker_class.return_value = mock_health_checker
        mock_health_server_class.return_value = mock_health_server

        config = {
            "apps": [{"name": "test", "flows": []}],
            "health_check": {
                "enabled": True,
                "port": 8080,
                "liveness_path": "/healthz",
                "readiness_path": "/readyz",
                "check_interval_seconds": 5
            }
        }

        with patch('solace_ai_connector.solace_ai_connector.setup_log'), \
             patch('solace_ai_connector.solace_ai_connector.resolve_config_values'), \
             patch('solace_ai_connector.solace_ai_connector.TimerManager'), \
             patch('solace_ai_connector.solace_ai_connector.CacheService'), \
             patch('solace_ai_connector.solace_ai_connector.create_storage_backend'), \
             patch('solace_ai_connector.solace_ai_connector.Monitoring'):

            sac = SolaceAiConnector(config)

            assert sac.health_checker is mock_health_checker
            assert sac.health_server is mock_health_server

            mock_health_checker_class.assert_called_once_with(sac, check_interval_seconds=5)
            mock_health_server_class.assert_called_once_with(
                mock_health_checker,
                port=8080,
                liveness_path="/healthz",
                readiness_path="/readyz"
            )
            mock_health_server.start.assert_called_once()
