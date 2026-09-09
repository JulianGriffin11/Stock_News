"""Agent 1: summarize unsummarized raw_items into item_summaries."""

from __future__ import annotations

from app.agent.client import parse_response
from app.agent.schemas import ItemSummaryOut
from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.database.models import RawItemRow
from app.database.summaries import insert_summary, list_unsummarized

INSTRUCTIONS = """\
You summarize one news item or SEC filing for a long-term fundamental investor.

Return JSON only, matching the schema.
- summary: 2–4 sentences. What happened. Copy figures only if they appear in the text.
- why_it_matters: 1–2 sentences on the investment thesis (quality, cash flow, valuation, durability).
- item_type: earnings | 8-k | form-4 | 10-q | 10-k | product | news | other
- key_numbers: short strings copied from the text. Empty list if none.

If the excerpt is incomplete (typical for 10-Q / 10-K), say so and do not invent numbers.
Do not interpret tone. Do not pad. Skip market-sentiment language.
"""


def _user_input(item: RawItemRow, settings: Settings) -> str:
    profile = settings.profile
    return (
        f"Reader: {profile.name}, {profile.title} ({profile.expertise_level}).\n"
        f"Background: {profile.background}\n"
        f"Source: {item.source}\n"
        f"Ticker: {item.ticker}\n"
        f"Title: {item.title}\n"
        f"Published: {item.published_at.isoformat()}\n"
        f"URL: {item.url}\n"
        f"Text:\n{item.raw_text}"
    )


def run_summarize(ctx: PipelineContext | None = None) -> int:
    ctx = ctx or make_context()
    log = step_logger("summarize", ctx)
    settings = ctx.settings
    items = list_unsummarized(settings)
    candidates = len(items)
    if not items:
        log.debug("done candidates=0 written=0")
        return 0

    written = 0
    for item in items:
        out = parse_response(
            model=settings.summarize_model,
            instructions=INSTRUCTIONS,
            user_input=_user_input(item, settings),
            schema=ItemSummaryOut,
            settings=settings,
        )
        insert_summary(
            raw_item_id=item.id,
            summary=out.summary,
            why_it_matters=out.why_it_matters,
            item_type=out.item_type,
            key_numbers=out.key_numbers,
            model=settings.summarize_model,
            settings=settings,
        )
        written += 1
        log.debug("summarized ticker=%s id=%s", item.ticker, item.id)
    log.debug("done candidates=%d written=%d", candidates, written)
    return written
