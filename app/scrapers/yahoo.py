"""Yahoo only: pull RSS headlines for each watchlist ticker."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from html import unescape
from re import sub

import feedparser
import httpx

from app.scrapers.schemas import RawItem

YAHOO_FEED = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
)
USER_AGENT = "StockNewsDigest/0.1 (personal weekly digest)"

log = logging.getLogger("digest.scrapers.yahoo")


def fetch_yahoo(tickers: Sequence[str], window_start: datetime) -> list[RawItem]:
    items: list[RawItem] = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for ticker in tickers:
            items.extend(_fetch_feed(client, ticker.upper(), window_start))
    items.sort(key=lambda row: row["published_at"], reverse=True)
    return items


def _fetch_feed(
    client: httpx.Client, ticker: str, window_start: datetime
) -> list[RawItem]:
    url = YAHOO_FEED.format(ticker=ticker)
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as error:
        log.warning("ticker=%s fetch failed: %s", ticker, error)
        return []

    feed = feedparser.parse(response.content)
    items: list[RawItem] = []
    for entry in feed.entries:
        published = _published_at(entry)
        if published is None or published < window_start:
            continue
        link = str(entry.get("link") or "")
        if not link:
            continue
        items.append(
            {
                "source": "rss",
                "ticker": ticker,
                "title": _clean_text(entry.get("title") or ""),
                "url": link,
                "published_at": published.isoformat(),
                "raw_text": _clean_text(entry.get("summary") or "")[:500],
                "external_id": link,
            }
        )
    time.sleep(0.4)
    return items


def _published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def _clean_text(text: str) -> str:
    text = sub(r"<[^>]+>", " ", text)
    return unescape(" ".join(text.split()))
