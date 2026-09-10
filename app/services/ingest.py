"""Fetch RSS + SEC items, normalize, dedupe, and upsert to Postgres."""

from __future__ import annotations

from collections import Counter

from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.db.queries import upsert_raw_items
from app.scrapers import RawItem, fetch_sec, fetch_yahoo


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


def run_ingest(ctx: PipelineContext | None = None) -> list[RawItem]:
    ctx = ctx or make_context()
    log = step_logger("ingest", ctx)
    settings = ctx.settings
    cutoff = settings.window_start()

    news = fetch_yahoo(settings.tickers, cutoff)
    filings = fetch_sec(
        settings.tickers,
        cutoff,
        user_agent=settings.sec_user_agent,
        cache_dir=settings.data_dir,
    )

    merged = news + filings
    items = dedupe(merged)
    items.sort(key=lambda row: row["published_at"], reverse=True)

    inserted, updated = upsert_raw_items(items)

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
