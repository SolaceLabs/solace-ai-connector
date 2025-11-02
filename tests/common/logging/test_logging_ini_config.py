import logging
import sys
import json

import pytest

from solace_ai_connector.common.logging_config import configure_from_file

sys.path.append("src")

def test_configure_ini_success_path(tmp_path, monkeypatch):
    log_file = tmp_path / "test.log"
    config_content = f"""[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('{log_file}',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
"""

    config_file = tmp_path / "test_logging.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    assert configure_from_file() is True

    test_logger = logging.getLogger("test_logger")

    file_handlers = [h for h in test_logger.parent.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1, "Parent logger should have exactly one FileHandler"

    test_message = "This is a test log message from pytest"
    test_logger.info(test_message)

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()
    assert "solace_ai_connector.common.logging_config - INFO - Root logger successfully configured based on LOGGING_CONFIG_PATH=" in log_content
    assert test_message in log_content
    assert "test_logger" in log_content, "Logger name should be in log file"


def test_configure_ini_no_env_var(monkeypatch):
    """
    Test configure_from_logging_ini when LOGGING_CONFIG_PATH is not set.

    This should return False.
    """
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    assert configure_from_file() is False


def test_configure_ini_file_not_found(tmp_path, monkeypatch):
    """
    Test configure_from_logging_ini when the config file doesn't exist.

    This should raise a FileNotFoundError.
    """
    non_existent_file = tmp_path / "non_existent.ini"
    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(non_existent_file))

    with pytest.raises(FileNotFoundError) as exc_info:
        configure_from_file()

    assert str(non_existent_file) in str(exc_info.value)


def test_configure_ini_invalid_config(tmp_path, monkeypatch):
    """
    Test configure_from_logging_ini with an invalid configuration file.

    Use a config with INVALID_LEVEL to trigger an error.
    """
    invalid_config_content = """[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=INVALID_LEVEL
formatter=simpleFormatter
args=('tests.log',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
"""
    config_file = tmp_path / "invalid_logging.ini"
    config_file.write_text(invalid_config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    with pytest.raises(ValueError) as exc_info:
        configure_from_file()

    assert "Unknown level: 'INVALID_LEVEL'" in str(exc_info.value)


def test_configure_ini_with_json_formatter(tmp_path, monkeypatch):
    """
    Test configure_from_logging_ini with pythonjsonlogger.jsonlogger.JsonFormatter.

    This test verifies that:
    1. The JsonFormatter can be configured via logging.ini using class=pythonjsonlogger.jsonlogger.JsonFormatter
    2. Log messages are output as valid JSON
    3. All configured fields (asctime, levelname, name, message) are present in the JSON
    4. Extra fields passed via the 'extra' parameter are included in the JSON output
    """
    log_file = tmp_path / "json_test.log"
    config_content = f"""[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=jsonFormatter

[logger_root]
level=INFO
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=jsonFormatter
args=('{log_file}',)

[formatter_jsonFormatter]
class=pythonjsonlogger.jsonlogger.JsonFormatter
format=%(asctime)s %(levelname)s %(name)s %(message)s
"""

    config_file = tmp_path / "logging_json.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    assert configure_from_file() is True

    test_logger = logging.getLogger("test_json_logger")

    # Log test messages with various log levels and extra fields
    test_logger.info("Test info message")
    test_logger.warning("Test warning message", extra={"custom_field": "custom_value"})
    test_logger.error("Test error message", extra={"error_code": 500, "user_id": 12345})

    assert log_file.exists(), "Log file should have been created"
    with open(log_file, "r") as f:
        lines = f.readlines()

    assert len(lines) >= 3, f"Expected at least 3 log lines, got {len(lines)}"

    # Parse each line and verify it's valid JSON
    for i, line in enumerate(lines):
        try:
            log_entry = json.loads(line)
        except json.JSONDecodeError as e:
            pytest.fail(f"Line {i+1} is not valid JSON: {line}\nError: {e}")

        # Verify common JSON log fields are present
        assert "message" in log_entry, f"Log entry {i+1} missing 'message' field"
        assert "levelname" in log_entry, f"Log entry {i+1} missing 'levelname' field"
        assert "name" in log_entry, f"Log entry {i+1} missing 'name' field"
        assert "asctime" in log_entry, f"Log entry {i+1} missing 'asctime' field"

    # Verify specific log messages and their content
    log_contents = [json.loads(line) for line in lines]

    # Find the info message
    info_logs = [log for log in log_contents if "Test info message" in log.get("message", "")]
    assert len(info_logs) == 1, "Should find exactly one info message"
    assert info_logs[0]["levelname"] == "INFO"
    assert info_logs[0]["name"] == "test_json_logger"

    # Find the warning message with custom field
    warning_logs = [log for log in log_contents if "Test warning message" in log.get("message", "")]
    assert len(warning_logs) == 1, "Should find exactly one warning message"
    assert warning_logs[0]["levelname"] == "WARNING"
    assert warning_logs[0]["custom_field"] == "custom_value", "Custom field should be included in JSON log"

    # Find the error message with extra fields
    error_logs = [log for log in log_contents if "Test error message" in log.get("message", "")]
    assert len(error_logs) == 1, "Should find exactly one error message"
    assert error_logs[0]["levelname"] == "ERROR"
    assert error_logs[0]["error_code"] == 500, "error_code field should be included"
    assert error_logs[0]["user_id"] == 12345, "user_id field should be included"


def test_configure_ini_env_var_substitution(tmp_path, monkeypatch):
    """Test that environment variables are substituted into INI values using ${NAME,default} syntax and other variations"""
    log_file = tmp_path / "env_var_test.log"
    config_content = """[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=${LOG_LEVEL , INFO}
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=${LOG_LEVEL2,INFO}
formatter=simpleFormatter
args=('${LOG_FILE_PATH, test.log}',)

[formatter_simpleFormatter]
format=${LOG_FORMAT ,%(levelname)s|%(message)s}
"""
    config_file = tmp_path / "env_var_logging.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_LEVEL2", "ERROR")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    assert configure_from_file() is True

    root_logger = logging.getLogger()

    assert root_logger.level == logging.DEBUG, "Root logger should be at DEBUG level"
    assert len(root_logger.handlers) == 1, "Root logger should have one handler"

    handler = root_logger.handlers[0]
    assert handler.level == logging.ERROR, "Handler should be at ERROR level"
    assert isinstance(handler, logging.FileHandler), "Handler should be a FileHandler"
    assert handler.formatter._fmt == "%(levelname)s|%(message)s", "Handler should have correct format"


