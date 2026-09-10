"""
Run this file to exercise the filings scraper alone:

    uv run python playground/test_sec.py
"""

from app.config.settings import Settings
from app.scrapers import fetch_sec
from print_items import print_items


def run() -> None:
    settings = Settings()
    items = fetch_sec(
        settings.tickers,
        settings.window_start(),
        user_agent=settings.sec_user_agent,
        cache_dir=settings.data_dir,
    )
    print_items("SEC", items, settings.tickers, settings.window_days)
    path = settings.write_json("sec_filings.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
