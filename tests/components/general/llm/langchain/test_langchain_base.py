"""Unit tests for LangChainBase."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_base import LangChainBase


class TestLangChainBaseInitialization:
    """Tests for the __init__ method of LangChainBase."""

    def test_initialization_with_minimal_config(
        self, langchain_base_module_info, minimal_component_config
    ):
        """Test that the component initializes correctly with minimal configuration."""
        with patch.object(LangChainBase, "load_component") as mock_load_component:
            with patch.object(
                LangChainBase, "create_component"
            ) as mock_create_component:
                # Mock the component class and instance
                mock_component_class = MagicMock()
                mock_component = MagicMock()
                mock_load_component.return_value = mock_component_class
                mock_create_component.return_value = mock_component

                # Initialize the component
                component = LangChainBase(
                    module_info=langchain_base_module_info,
                    config=minimal_component_config,
                )

                # Check that attributes are set correctly
                assert component.name == "test_component"
                assert (
                    component.component_config
                    == minimal_component_config["component_config"]
                )
                assert component.lc_module == "test_module"
                assert component.lc_class == "TestClass"
                assert component.lc_config == {}
                assert component.component_class == mock_component_class
                assert component.component == mock_component

                # Check that methods were called correctly
                mock_load_component.assert_called_once_with("test_module", "TestClass")
                mock_create_component.assert_called_once_with({}, mock_component_class)


class TestLangChainBaseLoadComponent:
    """Tests for the load_component method of LangChainBase."""

    def test_load_component_success(
        self,
        langchain_base_module_info,
        minimal_component_config,
        mock_langchain_module_fixture,
    ):
        """Test successful module loading."""
        # Mock the module and class
        mock_module = MagicMock()
        mock_class = MagicMock()
        mock_module.TestClass = mock_class
        mock_langchain_module_fixture.return_value = mock_module

        # Initialize the component
        component = LangChainBase(
            module_info=langchain_base_module_info, config=minimal_component_config
        )

        # Check that the component class was loaded correctly
        assert component.component_class == mock_class
        mock_langchain_module_fixture.assert_called_once_with("test_module")

    def test_load_component_import_error(
        self,
        langchain_base_module_info,
        minimal_component_config,
        mock_langchain_module_fixture,
    ):
        """Test handling of import errors."""
        # Mock the module to raise an exception
        mock_langchain_module_fixture.side_effect = ImportError("Module not found")

        # Check that the correct exception is raised
        with pytest.raises(ImportError) as excinfo:
            LangChainBase(
                module_info=langchain_base_module_info, config=minimal_component_config
            )

        assert "Unable to load component" in str(excinfo.value)


class TestLangChainBaseCreateComponent:
    """Tests for the create_component method of LangChainBase."""

    def test_create_component_success(
        self, langchain_base_module_info, minimal_component_config
    ):
        """Test successful component creation."""
        with patch.object(LangChainBase, "load_component") as mock_load_component:
            # Mock the component class and instance
            mock_component_class = MagicMock()
            mock_component = MagicMock()
            mock_component_class.return_value = mock_component
            mock_load_component.return_value = mock_component_class

            # Initialize the component
            component = LangChainBase(
                module_info=langchain_base_module_info, config=minimal_component_config
            )

            # Check that the component was created correctly
            assert component.component == mock_component
            mock_component_class.assert_called_once_with()

    def test_create_component_error(
        self, langchain_base_module_info, minimal_component_config
    ):
        """Test handling of creation errors."""
        with patch.object(LangChainBase, "load_component") as mock_load_component:
            # Mock the component class to raise an exception
            mock_component_class = MagicMock()
            mock_component_class.side_effect = Exception("Failed to create component")
            mock_load_component.return_value = mock_component_class

            # Check that the correct exception is raised
            with pytest.raises(ImportError) as excinfo:
                LangChainBase(
                    module_info=langchain_base_module_info,
                    config=minimal_component_config,
                )

            assert "Unable to create component" in str(excinfo.value)


class TestLangChainBaseInvoke:
    """Tests for the invoke method of LangChainBase."""

    def test_invoke_not_implemented(
        self, langchain_base_module_info, minimal_component_config, mock_message_fixture
    ):
        """Test that the invoke method raises NotImplementedError."""
        with patch.object(LangChainBase, "load_component") as mock_load_component:
            with patch.object(
                LangChainBase, "create_component"
            ) as mock_create_component:
                # Mock the component class and instance
                mock_component_class = MagicMock()
                mock_component = MagicMock()
                mock_load_component.return_value = mock_component_class
                mock_create_component.return_value = mock_component

                # Initialize the component
                component = LangChainBase(
                    module_info=langchain_base_module_info,
                    config=minimal_component_config,
                )

                # Check that invoke raises NotImplementedError
                with pytest.raises(NotImplementedError) as excinfo:
                    component.invoke(mock_message_fixture, {})

                assert "invoke() not implemented" in str(excinfo.value)
