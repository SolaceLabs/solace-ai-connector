import sys
import logging
import logging.handlers
import json
import os
from datetime import datetime


log = logging.getLogger("solace_ai_connector")


class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format.
    """

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


class JsonlFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON Lines (JSONL) format.
    """

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


def convert_to_bytes(size_str):
    size_str = size_str.upper()
    size_units = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "B": 1}
    for unit in size_units:
        if size_str.endswith(unit):
            return int(size_str[: -len(unit)]) * size_units[unit]
    return int(size_str)


# Helper function to handle trace formatting
def _format_with_trace(message, trace):
    try:
        import traceback

        if isinstance(trace, Exception):
            # If it's an Exception object
            stack_trace = traceback.format_exception(
                type(trace), trace, trace.__traceback__
            )
            full_message = f"{message} | TRACE: {trace}\n{''.join(stack_trace)}"
        else:
            # Regular trace info
            full_message = f"{message} | TRACE: {trace}"
    except Exception:
        # Fallback if there's an issue with the trace handling
        full_message = f"{message} | TRACE: {trace}"
    return full_message


def setup_log(
    logFilePath,
    stdOutLogLevel,
    fileLogLevel,
    logFormat,
    logBack,
    enableTrace=False,
):
    """
    Set up the configuration for the logger.

    Parameters:
        logFilePath (str): Path to the log file.
        stdOutLogLevel (int): Logging level for standard output.
        fileLogLevel (int): Logging level for the log file.
        logFormat (str): Format of the log output ('jsonl' or 'pipe-delimited').
        logBack (dict): Rolling log file configuration.
    """

    # Set the global logger level to the lowest of the two levels
    log.setLevel(min(stdOutLogLevel, fileLogLevel))

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdOutLogLevel)
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler.setFormatter(stream_formatter)

    if logFormat == "jsonl":
        file_formatter = JsonlFormatter()
    else:
        file_formatter = logging.Formatter("%(asctime)s |  %(levelname)s: %(message)s")

    if logBack:
        rollingpolicy = logBack.get("rollingpolicy", {})
        if rollingpolicy:
            if "file-name-pattern" not in rollingpolicy:
                log.warning(
                    "file-name-pattern is required in rollingpolicy. Continuing with default value '{LOG_FILE}.%d{yyyy-MM-dd}.%i'."
                )
            file_name_pattern = rollingpolicy.get(
                "file-name-pattern", "{LOG_FILE}.%d{yyyy-MM-dd}.%i.gz"
            )

            if "max-file-size" not in rollingpolicy:
                log.warning(
                    "max-file-size is required in rollingpolicy. Continuing with default value '1GB'."
                )
            max_file_size = rollingpolicy.get("max-file-size", "1GB")

            if "max-history" not in rollingpolicy:
                log.warning(
                    "max-history is required in rollingpolicy. Continuing with default value '7'."
                )
            max_history = rollingpolicy.get("max-history", 7)

            if "total-size-cap" not in rollingpolicy:
                log.warning(
                    "total-size-cap is required in rollingpolicy. Continuing with default value '1TB'."
                )
            total_size_cap = rollingpolicy.get("total-size-cap", "1TB")

            # Convert size strings to bytes
            max_file_size = convert_to_bytes(max_file_size)
            total_size_cap = convert_to_bytes(total_size_cap)

            # Generate the log file name using the pattern
            log_file_name = logFilePath

            # Overwrite the file handler with a rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file_name,
                backupCount=max_history,
                maxBytes=max_file_size,
            )
            file_handler.namer = (
                lambda name: file_name_pattern.replace("${LOG_FILE}", logFilePath)
                .replace("%d{yyyy-MM-dd}", datetime.now().strftime("%Y-%m-%d"))
                .replace("%i", str(name.split(".")[-1]))
            )
    else:
        file_handler = logging.FileHandler(filename=logFilePath, mode="a")

    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(fileLogLevel)

    log.addHandler(file_handler)
    log.addHandler(stream_handler)

    # Save the original logging methods
    original_debug = log.debug
    original_error = log.error

    # Define a wrapper function for debug logs with trace support
    def debug_wrapper(message, *args, trace=None, **kwargs):
        # Handle both string formatting args and trace
        if args and isinstance(message, str):
            # Format the message first with args
            formatted_message = message % args if args else message
            # Then add trace if available
            if trace and enableTrace:
                full_message = _format_with_trace(formatted_message, trace)
            else:
                full_message = formatted_message
            original_debug(full_message, **kwargs)
        else:
            # Handle case without formatting args
            if trace and enableTrace:
                full_message = _format_with_trace(message, trace)
            else:
                full_message = message
            original_debug(full_message, **kwargs)

    # Define a wrapper function for error logs with trace support
    def error_wrapper(message, *args, trace=None, **kwargs):
        # Handle both string formatting args and trace
        if args and isinstance(message, str):
            # Format the message first with args
            formatted_message = message % args if args else message
            # Then add trace if available
            if trace and enableTrace:
                full_message = _format_with_trace(formatted_message, trace)
            else:
                full_message = formatted_message
            original_error(full_message, **kwargs)
        else:
            # Handle case without formatting args
            if trace and enableTrace:
                full_message = _format_with_trace(message, trace)
            else:
                full_message = message
            original_error(full_message, **kwargs)

    # Always replace the logging methods, regardless of enableTrace
    log.debug = debug_wrapper
    log.error = error_wrapper
