"""Fetch SEC EDGAR filings for the profile tickers.

Needs SEC_USER_AGENT in .env (name + email).

Prefer the ingest CLI for the combined dump:

    uv run python -m digest ingest

Run this file to exercise the filings scraper alone:

    uv run python playground/test_sec_filings.py
"""

from app.config.settings import Settings
from app.ingest import print_items
from app.scrapers.sec_scraper import SecFilingsScraper


def run() -> None:
    settings = Settings()
    items = SecFilingsScraper(
        settings.tickers,
        settings.window_start(),
        user_agent=settings.sec_user_agent,
        cache_dir=settings.data_dir,
    ).fetch()
    print_items("SEC", items, settings.tickers, settings.window_days)
    path = settings.write_json("sec_filings.json", items)
    print(f"Wrote {len(items)} items to {path}")


if __name__ == "__main__":
    run()
