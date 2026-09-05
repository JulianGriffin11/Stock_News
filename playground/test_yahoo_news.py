"""Fetch Yahoo Finance RSS for the profile tickers.

Prefer the ingest CLI for the combined dump:

    uv run python -m digest ingest

Run this file to exercise the news scraper alone:

    uv run python playground/test_yahoo_news.py
"""

from app.config.settings import Settings
from app.ingest import print_items
from app.scrapers.yahoo_scraper import YahooNewsScraper


def run() -> None:
    settings = Settings()
    items = YahooNewsScraper(settings.tickers, settings.window_start()).fetch()
    print_items("Yahoo RSS", items, settings.tickers, settings.window_days)
    path = settings.write_json("yahoo_news.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
