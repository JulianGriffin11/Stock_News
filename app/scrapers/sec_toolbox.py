"""SEC helpers used by the filings scraper.

CikIndex         ticker → CIK (cached company_tickers.json)
FilingDocuments  download a filing and build raw_text
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from re import sub

import httpx
from bs4 import BeautifulSoup

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
KEEP_FORMS = {"8-K", "10-Q", "10-K", "4"}
EXCERPT_CHARS = 12_000
EXHIBIT_99_MARKERS = ("ex99", "exhibit99", "ex-99", "exhibit-99")
REQUEST_PAUSE = 0.2


def archive_url(cik: int, accession: str, filename: str = "") -> str:
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
    if not filename:
        return folder
    return f"{folder}/{filename}"


def form_kind(form: str) -> str:
    return form.split("/")[0]


def pause() -> None:
    time.sleep(REQUEST_PAUSE)


class CikIndex:
    """Ticker → {cik, title}. Cached under data/company_tickers.json."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def load(self, client: httpx.Client) -> dict[str, dict]:
        raw = self._read_or_download(client)
        mapping: dict[str, dict] = {}
        for row in raw.values():
            mapping[str(row["ticker"]).upper()] = {
                "cik": int(row["cik_str"]),
                "title": row["title"],
            }
        return mapping

    def _read_or_download(self, client: httpx.Client) -> dict:
        cache_path = self.cache_dir / "company_tickers.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())
        response = client.get(COMPANY_TICKERS_URL)
        response.raise_for_status()
        raw = response.json()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw))
        pause()
        return raw


class FilingDocuments:
    """Turn an EDGAR filing into capped plain text for Agent 1."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client

    def raw_text(
        self,
        *,
        cik: int,
        company: str,
        form: str,
        filing_date: str,
        sec_items: str,
        description: str,
        primary_url: str,
        accession: str,
    ) -> str:
        header = self._header(company, form, filing_date, sec_items, description)
        body = self.excerpt(primary_url)
        if form_kind(form) == "8-K":
            exhibit = self._exhibit_99(cik, accession, primary_url)
            if exhibit:
                body = f"{body}\n\nExhibit 99.1:\n{exhibit}".strip()
        if not body:
            return header
        return f"{header}\n\n{body}"[:EXCERPT_CHARS]

    def excerpt(self, url: str) -> str:
        html = self._get(url)
        if html is None:
            return ""
        return self._plain_text(html)[:EXCERPT_CHARS]

    def _header(
        self,
        company: str,
        form: str,
        filing_date: str,
        sec_items: str,
        description: str,
    ) -> str:
        lines = [f"{company} filed Form {form} on {filing_date}."]
        if sec_items:
            lines.append(f"Items: {sec_items}")
        if description:
            lines.append(f"Description: {description}")
        return "\n".join(lines)

    def _exhibit_99(self, cik: int, accession: str, primary_url: str) -> str:
        url = self._exhibit_99_url(cik, accession)
        if not url or url == primary_url:
            return ""
        return self.excerpt(url)

    def _exhibit_99_url(self, cik: int, accession: str) -> str | None:
        index_url = f"{archive_url(cik, accession)}/index.json"
        payload = self._get_json(index_url)
        if payload is None:
            return None
        entries = payload.get("directory", {}).get("item") or []
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            name = str(entry.get("name") or "")
            lowered = name.lower().replace("_", "-")
            if any(marker in lowered for marker in EXHIBIT_99_MARKERS):
                return archive_url(cik, accession, name)
        return None

    def _get(self, url: str) -> str | None:
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as error:
            print(f"sec get {url}: {error}")
            return None
        finally:
            pause()

    def _get_json(self, url: str) -> dict | None:
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
            print(f"sec get {url}: {error}")
            return None
        finally:
            pause()

    def _plain_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return sub(r"\s+", " ", soup.get_text(" ")).strip()
