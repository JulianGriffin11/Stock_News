"""Fetch RSS + SEC items, normalize, dedupe, and upsert to Postgres."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.db.queries import existing_external_ids, upsert_raw_items
from app.scrapers import RawItem, fetch_sec, fetch_yahoo
from app.scrapers.rss_filter import filter_rss_items


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
    known = existing_external_ids(nonempty_text=True)

    def _yahoo() -> tuple[list[RawItem], int]:
        raw = fetch_yahoo(settings.tickers, cutoff)
        return filter_rss_items(raw, settings.ticker_names)

    def _sec() -> list[RawItem]:
        return fetch_sec(
            settings.tickers,
            cutoff,
            user_agent=settings.sec_user_agent,
            cache_dir=settings.data_dir,
            skip_ids=known,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        yahoo_future = pool.submit(_yahoo)
        sec_future = pool.submit(_sec)
        news, rss_dropped = yahoo_future.result()
        filings = sec_future.result()

    rss_kept = len(news)
    merged = news + filings
    items = dedupe(merged)
    items.sort(key=lambda row: row["published_at"], reverse=True)

    inserted, updated = upsert_raw_items(items)

    source_counts = Counter(item["source"] for item in items)
    source_parts = " ".join(
        f"{source}={count}" for source, count in sorted(source_counts.items())
    )
    log.debug(
        "done items=%d %s inserted=%d updated=%d rss_kept=%d rss_dropped=%d",
        len(items),
        source_parts or "sources=none",
        inserted,
        updated,
        rss_kept,
        rss_dropped,
    )
    ticker_counts = Counter(item["ticker"] for item in items)
    if ticker_counts:
        ticker_parts = " ".join(
            f"{ticker}={count}"
            for ticker, count in sorted(ticker_counts.items())
        )
        log.debug("by_ticker %s", ticker_parts)
    return items
