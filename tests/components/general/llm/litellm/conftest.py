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


@pytest.fixture
def valid_bedrock_embedding_load_balancer_config():
    """Provides a minimal valid load_balancer configuration for Bedrock embeddings (env creds)."""
    return [
        {
            "model_name": "bedrock-titan-embed",
            "litellm_params": {
                "model": "bedrock/amazon.titan-embed-text-v1",
                # Assuming AWS creds are in environment
            },
        }
    ]


@pytest.fixture
def valid_bedrock_embedding_load_balancer_config_with_creds():
    """Provides a valid load_balancer configuration for Bedrock embeddings with explicit creds."""
    return [
        {
            "model_name": "bedrock-titan-embed-creds",
            "litellm_params": {
                "model": "bedrock/amazon.titan-embed-text-v1",
                "aws_access_key_id": "fake_access_key",
                "aws_secret_access_key": "fake_secret_key",
                "aws_region_name": "us-east-1",
            },
        }
    ]


@pytest.fixture
def minimal_bedrock_embedding_component_config(
    valid_bedrock_embedding_load_balancer_config,
):
    """Minimal config for LiteLLMBase with Bedrock embedding."""
    return {"load_balancer": valid_bedrock_embedding_load_balancer_config}
