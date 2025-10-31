# Logging

The Solace AI Connector leverages Python's built-in logging module to provide flexible and standardized logging capabilities.

## Configuring Logging

The Solace AI Connector uses Python's [fileConfig format](https://docs.python.org/3/library/logging.config.html#configuration-file-format) for logging configuration. To configure logging, create a logging configuration .ini file and point to the file with the environment variable: `LOGGING_CONFIG_PATH=./path/to/logging_config.ini`

Here's an example .ini configuration that demonstrates a common setup:

```ini
[loggers]
keys=root,solace_ai_connector,sam_trace

[logger_root]
level=WARN
handlers=streamHandler,rotatingFileHandler
qualname=root

[logger_solace_ai_connector]
level=${LOGGING_SOLACE_AI_CONNECTOR_LEVEL, INFO}
handlers=
qualname=solace_ai_connector

[logger_sam_trace]
level=${LOGGING_SAM_TRACE_LEVEL, INFO}
handlers=
qualname=sam_trace

[handlers]
keys=streamHandler,rotatingFileHandler
```

This configuration:
- Creates a root logger that catches all unhandled log messages from any module at WARN or higher

- Routes all qualifying log messages to both console and a rotating log file

- Defines a main application logger (`solace_ai_connector`) that captures INFO level logs specifically from the `solace_ai_connector` module

- Includes a special debug logger (`sam_trace`) that can be enabled during development for detailed troubleshooting of data structures and internal operations. To enable this logger, set its level to DEBUG.

Note that, as demonstrated in the above example, environment variable substitution is supported with the syntax `${VAR_NAME, default_value}`. Users can use variable names of their choice; the application will look for these environment variables at runtime and substitute their values accordingly. If the environment variable is not set, the provided default value will be used.

For additional standard logging configuration options and information on creating handlers, refer to the [Python logging documentation](https://docs.python.org/3/library/logging.config.html#configuration-file-format).

### Effective Log Level

When configuring levels for different loggers, the effective log level is determined by the most specific logger configuration in the hierarchy. For example, if you set the root logger to DEBUG but create a custom logger for `solace_ai_connector` at the INFO level, the effective log level for the `solace_ai_connector` module will be INFO. This means DEBUG level logs from `solace_ai_connector` will not be handled, as they fall below the effective log level.

### Structured Logging

Structured logging outputs log messages in JSON format, making them easier to parse, search, and analyze in log aggregation systems like Datadog, Splunk, or Elasticsearch.

#### Configuration

Enabling structured logging includes two steps:

**Step 1: Configure the JSON Formatter**

Define a formatter that uses `class=solace_ai_connector.logging.TaggedJsonFormatter` and apply it to your chosen handlers:

```ini
[formatters]
keys=simpleFormatter,jsonFormatter

[formatter_simpleFormatter]
format=%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s

[formatter_jsonFormatter]
class=solace_ai_connector.logging.TaggedJsonFormatter
format=%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s

[handler_rotatingFileHandler]
class=logging.handlers.RotatingFileHandler
formatter=jsonFormatter
args=('sam.log', 'a', 52428800, 10)
```

**Step 2: Configure Tags via Environment Variables (Optional)**

Log aggregation systems expect tags to be included in log records for better filtering, grouping, and analysis.

To configure which tags should be added to log records, use the `LOGGING_JSON_TAGS` environment variable:

```bash
# Specify which environment variables to inject as tags as a comma-separated list
export LOGGING_JSON_TAGS=SERVICE_NAME,ENVIRONMENT,VERSION,REGION

# Set the actual values for the tags
export SERVICE_NAME=payment-service
export ENVIRONMENT=production
export VERSION=2.1.0
export REGION=us-east-1
```

With this configuration, all JSON log records will automatically include these tags:

```json
{
   "asctime":"2025-10-30 22:25:56,960",
   "levelname":"INFO",
   "threadName":"MainThread",
   "name":"solace_ai_connector.flow",
   "message":"Processing message",
   "SERVICE_NAME": "payment-service",
   "ENVIRONMENT": "production",
   "VERSION": "2.1.0",
   "REGION": "us-east-1"
}
```

This is a flexible way to add contextual information to your logs without modifying the application code.

> **Note:** If `LOGGING_JSON_TAGS` is not provided, the `service` tag defaults to `"solace_agent_mesh"`. This is done for backward compatibility.

#### Common Use Cases

**Datadog Integration:**
```bash
export LOGGING_JSON_TAGS=service,env,version
export service=payment-service
export env=production
export version=2.1.0
```

**Splunk Or Elasticsearch Integration:**

Unlike Datadog, Splunk and Elasticsearch do not have reserved tag names. You can define any tag that suits your organizational needs:
```bash
export LOGGING_JSON_TAGS=APP,REGION
export APP=payment-service
export REGION=us-east-1
```