"""Read and write digest_runs (one row per week)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.config.settings import Settings
from app.database.models import DigestRunRow
from app.database.session import session_scope


def get_run_for_week(
    week_start: date,
    settings: Settings | None = None,
) -> DigestRunRow | None:
    with session_scope(settings) as session:
        row = session.scalar(
            select(DigestRunRow)
            .where(DigestRunRow.week_start == week_start)
            .options(selectinload(DigestRunRow.email))
        )
        if row is None:
            return None
        session.expunge(row)
        return row


def upsert_run(
    week_start: date,
    ranked_item_ids: list[str],
    rank_rationale: str,
    status: str,
    settings: Settings | None = None,
) -> uuid.UUID:
    now = datetime.now(UTC)
    payload = {
        "week_start": week_start,
        "status": status,
        "ranked_item_ids": ranked_item_ids,
        "rank_rationale": rank_rationale,
        "created_at": now,
    }
    stmt = insert(DigestRunRow).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["week_start"],
        set_={
            "status": stmt.excluded.status,
            "ranked_item_ids": stmt.excluded.ranked_item_ids,
            "rank_rationale": stmt.excluded.rank_rationale,
        },
    ).returning(DigestRunRow.id)
    with session_scope(settings) as session:
        return session.scalar(stmt)


def set_run_status(
    run_id: uuid.UUID,
    status: str,
    settings: Settings | None = None,
) -> None:
    with session_scope(settings) as session:
        row = session.get(DigestRunRow, run_id)
        if row is None:
            raise ValueError(f"digest_run {run_id} not found")
        row.status = status
