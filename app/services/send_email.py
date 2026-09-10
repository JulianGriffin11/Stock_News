"""Send this week's stored email via Resend. Fail the job if send fails."""

from __future__ import annotations

import logging

import resend

from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.database.digest_runs import set_run_status
from app.database.emails import get_email_for_run, mark_email_failed, mark_email_sent
from app.database.models import EmailRow
from app.email.render import footer_attachments

log = logging.getLogger("digest.send")


def _deliver(email: EmailRow, settings: Settings) -> str:
    resend.api_key = settings.require_resend_api_key()
    result = resend.Emails.send(
        {
            "from": settings.require_resend_from(),
            "to": [settings.require_recipient()],
            "subject": email.subject,
            "html": email.html_body,
            "text": email.text_body,
            "attachments": footer_attachments(),
        }
    )
    resend_id = result["id"] if isinstance(result, dict) else getattr(result, "id", None)
    if not resend_id:
        raise RuntimeError("Resend returned no email id")
    return str(resend_id)


def run_send(
    ctx: PipelineContext | None = None,
    force: bool = False,
) -> int:
    ctx = ctx or make_context()
    step_log = step_logger("send", ctx)
    settings = ctx.settings
    run = ctx.resolve_digest_run()
    if run is None:
        step_log.warning("skipped no digest_run — run rank first")
        return 0

    email = get_email_for_run(run.id, settings)
    if email is None:
        step_log.warning("skipped no email stored — run write-email first")
        return 0

    if email.status == "sent" and not force:
        step_log.warning("skipped already sent — pass --force to send again")
        return 0

    recipient = settings.require_recipient()
    try:
        resend_id = _deliver(email, settings)
    except Exception:
        mark_email_failed(email.id, settings)
        set_run_status(run.id, "failed", settings)
        log.exception(
            "week_start=%s step=send failed recipient=%s",
            ctx.week_start,
            recipient,
        )
        raise

    mark_email_sent(email.id, resend_id, settings)
    set_run_status(run.id, "sent", settings)
    step_log.debug("done recipient=%s resend_id=%s", recipient, resend_id)
    return 1
