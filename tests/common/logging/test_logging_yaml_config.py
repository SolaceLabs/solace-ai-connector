import json
import logging
import sys

import pytest

from solace_ai_connector.common.exceptions import InitializationError

sys.path.append("src")

from solace_ai_connector.common.logging_config import configure_from_file


def test_configure_yaml_basic(tmp_path, monkeypatch):
    """Test basic YAML dict configuration."""
    log_file = tmp_path / "yaml_dict_test.log"
    config_content = f"""
version: 1
disable_existing_loggers: false
formatters:
  simple:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
handlers:
  file:
    class: logging.FileHandler
    level: INFO
    formatter: simple
    filename: {log_file}
root:
  level: INFO
  handlers: [file]
"""

    config_file = tmp_path / "logging_config.yaml"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    assert configure_from_file() is True

    test_logger = logging.getLogger("test_yaml_dict_logger")
    test_message = "Test message from YAML dict config"
    test_logger.info(test_message)

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()
    assert test_message in log_content
    assert "test_yaml_dict_logger" in log_content


def test_configure_yaml_with_env_var_substitution(tmp_path, monkeypatch):
    """Test YAML configuration with environment variable substitution."""
    log_file = tmp_path / "yaml_env_var_test.log"
    config_content = """
version: 1
disable_existing_loggers: false
formatters:
  custom:
    format: '${LOG_FORMAT, %(levelname)s - %(message)s}'
handlers:
  file:
    class: logging.FileHandler
    level: ${LOG_LEVEL, INFO}
    formatter: custom
    filename: ${LOG_FILE_PATH}
root:
  level: ${ROOT_LOG_LEVEL, DEBUG}
  handlers: [file]
"""

    config_file = tmp_path / "logging_env_var.yaml"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    monkeypatch.setenv("ROOT_LOG_LEVEL", "INFO")

    assert configure_from_file() is True

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO, "Root logger should be at INFO level (from env var)"

    handler = root_logger.handlers[0]
    assert handler.level == logging.ERROR, "Handler should be at ERROR level (from env var)"

def test_configure_yaml_missing_env_var_no_default(tmp_path, monkeypatch):
    """Test that missing env var without default raises ValueError."""
    config_content = """
    version: 1
    disable_existing_loggers: false
    formatters:
      custom:
        format: '${MISSING_VAR}'
    handlers:
      file:
        class: logging.FileHandler
        level: INFO
        formatter: custom
        filename: logfile.log
    root:
      level: WARNING
      handlers: [file]
    """

    config_file = tmp_path / "missing_var.json"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("MISSING_VAR", raising=False)

    with pytest.raises(ValueError) as exc_info:
        configure_from_file()

    assert "Environment variable 'MISSING_VAR' is not set and no default value provided" in str(exc_info.value)

def test_configure_yaml_invalid_format(tmp_path, monkeypatch):
    """Test that invalid YAML raises appropriate error."""
    config_content = """
invalid: yaml: content:
  - this is
  - not: valid
    - yaml
"""

    config_file = tmp_path / "invalid.yaml"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    with pytest.raises(InitializationError) as exc_info:
        configure_from_file()

    error_str = str(exc_info.value)
    assert "Logging configuration file 'LOGGING_CONFIG_PATH=%s' could not be parsed" in error_str
    assert "The configuration must be valid JSON or YAML" in error_str
    assert str(config_file) in error_str

def test_structured_logging_with_contextual_info_added_to_every_log_message(tmp_path, monkeypatch):
    """
    Test contextual information can be added to every log statement via pythonjsonlogger's static field feature.
    https://nhairs.github.io/python-json-logger/latest/quickstart/#static-fields
    """
    log_file = tmp_path / "yaml_contextual_test.log"
    config_content = f"""
version: 1
disable_existing_loggers: false

formatters:
  jsonFormatter:
    "()": pythonjsonlogger.json.JsonFormatter
    format: "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
    static_fields:
      service: ${{SERVICE_NAME, solace_agent_mesh}}
      env: ${{ENV, dev}}

handlers:
  rotatingFileHandler:
    class: logging.handlers.RotatingFileHandler
    formatter: jsonFormatter
    filename: {log_file}
    mode: a
    maxBytes: 52428800
    backupCount: 10

loggers:
  solace_ai_connector:
    level: INFO
    handlers: []
    propagate: true

root:
  level: WARNING
  handlers:
    - rotatingFileHandler
"""

    config_file = tmp_path / "logging_contextual.yaml"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("SERVICE_NAME", "test_service")
    monkeypatch.setenv("ENV", "test_env")

    assert configure_from_file() is True

    test_logger = logging.getLogger("test_yaml_contextual_logger")
    test_message = "Test message with contextual info"
    test_logger.warning(test_message)

    # Log wit root logger as well
    logging.warning("Root logger test message with contextual info")

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()

    log_lines = [line for line in log_content.strip().splitlines() if line.strip()]
    for line in log_lines:
        log_json = json.loads(line)

        assert log_json["service"] == "test_service"
        assert log_json["env"] == "test_env"

        # Ensure 'service' and 'env' are the last two keys. We want contextual info at the end of the log.
        keys = list(log_json.keys())
        assert keys[-2:] == ["service", "env"]
