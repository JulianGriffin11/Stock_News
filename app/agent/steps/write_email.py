"""Agent 3: write subject + overview, then render the Arcane digest."""

from __future__ import annotations

import json
import uuid

from app.agent.client import openai_client, parse_response
from app.agent.prompts import pack_summary, reader_header
from app.agent.schemas import EmailOut, type_label
from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.db.models import ItemSummaryRow
from app.db.queries import (
    get_email_for_run,
    get_summaries_by_ids,
    set_run_status,
    upsert_unsent_email,
)
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


def _user_input(ranked: list[ItemSummaryRow], settings: Settings) -> str:
    profile = settings.profile
    header = reader_header(
        profile,
        f"Email tone: {profile.email_tone}",
        f"Watchlist: {', '.join(settings.tickers)}",
    )
    packed = [pack_summary(row) for row in ranked]
    return (
        f"{header}\n\n"
        f"Ranked items ({len(ranked)}):\n{json.dumps(packed, indent=2)}"
    )


def _item_body(row: ItemSummaryRow) -> str:
    parts = [row.summary.strip()]
    why = (row.why_it_matters or "").strip()
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
        item = row.raw_item
        listings.append(
            DigestListing(
                step=index,
                title=f"{item.ticker} · {type_label(row.item_type)}",
                body=_item_body(row),
                url=item.url,
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

    existing = get_email_for_run(run.id)
    if existing is not None and not force:
        log.warning("skipped email already stored — pass --force to replace")
        return 0

    ranked_ids = [uuid.UUID(str(item_id)) for item_id in run.ranked_item_ids]
    ranked = get_summaries_by_ids(ranked_ids)
    if not ranked:
        log.warning("skipped ranked_item_ids did not match any summaries")
        return 0

    out = parse_response(
        model=settings.email_model,
        instructions=INSTRUCTIONS,
        user_input=_user_input(ranked, settings),
        schema=EmailOut,
        client=openai_client(settings),
    )
    listings = _listings(ranked)
    html_body, text_body = render_digest(
        subject=out.subject,
        reader_name=_greeting_name(settings),
        overview=out.overview,
        listings=listings,
    )
    preview_html, _ = render_digest(
        subject=out.subject,
        reader_name=_greeting_name(settings),
        overview=out.overview,
        listings=listings,
        inline_icons=True,
    )
    upsert_unsent_email(
        digest_run_id=run.id,
        subject=out.subject,
        html_body=html_body,
        text_body=text_body,
    )
    _write_preview(preview_html, settings)
    set_run_status(run.id, "written")
    log.debug('done subject="%s"', out.subject)
    return 1
