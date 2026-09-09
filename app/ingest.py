"""Fetch RSS + SEC items, normalize, dedupe, and write data/raw_items.json."""

from __future__ import annotations

from collections import Counter

from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.models import RawItem
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


def run_ingest(ctx: PipelineContext | None = None) -> list[RawItem]:
    ctx = ctx or make_context()
    log = step_logger("ingest", ctx)
    settings = ctx.settings
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

    source_counts = Counter(item["source"] for item in items)
    source_parts = " ".join(
        f"{source}={count}" for source, count in sorted(source_counts.items())
    )
    log.debug(
        "done items=%d %s inserted=%d updated=%d",
        len(items),
        source_parts or "sources=none",
        inserted,
        updated,
    )
    ticker_counts = Counter(item["ticker"] for item in items)
    if ticker_counts:
        ticker_parts = " ".join(
            f"{ticker}={count}"
            for ticker, count in sorted(ticker_counts.items())
        )
        log.debug("by_ticker %s", ticker_parts)
    return items
