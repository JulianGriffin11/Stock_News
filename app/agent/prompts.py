"""Shared helpers for building LLM prompts from the profile and database rows."""

from __future__ import annotations

from typing import Any

from app.config.settings import Profile
from app.db.models import ItemSummaryRow


def reader_header(profile: Profile, *extra_lines: str) -> str:
    """First lines of every agent prompt: who the digest is for."""
    lines = [f"Reader: {profile.name}, {profile.title} ({profile.expertise_level})."]
    lines.extend(line for line in extra_lines if line)
    return "\n".join(lines)


def pack_summary(row: ItemSummaryRow) -> dict[str, Any]:
    """Turn an item_summaries row into JSON-safe dict for rank / write-email prompts."""
    item = row.raw_item
    return {
        "summary_id": str(row.id),
        "ticker": item.ticker,
        "source": item.source,
        "item_type": row.item_type,
        "title": item.title,
        "published_at": item.published_at.isoformat(),
        "summary": row.summary,
        "why_it_matters": row.why_it_matters,
        "key_numbers": row.key_numbers,
        "url": item.url,
    }
