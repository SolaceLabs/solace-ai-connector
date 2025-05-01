"""Scrape a website"""

from ...component_base import ComponentBase
from ....common.log import log

info = {
    "class_name": "WebScraper",
    "description": "Scrape javascript based websites.",
    "config_parameters": [
        {
            "name": "timeout",
            "required": False,
            "description": "The timeout for the browser in milliseconds.",
            "default": 30000,
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the website to scrape.",
            }
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "The title of the website."},
            "content": {"type": "string", "description": "The content of the website."},
        },
    },
}


class WebScraper(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.timeout = self.get_config("timeout", 30000)

    def invoke(self, message, data):
        url = data["url"]
        if type(url) != str or not url:
            raise ValueError("No URL provided") from None
        content = self.scrape(url)
        return content

    # Scrape a website
    def scrape(self, url):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            err_msg = "Please install playwright by running 'pip install playwright' and 'playwright install'."
            log.error(err_msg)
            raise ValueError(err_msg) from None

        with sync_playwright() as p:
            try:
                # Launch a Chromium browser instance
                browser = p.chromium.launch(
                    headless=True,
                    timeout=self.timeout,
                )  # Set headless=False to see the browser in action
            except ImportError:
                err_msg = "Failed to launch the Chromium instance. Please install the browser binaries by running 'playwright install'"
                log.error(err_msg)
                raise ValueError(err_msg) from None

            resp = {}
            try:
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
                log.debug("Scraping the website")
                page = context.new_page()
                page.goto(url)

                # Wait for the page to fully load
                page.wait_for_load_state("load", timeout=self.timeout)

                # Scroll to the bottom of the page to load more content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                # Scrape the text content of the page
                title = page.title()
                content = page.evaluate("document.body.innerText")
                resp = {"title": title, "content": content}
                log.debug("Scraped the website.")
                browser.close()
                return resp
            except Exception:
                log.error("Failed to scrape the website.")
                browser.close()
                return {
                    "title": "",
                    "content": "",
                    "error": "Failed to scrape the website.",
                }
