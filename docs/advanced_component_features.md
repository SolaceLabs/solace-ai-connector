# Advanced Component Features

This document describes advanced features available to custom components in the Solace AI Connector.

## Table of Contents
- [Broker Request-Response](#broker-request-response)
- [Cache Manager](#cache-manager)
- [Timer Features](#timer-features)

## Broker Request-Response

Components can perform a request and get a response from the broker using the `do_broker_request_response` method. This method supports both simple request-response and streamed responses.

**Enabling Request-Response:**

*   **Simplified App Mode (Recommended):** Set `request_reply_enabled: true` within the `broker:` section of your simplified app definition in the YAML configuration. The framework automatically creates and manages a dedicated `RequestResponseFlowController` for the app, using the same broker connection details.

    ```yaml
    # Simplified App Example
    apps:
      - name: my_requesting_app
        broker:
          # ... connection details ...
          input_enabled: true
          request_reply_enabled: true # Enable RRC for this app
          # ... other broker settings ...
        components:
          - name: my_component
            component_module: my_requesting_component
            # ...
    ```

*   **Standard Flows / Component Level (Deprecated):** You could previously configure `broker_request_response` directly under a component's definition. This is now deprecated in favor of the app-level configuration in simplified apps.

**Usage in Component `invoke`:**

Once enabled at the app level, any component within that app can use `self.do_broker_request_response()`:

```python
# Inside your component's invoke method
if self.is_broker_request_response_enabled():
    # Prepare your request message (payload, topic, user_properties)
    request_message = Message(payload={"query": "data"}, topic="service/request")

    try:
        # --- Simple Request-Response ---
        response_message = self.do_broker_request_response(request_message)
        if response_message:
            response_payload = response_message.get_payload()
            # Process the single response payload
            log.info(f"Received response: {response_payload}")
        else:
            log.warning("Request-response returned no message.")

        # --- Streaming Request-Response ---
        # streaming_complete_expression tells the controller how to identify the last chunk
        streaming_complete_expr = "input.payload:is_last" # Example expression

        response_generator = self.do_broker_request_response(
            request_message,
            stream=True,
            streaming_complete_expression=streaming_complete_expr
        )

        aggregated_result = ""
        for chunk_message, is_last in response_generator:
            chunk_payload = chunk_message.get_payload()
            log.info(f"Received chunk: {chunk_payload}")
            aggregated_result += chunk_payload.get("text", "") # Example aggregation
            if is_last:
                log.info("Last chunk received.")
                break # Exit loop after processing the last chunk

        log.info(f"Aggregated streaming result: {aggregated_result}")

    except TimeoutError:
        log.error("Request-response timed out.")
        # Handle timeout appropriately
    except Exception as e:
        log.error(f"Error during request-response: {e}", exc_info=True)
        # Handle other errors
else:
    log.warning("Broker request-response is not enabled for this component/app.")

```

### Parameters for `do_broker_request_response`

- `message`: The `Message` object containing the request payload, topic, and optional user properties.
- `stream` (optional): Boolean indicating whether to expect a streamed response. Default is `False`.
- `streaming_complete_expression` (optional): An expression (using [Expression Syntax](configuration.md#expression-syntax)) evaluated on each response chunk to determine if it's the last one. This is **required** when `stream=True`. The expression should evaluate to a truthy value for the last chunk.

### Return Value

- For non-streamed responses (`stream=False`): Returns the single response `Message` object, or `None` if no response is received before timeout.
- For streamed responses (`stream=True`): Returns a generator that yields tuples of `(chunk_message, is_last)`.
    - `chunk_message`: A `Message` object representing one chunk of the response.
    - `is_last`: A boolean indicating if this chunk is the last one, based on the evaluation of `streaming_complete_expression`.

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
# Set a value with expiry (expiry is in seconds)
self.cache_service.add_data("my_key", {"some": "data"}, expiry=300)

# Get a value
value = self.cache_service.get_data("my_key")
if value:
    # Process value
    pass

# Delete a value
self.cache_service.remove_data("my_key")

# Get all values (including metadata and expiry - specific to backend implementation)
# Note: get_all() might not be available on all backends or might be inefficient.
# Check specific backend documentation if needed.
# For InMemoryStorage:
# all_data = self.cache_service.storage.store
```

### Configuration

The cache service can be configured in the main configuration file:

```yaml
cache:
  backend: "memory"  # or "sqlalchemy"
  # connection_string: "sqlite:///cache.db"  # Required for SQLAlchemy backend
```

## Timer Features

The timer manager allows components to schedule one-time or recurring timer events. This is useful for implementing delayed actions, periodic tasks, or timeouts.

### Features

1. One-time and recurring timers
2. Customizable timer IDs for easy management
3. Optional payloads for timer events

### Usage

Components can access the timer manager through `self.add_timer` and `self.cancel_timer` (methods inherited from `ComponentBase`).

```python
# Add a one-time timer to trigger in 5 seconds
self.add_timer(delay_ms=5000, timer_id="my_one_time_timer", payload={"action": "process_later"})

# Add a recurring timer to trigger every 10 seconds, starting after 1 second
self.add_timer(delay_ms=1000, timer_id="recurring_check", interval_ms=10000, payload={"type": "health_check"})

# Cancel a timer
self.cancel_timer(timer_id="my_one_time_timer")
```

### Handling Timer Events

To handle timer events, components should implement the `handle_timer_event` method:

```python
def handle_timer_event(self, timer_data):
    """
    Called when a timer previously scheduled by this component instance fires.

    Args:
        timer_data (dict): A dictionary containing information about the timer event.
                           Includes 'timer_id' and 'payload'.
    """
    timer_id = timer_data.get("timer_id")
    payload = timer_data.get("payload")

    log.info(f"{self.log_identifier} Timer '{timer_id}' fired with payload: {payload}")

    if timer_id == "my_one_time_timer":
        # Perform the delayed action
        action = payload.get("action")
        # ... do something based on action ...
    elif timer_id == "recurring_check":
        # Perform the periodic task
        # ... run health check ...
    else:
        log.warning(f"{self.log_identifier} Received unknown timer event: {timer_id}")

```

Timer events are automatically dispatched to the `handle_timer_event` method of the specific component instance that scheduled the timer.
