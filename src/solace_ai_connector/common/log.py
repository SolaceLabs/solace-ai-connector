import logging
import sys
import logging
import logging.config
import logging.handlers
import json
import os
from datetime import datetime
from ..common.exceptions import InitializationError

log = logging.getLogger(__name__)

class JsonlFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON Lines (JSONL) format.
    """

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)

def validate_log_level(handler, level):
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level not in valid_levels:
        raise InitializationError(f"Invalid log level '{level}' specified for '{handler}'")


def convert_to_bytes(size_str):
    size_str = size_str.upper()
    size_units = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "B": 1}
    for unit in size_units:
        if size_str.endswith(unit):
            return int(size_str[: -len(unit)]) * size_units[unit]
    return int(size_str)

def setup_log(
    logFilePath,
    stdOutLogLevel,
    fileLogLevel,
    logFormat,
    logBack,
    enableTrace=False,
):
    """
    Set up the configuration for the root logger if logging was not yet configured.

    Parameters:
        logFilePath (str): Path to the log file.
        stdOutLogLevel (str): Logging level for standard output.
        fileLogLevel (str): Logging level for the log file.
        logFormat (str): Format of the log output ('jsonl' or 'pipe-delimited').
        logBack (dict): Rolling log file configuration.
    """
    validate_log_level("stdout_log_level", stdOutLogLevel)
    validate_log_level("log_file_level", fileLogLevel)
    
    # Get the root logger to configure it for the entire application
    root_logger = logging.getLogger()
    
    # Check if logging is already configured by examining the root logger
    if root_logger.handlers:
        log.info(f"Logging configuration already applied, skipping setup_log(logFilePath={logFilePath}, stdOutLogLevel={stdOutLogLevel}, fileLogLevel={fileLogLevel})")
        return

    # Set the root logger level to the lowest of the two levels
    root_logger.setLevel(min(logging.getLevelName(stdOutLogLevel), logging.getLevelName(fileLogLevel)))

    # Add stdout handler to root logger
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdOutLogLevel)
    stream_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    stream_handler.setFormatter(stream_formatter)
    root_logger.addHandler(stream_handler)

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

    if logFormat == "jsonl":
        file_formatter = JsonlFormatter()
    else:
        file_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(fileLogLevel)

    # Add file handler to root logger
    root_logger.addHandler(file_handler)

    # "sam_trace" logger is a special logger used for verbose logs
    sam_trace_logger = logging.getLogger('sam_trace')
    sam_trace_logger.propagate = False
    sam_trace_logger.addHandler(file_handler) # Only log to file
    if enableTrace:
        sam_trace_logger.setLevel(logging.DEBUG)
    else:
        sam_trace_logger.setLevel(logging.WARNING)
