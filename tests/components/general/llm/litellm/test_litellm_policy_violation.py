"""Test LiteLLM reaction to policy violation"""

import sys
import unittest
from unittest.mock import patch, MagicMock
import queue

sys.path.append("src")

from solace_ai_connector.components.general.llm.litellm.litellm_base import LiteLLMBase
from solace_ai_connector.common.message import Message
from solace_ai_connector.common import Message_NACK_Outcome
from litellm.exceptions import ContentPolicyViolationError


class TestLiteLLMPolicyViolation(unittest.TestCase):
    """Test LiteLLM reaction to policy violation"""

    def test_policy_violation_nack(self):
        """Test that a policy violation results in a NACK with REJECTED outcome"""
        # Create a mock message
        message = MagicMock()

        # Create a mock LiteLLMBase instance
        litellm_component = MagicMock(spec=LiteLLMBase)

        # Test the nack_reaction_to_exception method
        result = LiteLLMBase.nack_reaction_to_exception(
            litellm_component, ContentPolicyViolationError
        )

        # Verify that ContentPolicyViolationError results in REJECTED outcome
        self.assertEqual(result, Message_NACK_Outcome.REJECTED)


if __name__ == "__main__":
    unittest.main()
