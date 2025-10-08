import logging
import sys
import pytest
import json

sys.path.append("src")

from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.exceptions import InitializationError
from solace_ai_connector.common.log import validate_log_level
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
    # This is needed on top of the fixture since pytest re-adds the caplog handlers before we get to the actual test
    # For setup_log() to work correctly, the root logger must not have any handlers configured
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Also clear sam_trace logger in case it was created
    sam_trace_logger = logging.getLogger('sam_trace')
    for handler in sam_trace_logger.handlers[:]:
        sam_trace_logger.removeHandler(handler)
    sam_trace_logger.setLevel(logging.NOTSET)

def assert_sam_trace_logger_default_configuration():
    sam_trace_logger = logging.getLogger('sam_trace')

    assert len(sam_trace_logger.handlers) == 1
    assert isinstance(sam_trace_logger.handlers[0], logging.FileHandler)
    assert sam_trace_logger.level == logging.WARNING # Effectively disabled trace

def test_setup_logging_when_no_env_var(tmp_path, monkeypatch, apps_config, isolated_logging):
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

    assert_sam_trace_logger_default_configuration()

def test_setup_logging_with_logback_config(tmp_path, monkeypatch, apps_config, isolated_logging):
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

    assert_sam_trace_logger_default_configuration()


def test_setup_logging_with_missing_log_config_uses_defaults(monkeypatch, apps_config, isolated_logging):
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

    assert_sam_trace_logger_default_configuration()

def test_setup_logging_with_jsonl_formatting(tmp_path, monkeypatch, apps_config, isolated_logging):
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

    assert_sam_trace_logger_default_configuration()

@pytest.mark.parametrize(
    "invalid_key, valid_key",
    [
        ("stdout_log_level", "log_file_level"),
        ("log_file_level", "stdout_log_level"),
    ]
)
def test_setup_logging_with_invalid_log_level(tmp_path, monkeypatch, apps_config, invalid_key, valid_key, isolated_logging):
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

    with pytest.raises(InitializationError) as exc_info:
        SolaceAiConnector(config)

    assert f"Invalid log level 'INVALID_LEVEL' specified for '{invalid_key}'" in str(exc_info.value)

@pytest.mark.parametrize(
    "invalid_key, valid_key",
    [
        ("stdout_log_level", "log_file_level"),
        ("log_file_level", "stdout_log_level"),
    ]
)
def test_setup_logging_with_boolean_true_log_levels(tmp_path, monkeypatch, apps_config, invalid_key, valid_key, isolated_logging):
    """Test that boolean TRUE values for log levels raise InitializationError"""
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "boolean_level_test.log"

    config = {
        "log": {
            invalid_key: True,
            valid_key: "DEBUG",
            "log_file": log_file,
            "log_format": "pipe-delimited"
        },
        "apps": apps_config
    }

    with pytest.raises(InitializationError) as exc_info:
        SolaceAiConnector(config)

    assert f"Invalid log level type 'bool' for '{invalid_key}'" in str(exc_info.value)
    assert "Must be int or str" in str(exc_info.value)

def test_sam_trace_logger_configuration_when_enabled(tmp_path, monkeypatch, apps_config, isolated_logging):
    """Test that sam_trace logger is properly configured when enableTrace is True"""
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    
    log_file = tmp_path / "trace_enabled_test.log"

    config = {
        "log": {
            "stdout_log_level": "ERROR",
            "log_file_level": "DEBUG",
            "log_file": log_file,
            "log_format": "jsonl",
            "enable_trace": True
        },
        "apps": apps_config
    }

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    sam_trace_logger = logging.getLogger('sam_trace')
    assert sam_trace_logger.level == logging.DEBUG
    assert sam_trace_logger.propagate is False
    assert len(sam_trace_logger.handlers) == 1

    file_handler = sam_trace_logger.handlers[0]
    assert isinstance(file_handler, logging.FileHandler)
    assert file_handler.baseFilename == str(log_file)

class TestValidateLogLevel:

    @pytest.mark.parametrize(
        "level_str, expected_numeric",
        [
            ("DEBUG", 10),
            ("INFO", 20),
            ("WARNING", 30),
            ("ERROR", 40),
            ("CRITICAL", 50),
            ("debug", 10),  # Test case insensitivity
            ("info", 20),
            ("warning", 30),
            ("error", 40),
            ("critical", 50),
        ]
    )
    def test_validate_log_level_string_input(self, level_str, expected_numeric):
        """Test that string log levels are correctly converted to numeric values"""
        result = validate_log_level("test_handler", level_str)
        assert result == expected_numeric
        assert isinstance(result, int)

    @pytest.mark.parametrize(
        "level_int",
        [10, 20, 30, 40, 50]
    )
    def test_validate_log_level_integer_input(self, level_int):
        """Test that valid integer log levels are returned as-is"""
        result = validate_log_level("test_handler", level_int)
        assert result == level_int
        assert isinstance(result, int)

    @pytest.mark.parametrize(
        "invalid_string",
        ["INVALID", "TRACE", "VERBOSE", "", "123", "info_level"]
    )
    def test_validate_log_level_invalid_string(self, invalid_string):
        """Test that invalid string log levels raise InitializationError"""
        with pytest.raises(InitializationError) as exc_info:
            validate_log_level("test_handler", invalid_string)
        
        assert f"Invalid log level '{invalid_string}' specified for 'test_handler'" in str(exc_info.value)
        assert "Valid levels are:" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_int",
        [0, 5, 15, 25, 35, 45, 55, 100, -10]
    )
    def test_validate_log_level_invalid_integer(self, invalid_int):
        """Test that invalid integer log levels raise InitializationError"""
        with pytest.raises(InitializationError) as exc_info:
            validate_log_level("test_handler", invalid_int)
        
        assert f"Invalid numeric log level '{invalid_int}' specified for 'test_handler'" in str(exc_info.value)
        assert "Valid levels are: 10 (DEBUG), 20 (INFO), 30 (WARNING), 40 (ERROR), 50 (CRITICAL)" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_type",
        [None, [], {}, 10.5, True, False]
    )
    def test_validate_log_level_invalid_type(self, invalid_type):
        """Test that non-string/non-int types raise InitializationError"""
        with pytest.raises(InitializationError) as exc_info:
            validate_log_level("test_handler", invalid_type)
        
        expected_type_name = type(invalid_type).__name__
        assert f"Invalid log level type '{expected_type_name}' for 'test_handler'" in str(exc_info.value)
        assert "Must be int or str" in str(exc_info.value)

def test_setup_logging_with_numeric_log_levels(tmp_path, monkeypatch, apps_config, isolated_logging):
    """Test that setup_log works correctly with numeric log levels"""
    monkeypatch.delenv("LOGGING_CONFIG_PATH", raising=False)
    log_file = tmp_path / "numeric_levels_test.log"

    config = {
        "log": {
            "stdout_log_level": 40,  # ERROR
            "log_file_level": 10,    # DEBUG
            "log_file": str(log_file),
            "log_format": "pipe-delimited"
        }, 
        "apps": apps_config
    }

    remove_root_logger_handlers()
    SolaceAiConnector(config)

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG  # min(40, 10) = 10
    assert len(root_logger.handlers) == 2

    for h in root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            assert h.level == 10  # DEBUG
            assert h.baseFilename.endswith(log_file.name)
        else:
            assert h.level == 40  # ERROR

    assert_sam_trace_logger_default_configuration()
