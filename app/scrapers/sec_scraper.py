"""SEC EDGAR filings scraper for 8-K, 10-Q, and 10-K."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from app.config.models import RawItem
from app.scrapers.sec_toolbox import (
    KEEP_FORMS,
    SUBMISSIONS_URL,
    CikIndex,
    FilingDocuments,
    archive_url,
    form_kind,
    pause,
)

log = logging.getLogger("digest.scrapers.sec")


class SecFilingsScraper:
    """For each ticker, pull recent 8-K / 10-Q / 10-K as RawItems."""

    def __init__(
        self,
        tickers: Sequence[str],
        window_start: datetime,
        user_agent: str,
        cache_dir: Path,
    ) -> None:
        self.tickers = [ticker.upper() for ticker in tickers]
        self.window_start = window_start
        self.user_agent = user_agent.strip()
        self.cache_dir = cache_dir
        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT is missing. Set it in .env as: Your Name you@email.com"
            )

    def fetch(self) -> list[RawItem]:
        cutoff = self.window_start.date()
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        items: list[RawItem] = []
        with httpx.Client(
            headers=headers, timeout=30.0, follow_redirects=True
        ) as client:
            ticker_map = CikIndex(self.cache_dir).load(client)
            documents = FilingDocuments(client)
            for ticker in self.tickers:
                items.extend(
                    self._filings_for(client, ticker, ticker_map, documents, cutoff)
                )
                pause()
        items.sort(key=lambda row: row["published_at"], reverse=True)
        return items

    def _filings_for(
        self,
        client: httpx.Client,
        ticker: str,
        ticker_map: dict[str, dict],
        documents: FilingDocuments,
        cutoff: date,
    ) -> list[RawItem]:
        info = ticker_map.get(ticker)
        if not info:
            log.warning("ticker=%s no CIK found", ticker)
            return []

        cik = info["cik"]
        response = client.get(SUBMISSIONS_URL.format(cik10=f"{cik:010d}"))
        response.raise_for_status()
        payload = response.json()
        company = payload.get("name") or info["title"]
        recent = payload.get("filings", {}).get("recent", {})

        items: list[RawItem] = []
        for row in self._recent_rows(recent):
            form, filing_date, accession, primary, sec_items, description = row
            if not self._in_window(form, filing_date, cutoff):
                continue
            parsed = date.fromisoformat(filing_date)
            url = archive_url(cik, accession, primary)
            items.append(
                {
                    "source": "sec",
                    "ticker": ticker,
                    "title": f"{ticker} {form} — {company}",
                    "url": url,
                    "published_at": datetime(
                        parsed.year, parsed.month, parsed.day, tzinfo=UTC
                    ).isoformat(),
                    "raw_text": documents.raw_text(
                        cik=cik,
                        company=company,
                        form=form,
                        filing_date=filing_date,
                        sec_items=sec_items,
                        description=description,
                        primary_url=url,
                        accession=accession,
                    ),
                    "external_id": accession,
                }
            )
        return items

    def _in_window(self, form: str, filing_date: str, cutoff: date) -> bool:
        if "/A" in form.upper():
            return False
        if form_kind(form) not in KEEP_FORMS:
            return False
        try:
            parsed = date.fromisoformat(filing_date)
        except ValueError:
            return False
        return parsed >= cutoff

    def _recent_rows(
        self, recent: dict
    ) -> Iterator[tuple[str, str, str, str, str, str]]:
        forms = list(recent.get("form") or [])
        n = len(forms)

        def column(key: str) -> list:
            values = list(recent.get(key) or [])
            if len(values) < n:
                values.extend([""] * (n - len(values)))
            return values[:n]

        return zip(
            forms,
            column("filingDate"),
            column("accessionNumber"),
            column("primaryDocument"),
            column("items"),
            column("primaryDocDescription"),
        )
