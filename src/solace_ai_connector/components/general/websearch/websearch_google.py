# This is a Google search engine.
# The configuration will configure the Google engine.
import requests

from .websearch_base import (
    WebSearchBase,
)

info = {
    "class_name": "WebSearchGoogle",
    "description": "Perform a search query on Google.",
    "config_parameters": [
        {
            "name": "api_key",
            "required": True,
            "description": "Google API Key.",
        },
        {
            "name": "search_engine_id",
            "required": False,
            "description": "The custom search engine id.",
            "default": 1,
        },
        {
            "name": "count",
            "required": False,
            "description": "Max Number of search results to return.",
            "default": 10,
        },
        {
            "name": "detail",
            "required": False,
            "description": "Return the detail.",
            "default": False,
        },
    ],
    "input_schema": {"type": "string"},
    "output_schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "snippet": {"type": "string"},
                "url": {"type": "string"},
            },
        },
    },
}


class WebSearchGoogle(WebSearchBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()

    def init(self):
        self.api_key = self.get_config("api_key")
        self.search_engine_id = self.get_config("search_engine_id")
        self.count = self.get_config("count", 10)
        self.url = "https://www.googleapis.com/customsearch/v1"

    def invoke(self, message, data):
        if type(data) != str or not data:
            raise ValueError("Invalid search query") from None
        params = {
            "q": data,  # User query
            "key": self.api_key,  # Google API Key
            "cx": self.search_engine_id,  # Google custom search engine id
        }

        response = requests.get(self.url, params=params)
        if response.status_code == 200:
            response = response.json()
            response = self.parse(response)
            return response
        else:
            error = response.json().get("error", {}).get("message", "Unknown error")
            raise ValueError(f"Error: {response.status_code}") from None

    # Extract required data from a message
    def parse(self, message):
        if self.detail:
            return message
        else:
            data = []

            # Process the search results to create a summary
            for item in message.get("items", []):
                data.append(
                    {
                        "title": item["title"],
                        "snippet": item["snippet"],
                        "url": item["link"],
                    }
                )
            return data[: self.count]
