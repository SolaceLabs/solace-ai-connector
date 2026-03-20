# Observability

The solace-ai-connector provides comprehensive observability through OpenTelemetry metrics.

## Quick Start

Enable observability in your configuration:

```yaml
management_server:
  enabled: true
  port: 8080

  health:
    enabled: true

  observability:
    enabled: true
    path: /metrics
    metric_prefix: sam
```

Access metrics at: `http://localhost:8080/metrics`

## Metric Families

The framework provides 7 duration histogram families:

| Metric | Description | Labels |
|--------|-------------|--------|
| `outbound.request.duration` | Remote service calls | service.peer.name, operation.name, error.type |
| `gen_ai.client.operation.duration` | LLM inference duration | gen_ai.request.model, tokens, error.type |
| `gen_ai.client.operation.ttft.duration` | Time-to-first-token | gen_ai.request.model, error.type |
| `db.duration` | Database operations | db.collection.name, db.operation.name, error.type |
| `gateway.duration` | Gateway request handling | gateway.name, operation.name, error.type |
| `gateway.ttfb.duration` | Gateway time-to-first-byte | gateway.name, operation.name, error.type |
| `operation.duration` | Internal operations | type, component.name, operation.name, error.type |

## Instrumenting Code

Use the `MonitorLatency` decorator or context manager:

```python
from solace_ai_connector.common.observability import MonitorLatency, BrokerMonitor

# Decorator
@MonitorLatency(BrokerMonitor.publish())
def publish_message(msg):
    broker.publish(msg)

# Context manager
with MonitorLatency(BrokerMonitor.publish()):
    broker.publish(msg)

# Async support
async with MonitorLatency(GenAIMonitor.instance("gpt-4", 15000)):
    response = await llm.generate(prompt)
```

## Monitor Classes

### Available in solace-ai-connector

- **BrokerMonitor** - Solace broker operations
  - `BrokerMonitor.connect()`
  - `BrokerMonitor.publish()`
  - `BrokerMonitor.subscribe()`

- **GenAIMonitor** - LLM operations
  - `GenAIMonitor.instance(model="gpt-4", tokens=15000)`

- **GenAITTFTMonitor** - LLM time-to-first-token
  - `GenAITTFTMonitor.instance(model="gpt-4")`

- **DBMonitor** - Database operations
  - `DBMonitor.query(collection="sessions")`
  - `DBMonitor.insert(collection="users")`
  - `DBMonitor.update(collection="sessions")`
  - `DBMonitor.delete(collection="sessions")`

- **OperationMonitor** - Generic operations
  - `OperationMonitor.instance(component_type="connector", component_name="SolaceAIConnector", operation="create_flows")`

### Abstract Monitors (implement in downstream repos)

- **RemoteRequestMonitor** - Base for remote service calls (S3, OAuth, etc.)
- **GatewayMonitor** - Base for gateway implementations
- **GatewayTTFBMonitor** - Base for gateway TTFB tracking

## Configuration

### Default Buckets

All metrics use default "Aggressive" bucket configuration optimized for cost:

- Remote requests: [25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s]
- GenAI: [0.5s, 1s, 2s, 5s, 10s, 20s, 30s, 60s, 120s]
- GenAI TTFT: [0.1s, 0.25s, 0.5s, 1s, 2s, 3s, 5s, 10s, 20s, 30s]
- Database: [1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s]
- Gateway: [10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, 30s, 60s]
- Gateway TTFB: [10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, 30s, 60s]
- Operations: [10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s, 30s, 60s]

### Configuration Structure

The observability configuration has two sections:
- **system:** Configuration for built-in histogram metrics (the 7 duration families)
- **custom:** Label filtering for custom metrics created via factory methods

### Custom Buckets (Built-in Histograms)

Override buckets for specific metrics in the `system:` section:

```yaml
observability:
  enabled: true
  path: /metrics
  metric_prefix: sam

  system:
    gen_ai.client.operation.duration:
      values: [1.0, 5.0, 10.0, 30.0, 60.0]
```

### Label Exclusion (Built-in Histograms)

Reduce cardinality by excluding labels in the `system:` section:

```yaml
observability:
  system:
    gen_ai.client.operation.duration:
      exclude_labels: [tokens]  # Default: tokens excluded

    db.duration:
      exclude_labels: [db.operation.name]  # Only track by collection
```

### Disabling Metrics

Set empty buckets to disable a metric:

```yaml
observability:
  system:
    gateway.ttfb.duration:
      values: []  # Disabled
```

### Custom Metric Label Filtering

Filter labels for custom metrics (counters, gauges) in the `custom:` section:

```yaml
observability:
  custom:
    gateway.events.processed:
      exclude_labels: [verbose_detail]

    broker.active.connections:
      exclude_labels: [detail_label]
```

### Metric Prefix

