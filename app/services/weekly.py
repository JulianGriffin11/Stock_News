"""Weekly orchestrator: ingest → summarize → rank → write → send."""

from __future__ import annotations

import logging
import time

from sqlalchemy import func, select

from app.agent.steps import run_rank, run_summarize, run_write_email
from app.config.context import PipelineContext, make_context
from app.config.logging import run_timed_step
from app.database.emails import get_email_for_run
from app.database.models import DigestRunRow, EmailRow, ItemSummaryRow
from app.database.session import session_scope
from app.ingest import run_ingest
from app.services.send_email import run_send

log = logging.getLogger("digest")


def already_sent(ctx: PipelineContext) -> bool:
    run = ctx.resolve_digest_run()
    if run is None:
        return False
    email = get_email_for_run(run.id, ctx.settings)
    return email is not None and email.status == "sent"


def _log_db_summary(ctx: PipelineContext) -> None:
    week = ctx.week_start
    settings = ctx.settings
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
    log.debug(
        "week_start=%s item_summaries=%d digest_runs=%d emails=%d "
        "week_status=%s week_ranked=%d",
        week,
        summaries,
        runs,
        emails,
        week_status or "none",
        week_ranked,
    )


def run_weekly(ctx: PipelineContext | None = None, force: bool = False) -> None:
    ctx = ctx or make_context()
    week = ctx.week_start
    if already_sent(ctx) and not force:
        log.warning(
            "week_start=%s already sent — pass --force to redo",
            week,
        )
        _log_db_summary(ctx)
        return

    run_start = time.perf_counter()
    log.info("week_start=%s run started force=%s", week, force)

    run_timed_step(ctx, "ingest", run_ingest)
    run_timed_step(ctx, "summarize", run_summarize)
    run_timed_step(ctx, "rank", run_rank, force=force)
    run_timed_step(ctx, "write-email", run_write_email, force=force)
    sent = run_timed_step(ctx, "send", run_send, force=force)
    if sent == 0:
        raise RuntimeError(
            "Send did not complete. Check that rank and write-email produced a row."
        )

    run = ctx.resolve_digest_run(refresh=True)
    week_status = run.status if run else "unknown"
    week_ranked = len(run.ranked_item_ids) if run else 0
    duration_s = time.perf_counter() - run_start
    log.info(
        "week_start=%s run done duration_s=%.1f week_status=%s ranked=%d",
        week,
        duration_s,
        week_status,
        week_ranked,
    )
    _log_db_summary(ctx)
