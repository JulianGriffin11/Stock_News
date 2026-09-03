"""Shared settings and output helpers for the Phase 1 spike."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


class SpikeSettings:
    def __init__(self) -> None:
        self.tickers = ["NVDA", "AAPL", "MSFT"]
        self.ticker_names = {
            "NVDA": "NVIDIA",
            "AAPL": "Apple",
            "MSFT": "Microsoft",
        }
        self.window_days = 7
        self.repo_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.repo_root / "data"

    def window_start(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.window_days)

    def write_json(self, filename: str, items: list[dict]) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        path.write_text(json.dumps(items, indent=2, default=str) + "\n")
        return path

    def print_items(
        self,
        heading: str,
        items: list[dict],
        limit: int | None = 40,
    ) -> None:
        names = ", ".join(self.tickers)
        print(f"{heading} — {names} — last {self.window_days} days")
        print("-" * 60)
        if not items:
            print("(no items)")
            return

        shown = items if limit is None else items[:limit]
        for item in shown:
            source = item.get("form") or item.get("source") or "?"
            ticker = item.get("ticker", "")
            published = item.get("published") or item.get("filing_date") or ""
            headline = item.get("title") or item.get("company") or ""
            link = item.get("link") or item.get("url") or ""
            accession = item.get("accession") or ""
            print(f"[{source}] {ticker}  {published}  {headline}")
            if accession:
                print(f"          accession {accession}")
            if link:
                print(f"          {link}")
            print()

        leftover = len(items) - len(shown)
        if leftover > 0:
            print(f"... {leftover} more in the JSON dump")
