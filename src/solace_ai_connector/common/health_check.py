"""Health check components for Kubernetes liveness and readiness probes"""

import logging
import threading
import time

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
