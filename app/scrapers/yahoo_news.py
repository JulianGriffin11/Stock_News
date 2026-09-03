"""Yahoo Finance news scraper."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from html import unescape
from re import sub

import feedparser
import httpx

from app.config.settings import SpikeSettings

YAHOO_FEED = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
)
USER_AGENT = "StockNewsDigest/0.1 (personal weekly digest)"


class YahooNewsScraper:
    def __init__(self, settings: SpikeSettings | None = None) -> None:
        self.settings = settings or SpikeSettings()

    def fetch(self) -> list[dict]:
        items: list[dict] = []
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(
            headers=headers, timeout=30.0, follow_redirects=True
        ) as client:
            for ticker in self.settings.tickers:
                items.extend(self._fetch_feed(client, ticker))
        items.sort(key=lambda row: row.get("published") or "", reverse=True)
        return items

    def _yahoo_url(self, ticker: str) -> str:
        return YAHOO_FEED.format(ticker=ticker)

    def _fetch_feed(self, client: httpx.Client, ticker: str) -> list[dict]:
        url = self._yahoo_url(ticker)
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as error:
            print(f"yahoo {ticker}: {error}")
            return []

        feed = feedparser.parse(response.content)
        items = []
        for entry in feed.entries:
            published = self._published_at(entry)
            if published is None or published < self.settings.window_start():
                continue
            items.append(
                {
                    "source": "yahoo",
                    "ticker": ticker,
                    "title": self._clean_text(entry.get("title") or ""),
                    "link": entry.get("link") or "",
                    "published": published.isoformat(),
                    "summary": self._clean_text(entry.get("summary") or "")[:500],
                }
            )
        time.sleep(0.4)
        return items

    def _published_at(self, entry: feedparser.FeedParserDict) -> datetime | None:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not parsed:
            return None
        return datetime(*parsed[:6], tzinfo=UTC)

    def _clean_text(self, text: str) -> str:
        text = sub(r"<[^>]+>", " ", text)
        return unescape(" ".join(text.split()))
