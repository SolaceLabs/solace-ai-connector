# LangChain Base - Base class for all LangChain components

import importlib

from ....component_base import ComponentBase
from .....common.utils import resolve_config_values


class LangChainBase(ComponentBase):

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.name = self.get_config("component_name")
        self.component_config = self.get_config("component_config")
        self.init()

    def init(self):
        self.lc_module = self.component_config.get("langchain_module", "")
        self.lc_class = self.component_config.get("langchain_class", "")
        self.lc_config = self.component_config.get("langchain_component_config", {})

        resolve_config_values(self.lc_config)

        # Dynamically load the component
        self.component_class = self.load_component(self.lc_module, self.lc_class)

        # Create the component
        self.component = self.create_component(self.lc_config, self.component_class)

    def load_component(self, path, name):
        component_class = None
        try:
            module = importlib.import_module(path)
            component_class = getattr(module, name)
        except Exception:
            raise ImportError("Unable to load component") from None
        return component_class

    def create_component(self, config, cls):
        component = None
        if not config:
            config = {}
        try:
            component = cls(**config)
        except Exception:
            raise ImportError("Unable to create component") from None
        return component

    def invoke(self, message, data):
        raise NotImplementedError("invoke() not implemented") from None

    def __str__(self):
        return self.__class__.__name__ + " " + str(self.config)

    def __repr__(self):
        return self.__str__()
