import logging
import sys
import json

import pytest

sys.path.append("src")

from solace_ai_connector.common.logging_config import configure_from_logging_ini

def test_configure_from_logging_ini_success_path(tmp_path, monkeypatch, isolated_logging):
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
    
    assert configure_from_logging_ini() is True

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


def test_configure_from_logging_ini_no_env_var(monkeypatch):
    """
    Test configure_from_logging_ini when LOGGING_CONFIG_PATH is not set.
    
    This should return False.
    """
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    assert configure_from_logging_ini() is False


def test_configure_from_logging_ini_file_not_found(tmp_path, monkeypatch):
    """
    Test configure_from_logging_ini when the config file doesn't exist.
    
    This should raise a FileNotFoundError.
    """
    non_existent_file = tmp_path / "non_existent.ini"
    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(non_existent_file))
    
    with pytest.raises(FileNotFoundError) as exc_info:
        configure_from_logging_ini()
    
    assert str(non_existent_file) in str(exc_info.value)


def test_configure_from_logging_ini_invalid_config(tmp_path, monkeypatch, isolated_logging):
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
        configure_from_logging_ini()

    assert "Unknown level: 'INVALID_LEVEL'" in str(exc_info.value)


def test_configure_from_logging_ini_with_json_formatter(tmp_path, monkeypatch, isolated_logging):
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

    assert configure_from_logging_ini() is True

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
