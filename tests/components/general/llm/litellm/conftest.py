"""Pytest fixtures for LiteLLM component tests."""

import sys
import os
import pytest
from unittest.mock import patch
from threading import Lock  # Keep this import for fixtures if they create Locks directly

# Add the src directory to the path so we can import solace_ai_connector
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'src'))

from solace_ai_connector.common.message import Message
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    litellm_info_base as litellm_base_module_info_dict,
)
from solace_ai_connector.common.monitoring import Metrics
from solace_ai_connector.common.log import setup_log, log


@pytest.fixture(autouse=True)
def setup_litellm_logging():
    """Set up logging with trace enabled for LiteLLM tests."""
    # Reset any handlers that might be attached to the logger
    for handler in log.handlers[:]:
        log.removeHandler(handler)
    
    # Set up logging with trace enabled
    setup_log(
        logFilePath="litellm_test_logs.log",
        stdOutLogLevel="INFO",
        fileLogLevel="DEBUG",
        logFormat="pipe-delimited",
        logBack={},
        enableTrace=True
    )
    
    yield


@pytest.fixture
def mock_litellm_router_fixture(mocker):
    """Mocks litellm.Router to prevent actual Router instantiation."""
    # Patch where litellm.Router is looked up in the litellm_base module
    return mocker.patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router",
        autospec=True,
    )


@pytest.fixture
def litellm_base_module_info():
    """Provides the module_info dictionary for LiteLLMBase."""
    return litellm_base_module_info_dict.copy()


@pytest.fixture
def valid_load_balancer_config():
    """Provides a minimal valid load_balancer configuration."""
    return [
        {
            "model_name": "test-model",
            "litellm_params": {
                "model": "gpt-3.5-turbo",
                "api_key": "sk-fakekey",
                "base_url": "https://fake.api.com",
            },
        }
    ]


@pytest.fixture
def minimal_component_config(valid_load_balancer_config):
    """
    Provides a minimal config dictionary for LiteLLMBase instantiation,
    ensuring init_load_balancer can run without extensive mocking of its internals.
    """
    return {"load_balancer": valid_load_balancer_config}


@pytest.fixture
def mock_message_fixture():
    return Message(payload={"text": "hello"}, topic="test/topic")
