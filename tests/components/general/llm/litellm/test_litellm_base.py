"""Unit tests for LiteLLMBase."""

import pytest
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
