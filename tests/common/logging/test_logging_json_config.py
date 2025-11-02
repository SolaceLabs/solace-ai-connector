import logging
import sys
import json

import pytest

from solace_ai_connector.common.exceptions import InitializationError

sys.path.append("src")

from solace_ai_connector.common.logging_config import configure_from_file

def test_configure_json_basic(tmp_path, monkeypatch):
    """Test basic JSON dict configuration."""
    log_file = tmp_path / "json_dict_test.log"
    config_content = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "INFO",
                "formatter": "simple",
                "filename": str(log_file)
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["file"]
        }
    }

    config_file = tmp_path / "logging_config.json"
    config_file.write_text(json.dumps(config_content, indent=2))

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    assert configure_from_file() is True

    test_logger = logging.getLogger("test_json_dict_logger")
    test_message = "Test message from JSON dict config"
    test_logger.info(test_message)

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()
    assert test_message in log_content
    assert "test_json_dict_logger" in log_content

def test_configure_json_with_env_var_substitution(tmp_path, monkeypatch):
    """Test JSON configuration with environment variable substitution."""
    log_file = tmp_path / "json_env_var_test.log"
    config_content = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "custom": {
                "format": "${LOG_FORMAT, %(levelname)s - %(message)s}"
            }
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "${LOG_LEVEL,INFO}",
                "formatter": "custom",
                "filename": "${ LOG_FILE_PATH }"
            }
        },
        "root": {
            "level": "${ROOT_LOG_LEVEL,DEBUG }",
            "handlers": ["file"]
        }
    }

    config_file = tmp_path / "logging_env_var.json"
    config_file.write_text(json.dumps(config_content, indent=2))

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    monkeypatch.setenv("LOG_FORMAT", "%(name)s | %(levelname)s | %(message)s")

    assert configure_from_file() is True

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG, "Root logger should be at DEBUG level (from default)"

    handler = root_logger.handlers[0]
    assert handler.level == logging.WARNING, "Handler should be at WARNING level (from env var)"
    assert handler.formatter._fmt == "%(name)s | %(levelname)s | %(message)s"


def test_configure_json_missing_env_var_no_default(tmp_path, monkeypatch):
    """Test that missing env var without default raises ValueError."""
    config_content = {
        "version": 1,
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "${MISSING_VAR}",
                "filename": "test.log"
            }
        }
    }

    config_file = tmp_path / "missing_var.json"
    config_file.write_text(json.dumps(config_content))

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("MISSING_VAR", raising=False)

    with pytest.raises(ValueError) as exc_info:
        configure_from_file()

    assert "Environment variable 'MISSING_VAR' is not set and no default value provided" in str(exc_info.value)


def test_configure_json_invalid_format(tmp_path, monkeypatch):
    """Test that invalid JSON raises appropriate error."""
    config_content = "{ invalid json content"

    config_file = tmp_path / "invalid.json"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))

    with pytest.raises(InitializationError) as exc_info:
        configure_from_file()

    error_str = str(exc_info.value)
    assert "Logging configuration file 'LOGGING_CONFIG_PATH=%s' could not be parsed" in error_str
    assert "The configuration must be valid JSON or YAML" in error_str
    assert str(config_file) in error_str

