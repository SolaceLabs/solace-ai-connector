"""Base class for LiteLLM chat models"""

import litellm

from ....component_base import ComponentBase
from .....common.log import log

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
    ],
}


class LiteLLMBase(ComponentBase):

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.init()
        self.init_load_balancer()

    def init(self):
        litellm.suppress_debug_info = True
        self.load_balancer = self.get_config("load_balancer")
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties"
        )
        self.router = None

    def init_load_balancer(self):
        """initialize a load balancer"""
        try:
            self.router = litellm.Router(model_list=self.load_balancer)
            log.debug("Load balancer initialized with models: %s", self.load_balancer)
        except Exception as e:
            raise ValueError(f"Error initializing load balancer: {e}")

    def load_balance(self, messages, stream):
        """load balance the messages"""
        response = self.router.completion(
            model=self.load_balancer[0]["model_name"], messages=messages, stream=stream
        )
        log.debug("Load balancer response: %s", response)
        return response

    def invoke(self, message, data):
        """invoke the model"""
        pass
