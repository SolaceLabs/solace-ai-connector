"""Scrape a website and related subpages"""
from bs4 import BeautifulSoup
from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
from ...component_base import ComponentBase

info = {
    "class_name": "WebScraper",
    "description": "Scrape a website and related subpages.",
    "config_parameters": [
        {
            "name": "max_depth",
            "required": False,
            "description": "Maximum depth for scraping subpages.",
            "default": 1
        },
        {
            "name": "use_async",
            "required": False,
            "description": "Use asynchronous scraping.",
            "default": False
        },
        {
            "name": "extractor",
            "required": False,
            "description": "Custom extractor function for processing page content.",
            "default": "custom_extractor"
        },
        {
            "name": "metadata_extractor",
            "required": False,
            "description": "Function to extract metadata from pages.",
        },
        {
            "name": "exclude_dirs",
            "required": False,
            "description": "Directories to exclude from scraping.",
        },
        {
            "name": "timeout",
            "required": False,
            "description": "Maximum time to wait for a response in seconds.",
            "default": 10
        },
        {
            "name": "check_response_status",
            "required": False,
            "description": "Whether to check HTTP response status.",
            "default": False
        },
        {
            "name": "continue_on_failure",
            "required": False,
            "description": "Continue scraping even if some pages fail.",
            "default": True
        },
        {
            "name": "prevent_outside",
            "required": False,
            "description": "Prevent scraping outside the base URL.",
            "default": True
        },
        {
            "name": "base_url",
            "required": False,
            "description": "Base URL to begin scraping from.",
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {}
    },
    "output_schema": {
        "type": "object",
        "properties": {}
    }
}

class WebScraper(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.max_depth = self.get_config("max_depth")
        self.use_async = self.get_config("use_async")
        self.extractor = self.get_config("extractor")
        self.metadata_extractor = self.get_config("metadata_extractor")
        self.exclude_dirs = self.get_config("exclude_dirs")
        self.timeout = self.get_config("timeout")
        self.check_response_status = self.get_config("check_response_status")
        self.continue_on_failure = self.get_config("continue_on_failure")
        self.prevent_outside = self.get_config("prevent_outside")
        self.base_url = self.get_config("base_url")

    def invoke(self, message, data):
        url = data["text"]
        content = self.scrape(url)
        return content
    
    # Define a custom extractor function to extract text from HTML using BeautifulSoup
    def custom_extractor(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        return soup.get_text()

    # Scrape a website
    def scrape(self, url):
        loader = RecursiveUrlLoader(
            url=url,
            extractor=self.extractor,
            max_depth=self.max_depth,
            use_async=self.use_async,
            metadata_extractor=self.metadata_extractor,
            exclude_dirs=self.exclude_dirs,
            timeout=self.timeout,
            check_response_status=self.check_response_status,
            continue_on_failure=self.continue_on_failure,
            prevent_outside=self.prevent_outside,
            base_url=self.base_url
        )

        docs = loader.load()

        for doc in docs:
            title = doc.metadata.get("title")
            source = doc.metadata.get("source")
            content = doc.page_content

            # Ensure that the title, source, and content are string type
            resp = {}
            if isinstance(title, str) and isinstance(source, str) and isinstance(content, str):
                resp = {
                    "title": title,
                    "source": source,
                    "content": content
                }
            else:
                resp = {
                    "title": "",
                    "source": "",
                    "content": ""
                }
            return resp


