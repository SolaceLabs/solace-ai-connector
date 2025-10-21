# Logging

The AI Event Connector leverages Python's built-in logging module to provide flexible and standardized logging  

## Configuring Logging

The AI Event Connector uses Python's [fileConfig format](https://docs.python.org/3/library/logging.config.html#configuration-file-format) for logging configuration. To configure logging, create a logging configuration .ini file and set the following environment variable: `LOGGING_CONFIG_PATH=./path/to/logging_config.ini`

Here's an example configuration that demonstrates a common setup:

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
- creates a root logger that catches all unhandled log messages from any module at WARN or higher.
- routes all qualifying log messages to both console and a rotating log file
- a main application logger (`solace_ai_connector`) that captures INFO level logs specifically from the (`solace_ai_connector`) module 
- a special debug logger (`sam_trace`) that can be enabled during development for detailed troubleshooting of data structures and internal operations.

Note that, as demonstrated in the above example, environment variable substitution is supported with the syntax `${VAR_NAME, default_value}`.

For additional logging configuration options and information on creating handlers, refer to the [Python logging documentation](https://docs.python.org/3/library/logging.config.html#configuration-file-format).

### Priority

When configuring levels for different sections, the logger will prioritize the most specifc level. For example if you set the root logger to DEBUG but create a custom logger that points to `solace_ai_connector` at the INFO level, logs from `solace_ai_connector` at the DEBUG level will not be handled.

### Structured Logging

Structured logging outputs log messages in JSON format. This project supports structured logging via the [python-json-logger](https://github.com/nhairs/python-json-logger) library.

To enable JSON logging, define a formatter as in this example and apply it to your chosen handlers:

```ini
[formatters]
keys=simpleFormatter,jsonFormatter

[formatter_simpleFormatter]
format=%(asctime)s | %(levelname)-5s | %(name)s | %(message)s

[formatter_jsonFormatter]
class=pythonjsonlogger.jsonlogger.JsonFormatter
format=%(asctime)s %(levelname)s %(name)s %(message)s

[handler_rotatingFileHandler]
class=logging.handlers.RotatingFileHandler
formatter=jsonFormatter
args=('sam.log', 'a', 52428800, 10)
```
