"""Base class for Web Search"""

from ...component_base import ComponentBase

info_base = {
    "class_name": "WebSearchBase",
    "description": "Base class for performing a query on web search engines.",
    "config_parameters": [
        {
            "name": "engine",
            "required": True,
            "description": "The type of search engine.",
            "default": "DuckDuckGo",
        },
        {
            "name": "detail",
            "required": False,
            "description": "Return the detail.",
            "default": False,
        },
    ],
    "input_schema": {
        "type": "string",
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class WebSearchBase(ComponentBase):

    def __init__(self, info_base, **kwargs):
        super().__init__(info_base, **kwargs)
        self.detail = self.get_config("detail")

    def invoke(self, message, data):
        pass

    # Extract required data from a message
    def parse(self, message):
        pass
