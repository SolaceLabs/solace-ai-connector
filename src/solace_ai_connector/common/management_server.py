"""Management HTTP server for health checks and metrics."""

import logging
import threading
import time
import json
import sys
import traceback
import faulthandler
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)


class ManagementRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for management endpoints (health checks and metrics)"""

    # Class attributes set by ManagementHttpServer
    health_checker = None  # Can be None if health disabled
    liveness_path = None
    readiness_path = None
    startup_path = None
    metrics_path = None
    metric_registry = None
    debug_path = "/debug/threads"

    def do_GET(self):
        """Handle GET requests"""
        # Health endpoints (only if health enabled)
        if self.liveness_path and self.path == self.liveness_path:
            self._handle_liveness()
        elif self.readiness_path and self.path == self.readiness_path:
            self._handle_readiness()
        elif self.startup_path and self.path == self.startup_path:
            self._handle_startup()
        # Metrics endpoint (only if observability enabled)
        elif self.metrics_path and self.path == self.metrics_path:
            self._handle_metrics()
        # Debug endpoint (always available)
        elif self.path == self.debug_path:
            self._handle_thread_dump()
        else:
            self._handle_not_found()

    def _handle_liveness(self):
        """Handle liveness probe - always returns OK"""
        if self.health_checker is None:
            self._send_404("Health checks not enabled")
            return

        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"status": "ok"})
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def _handle_readiness(self):
        """Handle readiness probe - checks if connector is ready"""
        if self.health_checker is None:
            self._send_404("Health checks not enabled")
            return

        try:
            if self.health_checker.is_ready():
                self.send_response(200)
                response = json.dumps({"status": "ok"})
            else:
                self.send_response(503)
                response = json.dumps({"status": "not ready"})

            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def _handle_startup(self):
        """Handle startup probe - checks if startup has completed"""
        if self.health_checker is None:
            self._send_404("Health checks not enabled")
            return

        try:
            if self.health_checker.is_startup_complete():
                self.send_response(200)
                response = json.dumps({"status": "ok"})
            else:
                self.send_response(503)
                response = json.dumps({"status": "not ready"})

            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def _handle_metrics(self):
        """Handle Prometheus metrics endpoint."""
        if self.metric_registry is None:
            self._send_404("Observability not enabled")
            return

        try:
            # Get metrics from registry
            metrics_output = self.metric_registry.get_prometheus_metrics()

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics_output)

        except BrokenPipeError:
            pass
        except Exception as e:
            log.error(f"Error serving metrics: {e}")
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(f"# Error: {e}\n".encode())
            except:
                pass

    def _handle_thread_dump(self):
        """Handle thread dump request for debugging deadlocks."""
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()

            output = []
            output.append("=" * 80)
            output.append("PYTHON THREAD DUMP")
            output.append(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            output.append(f"Total threads: {threading.active_count()}")
            output.append("=" * 80)
            output.append("")

            frames = sys._current_frames()
            for thread_id, frame in frames.items():
                thread_name = "Unknown"
                thread_daemon = False
                for thread in threading.enumerate():
                    if thread.ident == thread_id:
                        thread_name = thread.name
                        thread_daemon = thread.daemon
                        break

                output.append(f"Thread: {thread_name} (ID: {thread_id}, Daemon: {thread_daemon})")
                output.append("-" * 40)

                for line in traceback.format_stack(frame):
                    output.append(line.rstrip())
                output.append("")

            output.append("=" * 80)
            output.append("END OF THREAD DUMP")
            output.append("=" * 80)

            response = "\n".join(output)
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def _send_404(self, message: str):
        """Send 404 with message."""
        try:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"error": "not found", "message": message})
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def _handle_not_found(self):
        """Handle unknown paths"""
        try:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({"error": "not found"})
            self.wfile.write(response.encode())
        except BrokenPipeError:
            pass

    def log_message(self, format, *args):
        """Override to suppress default logging"""
        pass


class ManagementHttpServer:
    """HTTP server for management endpoints (health checks and Prometheus metrics)"""

    def __init__(self, health_checker, port, liveness_path, readiness_path,
                 startup_path, metrics_path=None, metric_registry=None):
        """
        Initialize management server.

        Can serve:
        - Health only (metric_registry=None)
        - Metrics only (health_checker=None)
        - Both health and metrics

        Args:
            health_checker: HealthChecker instance (or None)
            port: HTTP server port
            liveness_path: Liveness probe path (or None)
            readiness_path: Readiness probe path (or None)
            startup_path: Startup probe path (or None)
            metrics_path: Prometheus metrics path (optional, default /metrics)
            metric_registry: MetricRegistry instance (or None)
        """
        self.health_checker = health_checker
        self.port = port
        self.liveness_path = liveness_path
        self.readiness_path = readiness_path
        self.startup_path = startup_path
        self.metrics_path = metrics_path or "/metrics"
        self.metric_registry = metric_registry
        self.httpd = None
        self.server_thread = None

    def start(self):
        """Start the HTTP server in a daemon thread"""
        # Enable faulthandler for debugging deadlocks via SIGUSR1 signal
        try:
            import signal
            faulthandler.register(signal.SIGUSR1, all_threads=True)
            log.info("Faulthandler registered for SIGUSR1 - send signal to dump thread stacks")
        except Exception as e:
            log.warning(f"Could not register faulthandler for SIGUSR1: {e}")

        # Set class attributes for request handler
        ManagementRequestHandler.health_checker = self.health_checker
        ManagementRequestHandler.liveness_path = self.liveness_path
        ManagementRequestHandler.readiness_path = self.readiness_path
        ManagementRequestHandler.startup_path = self.startup_path
        ManagementRequestHandler.metrics_path = self.metrics_path
        ManagementRequestHandler.metric_registry = self.metric_registry

        # Create HTTP server
        self.httpd = HTTPServer(('', self.port), ManagementRequestHandler)

        # Start server in daemon thread
        self.server_thread = threading.Thread(
            target=self.httpd.serve_forever,
            daemon=True
        )
        self.server_thread.start()

        # Log available endpoints
        endpoints = []
        if self.health_checker:
            endpoints.extend([
                f"{self.liveness_path} (liveness)",
                f"{self.readiness_path} (readiness)",
                f"{self.startup_path} (startup)"
            ])
        if self.metric_registry:
            endpoints.append(f"{self.metrics_path} (metrics)")
        endpoints.append("/debug/threads (thread dump)")

        log.info(f"Management server started on port {self.port}")
        log.info(f"Available endpoints: {', '.join(endpoints)}")

    def stop(self):
        """Stop the HTTP server"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            log.info("Management server stopped")