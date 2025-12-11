# Kubernetes Health Check Endpoints Design

**Date:** 2025-12-11
**Status:** Approved

## Overview

Add HTTP-based liveness and readiness endpoints to the Solace AI Connector to support Kubernetes health checks and deployments.

## Requirements

- **Liveness probe**: Indicates if the process is responsive (can handle requests)
- **Readiness probe**: Indicates if all apps/flows are loaded and operational
- **Ongoing monitoring**: Detect flow failures after initial startup and mark not-ready
- **Configurable**: Optional feature with customizable port and endpoint paths
- **No dependencies**: Use Python's built-in HTTP server to avoid new dependencies

## Design Decisions

### Liveness vs Readiness

- **Liveness**: Always returns 200 OK if the process can respond to HTTP requests
  - Simple health check - if we can respond, we're alive
  - Kubernetes restarts the pod if liveness fails

- **Readiness**: Returns 200 OK only when connector is ready to process messages
  - NOT_READY initially (during startup)
  - READY after `create_apps()` completes and all flow threads are verified alive
  - NOT_READY again if any flow thread dies after becoming ready
  - Kubernetes stops sending traffic if readiness fails

### State Machine

**Readiness Lifecycle:**

1. **NOT_READY (initial)** - From process start until all flows running
   - HTTP returns 503 Service Unavailable

2. **READY** - After `create_apps()` completes and all threads alive
   - HTTP returns 200 OK

3. **NOT_READY (degraded)** - If any flow thread dies
   - Background monitoring detects dead threads
   - HTTP returns 503 Service Unavailable

### Configuration

```yaml
health_check:
  enabled: true                          # Default: false
  port: 8080                             # Default: 8080
  liveness_path: /healthz                # Default: /healthz
  readiness_path: /readyz                # Default: /readyz
  check_interval_seconds: 5              # Default: 5 (integer seconds)
```

**Validation:**
- `enabled`: boolean
- `port`: integer (1-65535)
- `liveness_path`: string (must start with `/`)
- `readiness_path`: string (must start with `/`)
- `check_interval_seconds`: integer (≥ 1)

### Multiple Config Files

When using multiple config files, health check configuration follows standard merge rules:
- Last config file's `health_check` section wins (overwrites previous)
- All `apps` from all config files are concatenated
- Readiness monitors all threads from all apps (from all config files)

## Architecture

### Components

**1. HealthChecker** - Monitors connector state
- Tracks readiness state (thread-safe with Lock)
- Provides `is_ready()` method for HTTP server
- Monitors ongoing health via background thread
- Checks all flow threads periodically

**2. HealthCheckServer** - HTTP server for endpoints
- Uses Python's built-in `http.server.HTTPServer`
- Runs in daemon thread
- Serves liveness and readiness endpoints
- Returns simple JSON responses

### Implementation Details

**HealthChecker:**
```python
class HealthChecker:
    def __init__(self, connector, check_interval_seconds=5):
        self.connector = connector
        self.check_interval_seconds = check_interval_seconds
        self._ready = False
        self._lock = threading.Lock()
        self.monitor_thread = None
        self.stop_event = threading.Event()

    def is_ready(self) -> bool:
        """Thread-safe readiness check"""

    def mark_ready(self):
        """Called after create_apps() completes"""

    def start_monitoring(self):
        """Start background monitoring thread"""

    def _monitor_loop(self):
        """Periodically check flow health"""

    def _check_all_threads_alive(self) -> bool:
        """Verify all flow threads are alive"""

    def stop(self):
        """Stop monitoring"""
```

**HealthCheckServer:**
```python
class HealthCheckServer:
    def __init__(self, health_checker, port, liveness_path, readiness_path):
        self.health_checker = health_checker
        self.port = port
        self.liveness_path = liveness_path
        self.readiness_path = readiness_path
        self.httpd = None
        self.server_thread = None

    def start(self):
        """Start HTTP server in daemon thread"""

    def stop(self):
        """Stop HTTP server gracefully"""
```

**Request Handler:**
- `GET {liveness_path}` → 200 OK with `{"status": "ok"}`
- `GET {readiness_path}` → 200 OK with `{"status": "ok"}` if ready, else 503 with `{"status": "not ready"}`
- All other paths → 404 Not Found

### Integration with SolaceAiConnector

**In `__init__()`:**
```python
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

**In `run()` after `create_apps()`:**
```python
if self.health_checker:
    self.health_checker.mark_ready()
    self.health_checker.start_monitoring()
```

**In `stop()`:**
```python
if self.health_server:
    self.health_server.stop()
if self.health_checker:
    self.health_checker.stop()
```

## File Organization

- **New file:** `src/solace_ai_connector/common/health_check.py`
  - Contains `HealthChecker` class
  - Contains `HealthCheckServer` class

## Logging

Following project logging guidelines:

- **INFO**: Server started, connector ready state transitions
- **DEBUG**: Detailed thread health check results
- **WARNING**: Connector degraded (flows died after being ready)
- **ERROR**: Server startup failures

## Example Kubernetes Configuration

```yaml
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
    readinessProbe:
      httpGet:
        path: /readyz
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
```

## Testing Considerations

- Unit tests for `HealthChecker` state transitions
- Unit tests for `HealthCheckServer` endpoint responses
- Integration test: verify readiness transitions during startup
- Integration test: verify readiness fails when flow thread dies
- Manual test: verify endpoints work with multiple config files
