# Health Check Endpoints

The Solace AI Connector provides HTTP-based health check endpoints for Kubernetes liveness, readiness, and startup probes.

## Configuration

Add the following to your connector configuration:

```yaml
health_check:
  enabled: true                          # Default: false
  port: 8080                             # Default: 8080
  liveness_path: /healthz                # Default: /healthz
  readiness_path: /readyz                # Default: /readyz
  startup_path: /startup                 # Default: /startup
  readiness_check_period_seconds: 5      # Default: 5 - How often to check readiness
  startup_check_period_seconds: 5        # Default: 5 - How often to poll for startup completion
```

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

### Startup Probe: `GET /startup`

Indicates if the connector has completed initialization.

- **Returns 200 OK**: Initialization complete (latches to 200 forever once successful)
- **Returns 503 Service Unavailable**: Still initializing
- **Use for**: Kubernetes startup probe to prevent liveness from killing slow-starting containers

## Behavior

### Startup Sequence

1. Connector starts → Startup returns 503, Readiness returns 503
2. Apps/flows created and threads started → Startup returns 200 (latches), Readiness returns 200
3. Liveness always returns 200 (if process can respond)
4. If flows degrade → Startup stays 200 (latched), Readiness returns 503

**Key difference between Startup and Readiness:**
- **Startup** is a one-time gate. Once initialization completes, it returns 200 forever.
- **Readiness** is ongoing. It can toggle between ready (200) and not ready (503) based on flow health.

### Runtime Monitoring

The health checker continuously monitors:

- **Flow threads**: If any flow thread dies → Readiness changes to 503
- **App-level readiness**: Custom apps can provide their own readiness logic
- Kubernetes will stop routing traffic to the pod if not ready
- Readiness monitoring interval controlled by `readiness_check_period_seconds`
- Startup polling interval controlled by `startup_check_period_seconds`

### Custom App Startup

Apps can implement custom startup logic by overriding the `is_startup_complete()` method. This is useful when your app performs asynchronous initialization that must complete before the startup probe should succeed.

```python
from solace_ai_connector.flow.app import App

class MyCustomApp(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_loaded = False
        self.cache_warmed = False

    def is_startup_complete(self) -> bool:
        """Custom startup check - called until True, then latches"""
        # Startup complete only when model is loaded and cache is warmed
        return self.model_loaded and self.cache_warmed
```

**When to use custom startup:**

- ML model must be loaded into memory
- Database connection pool must be initialized
- Cache must be warmed up
- Initial data sync must complete
- Message broker subscriptions must be active

**Key difference from readiness:**

| Aspect | `is_startup_complete()` | `is_ready()` |
|--------|-------------------------|--------------|
| When called | Until it returns True (then stops) | Continuously while running |
| Behavior after True | Latches—never called again | Can return False later |
| Typical checks | One-time initialization tasks | Ongoing operational health |

### Custom App Readiness

Apps can implement custom readiness logic by overriding the `is_ready()` method:

```python
from solace_ai_connector.flow.app import App

class MyCustomApp(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_connected = False

    def is_ready(self) -> bool:
        """Custom readiness check - called continuously"""
        # Only ready when DB connection is healthy
        return self.db_connected
```

**When to use custom readiness:**

- Database connections must be established
- External services must be available
- Configuration must be loaded and validated
- Any app-specific condition required before processing messages

The connector is only marked ready when:

1. All flow threads are alive AND
2. All apps with custom `is_ready()` methods return `True`

The connector startup is only marked complete when:

1. All flow threads are alive AND
2. All apps with custom `is_startup_complete()` methods return `True`

## Kubernetes Configuration

Example pod specification:

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
    startupProbe:
      httpGet:
        path: /startup
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 30    # Allow up to 150 seconds for startup
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /readyz
        port: 8080
      periodSeconds: 5
      failureThreshold: 3
```

**Note:** When using a startup probe, Kubernetes disables liveness and readiness probes until the startup probe succeeds. This prevents the liveness probe from killing slow-starting containers.

## Testing

Test the endpoints manually:

```bash
# Test liveness
curl http://localhost:8080/healthz

# Test readiness
curl http://localhost:8080/readyz

# Expected responses
{"status": "ok"}           # When healthy/ready
{"status": "not ready"}    # When not ready
```

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
