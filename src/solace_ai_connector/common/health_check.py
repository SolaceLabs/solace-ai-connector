"""Health check components for Kubernetes liveness and readiness probes"""

import logging
import threading
import time
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)


class HealthChecker:
    """Monitors connector health for readiness and startup checks"""

    def __init__(self, connector, readiness_check_period_seconds=5, startup_check_period_seconds=5):
        """
        Args:
            connector: The SolaceAiConnector instance to monitor.
            readiness_check_period_seconds: Seconds between readiness checks. Set this to at least
                the maximum time your readiness checks take to complete.
            startup_check_period_seconds: Seconds between startup completion polls. Set this to at least
                the maximum time your startup checks take to complete.
        """
        self.connector = connector
        self.readiness_check_period_seconds = readiness_check_period_seconds
        self.startup_check_period_seconds = startup_check_period_seconds
        self._ready = False
        self._startup_complete = False
        self._lock = threading.Lock()
        self.readiness_monitor_thread = None
        self.startup_monitor_thread = None
        self.stop_event = threading.Event()

    def is_ready(self):
        """Thread-safe check if connector is ready.

        Returns True only when both:
        - Components are healthy (threads alive, app.is_ready() passes)
        - Startup has completed (app.is_startup_complete() passes)

        This ensures readiness returns 503 until startup completes,
        preventing Kubernetes from routing traffic prematurely.
        """
        with self._lock:
            return self._ready and self._startup_complete

    def is_startup_complete(self):
        """Thread-safe check if startup has completed (latches to True)"""
        with self._lock:
            return self._startup_complete

    def _check_components_ready(self):
        """Check if all apps are ready (threads alive and readiness callbacks pass)"""
        for app in self.connector.apps:
            # Check if app has custom readiness logic
            if hasattr(app, 'is_ready') and callable(app.is_ready):
                if not app.is_ready():
                    log.debug("App '%s' is not ready", app.name)
                    return False

            # Check threads
            for flow in app.flows:
                for thread in flow.threads:
                    if not thread.is_alive():
                        log.debug("Thread in flow '%s' is not alive", flow.name)
                        return False
        return True

    def _check_all_apps_startup_complete(self):
        """Check if all apps have completed startup"""
        for app in self.connector.apps:
            # Check if app has custom startup complete logic
            if hasattr(app, 'is_startup_complete') and callable(app.is_startup_complete):
                if not app.is_startup_complete():
                    return False
        return True

    def mark_ready(self):
        """Mark connector as ready if readiness checks pass"""
        if self._check_components_ready():
            with self._lock:
                self._ready = True
            log.info("Health check: Connector is READY")

            # Only mark startup complete if all apps report startup complete
            if self._check_all_apps_startup_complete():
                with self._lock:
                    self._startup_complete = True
                log.info("Health check: Startup complete")

    def start_monitoring(self):
        """Start background threads to monitor ongoing health"""
        # Start readiness monitoring thread
        self.readiness_monitor_thread = threading.Thread(
            target=self._readiness_monitor_loop, daemon=True
        )
        self.readiness_monitor_thread.start()

        # Start startup monitoring thread (polls until startup completes, then exits)
        if not self._startup_complete:
            self.startup_monitor_thread = threading.Thread(
                target=self._startup_monitor_loop, daemon=True
            )
            self.startup_monitor_thread.start()

    def _readiness_monitor_loop(self):
        """Periodically check if connector is still ready"""
        while not self.stop_event.is_set():
            time.sleep(self.readiness_check_period_seconds)
            is_healthy = self._check_components_ready()
            if self._ready and not is_healthy:
                with self._lock:
                    self._ready = False
                log.warning("Health check: Connector degraded - not ready")
            elif not self._ready and is_healthy:
                with self._lock:
                    self._ready = True
                log.info("Health check: Connector recovered - ready")

    def _startup_monitor_loop(self):
        """Periodically check if startup has completed until it latches"""
        while not self.stop_event.is_set():
            time.sleep(self.startup_check_period_seconds)
            if self._startup_complete:
                # Already complete, exit the loop
                return
            if self._check_all_apps_startup_complete():
                with self._lock:
                    self._startup_complete = True
                log.info("Health check: Startup complete")
                return

    def stop(self):
        """Stop monitoring"""
        self.stop_event.set()


class HealthCheckRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints"""

    # Class attributes set by HealthCheckHttpServer
    health_checker = None
    liveness_path = None
    readiness_path = None
    startup_path = None

    def do_GET(self):
        """Handle GET requests"""
        if self.path == self.liveness_path:
            self._handle_liveness()
        elif self.path == self.readiness_path:
            self._handle_readiness()
        elif self.path == self.startup_path:
            self._handle_startup()
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

    def _handle_startup(self):
        """Handle startup probe - checks if startup has completed (latches to True)"""
        if self.health_checker.is_startup_complete():
            self.send_response(200)
            response = json.dumps({"status": "ok"})
        else:
            self.send_response(503)
            response = json.dumps({"status": "not ready"})

        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        """Override to suppress default logging"""
        pass


class HealthCheckHttpServer:
    """HTTP server for Kubernetes health checks"""

    def __init__(self, health_checker, port, liveness_path, readiness_path, startup_path):
        self.health_checker = health_checker
        self.port = port
        self.liveness_path = liveness_path
        self.readiness_path = readiness_path
        self.startup_path = startup_path
        self.httpd = None
        self.server_thread = None

    def start(self):
        """Start the HTTP server in a daemon thread"""
        # Set class attributes for request handler
        HealthCheckRequestHandler.health_checker = self.health_checker
        HealthCheckRequestHandler.liveness_path = self.liveness_path
        HealthCheckRequestHandler.readiness_path = self.readiness_path
        HealthCheckRequestHandler.startup_path = self.startup_path

        # Create HTTP server
        self.httpd = HTTPServer(('', self.port), HealthCheckRequestHandler)

        # Start server in daemon thread
        self.server_thread = threading.Thread(
            target=self.httpd.serve_forever,
            daemon=True
        )
        self.server_thread.start()
        log.info("Health check server started on port %s", self.port)

    def stop(self):
        """Stop the HTTP server"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            log.info("Health check server stopped")
