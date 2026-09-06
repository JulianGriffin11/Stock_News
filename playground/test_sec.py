"""Fetch SEC EDGAR filings for the spike tickers.

Needs SEC_USER_AGENT in .env (name + email).

Run from the repo root:

    uv run python playground/test_sec.py
"""

from app.config.settings import SpikeSettings
from app.scrapers.sec import SecScraper


def run() -> None:
    settings = SpikeSettings()
    scraper = SecScraper(settings)
    items = scraper.fetch()
    settings.print_items("SEC", items)
    path = settings.write_json("sec.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
