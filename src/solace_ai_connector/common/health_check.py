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
