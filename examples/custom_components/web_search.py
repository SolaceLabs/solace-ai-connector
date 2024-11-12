# A component to search the web using APIs.
import sys
import requests

sys.path.append("src")

from solace_ai_connector.components.component_base import ComponentBase


info = {
    "class_name": "WebSearchCustomComponent",
    "description": "Search web using APIs.",
    "config_parameters": [
        {
            "name": "engine",
            "description": "The search engine.",
            "type": "string",
        },
        {
            "name": "output_format",
            "description": "Output format in json or html.",
            "type": "string",
            "default": "json"
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


class WebSearchCustomComponent(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.engine = self.get_config("engine")
        self.format = self.get_config("format")

    def invoke(self, message, data):
        query = data["text"]
        print(query)
        url = None
        if self.engine == "DuckDuckGo":
            url = "http://api.duckduckgo.com/"
            params = {
                "q": query,            # User query
                "format": self.format, # Response format (json by default)
                "pretty": 1,           # Beautify the output
                "no_html": 3,          # Remove HTML from the response
                "skip_disambig": 1     # Skip disambiguation
            }
        
        if url != None:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                if params["format"] == 'json':
                    print(response)
                    return response.json()  # Return JSON response if the format is JSON
                else:
                    return response  # Return raw response if not JSON format
            else:
                # Handle errors if the request fails
                return f"Error: {response.status_code}"
