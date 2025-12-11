"""Health check components for Kubernetes liveness and readiness probes"""

import logging
import threading
import time
import json
from http.server import BaseHTTPRequestHandler

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

    def _check_all_threads_alive(self):
        """Check if all flow threads are alive"""
        for app in self.connector.apps:
            for flow in app.flows:
                for thread in flow.threads:
                    if not thread.is_alive():
                        return False
        return True

    def mark_ready(self):
        """Mark connector as ready if all threads are alive"""
        if self._check_all_threads_alive():
            with self._lock:
                self._ready = True
            log.info("Health check: Connector is READY")

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
