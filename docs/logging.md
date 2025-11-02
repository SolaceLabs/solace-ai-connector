# Logging

The Solace AI Connector leverages Python's built-in logging module to provide flexible and standardized logging capabilities.

## Configuring Logging

To configure logging, point the environment variable `LOGGING_CONFIG_PATH=./path/to/logging_config.yaml` to your logging configuration file.

The application automatically detects the format of your configuration file and applies the appropriate configuration method:

1. **INI format** - Uses Python's [fileConfig](https://docs.python.org/3/library/logging.config.html#configuration-file-format)
2. **JSON format** - Uses Python's [dictConfig](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig)
3. **YAML format** - Uses Python's [dictConfig](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig)

> **Notes:** 
> - JSON and YAML formats are recommended as they provide advanced features not available with INI format.
> - This document uses YAML in its examples, but examples can be easily adapted to JSON format.

Here's an example configuration that demonstrates a common setup:
```yaml
version: 1
disable_existing_loggers: false

formatters:
  simpleFormatter:
    format: "%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s"

handlers:
  streamHandler:
    class: logging.StreamHandler
    formatter: simpleFormatter
    stream: "ext://sys.stdout"

  rotatingFileHandler:
    class: logging.handlers.RotatingFileHandler
    formatter: simpleFormatter
    filename: ${LOGGING_FILE_NAME, app.log}
    mode: a
    maxBytes: 52428800  # 50MB
    backupCount: 10

loggers:
  solace_ai_connector:
    level: INFO  
    handlers: []
    qualname: solace_ai_connector
    propagate: true

  sam_trace:
    level: INFO
    handlers: []
    qualname: sam_trace
    propagate: true

root:
  level: ${LOGGING_ROOT_LEVEL, WARNING}
  handlers: [streamHandler, rotatingFileHandler]
```

This configuration:
- Defines a simple log message format that is then applied to all handlers.
- Configures two handlers: `streamHandler` for console output and `rotatingFileHandler` for writing logs to a rotating file.
- Sets up the `solace_ai_connector` logger that captures INFO level logs specifically from the solace_ai_connector package
- Includes a special `sam_trace` tracing logger that can be enabled during development for detailed troubleshooting of data structures and internal operations. To enable this logger, set its level to DEBUG.
- Configures the root logger to catch all unhandled log messages from any module at WARNING or higher
- Configures the root logger to route all log messages to both the console and the rotating log file.
- Demonstrates the use of environment variable substitution for dynamic configuration.

### Environment Variable Substitution

All configuration formats support environment variable substitution with the syntax `${VAR_NAME, default_value}`:

- `${VAR_NAME}` - Use the environment variable value; raises an error if not set
- `${VAR_NAME, default_value}` - Use the environment variable value, or the default if not set

The application substitutes these environment variables at startup before applying the logging configuration.

### Effective Log Level

When configuring levels for different loggers, the effective log level is determined by the most specific logger configuration in the hierarchy. For example, if you set the root logger to DEBUG but create a custom logger for `solace_ai_connector` at the INFO level, the effective log level for the `solace_ai_connector` module will be INFO. This means DEBUG level logs from `solace_ai_connector` will not be handled, as they fall below the effective log level.

### Structured Logging

Structured logging outputs log messages in JSON format, making them easier to parse, search, and analyze in log aggregation systems. This project supports structured logging via the [python-json-logger](https://github.com/nhairs/python-json-logger) library.

To enable JSON logging, define a formatter which instantiates a `pythonjsonlogger.json.JsonFormatter` and apply the formatter to the handlers of your choice:

```yaml
formatters:
  simpleFormatter:
    format: "%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s"
  jsonFormatter:
    class: pythonjsonlogger.json.JsonFormatter
    format: "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
      
handlers:
  streamHandler:
    class: logging.StreamHandler
    formatter: simpleFormatter
    stream: "ext://sys.stdout"
  rotatingFileHandler:
    class: logging.handlers.RotatingFileHandler
    formatter: jsonFormatter
    filename: sam.log
    mode: a
    maxBytes: 52428800
    backupCount: 10
```
This configuration:
- Defines a jsonFormatter for structured JSON logs using `pythonjsonlogger.json.JsonFormatter`.
- Applies the jsonFormatter to the file handler while keeping the console handler in a human-readable format.

