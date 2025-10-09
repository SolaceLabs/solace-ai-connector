import logging
import sys

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
