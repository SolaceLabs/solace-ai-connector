# This is a Bing search engine.
# The configuration will configure the Bing engine.
import requests

from .websearch_base import (
    WebSearchBase,
)

info = {
    "class_name": "WebSearchBing",
    "description": "Perform a search query on Bing.",
    "config_parameters": [
        {
            "name": "api_key",
            "required": True,
            "description": "Bing API Key.",
        },
        {
            "name": "count",
            "required": False,
            "description": "Max number of search results to return.",
            "default": 10,
        },
        {
            "name": "safesearch",
            "required": False,
            "description": "Safe search setting: Off, Moderate, or Strict.",
            "default": "Moderate",
        },
    ],
    "input_schema": {
        "type": "string",
    },
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


class WebSearchBing(WebSearchBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()

    def init(self):
        self.api_key = self.get_config("api_key")
        self.count = self.get_config("count", 10)
        self.safesearch = self.get_config("safesearch")
        self.url = "https://api.bing.microsoft.com/v7.0/search"

    def invoke(self, message, data):
        if type(data) != str or not data:
            raise ValueError("Invalid search query") from None
        params = {
            "q": data,  # User query
            "count": self.count,  # Number of results to return
            "safesearch": self.safesearch,  # Safe search filter
        }
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}  # Bing API Key

        response = requests.get(self.url, headers=headers, params=params)
        if response.status_code == 200:
            response = response.json()
            response = self.parse(response)
            return response
        else:
            raise ValueError(f"Error: {response.status_code}") from None

    # Extract required data from a message
    def parse(self, message):
        if self.detail:
            return message
        else:
            data = []

            # Process the search results to create a summary
            for web_page in message.get("webPages", {}).get("value", []):
                data.append(
                    {
                        "title": web_page["name"],
                        "snippet": web_page["snippet"],
                        "url": web_page["url"],
                    }
                )
            return data
