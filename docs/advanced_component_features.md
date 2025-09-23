# Advanced Component Features

This document describes advanced features available to custom components in the Solace AI Connector.

## Table of Contents
- [Broker Request-Response](#broker-request-response)
- [Cache Manager](#cache-manager)
- [Timer Features](#timer-features)

## Broker Request-Response

Components can perform request-response operations with Solace brokers using two distinct modes, supporting both synchronous (blocking) and asynchronous (non-blocking) patterns.

### Single-Session Mode (Default)

This is the traditional and simplest approach, where a single, shared request-response session is automatically managed for an entire application.

-   **Overview**: One shared session per app.
-   **Configuration**: Enabled via the app-level `request_reply_enabled: true` setting in a simplified app's `broker` configuration.
-   **Use Cases**: Ideal for most standard request-response scenarios where components within an app can share a single broker session.

### Multi-Session Mode (Advanced)

This mode provides fine-grained control, allowing a component to create, manage, and destroy multiple independent request-response sessions, each with potentially different broker configurations.

-   **Overview**: A component can manage multiple, independent sessions.
-   **Configuration**: Enabled via the component-level `multi_session_request_response` configuration block.
-   **Use Cases**: Perfect for multi-tenant applications, scenarios requiring connections to different broker environments, or when session isolation is needed for reliability.

---

**For detailed documentation on both modes, API usage, and complete examples, please see the comprehensive guide:**

-   **[Broker Request-Response Guide](guides/broker_request_response.md)**

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
