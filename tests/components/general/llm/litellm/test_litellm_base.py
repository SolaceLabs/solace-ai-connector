"""Unit tests for LiteLLMBase."""

import pytest
import os
from unittest.mock import patch, MagicMock
from threading import Lock as ThreadingLock  # Import Lock directly for isinstance check

from litellm.exceptions import APIConnectionError
from solace_ai_connector.common.message import Message_NACK_Outcome
from solace_ai_connector.common.monitoring import Metrics
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    LiteLLMBase,
    litellm_info_base,
)


class TestLiteLLMBaseInitialization:
    """Tests for the __init__ method of LiteLLMBase."""

    @patch.object(
        LiteLLMBase, "init_load_balancer", MagicMock()
    )  # Mock to isolate __init__
    def test_stats_initialization_structure(self, litellm_base_module_info):
        """
        Tests the detailed structure of the initialized stats dictionary.
        """
        # We pass an empty config because init_load_balancer is mocked,
        # so it won't try to validate the load_balancer config.
        component = LiteLLMBase(module_info=litellm_base_module_info, config={})

        assert isinstance(component.stats, dict)
        assert component.stats == {
            Metrics.LITELLM_STATS_PROMPT_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TOKENS: [],
            Metrics.LITELLM_STATS_TOTAL_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TIME: [],
            Metrics.LITELLM_STATS_COST: [],
        }

    def test_initialization_calls_init_and_init_load_balancer(
        self, litellm_base_module_info, minimal_component_config
    ):
        """
        Tests that __init__ calls both init() and init_load_balancer().
        """
        with (
            patch.object(
                LiteLLMBase, "init", wraps=LiteLLMBase.init, autospec=True
            ) as mock_init,
            patch.object(
                LiteLLMBase,
                "init_load_balancer",
                wraps=LiteLLMBase.init_load_balancer,
                autospec=True,
            ) as mock_init_load_balancer,
            patch(
                "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
            ),
        ):  # Mock router to let init_load_balancer run
            LiteLLMBase(
                module_info=litellm_base_module_info, config=minimal_component_config
            )
            mock_init.assert_called_once()
            mock_init_load_balancer.assert_called_once()
            
    def test_disable_ssl_verify_env_var(self, litellm_base_module_info, minimal_component_config, monkeypatch, caplog):
        """
        Test that when DISABLE_SSL_VERIFY is set to "true", litellm.ssl_verify is set to False.
        """
        monkeypatch.setenv("DISABLE_SSL_VERIFY", "true")
        
        with patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm") as mock_litellm, \
             patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"):
            
            LiteLLMBase(module_info=litellm_base_module_info, config=minimal_component_config)
            
            assert mock_litellm.ssl_verify is False
            
            assert any("SSL verification is disabled (insecure mode)" in record.message for record in caplog.records)
    
    def test_ssl_cert_file_env_var(self, litellm_base_module_info, minimal_component_config, monkeypatch, tmp_path):
        """
        Test that when SSL_CERT_FILE is set to a valid path, litellm.ssl_verify is set to that path.
        """
        # Create a temporary file to use as the certificate
        cert_file = tmp_path / "test_cert.pem"
        cert_file.write_text("test certificate content")
        cert_path = str(cert_file)
        
        monkeypatch.setenv("SSL_CERT_FILE", cert_path)
        
        with patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm") as mock_litellm, \
             patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"):
            
            LiteLLMBase(module_info=litellm_base_module_info, config=minimal_component_config)
            
            # Verify litellm.ssl_verify was set to the certificate path
            assert mock_litellm.ssl_verify == cert_path
    
    def test_conflicting_ssl_settings(self, litellm_base_module_info, minimal_component_config, monkeypatch, tmp_path):
        """
        Test that when both DISABLE_SSL_VERIFY is "true" and SSL_CERT_FILE is set, a ValueError is raised.
        """
        # Create a temporary file to use as the certificate
        cert_file = tmp_path / "test_cert.pem"
        cert_file.write_text("test certificate content")
        cert_path = str(cert_file)
        
        monkeypatch.setenv("DISABLE_SSL_VERIFY", "True")
        monkeypatch.setenv("SSL_CERT_FILE", cert_path)
        
        with patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm"), \
             patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"), \
             pytest.raises(ValueError, match="Cannot have both DISABLE_SSL_VERIFY set to true and SSL_CERT_FILE provided"):
            
            LiteLLMBase(module_info=litellm_base_module_info, config=minimal_component_config)
    
    def test_invalid_ssl_cert_file(self, litellm_base_module_info, minimal_component_config, monkeypatch):
        """
        Test that when SSL_CERT_FILE is set to a non-existent path, a ValueError is raised.
        """
        monkeypatch.setenv("SSL_CERT_FILE", "/non/existent/path/cert.pem")
        
        with patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm"), \
             patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"), \
             pytest.raises(ValueError, match="does not exist or is not a file"):
            
            LiteLLMBase(module_info=litellm_base_module_info, config=minimal_component_config)
    
    def test_no_ssl_env_vars(self, litellm_base_module_info, minimal_component_config, monkeypatch):
        """
        Test that when neither DISABLE_SSL_VERIFY nor SSL_CERT_FILE is set, litellm.ssl_verify is not modified.
        """
        # Ensure environment variables are not set
        monkeypatch.delenv("DISABLE_SSL_VERIFY", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        
        with patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm") as mock_litellm, \
             patch("solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"):
            
            # Store the original value of ssl_verify
            original_ssl_verify = mock_litellm.ssl_verify
            
            LiteLLMBase(module_info=litellm_base_module_info, config=minimal_component_config)
            
            # Verify litellm.ssl_verify was not modified
            assert mock_litellm.ssl_verify == original_ssl_verify
