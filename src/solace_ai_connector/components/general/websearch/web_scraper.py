"""Scrape a website"""
from playwright.sync_api import sync_playwright
from ...component_base import ComponentBase

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
        with sync_playwright() as p:
            # Launch a browser instance (Chromium, Firefox, or WebKit)
            browser = p.chromium.launch(headless=True)  # Set headless=False to see the browser in action
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


