# Kubernetes Health Check Endpoints Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add HTTP-based liveness and readiness endpoints for Kubernetes health checks

**Architecture:** Build HealthChecker (monitors flow thread health) and HealthCheckServer (HTTP server using built-in http.server) components. Integrate with SolaceAiConnector lifecycle to track readiness state from startup through runtime.

**Tech Stack:** Python built-in http.server, threading, pytest

---

## Task 1: HealthChecker - Basic Structure and Initialization

**Files:**
- Create: `src/solace_ai_connector/common/health_check.py`
- Test: `tests/common/test_health_check.py`

**Step 1: Write the failing test for HealthChecker initialization**

Create `tests/common/test_health_check.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_health_checker_initialization -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'solace_ai_connector.common.health_check'"

**Step 3: Write minimal implementation**

Create `src/solace_ai_connector/common/health_check.py`:

```python
"""Health check components for Kubernetes liveness and readiness probes"""

import logging
import threading

log = logging.getLogger(__name__)


class HealthChecker:
    """Monitors connector health for readiness checks"""

    def __init__(self, connector, check_interval_seconds=5):
        self.connector = connector
        self.check_interval_seconds = check_interval_seconds
        self._ready = False
        self._lock = threading.Lock()
        self.monitor_thread = None
        self.stop_event = threading.Event()

    def is_ready(self):
        """Thread-safe check if connector is ready"""
        with self._lock:
            return self._ready
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_health_checker_initialization -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add HealthChecker initialization and is_ready method"
```

---

## Task 2: HealthChecker - Check All Threads Alive

**Files:**
- Modify: `src/solace_ai_connector/common/health_check.py`
- Modify: `tests/common/test_health_check.py`

**Step 1: Write the failing test**

Add to `tests/common/test_health_check.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_check_all_threads_alive -v`

Expected: FAIL with "AttributeError: 'HealthChecker' object has no attribute '_check_all_threads_alive'"

**Step 3: Write minimal implementation**

Add to `HealthChecker` class in `src/solace_ai_connector/common/health_check.py`:

```python
def _check_all_threads_alive(self):
    """Check if all flow threads are alive"""
    for app in self.connector.apps:
        for flow in app.flows:
            for thread in flow.threads:
                if not thread.is_alive():
                    return False
    return True
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_check_all_threads_alive -v`

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add thread health checking to HealthChecker"
```

---

## Task 3: HealthChecker - Mark Ready

**Files:**
- Modify: `src/solace_ai_connector/common/health_check.py`
- Modify: `tests/common/test_health_check.py`

**Step 1: Write the failing test**

Add to `tests/common/test_health_check.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_mark_ready -v`

Expected: FAIL with "AttributeError: 'HealthChecker' object has no attribute 'mark_ready'"

**Step 3: Write minimal implementation**

Add to `HealthChecker` class in `src/solace_ai_connector/common/health_check.py`:

```python
def mark_ready(self):
    """Mark connector as ready if all threads are alive"""
    if self._check_all_threads_alive():
        with self._lock:
            self._ready = True
        log.info("Health check: Connector is READY")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_mark_ready -v`

Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add mark_ready method to HealthChecker"
```

---

## Task 4: HealthChecker - Monitoring Loop

**Files:**
- Modify: `src/solace_ai_connector/common/health_check.py`
- Modify: `tests/common/test_health_check.py`

**Step 1: Write the failing test**

Add to `tests/common/test_health_check.py`:

```python
import time


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_start_monitoring -v`

Expected: FAIL with "AttributeError: 'HealthChecker' object has no attribute 'start_monitoring'"

**Step 3: Write minimal implementation**

Add to `HealthChecker` class in `src/solace_ai_connector/common/health_check.py`:

```python
import time


def start_monitoring(self):
    """Start background thread to monitor ongoing health"""
    self.monitor_thread = threading.Thread(
        target=self._monitor_loop, daemon=True
    )
    self.monitor_thread.start()


def _monitor_loop(self):
    """Periodically check if flows are still healthy"""
    while not self.stop_event.is_set():
        time.sleep(self.check_interval_seconds)
        if self._ready and not self._check_all_threads_alive():
            with self._lock:
                self._ready = False
            log.warning("Health check: Connector degraded - flows not healthy")


