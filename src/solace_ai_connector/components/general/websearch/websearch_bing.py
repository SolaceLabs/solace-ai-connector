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
            "description": "Number of search results to return.",
            "default": 10
        },
        {
            "name": "safesearch",
            "required": False,
            "description": "Safe search setting: Off, Moderate, or Strict.",
            "default": "Moderate"
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

class WebSearchBing(WebSearchBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()
        
    def init(self):
        self.api_key = self.get_config("api_key")
        self.count = self.get_config("count")
        self.safesearch = self.get_config("safesearch")
        self.url = "https://api.bing.microsoft.com/v7.0/search"

    def invoke(self, message, data):
        query = data["text"]
        params = {
            "q": query,                       # User query
            "count": self.count,              # Number of results to return
            "safesearch": self.safesearch     # Safe search filter
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key  # Bing API Key
        }

        response = requests.get(self.url, headers=headers, params=params)
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
            data = []
                
            # Process the search results to create a summary
            for web_page in message.get("webPages", {}).get("value", []):
                data.append({
                    "Title": web_page['name'],
                    "Snippet": web_page['snippet'],
                    "URL": web_page['url']
                })
            return data
