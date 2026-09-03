"""SEC EDGAR filings scraper for 8-K, 10-Q, 10-K, and Form 4."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from app.config.models import RawItem

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
KEEP_FORMS = {"8-K", "10-Q", "10-K", "4"}


class SecFilingsScraper:
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
            ticker_map = self._ticker_map(client)
            for ticker in self.tickers:
                items.extend(self._filings_for(client, ticker, ticker_map, cutoff))
                time.sleep(0.2)
        items.sort(key=lambda row: row["published_at"], reverse=True)
        return items

    def _ticker_map(self, client: httpx.Client) -> dict[str, dict]:
        cache_path = self.cache_dir / "company_tickers.json"
        if cache_path.exists():
            raw = json.loads(cache_path.read_text())
        else:
            response = client.get(COMPANY_TICKERS_URL)
            response.raise_for_status()
            raw = response.json()
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw))
            time.sleep(0.2)

        mapping: dict[str, dict] = {}
        for row in raw.values():
            mapping[str(row["ticker"]).upper()] = {
                "cik": int(row["cik_str"]),
                "title": row["title"],
            }
        return mapping

    def _filings_for(
        self,
        client: httpx.Client,
        ticker: str,
        ticker_map: dict[str, dict],
        cutoff: date,
    ) -> list[RawItem]:
        info = ticker_map.get(ticker)
        if not info:
            print(f"{ticker}: no CIK found")
            return []

        cik10 = f"{info['cik']:010d}"
        response = client.get(SUBMISSIONS_URL.format(cik10=cik10))
        response.raise_for_status()
        payload = response.json()
        recent = payload.get("filings", {}).get("recent", {})
        company = payload.get("name") or info["title"]

        items: list[RawItem] = []
        rows = zip(
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            strict=False,
        )
        for form, filing_date, accession, primary in rows:
            if form.split("/")[0] not in KEEP_FORMS:
                continue
            try:
                parsed = date.fromisoformat(filing_date)
            except ValueError:
                continue
            if parsed < cutoff:
                continue
            published_at = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
            items.append(
                {
                    "source": "sec",
                    "ticker": ticker,
                    "title": f"{ticker} {form} — {company}",
                    "url": self._document_url(info["cik"], accession, primary),
                    "published_at": published_at.isoformat(),
                    "raw_text": f"{company} filed Form {form} on {filing_date}.",
                    "external_id": accession,
                }
            )
        return items

    def _document_url(self, cik: int, accession: str, primary: str) -> str:
        accession_id = accession.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_id}/{primary}"
        )
