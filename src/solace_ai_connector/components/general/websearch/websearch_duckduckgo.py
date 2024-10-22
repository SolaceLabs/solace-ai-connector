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
            "default": 1
        },
        {
            "name": "no_html",
            "required": False,
            "description": "The number of output pages.",
            "default": 1
        },
        {
            "name": "skip_disambig",
            "required": False,
            "description": "Skip disambiguation.",
            "default": 1
        },
        {
            "name": "detail",
            "required": False,
            "description": "Return the detail.",
            "default": False
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}

class WebSearchDuckDuckGo(WebSearchBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()
        
    def init(self):
        self.pretty = self.get_config("pretty", 1)
        self.no_html = self.get_config("no_html", 1)
        self.skip_disambig = self.get_config("skip_disambig", 1)
        self.url = "http://api.duckduckgo.com/"

    def invoke(self, message, data):
        query = data["text"]
        params = {
            "q": query,                         # User query
            "format": "json",                   # Response format (json by default)
            "pretty": self.pretty,              # Beautify the output
            "no_html": self.no_html,            # Remove HTML from the response
            "skip_disambig": self.skip_disambig # Skip disambiguation
        }

        response = requests.get(self.url, params=params)
        if response.status_code == 200:
            response = response.json()
            response = self.parse(response)
            return response
        else:
            return f"Error: {response.status_code}"
        
    # Extract required data from a message
    def parse(self, message):
        if self.detail:
            return message
        else:
            return {
                    "Title": message['AbstractSource'],
                    "Snippet": message['Abstract'],
                    "URL": message['AbstractURL']
                }