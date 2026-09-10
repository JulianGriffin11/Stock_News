"""
Run this file to exercise the news scraper alone:

    uv run python playground/test_yahoo.py
"""

from app.config.settings import Settings
from app.scrapers import fetch_yahoo
from print_items import print_items


def run() -> None:
    settings = Settings()
    items = fetch_yahoo(settings.tickers, settings.window_start())
    print_items("Yahoo RSS", items, settings.tickers, settings.window_days)
    path = settings.write_json("yahoo_news.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
