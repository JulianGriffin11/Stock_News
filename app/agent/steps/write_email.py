"""Agent 3: write the weekly email and store it unsent."""

from __future__ import annotations

import json
import uuid

from app.agent.client import parse_response
from app.agent.schemas import EmailOut
from app.config.settings import Settings
from app.database.digest_runs import get_run_for_week, set_run_status
from app.database.emails import get_email_for_run, upsert_unsent_email
from app.database.models import ItemSummaryRow
from app.database.summaries import get_summaries_by_ids, list_week_summaries

INSTRUCTIONS = """\
You write one weekly investor digest email from ranked items.

Return JSON: subject, html_body, text_body.

Subject example:
Weekly digest: NVDA, AAPL — earnings, one 8-K, two headlines

Body sections, in this order:
1. This week in one paragraph
2. Filings — 8-K / Form 4 / 10-Q / 10-K (facts + link)
3. News — RSS items that survived ranking
4. Worth a look, not ranked — only if leftover filings are provided

Each ranked item: ticker, type badge (8-K / Form 4 / News / earnings / 10-Q),
1-3 sentences summary, why it matters, link.

Tone: match the requested email_tone. No hype. No invented numbers.
HTML should be simple and readable in a mail client (headings, paragraphs, links).
Plaintext should stand alone without HTML tags.
"""


def _pack(row: ItemSummaryRow) -> dict:
    item = row.raw_item
    return {
        "summary_id": str(row.id),
        "ticker": item.ticker,
        "source": item.source,
        "item_type": row.item_type,
        "title": item.title,
        "published_at": item.published_at.isoformat(),
        "summary": row.summary,
        "why_it_matters": row.why_it_matters,
        "key_numbers": row.key_numbers,
        "url": item.url,
    }


def _user_input(
    ranked: list[ItemSummaryRow],
    leftover: list[ItemSummaryRow],
    settings: Settings,
) -> str:
    profile = settings.profile
    return (
        f"Reader: {profile.name}, {profile.title} ({profile.expertise_level}).\n"
        f"Email tone: {profile.email_tone}\n"
        f"Watchlist: {', '.join(settings.tickers)}\n\n"
        f"Ranked items ({len(ranked)}):\n{json.dumps([_pack(row) for row in ranked], indent=2)}\n\n"
        f"Worth a look, not ranked ({len(leftover)}):\n"
        f"{json.dumps([_pack(row) for row in leftover], indent=2)}"
    )


def _leftover_filings(
    ranked: list[ItemSummaryRow],
    week: list[ItemSummaryRow],
) -> list[ItemSummaryRow]:
    ranked_ids = {row.id for row in ranked}
    filing_types = {"8-k", "form-4", "10-q", "10-k", "earnings"}
    leftover = [
        row
        for row in week
        if row.id not in ranked_ids and row.item_type in filing_types
    ]
    return leftover[:8]


def run_write_email(
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
            print(f"Write email: no digest_run for week_start={week}. Run rank first.")
        return 0

    existing = get_email_for_run(run.id, settings)
    if existing is not None and not force:
        if not quiet:
            print(
                f"Write email: already stored for week_start={week}. "
                "Pass --force to replace."
            )
        return 0

    ranked_ids = [uuid.UUID(str(item_id)) for item_id in run.ranked_item_ids]
    ranked = get_summaries_by_ids(ranked_ids, settings)
    if not ranked:
        if not quiet:
            print("Write email: ranked_item_ids did not match any summaries.")
        return 0

    leftover = _leftover_filings(ranked, list_week_summaries(settings))
    out = parse_response(
        model=settings.email_model,
        instructions=INSTRUCTIONS,
        user_input=_user_input(ranked, leftover, settings),
        schema=EmailOut,
        settings=settings,
    )
    upsert_unsent_email(
        digest_run_id=run.id,
        subject=out.subject,
        html_body=out.html_body,
        text_body=out.text_body,
        settings=settings,
    )
    set_run_status(run.id, "written", settings)
    if not quiet:
        print(f"Write email: stored unsent — {out.subject}")
    return 1
