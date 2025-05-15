"""Pytest fixtures for LangChain component tests."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.common.message import Message


@pytest.fixture
def mock_langchain_module_fixture(mocker):
    """Mocks dynamic module loading for LangChain components."""
    return mocker.patch(
        "importlib.import_module",
        autospec=True,
    )


@pytest.fixture
def langchain_base_module_info():
    """Provides a basic module_info dictionary for LangChainBase."""
    return {
        "class_name": "TestLangChainComponent",
        "description": "Test LangChain component",
        "config_parameters": [],
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
    }


@pytest.fixture
def minimal_component_config():
    """Provides a minimal config dictionary for LangChainBase instantiation."""
    return {
        "component_name": "test_component",
        "component_config": {
            "langchain_module": "test_module",
            "langchain_class": "TestClass",
            "langchain_component_config": {},
        },
    }


@pytest.fixture
def mock_message_fixture():
    """Provides a mock message object."""
    return Message(payload={"text": "hello"}, topic="test/topic")


@pytest.fixture
def mock_langchain_component():
    """Provides a mock LangChain component."""
    mock_component = MagicMock()
    mock_component.invoke.return_value = "Test response"
    return mock_component


@pytest.fixture
def mock_embedding_component():
    """Provides a mock embedding component."""
    mock_component = MagicMock()
    mock_component.embed_documents.return_value = [[0.1, 0.2, 0.3]]
    mock_component.embed_query.return_value = [0.1, 0.2, 0.3]
    mock_component.embed_images.return_value = [[0.1, 0.2, 0.3]]
    return mock_component


@pytest.fixture
def mock_vector_store():
    """Provides a mock vector store."""
    mock_store = MagicMock()
    mock_store.similarity_search.return_value = [
        MagicMock(page_content="Test content", metadata={"source": "test_source"})
    ]
    mock_store.add_texts.return_value = None
    mock_store.delete.return_value = None
    return mock_store
