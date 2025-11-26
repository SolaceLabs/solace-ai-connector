"""
Public-facing logging formatters for Solace AI Connector.

This module provides custom logging formatters that can be used in logging
configuration files to enhance log output readability and functionality.
"""

import logging
import os
import sys


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds ANSI color codes to log output for better readability.
    
    This formatter is designed to be used with non-JSON log formats and automatically
    detects TTY support. It respects NO_COLOR and FORCE_COLOR environment variables.
    
    Color scheme:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bold Red
    - Backend logs (gateway, http_sse, fastapi, uvicorn, starlette): Blue component names
    
    Usage in logging configuration (INI format):
    
    ```ini
    [formatters]
    keys=coloredFormatter
    
    [formatter_coloredFormatter]
    class=solace_ai_connector.logging.ColoredFormatter
    format=%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s
    ```
    
    Usage in logging configuration (YAML format):
    
    ```yaml
    formatters:
      coloredFormatter:
        class: solace_ai_connector.logging.ColoredFormatter
        format: "%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s"
    
    handlers:
      streamHandler:
        class: logging.StreamHandler
        formatter: coloredFormatter
        stream: ext://sys.stdout
    ```
    
    Environment Variables:
    - NO_COLOR: Set to any value to disable colored output (https://no-color.org/)
    - FORCE_COLOR: Set to any value to force colored output even when TTY detection fails
    """
    
    # ANSI color codes
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Foreground colors
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    BLUE = '\033[34m'
    
    # Log level colors
    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD + RED,
    }
    
    # Keywords that identify backend logs
    BACKEND_KEYWORDS = ['gateway', 'http_sse', 'fastapi', 'uvicorn', 'starlette']
    
    def __init__(self, *args, **kwargs):
        """Initialize the colored formatter with TTY detection."""
        super().__init__(*args, **kwargs)
        self.use_colors = self._supports_color()
    
    @staticmethod
    def _supports_color() -> bool:
        """
        Check if the terminal supports color output.
        
        Returns:
            True if colors are supported, False otherwise
        """
        if os.environ.get('NO_COLOR'):
            return False
        
        # Check for FORCE_COLOR environment variable
        # This overrides TTY detection
        if os.environ.get('FORCE_COLOR'):
            return True
        
        # Check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty'):
            return False
        if not sys.stdout.isatty():
            return False
        
        # On Windows, check for ANSICON or WT_SESSION (Windows Terminal)
        if sys.platform == 'win32':
            return bool(os.environ.get('ANSICON') or os.environ.get('WT_SESSION'))
        
        return True
    
    def _is_backend_log(self, record: logging.LogRecord) -> bool:
        """
        Check if the log record is from a backend component.
        
        Args:
            record: The log record to check
            
        Returns:
            True if this is a backend log, False otherwise
        """
        logger_name = record.name.lower()
        return any(keyword in logger_name for keyword in self.BACKEND_KEYWORDS)
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors if TTY is detected.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string with color codes (if colors are enabled)
        """
        if not self.use_colors:
            return super().format(record)
        
        # Save original values
        levelname_orig = record.levelname
        name_orig = record.name
        
        # Color the level name
        level_color = self.LEVEL_COLORS.get(record.levelno, '')
        record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        
        # Color backend component names
        if self._is_backend_log(record):
            record.name = f"{self.BLUE}{record.name}{self.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original values
        record.levelname = levelname_orig
        record.name = name_orig
        
        return result