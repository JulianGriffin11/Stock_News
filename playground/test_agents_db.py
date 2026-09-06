"""Count Phase 4 tables. Does not call OpenAI.

Run from the repo root after `uv run alembic upgrade head`:

    uv run python playground/test_agents_db.py
"""

from sqlalchemy import func, select

from app.config.settings import Settings
from app.database.models import DigestRunRow, EmailRow, ItemSummaryRow
from app.database.session import session_scope


def run() -> None:
    settings = Settings()
    week = settings.week_start()
    with session_scope(settings) as session:
        summaries = session.scalar(select(func.count()).select_from(ItemSummaryRow)) or 0
        runs = session.scalar(select(func.count()).select_from(DigestRunRow)) or 0
        emails = session.scalar(select(func.count()).select_from(EmailRow)) or 0
        this_week = session.scalar(
            select(DigestRunRow).where(DigestRunRow.week_start == week)
        )
        week_status = None
        week_ranked = 0
        if this_week is not None:
            week_status = this_week.status
            week_ranked = len(this_week.ranked_item_ids)
    print(f"item_summaries: {summaries}")
    print(f"digest_runs: {runs}")
    print(f"emails: {emails}")
    print(f"week_start: {week}")
    if week_status is None:
        print("this week: (no digest_run yet)")
    else:
        print(f"this week: status={week_status} ranked={week_ranked}")


if __name__ == "__main__":
    run()
