import os
try:
    from apify_client import ApifyClientAsync  # type: ignore
except Exception:  # pragma: no cover - allow discovery without the dependency installed
    ApifyClientAsync = None  # type: ignore[assignment]
from .base import Scraper, ScrapeResult
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()

logging.getLogger("apify_client").setLevel(logging.WARNING)

class ApifyAPIScraper(Scraper):
    """
    Scraper implementation for Apify API using the apify/web-scraper actor and the official Apify Python client.
    """
    def __init__(self):
        self.api_token = os.getenv("APIFY_API_TOKEN")
        if ApifyClientAsync is None:
            # Keep import-time lightweight so discovery works; fail when actually used
            raise RuntimeError("apify-client is not installed. Please `pip install apify-client`. ")
        if not self.api_token:
            raise RuntimeError("APIFY_API_TOKEN environment variable not set.")
        self.client = ApifyClientAsync(self.api_token)
        self.actor_id = "apify/web-scraper"

    async def scrape(self, url: str, run_id: str) -> ScrapeResult:
        error = None
        html = ""
        content_size = 0
        status_code = 500
        try:
            # Start the actor and wait for it to finish
            actor_client = self.client.actor(self.actor_id)
            run_result = await actor_client.call(
                run_input={
                    "startUrls": [{"url": url}],
                    "maxRequestsPerCrawl": 1,
                    "pseudoUrls": [],
                    "linkSelector": "",
                    "proxyConfiguration": {"useApifyProxy": True},
                    "crawlerType": "chrome",
                    "pageFunction": """
                      async function(context) {
                          const $ = context.jQuery;
                          return {
                              html: $('body').html(),
                              status_code: context.response ? context.response.status : null
                          };
                      }
                    """
                },
                timeout_secs=120  # Wait up to 2 minutes
            )
            if run_result is None:
                error = "Actor run failed."
            else:
                dataset_id = run_result["defaultDatasetId"]
                dataset_client = self.client.dataset(dataset_id)
                items = (await dataset_client.list_items()).items
                if items and "html" in items[0]:
                    html = items[0]["html"] or ""
                    status_code = items[0].get("status_code")
                    content_size = len(html.encode("utf-8")) if html else 0
                else:
                    error = "No HTML found in Apify dataset result."
        except Exception as e:
            error = str(e)

        return ScrapeResult(
            run_id=run_id,
            scraper="apify_api",
            url=url,
            status_code=status_code or 500,
            error=error,
            content_size=content_size,
            format="html",
            created_at=datetime.now().isoformat(),
            content=html,
        )
