"""Pytest fixtures for LLM component tests."""

# Removed sys.path manipulations.
# It's expected that the project is installed in editable mode
# in the test environment (e.g., via 'pip install -e .'),
# making 'solace_ai_connector' directly importable.

import pytest
from unittest.mock import patch
from threading import Lock  # Keep this import for fixtures if they create Locks directly

from solace_ai_connector.common.message import Message
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    litellm_info_base as litellm_base_module_info_dict,
)
from solace_ai_connector.common.monitoring import Metrics


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
