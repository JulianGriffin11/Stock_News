"""Read and write the four digest tables."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.db.models import DigestRunRow, EmailRow, ItemSummaryRow, RawItemRow
from app.db.session import session_scope
from app.scrapers.schemas import RawItem


def _parse_published_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def upsert_raw_items(items: list[RawItem]) -> tuple[int, int]:
    """Insert new rows; refresh existing ones matched on external_id.

    Returns (inserted, updated).
    """
    if not items:
        return 0, 0

    now = datetime.now(UTC)
    ids = [item["external_id"] for item in items]

    with session_scope() as session:
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


def list_unsummarized(cutoff: datetime) -> list[RawItemRow]:
    """Raw items in the window that do not yet have a summary."""
    with session_scope() as session:
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


def insert_summaries(
    rows: list[tuple[uuid.UUID, str, str, str, list[str], str]],
) -> int:
    """Insert item_summaries in one session / commit.

    Each tuple is (raw_item_id, summary, why_it_matters, item_type, key_numbers, model).
    """
    if not rows:
        return 0
    now = datetime.now(UTC)
    with session_scope() as session:
        for raw_item_id, summary, why_it_matters, item_type, key_numbers, model in rows:
            session.add(
                ItemSummaryRow(
                    raw_item_id=raw_item_id,
                    summary=summary,
                    why_it_matters=why_it_matters,
                    item_type=item_type,
                    key_numbers=key_numbers,
                    model=model,
                    created_at=now,
                )
            )
    return len(rows)


def list_week_summaries(cutoff: datetime) -> list[ItemSummaryRow]:
    with session_scope() as session:
        rows = session.scalars(
            select(ItemSummaryRow)
            .join(RawItemRow)
            .where(RawItemRow.published_at >= cutoff)
            .options(selectinload(ItemSummaryRow.raw_item))
            .order_by(RawItemRow.published_at.desc())
        ).all()
        session.expunge_all()
        return list(rows)


def get_summaries_by_ids(ids: list[uuid.UUID]) -> list[ItemSummaryRow]:
    if not ids:
        return []
    with session_scope() as session:
        rows = session.scalars(
            select(ItemSummaryRow)
            .where(ItemSummaryRow.id.in_(ids))
            .options(selectinload(ItemSummaryRow.raw_item))
        ).all()
        session.expunge_all()
        by_id = {row.id: row for row in rows}
        return [by_id[item_id] for item_id in ids if item_id in by_id]


def get_run_for_week(week_start: date) -> DigestRunRow | None:
    with session_scope() as session:
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
    with session_scope() as session:
        return session.scalar(stmt)


def set_run_status(run_id: uuid.UUID, status: str) -> None:
    with session_scope() as session:
        row = session.get(DigestRunRow, run_id)
        if row is None:
            raise ValueError(f"digest_run {run_id} not found")
        row.status = status


def get_email_for_run(digest_run_id: uuid.UUID) -> EmailRow | None:
    with session_scope() as session:
        row = session.scalar(
            select(EmailRow).where(EmailRow.digest_run_id == digest_run_id)
        )
        if row is None:
            return None
        session.expunge(row)
        return row


def upsert_unsent_email(
    digest_run_id: uuid.UUID,
    subject: str,
    html_body: str,
    text_body: str,
) -> uuid.UUID:
    payload = {
        "digest_run_id": digest_run_id,
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
        "sent_at": None,
        "resend_id": None,
        "status": "unsent",
    }
    stmt = insert(EmailRow).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["digest_run_id"],
        set_={
            "subject": stmt.excluded.subject,
            "html_body": stmt.excluded.html_body,
            "text_body": stmt.excluded.text_body,
            "sent_at": None,
            "resend_id": None,
            "status": "unsent",
        },
    ).returning(EmailRow.id)
    with session_scope() as session:
        return session.scalar(stmt)


def mark_email_sent(email_id: uuid.UUID, resend_id: str) -> None:
    with session_scope() as session:
        row = session.get(EmailRow, email_id)
        if row is None:
            raise ValueError(f"email {email_id} not found")
        row.status = "sent"
        row.resend_id = resend_id
        row.sent_at = datetime.now(UTC)


def mark_email_failed(email_id: uuid.UUID) -> None:
    with session_scope() as session:
        row = session.get(EmailRow, email_id)
        if row is None:
            raise ValueError(f"email {email_id} not found")
        row.status = "failed"
