"""Base class for LiteLLM chat models"""

import litellm

from litellm.exceptions import APIConnectionError
from litellm.router import RetryPolicy
from litellm.router import AllowedFailsPolicy

from ....component_base import ComponentBase
from .....common.log import log
from .....common import Message_NACK_Outcome

litellm_info_base = {
    "class_name": "LiteLLMChatModelBase",
    "description": "Base class for LiteLLM chat models",
    "config_parameters": [
        {
            "name": "load_balancer",
            "required": False,
            "description": ("Add a list of models to load balancer."),
            "default": "",
        },
        {
            "name": "embedding_params",
            "required": False,
            "description": (
                "LiteLLM model parameters. The model, api_key and base_url are mandatory."
                "find more models at https://docs.litellm.ai/docs/providers"
                "find more parameters at https://docs.litellm.ai/docs/completion/input"
            ),
            "default": "",
        },
        {
            "name": "temperature",
            "required": False,
            "description": "Sampling temperature to use",
            "default": 0.7,
        },
        {
            "name": "set_response_uuid_in_user_properties",
            "required": False,
            "description": (
                "Whether to set the response_uuid in the user_properties of the "
                "input_message. This will allow other components to correlate "
                "streaming chunks with the full response."
            ),
            "default": False,
            "type": "boolean",
        },
        {
            "name": "timeout",
            "required": False,
            "description": "Request timeout in seconds",
            "default": 60,
        },
        {
            "name": "retry_policy",
            "required": False,
            "description": (
                "Retry policy for the load balancer. "
                "Find more at https://docs.litellm.ai/docs/routing#cooldowns"
            ),
        },
        {
            "name": "allowed_fails_policy",
            "required": False,
            "description": (
                "Allowed fails policy for the load balancer. "
                "Find more at https://docs.litellm.ai/docs/routing#cooldowns"
            ),
        },
    ],
}


class LiteLLMBase(ComponentBase):

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.init()
        self.init_load_balancer()

    def init(self):
        litellm.suppress_debug_info = True
        self.timeout = self.get_config("timeout")
        self.retry_policy_config = self.get_config("retry_policy")
        self.allowed_fails_policy_config = self.get_config("allowed_fails_policy")
        self.load_balancer_config = self.get_config("load_balancer")
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties"
        )
        self.router = None

    def init_load_balancer(self):
        """initialize a load balancer"""
        try:

            if self.retry_policy_config:
                retry_policy = RetryPolicy(
                    ContentPolicyViolationErrorRetries=self.retry_policy_config.get(
                        "ContentPolicyViolationErrorRetries", None
                    ),
                    AuthenticationErrorRetries=self.retry_policy_config.get(
                        "AuthenticationErrorRetries", None
                    ),
                    BadRequestErrorRetries=self.retry_policy_config.get(
                        "BadRequestErrorRetries", None
                    ),
                    TimeoutErrorRetries=self.retry_policy_config.get(
                        "TimeoutErrorRetries", None
                    ),
                    RateLimitErrorRetries=self.retry_policy_config.get(
                        "RateLimitErrorRetries", None
                    ),
                    InternalServerErrorRetries=self.retry_policy_config.get(
                        "InternalServerErrorRetries", None
                    ),
                )
            else:
                retry_policy = RetryPolicy()

            if self.allowed_fails_policy_config:
                allowed_fails_policy = AllowedFailsPolicy(
                    ContentPolicyViolationErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "ContentPolicyViolationErrorAllowedFails", None
                    ),
                    RateLimitErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "RateLimitErrorAllowedFails", None
                    ),
                    BadRequestErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "BadRequestErrorAllowedFails", None
                    ),
                    AuthenticationErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "AuthenticationErrorAllowedFails", None
                    ),
                    TimeoutErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "TimeoutErrorAllowedFails", None
                    ),
                    InternalServerErrorAllowedFails=self.allowed_fails_policy_config.get(
                        "InternalServerErrorAllowedFails", None
                    ),
                )
            else:
                allowed_fails_policy = AllowedFailsPolicy()

            self.router = litellm.Router(
                model_list=self.load_balancer_config,
                retry_policy=retry_policy,
                allowed_fails_policy=allowed_fails_policy,
                timeout=self.timeout,
            )
            log.debug("Litellm Load balancer was initialized")
        except Exception as e:
            raise ValueError(f"Error initializing load balancer: {e}")

    def load_balance(self, messages, stream):
        """load balance the messages"""
        response = self.router.completion(
            model=self.load_balancer_config[0]["model_name"],
            messages=messages,
            stream=stream,
        )
        log.debug("Load balancer responded")
        return response

    def invoke(self, message, data):
        """invoke the model"""
        pass

    def nack_reaction_to_exception(self, exception_type):
        """get the nack reaction to an exception"""
        if exception_type in {APIConnectionError}:
            return Message_NACK_Outcome.FAILED
        else:
            return Message_NACK_Outcome.REJECTED
