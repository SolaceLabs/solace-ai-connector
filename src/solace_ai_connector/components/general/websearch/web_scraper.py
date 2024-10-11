"""Scrape a website"""
from ...component_base import ComponentBase
from ....common.log import log

info = {
    "class_name": "WebScraper",
    "description": "Scrape javascript based websites.",
    "config_parameters": [
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

    def invoke(self, message, data):
        url = data["text"]
        content = self.scrape(url)
        return content

    # Scrape a website
    def scrape(self, url):
        err_msg = "Please install playwright by running 'pip install playwright' and 'playwright install'."
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
                log.error(
                    err_msg
                )
                raise ValueError(
                    err_msg
                )
    
        with sync_playwright() as p:
            err_msg = "Failed to launch the Chromium instance. Please install the browser binaries by running 'playwright install'"
            try:
                # Launch a Chromium browser instance
                browser = p.chromium.launch(headless=True)  # Set headless=False to see the browser in action
            except ImportError:
                log.error(
                    err_msg
                )
                raise ValueError(
                    err_msg
                )
            page = browser.new_page()
            page.goto(url)

            # Wait for the page to fully load
            page.wait_for_load_state("networkidle")

            # Scrape the text content of the page
            title = page.title()
            content = page.evaluate("document.body.innerText")
            resp = {
                "title": title,
                "content": content
            }
            browser.close()

            return resp


