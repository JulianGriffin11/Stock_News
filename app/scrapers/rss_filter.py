"""Keep company-specific Yahoo headlines; drop off-ticker and price-action junk."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from app.scrapers.schemas import RawItem

# Titles that are short-term price / sentiment even when the company is named.
_PRICE_ACTION = re.compile(
    r"("
    r"why\s+.+?\s+stock\s+(?:just\s+)?"
    r"(?:crashed|jumped|plunged|soared|fell|rose)"
    r"|stocks?\s+to\s+(?:buy|watch|sell)"
    r"|shares?\s+(?:soar|soared|plunge|plunged|rally|rallied|"
    r"tumble|tumbled|slip|slipped|jump|jumped|crash|crashed)"
    r"|stock\s+(?:just\s+)?"
    r"(?:rises?|rose|falls?|fell|jumps?|jumped|plunges?|plunged|"
    r"soars?|soared|crashes?|crashed|slips?|slipped)"
    r"|(?:i['’]?m\s+)?buy(?:ing)?\b.+\bdip\b"
    r"|headed\s+for\s+a\s+big\s+move"
    r")",
    re.IGNORECASE,
)


def _mentions_company(text: str, ticker: str, company_name: str) -> bool:
    blob = text.lower()
    if ticker and re.search(rf"\b{re.escape(ticker.lower())}\b", blob):
        return True
    name = company_name.strip()
    if name and re.search(rf"\b{re.escape(name.lower())}\b", blob):
        return True
    return False


def keep_rss_headline(
    title: str,
    snippet: str,
    ticker: str,
    company_name: str,
) -> bool:
    """True when the item is about this ticker and is not price-action chatter."""
    haystack = f"{title}\n{snippet}"
    if not _mentions_company(haystack, ticker, company_name):
        return False
    if _PRICE_ACTION.search(title):
        return False
    return True


def filter_rss_items(
    items: Sequence[RawItem],
    names: Mapping[str, str],
) -> tuple[list[RawItem], int]:
    """Return (kept items, dropped count). Non-RSS rows are always kept."""
    kept: list[RawItem] = []
    dropped = 0
    for item in items:
        if item["source"] != "rss":
            kept.append(item)
            continue
        ticker = item["ticker"]
        if keep_rss_headline(
            item["title"],
            item["raw_text"],
            ticker,
            names.get(ticker, ""),
        ):
            kept.append(item)
        else:
            dropped += 1
    return kept, dropped
