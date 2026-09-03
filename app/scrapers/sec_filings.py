"""SEC EDGAR filings scraper for 8-K, 10-Q, 10-K, and Form 4."""

from __future__ import annotations

import json
import os
import time
from datetime import date

import httpx
from dotenv import load_dotenv

from app.config.settings import SpikeSettings

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
KEEP_FORMS = {"8-K", "10-Q", "10-K", "4"}


class SecFilingsScraper:
    def __init__(self, settings: SpikeSettings | None = None) -> None:
        self.settings = settings or SpikeSettings()
        load_dotenv(self.settings.repo_root / ".env")
        self.user_agent = (os.getenv("SEC_USER_AGENT") or "").strip()

    def fetch(self) -> list[dict]:
        window_start = self.settings.window_start().date()
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        items: list[dict] = []
        with httpx.Client(
            headers=headers, timeout=30.0, follow_redirects=True
        ) as client:
            ticker_map = self._ticker_map(client)
            for ticker in self.settings.tickers:
                items.extend(
                    self._filings_for(client, ticker, ticker_map, window_start)
                )
                time.sleep(0.2)
        items.sort(key=lambda row: row.get("filing_date") or "", reverse=True)
        return items

    def _ticker_map(self, client: httpx.Client) -> dict[str, dict]:
        cache_path = self.settings.data_dir / "company_tickers.json"
        if cache_path.exists():
            raw = json.loads(cache_path.read_text())
        else:
            response = client.get(COMPANY_TICKERS_URL)
            response.raise_for_status()
            raw = response.json()
            self.settings.data_dir.mkdir(parents=True, exist_ok=True)
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
        window_start: date,
    ) -> list[dict]:
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

        items: list[dict] = []
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
            if parsed < window_start:
                continue
            items.append(
                {
                    "source": "sec",
                    "ticker": ticker,
                    "company": company,
                    "form": form,
                    "filing_date": filing_date,
                    "accession": accession,
                    "url": self._document_url(info["cik"], accession, primary),
                }
            )
        return items

    def _document_url(self, cik: int, accession: str, primary: str) -> str:
        accession_id = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_id}/{primary}"