def stop(self):
    """Stop monitoring"""
    self.stop_event.set()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_start_monitoring -v`
Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_monitoring_detects_thread_death -v`
Run: `pytest tests/common/test_health_check.py::TestHealthChecker::test_stop_halts_monitoring -v`

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add monitoring loop to HealthChecker"
```

---

## Task 5: HealthCheckServer - HTTP Request Handler

**Files:**
- Modify: `src/solace_ai_connector/common/health_check.py`
- Modify: `tests/common/test_health_check.py`

**Step 1: Write the failing test**

Add to `tests/common/test_health_check.py`:

```python
import json
from http.server import HTTPServer
from unittest.mock import patch
from io import BytesIO


class TestHealthCheckRequestHandler:
    def test_liveness_endpoint_returns_ok(self):
        """Test liveness endpoint always returns 200 OK"""
        mock_health_checker = Mock()

        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        # Create handler with mock request
        handler = HealthCheckRequestHandler
        handler.health_checker = mock_health_checker
        handler.liveness_path = "/healthz"
        handler.readiness_path = "/readyz"

        # Mock the request
        mock_request = BytesIO()
        mock_client_address = ('127.0.0.1', 12345)
        mock_server = Mock()

        # Create instance
        with patch.object(handler, 'send_response'), \
             patch.object(handler, 'send_header'), \
             patch.object(handler, 'end_headers'), \
             patch.object(handler, 'wfile', BytesIO()):

            h = handler(mock_request, mock_client_address, mock_server)
            h.path = "/healthz"
            h.do_GET()

            h.send_response.assert_called_once_with(200)


    def test_readiness_endpoint_ready(self):
        """Test readiness endpoint returns 200 when ready"""
        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True

        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        handler = HealthCheckRequestHandler
        handler.health_checker = mock_health_checker
        handler.liveness_path = "/healthz"
        handler.readiness_path = "/readyz"

        mock_request = BytesIO()
        mock_client_address = ('127.0.0.1', 12345)
        mock_server = Mock()

        with patch.object(handler, 'send_response'), \
             patch.object(handler, 'send_header'), \
             patch.object(handler, 'end_headers'), \
             patch.object(handler, 'wfile', BytesIO()):

            h = handler(mock_request, mock_client_address, mock_server)
            h.path = "/readyz"
            h.do_GET()

            h.send_response.assert_called_once_with(200)


    def test_readiness_endpoint_not_ready(self):
        """Test readiness endpoint returns 503 when not ready"""
        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = False

        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        handler = HealthCheckRequestHandler
        handler.health_checker = mock_health_checker
        handler.liveness_path = "/healthz"
        handler.readiness_path = "/readyz"

        mock_request = BytesIO()
        mock_client_address = ('127.0.0.1', 12345)
        mock_server = Mock()

        with patch.object(handler, 'send_response'), \
             patch.object(handler, 'send_header'), \
             patch.object(handler, 'end_headers'), \
             patch.object(handler, 'wfile', BytesIO()):

            h = handler(mock_request, mock_client_address, mock_server)
            h.path = "/readyz"
            h.do_GET()

            h.send_response.assert_called_once_with(503)


    def test_unknown_path_returns_404(self):
        """Test unknown paths return 404"""
        mock_health_checker = Mock()

        from solace_ai_connector.common.health_check import HealthCheckRequestHandler

        handler = HealthCheckRequestHandler
        handler.health_checker = mock_health_checker
        handler.liveness_path = "/healthz"
        handler.readiness_path = "/readyz"

        mock_request = BytesIO()
        mock_client_address = ('127.0.0.1', 12345)
        mock_server = Mock()

        with patch.object(handler, 'send_response'), \
             patch.object(handler, 'send_header'), \
             patch.object(handler, 'end_headers'), \
             patch.object(handler, 'wfile', BytesIO()):

            h = handler(mock_request, mock_client_address, mock_server)
            h.path = "/unknown"
            h.do_GET()

            h.send_response.assert_called_once_with(404)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/common/test_health_check.py::TestHealthCheckRequestHandler -v`

Expected: FAIL with "ImportError: cannot import name 'HealthCheckRequestHandler'"

**Step 3: Write minimal implementation**

Add to `src/solace_ai_connector/common/health_check.py`:

```python
from http.server import BaseHTTPRequestHandler
import json


class HealthCheckRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints"""

    # Class attributes set by HealthCheckServer
    health_checker = None
    liveness_path = None
    readiness_path = None

    def do_GET(self):
        """Handle GET requests"""
        if self.path == self.liveness_path:
            self._handle_liveness()
        elif self.path == self.readiness_path:
            self._handle_readiness()
        else:
            self._handle_not_found()

    def _handle_liveness(self):
        """Handle liveness probe - always returns OK"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({"status": "ok"})
        self.wfile.write(response.encode())

    def _handle_readiness(self):
        """Handle readiness probe - checks if connector is ready"""
        if self.health_checker.is_ready():
            self.send_response(200)
            response = json.dumps({"status": "ok"})
        else:
            self.send_response(503)
            response = json.dumps({"status": "not ready"})

        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(response.encode())

    def _handle_not_found(self):
        """Handle unknown paths"""
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({"error": "not found"})
        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        """Override to suppress default logging"""
        pass
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/common/test_health_check.py::TestHealthCheckRequestHandler -v`

Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add HTTP request handler for health endpoints"
```

---

## Task 6: HealthCheckServer - Server Lifecycle

**Files:**
- Modify: `src/solace_ai_connector/common/health_check.py`
- Modify: `tests/common/test_health_check.py`

**Step 1: Write the failing test**

Add to `tests/common/test_health_check.py`:

```python
import socket


class TestHealthCheckServer:
    def test_server_initialization(self):
        """Test HealthCheckServer initializes correctly"""
        from solace_ai_connector.common.health_check import HealthCheckServer

        mock_health_checker = Mock()
        server = HealthCheckServer(
            mock_health_checker,
            port=8080,
            liveness_path="/healthz",
            readiness_path="/readyz"
        )

        assert server.health_checker is mock_health_checker
        assert server.port == 8080
        assert server.liveness_path == "/healthz"
        assert server.readiness_path == "/readyz"
        assert server.httpd is None
        assert server.server_thread is None


    def test_server_starts_and_stops(self):
        """Test server starts and stops correctly"""
        from solace_ai_connector.common.health_check import HealthCheckServer

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HealthCheckServer(
            mock_health_checker,
            port=port,
            liveness_path="/healthz",
            readiness_path="/readyz"
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
        from solace_ai_connector.common.health_check import HealthCheckServer
        import urllib.request

        mock_health_checker = Mock()
        mock_health_checker.is_ready.return_value = True

        # Find available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]

        server = HealthCheckServer(
            mock_health_checker,
            port=port,
            liveness_path="/healthz",
            readiness_path="/readyz"
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/common/test_health_check.py::TestHealthCheckServer -v`

Expected: FAIL with "ImportError: cannot import name 'HealthCheckServer'"

**Step 3: Write minimal implementation**

Add to `src/solace_ai_connector/common/health_check.py`:

