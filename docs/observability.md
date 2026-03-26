# Observability

The solace-ai-connector provides comprehensive observability through OpenTelemetry metrics. The framework includes 7 prebuilt duration histograms for common operations and supports custom counters and gauges for application-specific metrics.

## Quick Start

Enable observability in your configuration:

```yaml
management_server:
  enabled: true
  port: 8080
  observability:
    enabled: true
    path: /metrics
    metric_prefix: sam
```

Access metrics at: `http://localhost:8080/metrics`

## Prebuilt Histogram Metrics

The framework provides 7 duration histograms that automatically track latency:

| Metric | Description | Default Buckets (seconds) |
|--------|-------------|---------------------------|
| `outbound.request.duration` | Remote service calls (S3, OAuth, HTTP) | [0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10] |
| `gen_ai.client.operation.duration` | LLM inference duration | [0.5, 1, 2, 5, 10, 20, 30, 60, 120] |
| `gen_ai.client.operation.ttft.duration` | Time-to-first-token for streaming | [0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 30] |
| `db.duration` | Database operations | [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1] |
| `gateway.duration` | Gateway request processing | [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60] |
| `gateway.ttfb.duration` | Gateway time-to-first-byte | [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60] |
| `operation.duration` | Internal component operations | [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60] |

## Configuration

### Full YAML Configuration

```yaml
management_server:
  enabled: true
  port: 8080
  observability:
    enabled: true
    path: /metrics
    metric_prefix: sam

    # Histogram configuration
    distribution_metrics:
      outbound.request.duration:
        values: [0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

      gen_ai.client.operation.duration:
        values: [0.5, 1, 2, 5, 10, 20, 30, 60, 120]

      gen_ai.client.operation.ttft.duration:
        values: [0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 30]

      db.duration:
        values: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1]

      gateway.duration:
        values: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]

      gateway.ttfb.duration:
        values: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]

      operation.duration:
        values: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60]

```

### Filtering Labels

You can reduce metric cardinality by excluding specific labels:

```yaml
observability:
  distribution_metrics:
    gen_ai.client.operation.duration:
      exclude_labels: [tokens]  # Remove high-cardinality token count label
```

Framework also support `value_metrics` section - for counter and gauge types, 
you can use it in the config to explicitely filter labels or disable metrics totally.

```yaml
observability:
  ...
  value_metrics:
    gateway.events.processed:
      exclude_labels: [event_detail, timestamp]
```

### Disabling Metrics

To disable a metric entirely, exclude all labels using the wildcard `[*]`:

```yaml
observability:
  distribution_metrics:
    gateway.ttfb.duration:
      exclude_labels: [*]  # Metric completely disabled

  value_metrics:
    debug.temporary.metric:
      exclude_labels: [*]  # Metric completely disabled
```

## Using Metrics in Code

### Recording Histogram Metrics

Use the `MonitorLatency` decorator or context manager:

```python
from solace_ai_connector.common.observability import MonitorLatency, BrokerMonitor, GenAIMonitor


# Decorator
@MonitorLatency(BrokerMonitor.publish())
def publish_message(msg):
    broker.publish(msg)


# Context manager
with MonitorLatency(GenAIMonitor.create("gpt-4", 15000)):
    response = await llm.generate(prompt)
```

### Creating Custom Metrics

Use factory methods to create counters and gauges:

```python
from solace_ai_connector.common.observability import MetricRegistry

registry = MetricRegistry.get_instance()

# Counter - tracks cumulative event counts
event_counter = registry.create_counter(
    name="gateway.events.processed",
    description="Number of events processed",
    unit="1"
)
event_counter.record(1, {"gateway": "chat", "event_type": "message"})

# Gauge - tracks fluctuating values
connection_gauge = registry.create_gauge(
    name="broker.active.connections",
    description="Active broker connections",
    unit="1"
)
connection_gauge.record(1, {"broker.name": "prod"})   # Increment
connection_gauge.record(-1, {"broker.name": "prod"})  # Decrement
```

## Available Monitor Classes

- **BrokerMonitor** - `publish()`
- **GenAIMonitor** - `create(model, tokens=None)`
- **GenAITTFTMonitor** - `create(model)`
- **DBMonitor** - `query(collection)`, `insert(collection)`, `update(collection)`, `delete(collection)`
- **OperationMonitor** - `create(component_type, component_name, operation)`
- **GatewayMonitor** - Abstract base class (implement in downstream repos)
- **GatewayTTFBMonitor** - Abstract base class (implement in downstream repos)

## See Also

- [Health Checks](./health_checks.md)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)