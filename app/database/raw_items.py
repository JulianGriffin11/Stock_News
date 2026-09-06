"""Upsert ingested items into raw_items. Dedupe on external_id."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config.models import RawItem
from app.config.settings import Settings
from app.database.models import RawItemRow
from app.database.session import session_scope


def _parse_published_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def upsert_raw_items(
    items: list[RawItem],
    settings: Settings | None = None,
) -> tuple[int, int]:
    """Insert new rows; refresh existing ones matched on external_id.

    Returns (inserted, updated).
    """
    if not items:
        return 0, 0

    now = datetime.now(UTC)
    ids = [item["external_id"] for item in items]

    with session_scope(settings) as session:
        existing = set(
            session.scalars(
                select(RawItemRow.external_id).where(RawItemRow.external_id.in_(ids))
            )
        )
        rows = [
            {
                "source": item["source"],
                "ticker": item["ticker"],
                "title": item["title"],
                "url": item["url"],
                "published_at": _parse_published_at(item["published_at"]),
                "raw_text": item["raw_text"],
                "external_id": item["external_id"],
                "fetched_at": now,
            }
            for item in items
        ]
        stmt = insert(RawItemRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_={
                "source": stmt.excluded.source,
                "ticker": stmt.excluded.ticker,
                "title": stmt.excluded.title,
                "url": stmt.excluded.url,
                "published_at": stmt.excluded.published_at,
                "raw_text": stmt.excluded.raw_text,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        session.execute(stmt)

    inserted = sum(1 for item in items if item["external_id"] not in existing)
    updated = len(items) - inserted
    return inserted, updated