Control the prefix prepended to all metric names:

```yaml
observability:
  metric_prefix: sam  # Results in "sam.outbound.request.duration"
  # metric_prefix: ""  # Results in "outbound.request.duration" (no prefix)
```

## Custom Metrics (Factory Methods)

In addition to the built-in histogram families, you can create custom counters and gauges using factory methods.

### Creating Counters

Use `create_counter()` to track event counts:

```python
from solace_ai_connector.common.observability import MetricRegistry

registry = MetricRegistry.get_instance()

# Create a counter (returns NoOpRecorder if observability is disabled)
event_counter = registry.create_counter(
    name="gateway.events.processed",
    description="Number of events processed by gateway",
    unit="1"
)

# Record events - always safe to call
event_counter.record(1, {"gateway": "chat", "event_type": "message"})
event_counter.record(1, {"gateway": "chat", "event_type": "command"})
```

### Creating Push-Style Gauges

Use `create_gauge()` to track values that go up and down:

```python
# Create a gauge (UpDownCounter)
connection_gauge = registry.create_gauge(
    name="broker.active.connections",
    description="Active broker connections",
    unit="1"
)

# Increment when connection established
connection_gauge.record(1, {"broker.name": "prod"})

# Decrement when connection closed
connection_gauge.record(-1, {"broker.name": "prod"})
```

### Creating Observable Gauges

Use `create_observable_gauge()` for callback-based gauges:

```python
from opentelemetry.metrics import Observation

# Callback function to report current value
def report_queue_depth(options):
    return [
        Observation(len(message_queue), {"queue": "main"}),
        Observation(len(error_queue), {"queue": "errors"})
    ]

# Create observable gauge (returns None if disabled)
obs_gauge = registry.create_observable_gauge(
    name="queue.depth",
    callbacks=[report_queue_depth],
    description="Current queue depth",
    unit="1"
)
# OTel will call the callback automatically at scrape/export time
```

### Factory Method Behavior

Factory methods return safe-to-use recorders even when observability is disabled:

- `create_counter()` - Returns `NoOpRecorder` if disabled (safe to call `record()`)
- `create_gauge()` - Returns `NoOpRecorder` if disabled (safe to call `record()`)
- `create_observable_gauge()` - Returns `None` if disabled (single init-time check acceptable)

No need to guard factory method calls or recorder usage:

```python
# This pattern is safe and recommended
counter = MetricRegistry.get_instance().create_counter("my.metric")
counter.record(1, {"label": "value"})  # Always safe, no guards needed
```

## Exporter Integration

### Prometheus (Default)

Metrics automatically exposed at `/metrics` endpoint for Prometheus scraping.

**Kubernetes ServiceMonitor:**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: solace-ai-connector
spec:
  selector:
    matchLabels:
      app: solace-ai-connector
  endpoints:
  - port: management
    path: /metrics
    interval: 30s
```

### Additional Exporters (OTLP, Datadog, Grafana Cloud)

Add additional exporters in downstream code:

```python
from solace_ai_connector.common.observability import MetricRegistry
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

registry = MetricRegistry.get_instance()

# Add OTLP exporter
otlp_exporter = OTLPMetricExporter(endpoint="http://otel-collector:4318")
registry.add_exporter(otlp_exporter)
```

**Datadog exporter:**
```python
from opentelemetry.exporter.datadog import DatadogMetricExporter

dd_exporter = DatadogMetricExporter(
    api_key=os.getenv("DD_API_KEY"),
    site="datadoghq.com"
)
registry.add_exporter(dd_exporter)
```

**Grafana Cloud (Prometheus Remote Write):**
```python
from opentelemetry.exporter.prometheus_remote_write import PrometheusRemoteWriteMetricExporter

grafana_exporter = PrometheusRemoteWriteMetricExporter(
    endpoint="https://prometheus-prod-01.grafana.net/api/prom/push",
    headers={"Authorization": f"Bearer {grafana_token}"}
)
registry.add_exporter(grafana_exporter)
```

## Implementing Custom Monitors

For downstream repos (SAM/SAMe) to add custom remote service monitors:

```python
from solace_ai_connector.common.observability.monitors import RemoteRequestMonitor, MonitorInstance

class S3Monitor(RemoteRequestMonitor):
    """Monitor for S3 operations."""

    @classmethod
    def put_object(cls):
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "service.peer.name": "s3",
                "operation.name": "put_object"
            },
            error_parser=cls.parse_error
        )

    @classmethod
    def get_object(cls):
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "service.peer.name": "s3",
                "operation.name": "get_object"
            },
            error_parser=cls.parse_error
        )
```

Usage:
```python
@MonitorLatency(S3Monitor.put_object())
def upload_file(file_data):
    s3_client.upload(file_data)
```

## See Also

- [Health Checks](./health_checks.md)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Configuration Guide](./configuration.md)