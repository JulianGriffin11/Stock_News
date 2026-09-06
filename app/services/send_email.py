"""Send this week's stored email via Resend. Fail the job if send fails."""

from __future__ import annotations

import resend

from app.config.settings import Settings
from app.database.digest_runs import get_run_for_week, set_run_status
from app.database.emails import get_email_for_run, mark_email_failed, mark_email_sent
from app.database.models import EmailRow


def _deliver(email: EmailRow, settings: Settings) -> str:
    resend.api_key = settings.require_resend_api_key()
    result = resend.Emails.send(
        {
            "from": settings.require_resend_from(),
            "to": [settings.require_recipient()],
            "subject": email.subject,
            "html": email.html_body,
            "text": email.text_body,
        }
    )
    resend_id = result["id"] if isinstance(result, dict) else getattr(result, "id", None)
    if not resend_id:
        raise RuntimeError("Resend returned no email id")
    return str(resend_id)


def run_send(
    settings: Settings | None = None,
    force: bool = False,
    *,
    quiet: bool = False,
) -> int:
    settings = settings or Settings()
    week = settings.week_start()
    run = get_run_for_week(week, settings)
    if run is None:
        if not quiet:
            print(f"Send: no digest_run for week_start={week}. Run rank first.")
        return 0

    email = get_email_for_run(run.id, settings)
    if email is None:
        if not quiet:
            print(f"Send: no email for week_start={week}. Run write-email first.")
        return 0

    if email.status == "sent" and not force:
        if not quiet:
            print(
                f"Send: already sent for week_start={week}. "
                "Pass --force to send again."
            )
        return 0

    try:
        resend_id = _deliver(email, settings)
    except Exception:
        mark_email_failed(email.id, settings)
        set_run_status(run.id, "failed", settings)
        raise

    mark_email_sent(email.id, resend_id, settings)
    set_run_status(run.id, "sent", settings)
    if not quiet:
        print(f"Send: sent to {settings.require_recipient()} ({resend_id})")
    return 1
