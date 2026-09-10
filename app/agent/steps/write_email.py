"""Agent 3: write subject + overview, then render the Arcane digest."""

from __future__ import annotations

import json
import uuid

from app.agent.client import parse_response
from app.agent.prompts import pack_summary
from app.agent.schemas import EmailOut
from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.database.digest_runs import set_run_status
from app.database.emails import get_email_for_run, upsert_unsent_email
from app.database.models import ItemSummaryRow
from app.database.summaries import get_summaries_by_ids
from app.email.render import DigestListing, render_digest

INSTRUCTIONS = """\
You write the subject line and a short overview for a weekly investor digest.

Return JSON: subject, overview (1-2 paragraphs as an array of strings).

Subject example:
Weekly digest: NVDA, AAPL — earnings, one 8-K, two headlines

overview: 1-2 short paragraphs covering this week's ranked set. Do not recap
every item. Do not write HTML.

Tone: match the requested email_tone. No hype. No invented numbers.
"""

TYPE_LABELS = {
    "earnings": "earnings",
    "8-k": "8-K",
    "form-4": "Form 4",
    "10-q": "10-Q",
    "10-k": "10-K",
    "product": "product",
    "news": "News",
    "other": "other",
}


def _user_input(ranked: list[ItemSummaryRow], settings: Settings) -> str:
    profile = settings.profile
    return (
        f"Reader: {profile.name}, {profile.title} ({profile.expertise_level}).\n"
        f"Email tone: {profile.email_tone}\n"
        f"Watchlist: {', '.join(settings.tickers)}\n\n"
        f"Ranked items ({len(ranked)}):\n"
        f"{json.dumps([pack_summary(row) for row in ranked], indent=2)}"
    )


def _type_label(item_type: str) -> str:
    return TYPE_LABELS.get(item_type, item_type)


def _item_title(packed: dict) -> str:
    return f"{packed['ticker']} · {_type_label(packed['item_type'])}"


def _item_body(packed: dict) -> str:
    parts = [str(packed["summary"]).strip()]
    why = str(packed.get("why_it_matters") or "").strip()
    if why:
        parts.append(why)
    return " ".join(parts)


def _greeting_name(settings: Settings) -> str:
    name = (settings.profile.name or "").strip()
    if not name:
        return "there"
    return name.split()[0]


def _listings(ranked: list[ItemSummaryRow]) -> list[DigestListing]:
    listings: list[DigestListing] = []
    for index, row in enumerate(ranked, start=1):
        packed = pack_summary(row)
        listings.append(
            DigestListing(
                step=index,
                title=_item_title(packed),
                body=_item_body(packed),
                url=str(packed["url"]),
            )
        )
    return listings


def _write_preview(html: str, settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.data_dir / "email-preview.html"
    path.write_text(html, encoding="utf-8")


def run_write_email(
    ctx: PipelineContext | None = None,
    force: bool = False,
) -> int:
    ctx = ctx or make_context()
    log = step_logger("write-email", ctx)
    settings = ctx.settings
    run = ctx.resolve_digest_run()
    if run is None:
        log.warning("skipped no digest_run — run rank first")
        return 0

    existing = get_email_for_run(run.id, settings)
    if existing is not None and not force:
        log.warning("skipped email already stored — pass --force to replace")
        return 0

    ranked_ids = [uuid.UUID(str(item_id)) for item_id in run.ranked_item_ids]
    ranked = get_summaries_by_ids(ranked_ids, settings)
    if not ranked:
        log.warning("skipped ranked_item_ids did not match any summaries")
        return 0

    out = parse_response(
        model=settings.email_model,
        instructions=INSTRUCTIONS,
        user_input=_user_input(ranked, settings),
        schema=EmailOut,
        settings=settings,
    )
    html_body, text_body = render_digest(
        subject=out.subject,
        reader_name=_greeting_name(settings),
        overview=out.overview,
        listings=_listings(ranked),
    )
    preview_html, _ = render_digest(
        subject=out.subject,
        reader_name=_greeting_name(settings),
        overview=out.overview,
        listings=_listings(ranked),
        inline_icons=True,
    )
    upsert_unsent_email(
        digest_run_id=run.id,
        subject=out.subject,
        html_body=html_body,
        text_body=text_body,
        settings=settings,
    )
    _write_preview(preview_html, settings)
    set_run_status(run.id, "written", settings)
    log.debug('done subject="%s"', out.subject)
    return 1