```python
from http.server import HTTPServer


class HealthCheckServer:
    """HTTP server for Kubernetes health checks"""

    def __init__(self, health_checker, port, liveness_path, readiness_path):
        self.health_checker = health_checker
        self.port = port
        self.liveness_path = liveness_path
        self.readiness_path = readiness_path
        self.httpd = None
        self.server_thread = None

    def start(self):
        """Start the HTTP server in a daemon thread"""
        # Set class attributes for request handler
        HealthCheckRequestHandler.health_checker = self.health_checker
        HealthCheckRequestHandler.liveness_path = self.liveness_path
        HealthCheckRequestHandler.readiness_path = self.readiness_path

        # Create HTTP server
        self.httpd = HTTPServer(('', self.port), HealthCheckRequestHandler)

        # Start server in daemon thread
        self.server_thread = threading.Thread(
            target=self.httpd.serve_forever,
            daemon=True
        )
        self.server_thread.start()
        log.info(f"Health check server started on port {self.port}")

    def stop(self):
        """Stop the HTTP server"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            log.info("Health check server stopped")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/common/test_health_check.py::TestHealthCheckServer -v`

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add tests/common/test_health_check.py src/solace_ai_connector/common/health_check.py
git commit -m "feat: add HealthCheckServer with start/stop lifecycle"
```

---

## Task 7: Integration with SolaceAiConnector - Initialization

**Files:**
- Modify: `src/solace_ai_connector/solace_ai_connector.py`
- Test: `tests/test_solace_ai_connector_health.py`

**Step 1: Write the failing test**

Create `tests/test_solace_ai_connector_health.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth -v`

Expected: FAIL with "AttributeError: 'SolaceAiConnector' object has no attribute 'health_checker'"

**Step 3: Write minimal implementation**

Modify `src/solace_ai_connector/solace_ai_connector.py`:

Add import at the top:
```python
from .common.health_check import HealthChecker, HealthCheckServer
```

Add to `__init__()` method after monitoring initialization (around line 50):
```python
# Initialize health check if enabled
self.health_checker = None
self.health_server = None
if self.config.get("health_check", {}).get("enabled", False):
    health_config = self.config.get("health_check", {})
    self.health_checker = HealthChecker(
        self,
        check_interval_seconds=health_config.get("check_interval_seconds", 5)
    )
    self.health_server = HealthCheckServer(
        self.health_checker,
        port=health_config.get("port", 8080),
        liveness_path=health_config.get("liveness_path", "/healthz"),
        readiness_path=health_config.get("readiness_path", "/readyz")
    )
    self.health_server.start()
    log.info(f"Health check server started on port {health_config.get('port', 8080)}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth -v`

Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add tests/test_solace_ai_connector_health.py src/solace_ai_connector/solace_ai_connector.py
git commit -m "feat: integrate health check server into connector initialization"
```

---

## Task 8: Integration with SolaceAiConnector - Mark Ready After Startup

**Files:**
- Modify: `src/solace_ai_connector/solace_ai_connector.py`
- Modify: `tests/test_solace_ai_connector_health.py`

**Step 1: Write the failing test**

Add to `tests/test_solace_ai_connector_health.py`:

```python
@patch('solace_ai_connector.solace_ai_connector.HealthCheckServer')
@patch('solace_ai_connector.solace_ai_connector.HealthChecker')
def test_health_checker_marked_ready_after_create_apps(self, mock_health_checker_class, mock_health_server_class):
    """Test health checker is marked ready after create_apps"""
    mock_health_checker = Mock()
    mock_health_server = Mock()
    mock_health_checker_class.return_value = mock_health_checker
    mock_health_server_class.return_value = mock_health_server

    config = {
        "apps": [{"name": "test", "flows": []}],
        "health_check": {
            "enabled": True
        }
    }

    with patch('solace_ai_connector.solace_ai_connector.setup_log'), \
         patch('solace_ai_connector.solace_ai_connector.resolve_config_values'), \
         patch('solace_ai_connector.solace_ai_connector.TimerManager'), \
         patch('solace_ai_connector.solace_ai_connector.CacheService'), \
         patch('solace_ai_connector.solace_ai_connector.create_storage_backend'), \
         patch('solace_ai_connector.solace_ai_connector.Monitoring'), \
         patch.object(SolaceAiConnector, 'create_apps'):

        sac = SolaceAiConnector(config)

        # Mark ready and start monitoring should not be called yet
        mock_health_checker.mark_ready.assert_not_called()
        mock_health_checker.start_monitoring.assert_not_called()

        # Run the connector
        sac.run()

        # Now they should be called
        mock_health_checker.mark_ready.assert_called_once()
        mock_health_checker.start_monitoring.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth::test_health_checker_marked_ready_after_create_apps -v`

Expected: FAIL with "AssertionError: Expected 'mark_ready' to be called once"

**Step 3: Write minimal implementation**

Modify `src/solace_ai_connector/solace_ai_connector.py`:

In the `run()` method, after the line `log.info("Solace AI Event Connector started successfully")` (around line 63), add:

```python
# Mark health check as ready if enabled
if self.health_checker:
    self.health_checker.mark_ready()
    self.health_checker.start_monitoring()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth::test_health_checker_marked_ready_after_create_apps -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_solace_ai_connector_health.py src/solace_ai_connector/solace_ai_connector.py
git commit -m "feat: mark health checker ready after apps created"
```

---

## Task 9: Integration with SolaceAiConnector - Stop Health Check

**Files:**
- Modify: `src/solace_ai_connector/solace_ai_connector.py`
- Modify: `tests/test_solace_ai_connector_health.py`

**Step 1: Write the failing test**

Add to `tests/test_solace_ai_connector_health.py`:

```python
@patch('solace_ai_connector.solace_ai_connector.HealthCheckServer')
@patch('solace_ai_connector.solace_ai_connector.HealthChecker')
def test_health_check_stopped_on_connector_stop(self, mock_health_checker_class, mock_health_server_class):
    """Test health check server and checker are stopped when connector stops"""
    mock_health_checker = Mock()
    mock_health_server = Mock()
    mock_health_checker_class.return_value = mock_health_checker
    mock_health_server_class.return_value = mock_health_server

    config = {
        "apps": [{"name": "test", "flows": []}],
        "health_check": {
            "enabled": True
        }
    }

    with patch('solace_ai_connector.solace_ai_connector.setup_log'), \
         patch('solace_ai_connector.solace_ai_connector.resolve_config_values'), \
         patch('solace_ai_connector.solace_ai_connector.TimerManager') as mock_timer_manager, \
         patch('solace_ai_connector.solace_ai_connector.CacheService') as mock_cache_service, \
         patch('solace_ai_connector.solace_ai_connector.create_storage_backend'), \
         patch('solace_ai_connector.solace_ai_connector.Monitoring'):

        sac = SolaceAiConnector(config)

        # Stop the connector
        sac.stop()

        # Health check components should be stopped
        mock_health_server.stop.assert_called_once()
        mock_health_checker.stop.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth::test_health_check_stopped_on_connector_stop -v`

Expected: FAIL with "AssertionError: Expected 'stop' to be called once"

**Step 3: Write minimal implementation**

Modify `src/solace_ai_connector/solace_ai_connector.py`:

In the `stop()` method, after `self.stop_signal.set()` and before `self.timer_manager.stop()` (around line 652), add:

```python
# Stop health check components first
if self.health_server:
    self.health_server.stop()
if self.health_checker:
    self.health_checker.stop()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_solace_ai_connector_health.py::TestSolaceAiConnectorHealth::test_health_check_stopped_on_connector_stop -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_solace_ai_connector_health.py src/solace_ai_connector/solace_ai_connector.py
git commit -m "feat: stop health check components on connector stop"
```

---

## Task 10: End-to-End Integration Test

**Files:**
- Create: `tests/integration/test_health_check_integration.py`

**Step 1: Write the integration test**

Create `tests/integration/test_health_check_integration.py`:

```python
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
```

**Step 2: Run test to verify current state**

Run: `pytest tests/integration/test_health_check_integration.py -v`

Expected: PASS if all previous tasks completed correctly

**Step 3: Fix any issues found**

If test fails, debug and fix issues in previous implementations.

**Step 4: Run full test suite**

Run: `pytest tests/common/test_health_check.py tests/test_solace_ai_connector_health.py tests/integration/test_health_check_integration.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/integration/test_health_check_integration.py
git commit -m "test: add end-to-end integration test for health checks"
```

---

## Task 11: Documentation and Example

**Files:**
- Create: `docs/health_checks.md`
- Create: `examples/health_check_config.yaml`

**Step 1: Write documentation**

Create `docs/health_checks.md`:

```markdown
# Health Check Endpoints

The Solace AI Connector provides HTTP-based health check endpoints for Kubernetes liveness and readiness probes.

## Configuration

Add the following to your connector configuration:

\`\`\`yaml
health_check:
  enabled: true                          # Default: false
  port: 8080                             # Default: 8080
  liveness_path: /healthz                # Default: /healthz
  readiness_path: /readyz                # Default: /readyz
  check_interval_seconds: 5              # Default: 5
\`\`\`

## Endpoints

### Liveness Probe: `GET /healthz`

Indicates if the process is alive and responsive.

- **Returns 200 OK**: Process is running and can handle requests
- **Use for**: Kubernetes liveness probe to restart unhealthy pods

### Readiness Probe: `GET /readyz`

Indicates if the connector is ready to process messages.

- **Returns 200 OK**: All apps and flows are loaded and operational
- **Returns 503 Service Unavailable**: Connector is starting up or flows have failed
- **Use for**: Kubernetes readiness probe to control traffic routing

## Behavior

### Startup Sequence

1. Connector starts → Readiness returns 503
2. Apps/flows created and threads started → Readiness returns 200
3. Liveness always returns 200 (if process can respond)

### Runtime Monitoring

The health checker continuously monitors flow threads:

- If any flow thread dies → Readiness changes to 503
- Kubernetes will stop routing traffic to the pod
- Monitoring interval controlled by `check_interval_seconds`

## Kubernetes Configuration

Example pod specification:

\`\`\`yaml
apiVersion: v1
kind: Pod
metadata:
  name: solace-ai-connector
spec:
  containers:
  - name: connector
    image: solace-ai-connector:latest
    ports:
    - containerPort: 8080
      name: health
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /readyz
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 3
\`\`\`

## Testing

Test the endpoints manually:

\`\`\`bash
# Test liveness
curl http://localhost:8080/healthz

# Test readiness
curl http://localhost:8080/readyz

# Expected responses
{"status": "ok"}           # When healthy/ready
{"status": "not ready"}    # When not ready
\`\`\`

## Troubleshooting

### Readiness probe failing

- Check logs for flow startup errors
- Verify all flow threads are alive
- Check monitoring interval isn't too short

### Liveness probe failing

- Process has crashed or is unresponsive
- Check for deadlocks or infinite loops
- Review error logs

### Port conflicts

- Ensure configured port is available
- Check for other services using the same port
- Kubernetes will report port binding errors in pod logs
```

**Step 2: Create example configuration**

Create `examples/health_check_config.yaml`:

```yaml
# Example configuration with health check endpoints enabled

# Health check configuration for Kubernetes
health_check:
  enabled: true
  port: 8080
  liveness_path: /healthz
  readiness_path: /readyz
  check_interval_seconds: 5

# Logging configuration
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: logs/solace_ai_connector.log

# Example application
apps:
  - name: example_app
    flows:
      - name: example_flow
        components:
          - component_name: input
            component_module: broker_input
            component_config:
              broker_type: solace
              broker_url: ${SOLACE_BROKER_URL}
              broker_username: ${SOLACE_USERNAME}
              broker_password: ${SOLACE_PASSWORD}
              broker_vpn: ${SOLACE_VPN}
              broker_queue_name: input_queue

          - component_name: processor
            component_module: pass_through

          - component_name: output
            component_module: broker_output
            component_config:
              broker_type: solace
              broker_url: ${SOLACE_BROKER_URL}
              broker_username: ${SOLACE_USERNAME}
              broker_password: ${SOLACE_PASSWORD}
              broker_vpn: ${SOLACE_VPN}
```

**Step 3: Verify documentation**

Manually review the documentation for:
- Clarity and completeness
- Accurate code examples
- Correct YAML syntax
- Proper formatting

**Step 4: Commit**

```bash
git add docs/health_checks.md examples/health_check_config.yaml
git commit -m "docs: add health check documentation and example config"
```

---

## Task 12: Run Full Test Suite and Verify

**Step 1: Run all health check tests**

Run: `pytest tests/common/test_health_check.py tests/test_solace_ai_connector_health.py tests/integration/test_health_check_integration.py -v`

Expected: All tests PASS

**Step 2: Run full connector test suite**

Run: `pytest tests/ -v`

Expected: All tests PASS (including existing tests)

**Step 3: Check code formatting**

Run: `ruff check src/solace_ai_connector/common/health_check.py`

Expected: No issues found

**Step 4: Manual smoke test**

Create a simple test config and run manually:

```bash
# Create test config
cat > /tmp/test_health.yaml << 'EOF'
health_check:
  enabled: true
  port: 8080

log:
  stdout_log_level: INFO

apps:
  - name: test
    flows:
      - name: test_flow
        components:
          - component_name: test
            component_module: pass_through
EOF

# Run connector
solace-ai-connector /tmp/test_health.yaml &
PID=$!

# Wait for startup
sleep 2

# Test endpoints
curl http://localhost:8080/healthz
curl http://localhost:8080/readyz

# Cleanup
kill $PID
```

Expected: Both endpoints return `{"status": "ok"}`

**Step 5: Final commit**

If any fixes were needed:
```bash
git add .
git commit -m "fix: final adjustments after testing"
```

---

## Verification Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Full test suite passes
- [ ] Code passes ruff checks
- [ ] Manual smoke test successful
- [ ] Documentation complete and accurate
- [ ] Example configuration works
- [ ] All commits have clear messages
- [ ] Design document matches implementation

## Next Steps

After implementation is complete:
1. Review all changes
2. Test in a Kubernetes environment
3. Create pull request
4. Update main documentation index to reference health check docs
