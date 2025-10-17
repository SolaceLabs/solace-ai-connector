# Configuring logging for the AI Event Connector

The preferred method of configuring logging now utilizes Python's built-in logging framework.

To enable it, create a .ini file and add the following environment variable pointing to it:
`LOGGING_CONFIG_PATH=./Path/to/file.ini`

## Configuration Format

The logging configuration uses the INI file format with several sections that define loggers, handlers, and formatters. Here's a typical configuration example:

```ini
[loggers]
keys=root,solace_ai_connector,solace_agent_mesh,sam_trace

[logger_root]
level=WARN
handlers=streamHandler,rotatingFileHandler
qualname=root

[logger_solace_ai_connector]
level=INFO
handlers=
qualname=solace_ai_connector

[logger_solace_agent_mesh]
level=INFO
handlers=
qualname=solace_agent_mesh

[logger_sam_trace]
level=INFO
handlers=
qualname=sam_trace

[handlers]
keys=streamHandler,rotatingFileHandler

[handler_rotatingFileHandler]
class=logging.handlers.RotatingFileHandler
formatter=simpleFormatter
args=('sam.log', 'a', 52428800, 10)

[handler_streamHandler]
class=StreamHandler
formatter=simpleFormatter
args=(sys.stdout,)

[formatters]
keys=simpleFormatter,jsonFormatter

[formatter_simpleFormatter]
format=%(asctime)s | %(levelname)-5s | %(name)s | %(message)s

[formatter_jsonFormatter]
class=pythonjsonlogger.jsonlogger.JsonFormatter
format=%(asctime)s | %(levelname)-5s | %(name)s | %(message)s
```

### Understanding the Configuration

1. **Loggers** (`[loggers]`):
   - Lists all configured loggers in the `keys` property
   - Each logger needs its own section starting with `logger_`
   - The root logger is special and configures the default logging behavior

2. **Logger Sections** (`[logger_*]`):
   - `level`: Sets the logging level (DEBUG, INFO, WARN, ERROR, CRITICAL)
   - `handlers`: Comma-separated list of handlers to use
   - `qualname`: The code module to target

3. **Handlers** (`[handlers]`):
   - Define where log messages are sent
   - Common types include:
     - `StreamHandler`: Outputs to console
     - `RotatingFileHandler`: Writes to files with rotation

4. **Handler Sections** (`[handler_*]`):
   - `class`: The Python handler class to use
   - `formatter`: Which formatter to apply
   - `args`: Arguments for the handler (e.g., filename, max size)

5. **Formatters** (`[formatters]`):
   - Define how log messages are formatted
   - Can use standard Python logging variables like:
     - `%(asctime)s`: Timestamp
     - `%(levelname)s`: Log level
     - `%(name)s`: Logger name
     - `%(message)s`: The log message

6. **Sam_Trace**:
    - sam_trace is a special logger than enables verbose logs
    - When enabled, sections of code that call the special trace function will output detailed structures allowing for easier debugging

### Priority

When configuring levels for different sections, the logger will prioritize the most specifc level. For example if you set the root logger to DEBUG but create a custom logger that points to `solace_agent_mesh` at the INFO level, logs from `solace_agent_mesh` at the DEBUG level will not be handled.

### Third-Party loggers

Python logging also supports importing third-party libraries to help with more structured logging.

For example, after importing the python-json-logger, you can enable it using the following config:

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

> **Note:**
> While this method is preferred for configuring logging, YAML based logging is still available. Although, this method will take precedence over any YAML configuration. Thus, YAML configs will only function if Python logging is not set up.

