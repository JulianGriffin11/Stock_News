"""App settings: paths, 7-day window, and the Python profile."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from app.config.profile import Profile, load_profile


class Settings:
    window_days = 7

    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.repo_root / "data"
        load_dotenv(self.repo_root / ".env")
        self.sec_user_agent = (os.getenv("SEC_USER_AGENT") or "").strip()
        self.database_url = (os.getenv("DATABASE_URL") or "").strip()
        self.profile: Profile = load_profile()

    @property
    def tickers(self) -> list[str]:
        return [ticker.symbol for ticker in self.profile.tickers]

    @property
    def ticker_names(self) -> dict[str, str]:
        return {ticker.symbol: ticker.name for ticker in self.profile.tickers}

    def require_database_url(self) -> str:
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is missing. Copy it from Supabase → Project "
                "Settings → Database → URI and put it in .env"
            )
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if "sslmode=" not in url:
            url += "&sslmode=require" if "?" in url else "?sslmode=require"
        return url

    def window_start(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.window_days)

    def write_json(self, filename: str, items: list[dict]) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        path.write_text(json.dumps(items, indent=2, default=str) + "\n")
        return path
