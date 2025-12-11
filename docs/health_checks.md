# Health Check Endpoints

The Solace AI Connector provides HTTP-based health check endpoints for Kubernetes liveness and readiness probes.

## Configuration

Add the following to your connector configuration:

```yaml
health_check:
  enabled: true                          # Default: false
  port: 8080                             # Default: 8080
  liveness_path: /healthz                # Default: /healthz
  readiness_path: /readyz                # Default: /readyz
  check_interval_seconds: 5              # Default: 5
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
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /readyz
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 3
```

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
