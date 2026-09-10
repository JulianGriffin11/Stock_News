from app.db.models import Base, DigestRunRow, EmailRow, ItemSummaryRow, RawItemRow
from app.db.queries import (
    get_email_for_run,
    get_run_for_week,
    get_summaries_by_ids,
    insert_summaries,
    list_unsummarized,
    list_week_summaries,
    mark_email_failed,
    mark_email_sent,
    set_run_status,
    upsert_raw_items,
    upsert_run,
    upsert_unsent_email,
)
from app.db.session import session_scope

__all__ = [
    "Base",
    "DigestRunRow",
    "EmailRow",
    "ItemSummaryRow",
    "RawItemRow",
    "get_email_for_run",
    "get_run_for_week",
    "get_summaries_by_ids",
    "insert_summaries",
    "list_unsummarized",
    "list_week_summaries",
    "mark_email_failed",
    "mark_email_sent",
    "session_scope",
    "set_run_status",
    "upsert_raw_items",
    "upsert_run",
    "upsert_unsent_email",
]
