# Simplified App Mode

## Introduction

The Solace AI Event Connector provides a "Simplified App Mode" designed to streamline the configuration for common application patterns. Instead of explicitly defining a `flow` with `BrokerInput`, `BrokerOutput`, and potentially other plumbing components, you can define an `app` directly, specifying its broker interactions and processing logic components. The framework automatically generates the necessary underlying flow and components based on your simplified configuration.

This mode is ideal for applications that primarily:

1.  Receive messages from a single Solace queue based on topic subscriptions.
2.  Process these messages using one or more custom or built-in components.
3.  Optionally, send output messages back to the broker.
4.  Optionally, perform request-reply interactions with the broker during processing.

## Benefits

*   **Reduced Boilerplate:** Eliminates the need to manually configure `BrokerInput`, `BrokerOutput`, and routing components for simple scenarios.
*   **Clearer Configuration:** Focuses the configuration on the application's core logic and its direct interaction points with the broker.
*   **Faster Development:** Simplifies getting started with basic connector applications.

## Configuration

Simplified Apps are defined within the main `config.yaml` (or merged configuration files) under the `apps:` list. A simplified app definition includes `name`, `broker`, optional `config`, and `components` sections, but **omits** the `flows` section.

### Core Structure (YAML)

```yaml
# config.yaml
apps:
  - name: my_simple_processor # Unique name for this app instance
    # --- Broker Interaction Definition ---
    broker:
      # Standard Solace Connection Details (Required)
      broker_type: solace # Or dev_broker
      broker_url: <protocol>://<host>:<port>
      broker_vpn: <vpn_name>
      broker_username: <username>
      broker_password: <password>
      # Optional: trust_store_path, reconnection_strategy, retry_interval, retry_count

      # --- Interaction Flags ---
      input_enabled: true # REQUIRED: Must be true to receive messages
      output_enabled: true # Optional: Set true to enable sending messages
      request_reply_enabled: false # Optional: Set true to enable request-reply

      # --- Input Config (if input_enabled: true) ---
      queue_name: "my/app/input" # REQUIRED: The single queue this app listens on
      create_queue_on_start: true # Optional: Default true. Attempts to create the queue.
      payload_encoding: "utf-8" # Optional: Default utf-8. For decoding incoming messages.
      payload_format: "json" # Optional: Default json. For decoding incoming messages.
      # Optional: max_redelivery_count

      # --- Output Config (if output_enabled: true) ---
      payload_encoding: "utf-8" # Optional: Default utf-8. For encoding outgoing messages.
      payload_format: "json" # Optional: Default json. For encoding outgoing messages.
      # Optional: propagate_acknowledgements (default: true)

      # --- Request-Reply Config (if request_reply_enabled: true) ---
      # Uses the same connection details as input/output.
      # Optional: request_expiry_ms (default: 60000)
      # Optional: response_topic_prefix (default: "reply")
      # Optional: response_topic_suffix (default: "")
      # Optional: response_queue_prefix (default: "reply-queue")
      # Optional: user_properties_reply_topic_key (default: "__solace_ai_connector_broker_request_response_topic__")
      # Optional: user_properties_reply_metadata_key (default: "__solace_ai_connector_broker_request_reply_metadata__")
      # Optional: response_topic_insertion_expression (default: "")

    # --- App-Level Configuration ---
    app_config: # Optional
      # Global configuration accessible by all components in this app
      # via self.get_config('my_global_param')
      my_global_param: "some_value"
      api_key: ${MY_API_KEY} # Environment variables supported

    # --- Processing Components ---
    components:
      # List of one or more components that define the app's logic
      - name: main_processor # Unique name for the component within the app
        component_module: my_processor_module # Module containing the component class
        # Optional: component_package, component_base_path
        num_instances: 1 # Optional: Default 1. Scales this specific component.
        component_config:
          # Configuration specific to 'my_processor_module'
          processing_threshold: 100
        # Subscriptions this component handles (Required if input_enabled: true)
        subscriptions:
          - topic: "data/input/topic1/>"
          - topic: "data/input/topic2"
      # --- Optional Second Component ---
      - name: secondary_logger
        component_module: log_message
        component_config:
          log_level: "INFO"
          message_prefix: "Secondary:"
        subscriptions:
          - topic: "audit/events/>"

# --- Optional: Define App in Code ---
# Alternatively, define the entire app in a Python file and load via app_module:
# apps:
#  - name: my_code_based_app
#    app_module: my_app_definition_module # Points to a .py file
#    # YAML config here merges with/overrides config defined in the Python file
#    app_config:
#      my_global_param: "yaml_override_value"
```

