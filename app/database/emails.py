"""Read and write emails (unsent until Phase 5)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config.settings import Settings
from app.database.models import EmailRow
from app.database.session import session_scope


def get_email_for_run(
    digest_run_id: uuid.UUID,
    settings: Settings | None = None,
) -> EmailRow | None:
    with session_scope(settings) as session:
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
    settings: Settings | None = None,
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
    with session_scope(settings) as session:
        return session.scalar(stmt)
