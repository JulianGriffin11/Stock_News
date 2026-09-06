"""Weekly orchestrator: ingest → summarize → rank → write → send."""

from __future__ import annotations

from sqlalchemy import func, select

from app.agent.steps import run_rank, run_summarize, run_write_email
from app.config.settings import Settings
from app.database.digest_runs import get_run_for_week
from app.database.emails import get_email_for_run
from app.database.models import DigestRunRow, EmailRow, ItemSummaryRow
from app.database.session import session_scope
from app.ingest import run_ingest
from app.services.send_email import run_send


def already_sent(settings: Settings) -> bool:
    run = get_run_for_week(settings.week_start(), settings)
    if run is None:
        return False
    email = get_email_for_run(run.id, settings)
    return email is not None and email.status == "sent"


def _started(name: str) -> None:
    print(f"{name:<14} started")


def _finished(name: str) -> None:
    print(f"{name:<14} finished")
    print()


def _print_summary(settings: Settings) -> None:
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


def run_weekly(settings: Settings | None = None, force: bool = False) -> None:
    settings = settings or Settings()
    week = settings.week_start()
    if already_sent(settings) and not force:
        print(
            f"run-weekly: already sent for week_start={week}. "
            "Pass --force to redo."
        )
        print()
        _print_summary(settings)
        return

    print(f"run-weekly     week_start={week}")
    print()

    _started("ingest")
    run_ingest(settings, quiet=True)
    _finished("ingest")

    _started("summarize")
    run_summarize(settings, quiet=True)
    _finished("summarize")

    _started("rank")
    run_rank(settings, force=force, quiet=True)
    _finished("rank")

    _started("write-email")
    run_write_email(settings, force=force, quiet=True)
    _finished("write-email")

    _started("send")
    sent = run_send(settings, force=force, quiet=True)
    if sent == 0:
        raise RuntimeError(
            "Send did not complete. Check that rank and write-email produced a row."
        )
    _finished("send")

    print("run-weekly     done")
    print()
    _print_summary(settings)
