# Advanced Component Features

This document describes advanced features available to custom components in the Solace AI Connector.

## Table of Contents
- [Broker Request-Response](#broker-request-response)
- [Cache Manager](#cache-manager)
- [Timer Features](#timer-features)

## Broker Request-Response

Components can perform a request and get a response from the broker using the `do_broker_request_response` method. This method supports both simple request-response and streamed responses. To use this feature, the component's configuration must include a `broker_request_response` section. For details on how to configure this section, refer to the [Broker Request-Response Configuration](configuration.md#broker-request-response-configuration) in the configuration documentation.

This feature would be used in the invoke method of a custom component. When the `do_broker_request_response` method is called, the component will send a message to the broker and then block until a response (or a series of streamed chunks) is received. This makes it very easy to call services that are available via the broker.

### Usage

```python
response = self.do_broker_request_response(message, stream=False)
```

For streamed responses:

```python
for chunk, is_last in self.do_broker_request_response(message, stream=True, streaming_complete_expression="input.payload:streaming.last_message"):
    # Process each chunk
    if is_last:
        break
```

### Parameters

- `message`: The message to send to the broker. This must have a topic and payload.
- `stream` (optional): Boolean indicating whether to expect a streamed response. Default is False.
- `streaming_complete_expression` (optional): An expression to evaluate on each response chunk to determine if it's the last one. This is required when `stream=True`.

### Return Value

- For non-streamed responses: Returns the response message.
- For streamed responses: Returns a generator that yields tuples of (chunk, is_last). Each chunk is a fully formed message with the format of the response. `is_last` is a boolean indicating if the chunk is the last one.

## Memory Cache

The cache service provides a flexible way to store and retrieve data with optional expiration. It supports different storage backends and offers features like automatic expiry checks.

### Features

1. Multiple storage backends:
   - In-memory storage
   - SQLAlchemy-based storage (for persistent storage)

2. Key-value storage with metadata and expiry support
3. Automatic expiry checks in a background thread
4. Thread-safe operations

### Usage

Components can access the cache service through `self.cache_service`. Here are some common operations:

```python
# Set a value with expiry
self.cache_service.set("key", "value", expiry=300)  # Expires in 300 seconds

# Get a value
value = self.cache_service.get("key")

# Delete a value
self.cache_service.delete("key")

# Get all values (including metadata and expiry)
all_data = self.cache_service.get_all()
```

### Configuration

The cache service can be configured in the main configuration file:

```yaml
cache:
  backend: "memory"  # or "sqlalchemy"
  connection_string: "sqlite:///cache.db"  # for SQLAlchemy backend
```

## Timer Features

The timer manager allows components to schedule one-time or recurring timer events. This is useful for implementing delayed actions, periodic tasks, or timeouts.

### Features

1. One-time and recurring timers
2. Customizable timer IDs for easy management
3. Optional payloads for timer events

### Usage

Components can access the timer manager through `self.timer_manager`. Here are some common operations:

```python
# Add a one-time timer
self.add_timer(delay_ms=5000, timer_id="my_timer", payload={"key": "value"})

# Add a recurring timer
self.add_timer(delay_ms=5000, timer_id="recurring_timer", interval_ms=10000, payload={"type": "recurring"})

# Cancel a timer
self.cancel_timer(timer_id="my_timer")
```

### Handling Timer Events

To handle timer events, components should implement the `handle_timer_event` method:

```python
def handle_timer_event(self, timer_data):
    timer_id = timer_data["timer_id"]
    payload = timer_data["payload"]
    # Process the timer event
```

Timer events are automatically dispatched to the appropriate component by the timer manager.
