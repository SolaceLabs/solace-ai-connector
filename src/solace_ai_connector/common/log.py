import sys
import logging
import logging.config
import logging.handlers
import json
import os
from datetime import datetime


# Global flag to indicate if INI configuration was successfully applied
_ini_config_applied = False
log = logging.getLogger("solace_ai_connector")
logging.captureWarnings(True)


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


# These wrappers will be applied to the global 'log' instance at the end of the module.
# Trace is conditionally enabled based on the enableTrace parameter.
_MODULE_ORIGINAL_DEBUG = log.debug
_MODULE_ORIGINAL_ERROR = log.error

def _create_module_wrapper_with_trace(original_method):
    def wrapper(message, *args, trace=None, **kwargs):
        if args and isinstance(message, str):
            formatted_message = message % args if args else message
            if trace:
                full_message = _format_with_trace(formatted_message, trace)
            else:
                full_message = formatted_message
            original_method(full_message, stacklevel=2, **kwargs)
        else:
            if trace:
                full_message = _format_with_trace(message, trace)
            else:
                full_message = message
            original_method(full_message, stacklevel=2, **kwargs)
    return wrapper

_module_debug_wrapper_with_trace = _create_module_wrapper_with_trace(_MODULE_ORIGINAL_DEBUG)
_module_error_wrapper_with_trace = _create_module_wrapper_with_trace(_MODULE_ORIGINAL_ERROR)


def setup_log(
    logFilePath,
    stdOutLogLevel,
    fileLogLevel,
    logFormat,
    logBack,
    enableTrace=False,
):
    # If INI configuration was successfully applied, do not allow this programmatic setup
    # to reconfigure the 'solace_ai_connector' logger (the global 'log' object).
    if _ini_config_applied:
        return

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

    if not _ini_config_applied:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(stdOutLogLevel)
        stream_formatter = logging.Formatter("%(message)s")
        stream_handler.setFormatter(stream_formatter)
        log.addHandler(stream_handler)

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

# Module-level logging configuration based on LOGGING_CONFIG_PATH
# This code will run once when the module is first imported.
# If LOGGING_CONFIG_PATH is set and points to a valid file, INI-based logging is used.
# Otherwise, programmatic logging via setup_log() will be used.
ini_path_from_env = os.getenv("LOGGING_CONFIG_PATH")

if ini_path_from_env:
    if not os.path.exists(ini_path_from_env):
        print(
            f"LOGGING_CONFIG_PATH is set to '{ini_path_from_env}', but the file was not found. "
            "Proceeding with default programmatic logging.",
            file=sys.stderr
        )
    else:
        try:
            # Setting disable_existing_loggers=True will disable any loggers that existed
            # prior to this call if they are also defined in the INI file.
            # This is crucial for ensuring that library loggers (like litellm)
            # which might have default handlers, only use the handlers defined in the INI.
            logging.config.fileConfig(ini_path_from_env, disable_existing_loggers=True)
            module_init_logger = logging.getLogger("solace_ai_connector.common.log_init")
            module_init_logger.info(
                f"Logging configured via INI file '{ini_path_from_env}' "
                "(specified by LOGGING_CONFIG_PATH) from solace_ai_connector.common.log module import."
            )
            _ini_config_applied = True # Set flag if INI load is successful
        except Exception as e:
            print(
                f"Error configuring logging from INI file '{ini_path_from_env}': {e}. "
                "Proceeding with default programmatic logging.",
                file=sys.stderr
            )
# else:
    # LOGGING_CONFIG_PATH is not set.
    # The application will rely on the programmatic setup_log() or Python's default.
    # print("LOGGING_CONFIG_PATH is not set. Proceeding with default programmatic logging.", file=sys.stderr)

# Apply the module-level trace-enabled wrappers to the global 'log' instance.
# This ensures that log.debug and log.error always handle the 'trace' kwarg.
log.debug = _module_debug_wrapper_with_trace
log.error = _module_error_wrapper_with_trace
