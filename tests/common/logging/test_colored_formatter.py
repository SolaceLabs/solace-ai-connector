"""Tests for the ColoredFormatter class."""

import logging
import os
import sys
from io import StringIO

import pytest

sys.path.append("src")

from solace_ai_connector.common.logging_config import configure_from_file
from solace_ai_connector.logging import ColoredFormatter


def test_colored_formatter_with_yaml_config(tmp_path, monkeypatch):
    """Test ColoredFormatter integration with YAML logging configuration."""
    log_file = tmp_path / "colored_test.log"
    config_content = f"""
version: 1
disable_existing_loggers: false

formatters:
  coloredFormatter:
    class: solace_ai_connector.logging.ColoredFormatter
    format: '%(asctime)s | %(levelname)-5s | %(name)s | %(message)s'

handlers:
  file:
    class: logging.FileHandler
    level: DEBUG
    formatter: coloredFormatter
    filename: {log_file}

root:
  level: DEBUG
  handlers: [file]
"""

    config_file = tmp_path / "logging_colored.yaml"
    config_file.write_text(config_content)

    monkeypatch.setenv("LOGGING_CONFIG_PATH", str(config_file))
    
    # ColoredFormatter should auto-disable for file handlers (non-TTY)
    assert configure_from_file() is True

    test_logger = logging.getLogger("test_colored_logger")
    
    # Test different log levels
    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    test_logger.error("Error message")
    test_logger.critical("Critical message")

    assert log_file.exists(), "Log file should have been created"
    log_content = log_file.read_text()
    
    # Verify all messages are present
    assert "Debug message" in log_content
    assert "Info message" in log_content
    assert "Warning message" in log_content
    assert "Error message" in log_content
    assert "Critical message" in log_content
    
    # Verify logger name is present
    assert "test_colored_logger" in log_content
    
    # Colors should NOT be in file output (non-TTY)
    assert '\033[' not in log_content, "ANSI color codes should not be in file output"


def test_colored_formatter_tty_detection():
    """Test that ColoredFormatter correctly detects TTY support."""
    formatter = ColoredFormatter()
    
    # The formatter should have detected TTY support
    # In test environment, this will likely be False since pytest doesn't run in a TTY
    assert isinstance(formatter.use_colors, bool)


def test_colored_formatter_respects_no_color_env_var(monkeypatch):
    """Test that ColoredFormatter respects NO_COLOR environment variable."""
    monkeypatch.setenv("NO_COLOR", "1")
    
    formatter = ColoredFormatter()
    assert formatter.use_colors is False, "Colors should be disabled when NO_COLOR is set"


def test_colored_formatter_respects_force_color_env_var(monkeypatch):
    """Test that ColoredFormatter respects FORCE_COLOR environment variable."""
    # Set FORCE_COLOR before creating the formatter
    monkeypatch.setenv("FORCE_COLOR", "1")
    
    # Even if TTY detection would fail, FORCE_COLOR should enable colors
    formatter = ColoredFormatter()
    
    # FORCE_COLOR should override TTY detection
    # Note: In test environment, isatty() typically returns False
    # but FORCE_COLOR should still enable colors
    assert formatter.use_colors is True, "Colors should be enabled when FORCE_COLOR is set"


def test_colored_formatter_colors_log_levels():
    """Test that ColoredFormatter applies correct colors to log levels."""
    # Create a formatter with colors forced on
    os.environ['FORCE_COLOR'] = '1'
    formatter = ColoredFormatter('%(levelname)s - %(message)s')
    
    # Create a string buffer to capture output
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger('test_colors')
    logger.setLevel(logging.DEBUG)
    logger.handlers = [handler]
    
    # Test different log levels
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    output = stream.getvalue()
    
    # Verify ANSI color codes are present when FORCE_COLOR is set
    if formatter.use_colors:
        assert '\033[' in output, "ANSI color codes should be present when colors are enabled"
        assert formatter.CYAN in output, "Cyan color should be used for DEBUG"
        assert formatter.GREEN in output, "Green color should be used for INFO"
        assert formatter.YELLOW in output, "Yellow color should be used for WARNING"
        assert formatter.RED in output, "Red color should be used for ERROR"
    
    # Clean up
    del os.environ['FORCE_COLOR']


def test_colored_formatter_highlights_backend_logs():
    """Test that ColoredFormatter highlights backend component names."""
    os.environ['FORCE_COLOR'] = '1'
    formatter = ColoredFormatter('%(name)s - %(message)s')
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    
    # Test backend logger
    backend_logger = logging.getLogger('solace_agent_mesh.gateway.http_sse.main')
    backend_logger.setLevel(logging.INFO)
    backend_logger.handlers = [handler]
    backend_logger.info("Backend log message")
    
    output = stream.getvalue()
    
    # Verify backend component name is colored blue when colors are enabled
    if formatter.use_colors:
        assert formatter.BLUE in output, "Backend component names should be colored blue"
    
    # Clean up
    del os.environ['FORCE_COLOR']


def test_colored_formatter_preserves_original_record():
    """Test that ColoredFormatter doesn't permanently modify log records."""
    os.environ['FORCE_COLOR'] = '1'
    formatter = ColoredFormatter('%(levelname)s - %(name)s - %(message)s')
    
    # Create a log record
    record = logging.LogRecord(
        name='test.logger',
        level=logging.INFO,
        pathname='test.py',
        lineno=1,
        msg='Test message',
        args=(),
        exc_info=None
    )
    
    # Save original values
    original_levelname = record.levelname
    original_name = record.name
    
    # Format the record
    formatted = formatter.format(record)
    
    # Verify original values are restored
    assert record.levelname == original_levelname, "Original levelname should be restored"
    assert record.name == original_name, "Original name should be restored"
    
    # Verify formatted output contains color codes (if colors enabled)
    if formatter.use_colors:
        assert '\033[' in formatted, "Formatted output should contain color codes"
    
    # Clean up
    del os.environ['FORCE_COLOR']