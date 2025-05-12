"""Unit tests for LangChainTextSplitter."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_split_text import (
    LangChainTextSplitter,
    SingleChunkSplitter,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_base import (
    LangChainBase,
)


class TestLangChainTextSplitter:
    """Tests for the LangChainTextSplitter class."""

    def test_initialization(self):
        """Test that LangChainTextSplitter initializes correctly."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            # Initialize the component
            component = LangChainTextSplitter(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LangChainTextSplitter"
        assert "split" in info["description"].lower()

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema has the required properties
        assert "text" in info["input_schema"]["properties"]
        assert info["input_schema"]["required"] == ["text"]

        # Verify the output schema is an array of strings
        assert info["output_schema"]["type"] == "array"
        assert info["output_schema"]["items"]["type"] == "string"

    def test_invoke_success(self, mock_message_fixture):
        """Test successful invocation of the component."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainTextSplitter(config={})

            # Mock the component's split_text method
            component.component = MagicMock()
            component.component.split_text.return_value = ["Chunk 1", "Chunk 2"]

            # Call invoke
            data = "This is a long text that needs to be split."
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's split_text method was called
            component.component.split_text.assert_called_once_with(data)

            # Verify the result
            assert result == ["Chunk 1", "Chunk 2"]


class TestSingleChunkSplitter:
    """Tests for the SingleChunkSplitter class."""

    def test_split_text(self):
        """Test the split_text method."""
        splitter = SingleChunkSplitter()

        # Call split_text
        result = splitter.split_text("This is a test text.")

        # Verify the result is a list containing the original text
        assert result == ["This is a test text."]

    def test_invoke(self, mock_message_fixture):
        """Test the invoke method."""
        splitter = SingleChunkSplitter()

        # Call invoke
        data = "This is a test text."
        result = splitter.invoke(mock_message_fixture, data)

        # Verify the result is a list containing the original text
        assert result == ["This is a test text."]
