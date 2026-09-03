"""Assemble a Profile from app/profiles/user.py and app/profiles/tickers.py."""

from __future__ import annotations

from dataclasses import dataclass

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
    timezone: str
    send_day: str
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
        timezone=str(USER_PROFILE.get("timezone") or "America/New_York"),
        send_day=str(USER_PROFILE.get("send_day") or "sunday"),
        ranking_criteria=str(USER_PROFILE.get("ranking_criteria") or "").strip(),
        email_tone=str(USER_PROFILE.get("email_tone") or "").strip(),
        tickers=tickers,
    )
