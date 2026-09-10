"""App settings: .env, profile, and the 7-day window."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from app.profiles.tickers import TICKERS
from app.profiles.user import USER_PROFILE


@dataclass(frozen=True)
class Ticker:
    symbol: str
    name: str


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    background: str
    interests: tuple[str, ...]
    preferences: dict[str, bool]
    expertise_level: str
    recipient: str
    ranking_criteria: str
    email_tone: str
    tickers: tuple[Ticker, ...]


def load_profile() -> Profile:
    tickers = tuple(
        Ticker(symbol=str(row["symbol"]).upper(), name=str(row["name"]))
        for row in TICKERS
    )
    if not tickers:
        raise ValueError("No tickers in app/profiles/tickers.py")
    return Profile(
        name=str(USER_PROFILE.get("name") or ""),
        title=str(USER_PROFILE.get("title") or ""),
        background=str(USER_PROFILE.get("background") or "").strip(),
        interests=tuple(str(item) for item in USER_PROFILE.get("interests") or ()),
        preferences=dict(USER_PROFILE.get("preferences") or {}),
        expertise_level=str(USER_PROFILE.get("expertise_level") or ""),
        recipient=str(USER_PROFILE.get("recipient") or ""),
        ranking_criteria=str(USER_PROFILE.get("ranking_criteria") or "").strip(),
        email_tone=str(USER_PROFILE.get("email_tone") or "").strip(),
        tickers=tickers,
    )


class Settings:
    window_days = 7

    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.repo_root / "data"
        load_dotenv(self.repo_root / ".env")
        self.sec_user_agent = (os.getenv("SEC_USER_AGENT") or "").strip()
        self.database_url = (os.getenv("DATABASE_URL") or "").strip()
        self.openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        self.resend_api_key = (os.getenv("RESEND_API_KEY") or "").strip()
        self.resend_from = (os.getenv("RESEND_FROM") or "").strip()
        self.summarize_model = (
            os.getenv("OPENAI_SUMMARIZE_MODEL") or "gpt-4o-mini"
        ).strip()
        self.rank_model = (os.getenv("OPENAI_RANK_MODEL") or "gpt-4o").strip()
        self.email_model = (os.getenv("OPENAI_EMAIL_MODEL") or "gpt-4o-mini").strip()
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

    def require_openai_api_key(self) -> str:
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing. Put it in .env")
        return self.openai_api_key

    def require_resend_api_key(self) -> str:
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is missing. Put it in .env")
        return self.resend_api_key

    def require_resend_from(self) -> str:
        if not self.resend_from:
            raise ValueError(
                "RESEND_FROM is missing. Use a Resend-verified address, e.g. "
                "Digest <news@yourdomain.com>"
            )
        return self.resend_from

    def require_recipient(self) -> str:
        recipient = (self.profile.recipient or "").strip()
        if not recipient:
            raise ValueError("recipient is missing in app/profiles/user.py")
        return recipient

    def window_start(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.window_days)

    def week_start(self) -> date:
        """Monday of the current UTC week — stable digest_runs key."""
        today = datetime.now(UTC).date()
        return today - timedelta(days=today.weekday())

    def write_json(self, filename: str, items: list[dict]) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / filename
        path.write_text(json.dumps(items, indent=2, default=str) + "\n")
        return path
