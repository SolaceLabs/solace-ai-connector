"""Pytest fixtures for all tests."""

import sys
import os
import pytest

# Add the src directory to the path so we can import solace_ai_connector
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from solace_ai_connector.common.log import setup_log, log


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Set up logging with trace enabled for all tests."""
    # Reset any handlers that might be attached to the logger
    for handler in log.handlers[:]:
        log.removeHandler(handler)
    
    # Set up logging with trace enabled
    setup_log(
        logFilePath="test_logs.log",
        stdOutLogLevel="INFO",
        fileLogLevel="DEBUG",
        logFormat="pipe-delimited",
        logBack={},
        enableTrace=True
    )
    
    yield
    
    # Clean up if needed
    for handler in log.handlers[:]:
        handler.close()
        log.removeHandler(handler)
