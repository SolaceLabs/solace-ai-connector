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

class WebSearchGoogle(WebSearchBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.init()
        
    def init(self):
        self.api_key = self.get_config("api_key")
        self.search_engine_id = self.get_config("search_engine_id")
        self.url = "https://www.googleapis.com/customsearch/v1"

    def invoke(self, message, data):
        query = data["text"]
        params = {
            "q": query,                       # User query
            "key": self.api_key,              # Google API Key
            "cx": self.search_engine_id,      # Google custom search engine id
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
            data = []
                
            # Process the search results to create a summary
            for item in message.get('items', []):
                data.append({
                    "Title": item['title'],
                    "Snippet": item['snippet'],
                    "URL": item['link']
                })
            return data