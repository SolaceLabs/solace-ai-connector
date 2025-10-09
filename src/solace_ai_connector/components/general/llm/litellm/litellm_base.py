"""Base class for LiteLLM chat models"""

import logging
import litellm
import time

from threading import Lock
from litellm import ModelResponse
from litellm.exceptions import APIConnectionError
from litellm.router import RetryPolicy
from litellm.router import AllowedFailsPolicy

from ....component_base import ComponentBase
from .....common import Message_NACK_Outcome
from .....common.monitoring import Metrics

log = logging.getLogger(__name__)

litellm_info_base = {
    "class_name": "LiteLLMChatModelBase",
    "description": "Base class for LiteLLM chat models",
    "config_parameters": [
        {
            "name": "load_balancer",
            "required": False,
            "description": (
                "A list of models to configure for the LiteLLM load balancer. "
                "Each item in the list is a dictionary defining a model and must contain:\n"
                "  - 'model_name': An alias for this model configuration (e.g., 'my-openai-model', 'my-bedrock-claude').\n"
                "  - 'litellm_params': A dictionary of parameters passed directly to LiteLLM for this model.\n"
                "    Common 'litellm_params' include:\n"
                "      - 'model': The actual model identifier (e.g., 'gpt-4o', 'anthropic.claude-3-sonnet-20240229-v1:0').\n"
                "      - 'api_key': Required for many providers like OpenAI, Anthropic direct (but NOT for AWS Bedrock).\n"
                "      - 'api_base': The base URL for the API endpoint, if not default.\n"
                "      - 'temperature', 'max_tokens', etc., as supported by LiteLLM and the provider.\n"
                "    For AWS Bedrock models:\n"
                "      - 'model' format: 'bedrock/<provider>.<model_id>' (e.g., 'bedrock/anthropic.claude-3-sonnet-20240229-v1:0').\n"
                "      - 'api_key' is NOT used.\n"
                "      - AWS credentials (aws_access_key_id, aws_secret_access_key, aws_session_token (optional), aws_region_name) "
                "can be provided directly in 'litellm_params'. If not, LiteLLM (via Boto3) attempts to use standard AWS environment variables "
                "(e.g., AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION/AWS_REGION_NAME).\n"
                "      - 'aws_region_name' is generally required for Bedrock, either in 'litellm_params' or as an environment variable.\n"
                "      - Other Bedrock-specific params like 'model_id' (for provisioned throughput) or 'aws_bedrock_runtime_endpoint' can be included."
            ),
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
            "name": "suppress_debug_info",
            "required": False,
            "description": "Whether to suppress debug info in LiteLLM",
            "default": False,
            "type": "boolean",
        },
        {
            "name": "aiohttp_trust_env",
            "required": False,
            "description": "Whether to trust environment variables for aiohttp",
            "default": True,
            "type": "boolean",
        },
        {
            "name": "ssl_verify",
            "required": False,
            "description": "Whether to verify SSL certificates. Can be a boolean or a path to a PEM file.",
            "default": False,
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
        # Get configuration parameters
        suppress_debug_info = self.get_config("suppress_debug_info", False)
        aiohttp_trust_env = self.get_config("aiohttp_trust_env", True)
        ssl_verify = self.get_config("ssl_verify", False)

        # Set LiteLLM parameters
        litellm.suppress_debug_info = suppress_debug_info
        litellm.aiohttp_trust_env = aiohttp_trust_env
        litellm.ssl_verify = ssl_verify
        
        # Turn on debug if suppress_debug_info is True
        if suppress_debug_info:
            litellm._turn_on_debug()
            
        log.info(f"LiteLLM initialized with suppress_debug_info={suppress_debug_info}, aiohttp_trust_env={aiohttp_trust_env}, ssl_verify={ssl_verify}")
        
        self.timeout = self.get_config("timeout")
        self.retry_policy_config = self.get_config("retry_policy")
        self.allowed_fails_policy_config = self.get_config("allowed_fails_policy")
        self.load_balancer_config = self.get_config("load_balancer")
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties"
        )
        self.router = None
        self._lock_stats = Lock()
        self.stats = {
            Metrics.LITELLM_STATS_PROMPT_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TOKENS: [],
            Metrics.LITELLM_STATS_TOTAL_TOKENS: [],
            Metrics.LITELLM_STATS_RESPONSE_TIME: [],
            Metrics.LITELLM_STATS_COST: [],
        }

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

            self.validate_model_config(self.load_balancer_config)
            self.router = litellm.Router(
                model_list=self.load_balancer_config,
                retry_policy=retry_policy,
                allowed_fails_policy=allowed_fails_policy,
                timeout=self.timeout,
            )
            log.debug("Litellm Load balancer was initialized")
        except Exception:
            raise ValueError("Error initializing load balancer") from None

    def load_balance(self, messages, stream):
        """load balance the messages"""
        params = self.load_balancer_config[0].get("litellm_params", {})
        model = params["model"]
        try:
            response = self.router.completion(
                model=model,
                messages=messages,
                stream=stream,
                **({"stream_options": {"include_usage": True}} if stream else {}),
            )
        except litellm.BadRequestError as e:
            # Handle context window exceeded error
            if "ContextWindowExceededError" in str(e):
                log.exception("Context window exceeded error")
                return self.context_exceeded_response(model)
            log.exception("Bad request error.")
            raise ValueError("Error LiteLLM bad request") from None
        except Exception:
            log.exception("LiteLLM API connection error.")
            raise ValueError("Error LiteLLM API connection") from None

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

    def flush_metrics(self):
        with self._lock_stats:
            self.stats = {
                Metrics.LITELLM_STATS_PROMPT_TOKENS: [],
                Metrics.LITELLM_STATS_RESPONSE_TOKENS: [],
                Metrics.LITELLM_STATS_TOTAL_TOKENS: [],
                Metrics.LITELLM_STATS_RESPONSE_TIME: [],
                Metrics.LITELLM_STATS_COST: [],
            }

    def get_metrics(self):
        return self.stats

    def validate_model_config(self, config):
        """Validate the model config and throw a descriptive error if it's invalid."""
        for model_entry in config:  # 'config' is the list from load_balancer
            params = model_entry.get("litellm_params", {})
            model_identifier = params.get("model")
            model_alias = model_entry.get("model_name")

            if not model_identifier:
                raise ValueError(
                    f"Missing 'model' in 'litellm_params' for model alias '{model_alias}'."
                )

            if model_identifier.startswith("bedrock/"):
                # Bedrock-specific validation
                log.info(
                    "Ensure AWS profile is set up correctly or AWS credentials, including aws_access_key_id, aws_secret_access_key, and aws_region_name are provided."
                )
            else:
                # Validation for other providers (e.g., OpenAI, Anthropic direct)
                if not params.get("api_key"):
                    raise ValueError(
                        f"Missing 'api_key' in 'litellm_params' for non-Bedrock model '{model_identifier}' (alias '{model_alias}')."
                    )

    def context_exceeded_response(self, model):
        """Create a response for when context is too large for any model"""
        response_message = {
            "role": "assistant",
            "content": (
                f"Your request exceeds the maximum context length for {model}.\n\n"
                f"The input is too long for the model to process. Please consider:\n"
                f"1. Reducing the length of your input\n"
                f"2. Splitting your request into smaller chunks\n"
                f"3. Summarizing or extracting only the most relevant parts of your content\n\n"
                f"Technical details: Input is too long for requested model."
            ),
        }
        # Create a ModelResponse object with the error message
        return ModelResponse(
            id=f"context-exceeded-{int(time.time())}",
            choices=[
                {
                    "message": response_message,
                    "finish_reason": "context_window_exceeded",
                    "index": 0,
                }
            ],
            model=model,
        )
