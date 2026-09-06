"""Fetch RSS + SEC items, normalize, dedupe, and write data/raw_items.json."""

from __future__ import annotations

from collections import Counter

from app.config.models import RawItem
from app.config.settings import Settings
from app.database.raw_items import upsert_raw_items
from app.scrapers.sec_scraper import SecFilingsScraper
from app.scrapers.yahoo_scraper import YahooNewsScraper


def dedupe(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    unique: list[RawItem] = []
    for item in items:
        key = item["external_id"]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def print_items(
    heading: str,
    items: list[RawItem],
    tickers: list[str],
    window_days: int,
    limit: int | None = 40,
) -> None:
    names = ", ".join(tickers)
    print(f"{heading} — {names} — last {window_days} days")
    print("-" * 60)
    if not items:
        print("(no items)")
        return

    shown = items if limit is None else items[:limit]
    for item in shown:
        print(
            f"[{item['source']}] {item['ticker']}  "
            f"{item['published_at']}  {item['title']}"
        )
        if item["source"] == "sec":
            print(f"          accession {item['external_id']}")
        if item["url"]:
            print(f"          {item['url']}")
        print()

    leftover = len(items) - len(shown)
    if leftover > 0:
        print(f"... {leftover} more in the JSON dump")


def run_ingest(
    settings: Settings | None = None,
    *,
    quiet: bool = False,
) -> list[RawItem]:
    settings = settings or Settings()
    cutoff = settings.window_start()

    news = YahooNewsScraper(settings.tickers, cutoff).fetch()
    filings = SecFilingsScraper(
        settings.tickers,
        cutoff,
        user_agent=settings.sec_user_agent,
        cache_dir=settings.data_dir,
    ).fetch()

    merged = news + filings
    items = dedupe(merged)
    items.sort(key=lambda row: row["published_at"], reverse=True)

    settings.write_json("raw_items.json", items)
    inserted, updated = upsert_raw_items(items, settings)
    if not quiet:
        counts = Counter(item["source"] for item in items)
        parts = [f"{count} {source}" for source, count in sorted(counts.items())]
        print(f"Ingest: {len(items)} items ({'; '.join(parts) or 'none'})")
        print(f"Postgres: {inserted} inserted, {updated} updated")
    return items