def test_configure_ini_empty_env_var(tmp_path, monkeypatch):
    """Test that empty environment variables are treated as set (not falling back to default)."""
    log_file = tmp_path / "empty_env_var_test.log"
    config_content = """[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('${LOG_FILE_PATH, test.log}',)

[formatter_simpleFormatter]
format=${LOG_FORMAT, %(name)s}
"""
    config_file = tmp_path / "empty_env_var_logging.ini"
    config_file.write_text(config_content)

    # Set LOG_FORMAT to empty string (should not fall back to default)
    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_FORMAT", "")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    assert configure_from_file() is True

    root_logger = logging.getLogger()

    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.FileHandler), "Handler should be a FileHandler"
    assert handler.formatter._fmt == "%(message)s", "Handler should use the default formatting when LOG_FORMAT is the empty string"


def test_configure_ini_missing_env_var_no_default(tmp_path, monkeypatch):
    """Test that missing env var without default raises ValueError."""
    log_file = tmp_path / "missing_env_var_test.log"
    config_content = """[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=${MISSING_ENV_VAR}
formatter=simpleFormatter
args=('${LOG_FILE_PATH,test.log}',)

[formatter_simpleFormatter]
format=%(name)s: %(message)s
"""
    config_file = tmp_path / "missing_env_var_logging.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    monkeypatch.delenv("MISSING_ENV_VAR", raising=False)  # Ensure it's not set

    with pytest.raises(ValueError) as exc_info:
        configure_from_file()

    assert "Environment variable 'MISSING_ENV_VAR' is not set and no default value provided in logging config." in str(exc_info.value)


def test_configure_ini_empty_value(tmp_path, monkeypatch):
    """Test that empty values in the INI file are handled correctly."""
    log_file = tmp_path / "empty_value_test.log"
    config_content = """[loggers]
keys=root

[handlers]
keys=fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=DEBUG
handlers=fileHandler

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('${LOG_FILE_PATH, test.log}',)

[formatter_simpleFormatter]
format=
"""
    config_file = tmp_path / "empty_value_logging.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    assert configure_from_file() is True

    root_logger = logging.getLogger()

    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.FileHandler), "Handler should be a FileHandler"
    assert handler.formatter._fmt == "%(message)s", "Handler should use the default formatting when LOG_FORMAT is the empty string"

def test_configure_ini_no_interpolation(tmp_path, monkeypatch):
    """Test that logging configuration works when interpolation is disabled with a format string containing %()s patterns."""
    log_file = tmp_path / "no_interpolation_test.log"
    config_content = """[loggers]
keys=root,sam_trace

[logger_root]
level=INFO
handlers=fileHandler
qualname=root

[logger_sam_trace]
level=INFO
handlers=
qualname=sam_trace

[handlers]
keys=fileHandler

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('${LOG_FILE_PATH, test.log}',)

[formatters]
keys=simpleFormatter

[formatter_simpleFormatter]
format=%(asctime)s | %(levelname)-5s | %(name)s | %(message)s
"""
    config_file = tmp_path / "no_interpolation_logging.ini"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))

    assert configure_from_file() is True

    root_logger = logging.getLogger()

    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.FileHandler), "Handler should be a FileHandler"
    assert handler.formatter._fmt == "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s", "Handler should have correct format"
