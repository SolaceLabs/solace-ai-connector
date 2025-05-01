# This is a DuckDuckGo search engine.
# The configuration will configure the DuckDuckGo engine.
import requests

from .websearch_base import (
    WebSearchBase,
)

info = {
    "class_name": "WebSearchDuckDuckGo",
    "description": "Perform a search query on DuckDuckGo.",
    "config_parameters": [
        {
            "name": "pretty",
            "required": False,
            "description": "Beautify the search output.",
            "default": 1,
        },
        {
            "name": "no_html",
            "required": False,
            "description": "The number of output pages.",
            "default": 1,
        },
        {
            "name": "count",
            "required": False,
            "description": "Max Number of search results to return.",
            "default": 10,
        },
        {
            "name": "skip_disambig",
            "required": False,
            "description": "Skip disambiguation.",
            "default": 1,
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


class WebSearchDuckDuckGo(WebSearchBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()

    def init(self):
        self.pretty = self.get_config("pretty", 1)
        self.no_html = self.get_config("no_html", 1)
        self.count = self.get_config("count", 10)
        self.skip_disambig = self.get_config("skip_disambig", 1)
        self.url = "http://api.duckduckgo.com/"

    def invoke(self, message, data):
        if type(data) != str or not data:
            raise ValueError("Invalid search query") from None
        params = {
            "q": data,  # User query
            "format": "json",  # Response format (json by default)
            "pretty": self.pretty,  # Beautify the output
            "no_html": self.no_html,  # Remove HTML from the response
            "skip_disambig": self.skip_disambig,  # Skip disambiguation
        }

        response = requests.get(self.url, params=params)
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
            if (
                message.get("AbstractSource")
                and message.get("Abstract")
                and message.get("AbstractURL")
            ):
                data.append(
                    {
                        "title": message["AbstractSource"],
                        "snippet": message["Abstract"],
                        "url": message["AbstractURL"],
                    }
                )
            for message in message["RelatedTopics"]:
                if "FirstURL" in message and "Text" in message and "Result" in message:
                    data.append(
                        {
                            "url": message["FirstURL"],
                            "title": message["Text"],
                            "snippet": message["Result"],
                        }
                    )
        return data[: self.count]
