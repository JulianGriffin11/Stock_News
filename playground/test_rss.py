"""Fetch Yahoo Finance RSS for the spike tickers.

Run from the repo root:

    uv run python playground/test_rss.py
"""

from app.config.settings import SpikeSettings
from app.scrapers.rss import RssScraper


def run() -> None:
    settings = SpikeSettings()
    scraper = RssScraper(settings)
    items = scraper.fetch()
    settings.print_items("RSS", items)
    path = settings.write_json("rss.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
