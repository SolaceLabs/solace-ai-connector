import logging
import sys
import pytest
import json

sys.path.append("src")

from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.exceptions import InitializationError
from logging.handlers import RotatingFileHandler

@pytest.fixture
def apps_config():
    return [
        {
            "name": "test_app",
            "flows": [
                {
                    "name": "test_flow",
                    "components": [
                        {
                            "component_name": "test_component",
                            "component_module": "pass_through"
                        }
                    ]
                }
            ]
        }
    ]

def remove_root_logger_handlers():
    """Reset logging configuration """
    # This can't be a fixture since pytest re-adds the handlers before we get to the actual test
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

def test_setup_logging_when_no_env_var(tmp_path, monkeypatch, apps_config):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "test_connector.log"

    config = {
        "log": {
            "stdout_log_level": "CRITICAL",
            "log_file_level": "WARNING",
            "log_file": str(log_file),
            "log_format": "pipe-delimited"
        }, "apps": apps_config}

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
    assert len(root_logger.handlers) == 2  # 1 StreamHandler and 1 FileHandler

    for h in root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            assert h.level == logging.WARNING
            assert h.baseFilename.endswith(log_file.name)
        else:
            assert h.level == logging.CRITICAL

    logger = logging.getLogger(__name__)
    log_message = "This is a test log message"
    logger.warning(log_message)

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()
    assert f"| WARNING | common.logging.test_logging_integration | {log_message}" in log_content

def test_setup_logging_with_logback_config(tmp_path, monkeypatch, apps_config):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "rolling_test.log"

    config = {
        "log": {
            "stdout_log_level": "INFO",
            "log_file_level": "DEBUG",
            "log_file": str(log_file),
            "log_format": "pipe-delimited",
            "logback": {
                "rollingpolicy": {
                    "file-name-pattern": "{LOG_FILE}.%d{yyyy-MM-dd}.%i.gz",
                    "max-file-size": "1MB",
                    "max-history": 5,
                    "total-size-cap": "10MB"
                }
            }
        },
        "apps": apps_config
    }

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 2  # 1 StreamHandler and 1 RotatingFileHandler

    found_rotating_handler = False

    for h in root_logger.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            assert h.level == logging.DEBUG
            assert h.baseFilename.endswith(log_file.name)
            assert h.backupCount == 5
            assert h.maxBytes == 1048576
            found_rotating_handler = True
        else:
            assert h.level == logging.INFO

    assert found_rotating_handler is True


def test_setup_logging_with_missing_log_config_uses_defaults(monkeypatch, apps_config):
    """Test that connector uses default logging config when log section is missing"""
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)

    # Config without log section
    config = {
        "apps": apps_config
    }

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) == 2

    for h in root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            assert h.level == logging.INFO
            assert h.baseFilename.endswith("solace_ai_connector.log")
        else:
            assert h.level == logging.INFO

def test_setup_logging_with_json_formatting(tmp_path, monkeypatch, apps_config):
    """Test that connector sets up JSON logging format correctly"""
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "json_format_test.log"

    config = {
        "log": {
            "stdout_log_level": "ERROR",
            "log_file_level": "DEBUG",
            "log_file": log_file,
            "log_format": "jsonl"
        },
        "apps": apps_config
    }

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 2  # 1 StreamHandler and 1 FileHandler

    logger = logging.getLogger("json_test_logger")
    logger.warning("This is a test warning message")
    logger.info("This is a test info message")

    assert log_file.exists(), "Log file should have been created"
    with open(log_file, "r") as f:
        for line in f:
            try:
                json.loads(line)
            except json.JSONDecodeError:
                assert False, f"Line is not valid JSON: {line}"

@pytest.mark.parametrize(
    "invalid_key, valid_key",
    [
        ("stdout_log_level", "log_file_level"),
        ("log_file_level", "stdout_log_level"),
    ]
)
def test_setup_logging_with_invalid_log_level(tmp_path, monkeypatch, apps_config, invalid_key, valid_key):
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "invalid_level_test.log"

    config = {
        "log": {
            invalid_key: "INVALID_LEVEL",
            valid_key: "DEBUG",
            "log_file": log_file,
            "log_format": "pipe-delimited"
        },
        "apps": apps_config
    }

    remove_root_logger_handlers()
    with pytest.raises(InitializationError) as exc_info:
        SolaceAiConnector(config)

    assert f"Invalid log level 'INVALID_LEVEL' specified for '{invalid_key}'" in str(exc_info.value)