"""Read and write item_summaries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.database.models import ItemSummaryRow, RawItemRow
from app.database.session import session_scope


def list_unsummarized(settings: Settings | None = None) -> list[RawItemRow]:
    """Raw items in the 7-day window that do not yet have a summary."""
    settings = settings or Settings()
    cutoff = settings.window_start()
    with session_scope(settings) as session:
        rows = session.scalars(
            select(RawItemRow)
            .outerjoin(ItemSummaryRow)
            .where(ItemSummaryRow.id.is_(None))
            .where(RawItemRow.published_at >= cutoff)
            .where(RawItemRow.raw_text != "")
            .order_by(RawItemRow.published_at.desc())
        ).all()
        session.expunge_all()
        return list(rows)


def insert_summary(
    raw_item_id: uuid.UUID,
    summary: str,
    why_it_matters: str,
    item_type: str,
    key_numbers: list[str],
    model: str,
    settings: Settings | None = None,
) -> uuid.UUID:
    row = ItemSummaryRow(
        raw_item_id=raw_item_id,
        summary=summary,
        why_it_matters=why_it_matters,
        item_type=item_type,
        key_numbers=key_numbers,
        model=model,
        created_at=datetime.now(UTC),
    )
    with session_scope(settings) as session:
        session.add(row)
        session.flush()
        return row.id


def list_week_summaries(settings: Settings | None = None) -> list[ItemSummaryRow]:
    settings = settings or Settings()
    cutoff = settings.window_start()
    with session_scope(settings) as session:
        rows = session.scalars(
            select(ItemSummaryRow)
            .join(RawItemRow)
            .where(RawItemRow.published_at >= cutoff)
            .options(selectinload(ItemSummaryRow.raw_item))
            .order_by(RawItemRow.published_at.desc())
        ).all()
        session.expunge_all()
        return list(rows)


def get_summaries_by_ids(
    ids: list[uuid.UUID],
    settings: Settings | None = None,
) -> list[ItemSummaryRow]:
    if not ids:
        return []
    with session_scope(settings) as session:
        rows = session.scalars(
            select(ItemSummaryRow)
            .where(ItemSummaryRow.id.in_(ids))
            .options(selectinload(ItemSummaryRow.raw_item))
        ).all()
        session.expunge_all()
        by_id = {row.id: row for row in rows}
        return [by_id[item_id] for item_id in ids if item_id in by_id]
