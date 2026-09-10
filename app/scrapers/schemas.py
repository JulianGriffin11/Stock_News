"""Shared scrape output shape."""

from __future__ import annotations

from typing import Literal, TypedDict

Source = Literal["rss", "sec"]


class RawItem(TypedDict):
    source: Source
    ticker: str
    title: str
    url: str
    published_at: str
    raw_text: str
    external_id: str
