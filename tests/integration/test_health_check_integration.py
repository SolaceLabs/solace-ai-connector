"""Integration tests for health check endpoints"""

import pytest
import time
import json
import socket
import urllib.request
from unittest.mock import patch
from solace_ai_connector.solace_ai_connector import SolaceAiConnector


class TestHealthCheckIntegration:
    def test_full_health_check_lifecycle(self):
        """Test complete health check lifecycle from startup to shutdown"""
        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        config = {
            "log": {
                "stdout_log_level": "ERROR",
                "log_file_level": "ERROR",
                "log_file": "/tmp/test.log"
            },
            "apps": [{
                "name": "test_app",
                "flows": [{
                    "name": "test_flow",
                    "components": [{
                        "component_name": "test_component",
                        "component_module": "pass_through"
                    }]
                }]
            }],
            "health_check": {
                "enabled": True,
                "port": port,
                "liveness_path": "/healthz",
                "readiness_path": "/readyz",
                "check_interval_seconds": 1
            }
        }

        sac = None
        try:
            # Create connector
            sac = SolaceAiConnector(config)

            # Give server time to start
            time.sleep(0.2)

            # Liveness should work immediately
            response = urllib.request.urlopen(f"http://localhost:{port}/healthz")
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data["status"] == "ok"

            # Readiness should be not ready initially
            try:
                urllib.request.urlopen(f"http://localhost:{port}/readyz")
                assert False, "Should have returned 503"
            except urllib.error.HTTPError as e:
                assert e.code == 503
                data = json.loads(e.read().decode())
                assert data["status"] == "not ready"

            # Run the connector to create apps/flows
            with patch.object(sac, 'wait_for_flows'):
                sac.run()

            # Give time for readiness to update
            time.sleep(0.2)

            # Now readiness should be ready
            response = urllib.request.urlopen(f"http://localhost:{port}/readyz")
            assert response.status == 200
            data = json.loads(response.read().decode())
            assert data["status"] == "ok"

            # Stop connector
            sac.stop()
            sac.cleanup()

            # Give time for server to stop
            time.sleep(0.2)

            # Server should no longer respond
            with pytest.raises(Exception):
                urllib.request.urlopen(f"http://localhost:{port}/healthz", timeout=1)

        finally:
            if sac:
                try:
                    sac.stop()
                    sac.cleanup()
                except:
                    pass