### Key Sections Explained

*   **`name`**: A unique identifier for this application instance within the connector.
*   **`broker`**: Defines how the application interacts with the Solace broker.
    *   **Connection Details**: Standard parameters (`broker_url`, `broker_vpn`, etc.) to connect.
    *   **`input_enabled`**: Must be `true` for the app to receive messages.
    *   **`output_enabled`**: Set to `true` if any component needs to send messages back to the broker (either via return value or `app.send_message`).
    *   **`request_reply_enabled`**: Set to `true` if any component needs to perform synchronous request-reply operations using `self.do_broker_request_response()`.
    *   **`queue_name`**: The **single, dedicated queue** this application instance will listen on. All subscriptions from all components are added to this queue.
    *   **`payload_encoding`/`payload_format`**: Specify how message payloads are decoded on input and encoded on output by the implicit broker components.
*   **`app_config`**: An optional dictionary for application-level configuration. Any component within this app can access these values using `self.get_config('param_name')`. This is useful for shared settings like API keys, thresholds, etc.
*   **`components`**: A list defining the processing logic.
    *   **`name`**: Unique name for the component within the app.
    *   **`component_module`**: The Python module name where the component class is defined (e.g., `my_processor`, `llm_chat`).
    *   **`component_config`**: Configuration specific to this component instance, passed during its initialization.
    *   **`subscriptions`**: **Required if `input_enabled` is true.** A list of dictionaries, each specifying a `topic` (using Solace wildcards `*` and `>`) that this component should process. Messages arriving on the app's `queue_name` are routed based on these subscriptions.
    *   **`num_instances`**: Optional (default 1). Scales *only this specific component* for parallel processing. See [Scalability](#scalability).

## How it Works: Implicit Flow Generation

When the connector loads a simplified app configuration, it automatically creates an internal `Flow` containing the necessary components:

1.  **`BrokerInput` (Implicit):**
    *   Created if `input_enabled: true`.
    *   Connects to the broker using `broker` details.
    *   Listens on the specified `broker.queue_name`.
    *   Applies **all** subscriptions from **all** components listed in `app.components` to this single queue.
    *   Receives messages, decodes the payload, and passes the `Message` object to the next step.

2.  **`SubscriptionRouter` (Implicit):**
    *   Created if `input_enabled: true` AND there is **more than one** component defined in `app.components`.
    *   Receives the `Message` from `BrokerInput`.
    *   Inspects the message topic.
    *   Compares the topic against the `subscriptions` of each component *in the order they appear in the configuration*.
    *   Forwards the `Message` to the **first** component whose subscription matches the topic.
    *   If no match is found, the message is logged and discarded.

3.  **User Components:**
    *   These are the components you define in the `app.components` list.
    *   They receive the `Message` from `BrokerInput` (if only one component) or `SubscriptionRouter`.
    *   Execute their `invoke` method.
    *   Can access app-level config via `self.get_config()`.
    *   Can access the parent app object via `self.get_app()`.

4.  **`BrokerOutput` (Implicit):**
    *   Created if `output_enabled: true`.
    *   Connects to the *same* broker using `broker` details.
    *   Receives output data from user components (see [Output Mechanisms](#output-mechanisms)).
    *   Encodes the payload according to `broker.payload_encoding`/`broker.payload_format`.
    *   Sends the message to the specified topic.

**Visual Flow:**

*   **Single Component:** `BrokerInput` -> `User Component` -> `BrokerOutput` (if enabled)
*   **Multiple Components:** `BrokerInput` -> `SubscriptionRouter` -> `User Component A` or `User Component B` ... -> `BrokerOutput` (if enabled)

## Routing

When multiple components are defined, the implicit `SubscriptionRouter` handles message distribution:

*   **Order Matters:** The router checks subscriptions in the order components are listed in the `app.components` section.
*   **First Match Wins:** The message is sent to the *first* component whose subscription list contains a topic matching the incoming message's topic. Subsequent components are not checked for that message.
*   **Wildcards:** Standard Solace topic wildcards (`*` for single level, `>` for multiple levels at the end) are supported in subscriptions.
*   **No Match:** If a message arrives on the queue but its topic doesn't match any subscription in any component, it will be logged and discarded by the router. Ensure your subscriptions cover all expected topics.

## Output Mechanisms

Components can send messages back to the broker if `output_enabled: true`:

1.  **Return Value (Primary):**
    *   The return value of your component's `invoke` method is automatically sent to the implicit `BrokerOutput`.
    *   The return value **must** be a dictionary matching the `BrokerOutput` input schema:
        ```python
        return {
            "payload": {"processed_data": "value"},
            "topic": "results/processed",
            "user_properties": {"correlation_id": "123"} # Optional
        }
        ```
    *   If `invoke` returns `None`, no message is sent via this mechanism.

2.  **`app.send_message()` (Secondary):**
    *   Components can access the parent `App` object using `self.get_app()`.
    *   The `App` object has a `send_message` method:
        ```python
        app = self.get_app()
        app.send_message(
            payload={"status": "update", "detail": "step 1 complete"},
            topic="process/updates",
            user_properties={"id": "xyz"}
        )
        ```
    *   This allows sending multiple, independent messages from within a single `invoke` call.
    *   Messages sent via `app.send_message()` are handled independently of the `invoke` return value.

## Request-Reply

If `request_reply_enabled: true` in the `broker` config:

*   The framework automatically sets up a dedicated `RequestResponseFlowController` for the app, using the same broker connection details.
*   Components within the app can then use the standard `self.do_broker_request_response()` method to send a request and wait for a response.
    ```python
    if self.is_broker_request_response_enabled():
        request_payload = {"query": "some data"}
        request_topic = "service/request/topic"
        request_message = Message(payload=request_payload, topic=request_topic)

        # For a single response:
        response_message = self.do_broker_request_response(request_message)
        if response_message:
            response_payload = response_message.get_payload()
            # ... process response ...

        # For streaming responses:
        # response_generator = self.do_broker_request_response(
        #     request_message,
        #     stream=True,
        #     streaming_complete_expression="input.payload:is_last_chunk" # Example expression
        # )
        # for response_message, is_last in response_generator:
        #     # ... process chunk ...
        #     if is_last:
        #         break
    else:
        log.warning("Request-reply is not enabled for this app.")
    ```

## Defining Apps in Code (`app_module`)

For more complex scenarios or tighter integration, you can define the entire simplified app structure within a Python file.

1.  **Create a Python file** (e.g., `my_app_definition.py`).
2.  **Define your component class(es)** inheriting from `ComponentBase`.
3.  **Define a custom App class** inheriting from `solace_ai_connector.flow.app.App`.
4.  **Define the app configuration** as a class attribute named `app_config` within your custom App class. Use `component_class: YourComponentClassName` instead of `component_module`.
5.  **Reference this file in your YAML:**

    ```yaml
    # config.yaml
    apps:
      - name: my_code_app_instance # Name for this instance
        app_module: my_app_definition # Module name (e.g., my_app_definition.py)
        # Optional: Override or add app-level config here
        config:
          code_defined_param: "override_from_yaml"
    ```

See `examples/simple_echo_app.py` for a complete working example.

## Configuration Merging (Code vs. YAML)

When using `app_module`:

*   Configuration defined in the YAML (`app_info` passed to `App.__init__`) is **merged over** the configuration defined in the code (`YourAppClass.app_config`).
*   **YAML values take precedence.**
*   This allows you to define defaults in code and override specific settings (like broker credentials, topics, etc.) in the deployment YAML.
*   The merging applies to the entire app structure (`broker`, `config`, `components`, etc.). `deep_merge` logic is used.

Component configuration (`component_config`) precedence within `self.get_config()`:

1.  Value from YAML `component_config` for the specific component instance.
2.  Value from YAML `app.config` (app-level global config).
3.  Value from the component's definition in the flow config (less common for simplified apps) or default from the component's `info` dictionary.

## Scalability (`num_instances`)

*   **App Level:** Setting `num_instances` directly under the app definition in YAML (e.g., `apps: - name: my_app\n num_instances: 3`) creates multiple independent instances of the entire app, each with its own broker connections (Input, Output, RRC) and component instances. This scales the entire application horizontally.
*   **Component Level:** Setting `num_instances` within a specific component's definition (e.g., `components: - name: processor\n num_instances: 5`) scales *only that component*.
    *   Multiple instances of the component class are created.
    *   They all share the same input queue managed by the framework.
    *   This allows parallel processing for that specific step without increasing broker connections.
    *   Useful for CPU-bound or I/O-bound processing steps within the app.

## Example: Simple Echo App (Code-Based)

Refer to the `examples/simple_echo_app.py` file for a complete example of defining a simplified app entirely within Python code, including the component and the custom `App` subclass. This demonstrates using `component_class` and defining the `app_config` structure in code.
