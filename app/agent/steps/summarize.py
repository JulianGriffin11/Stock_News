"""Agent 1: summarize unsummarized raw_items into item_summaries."""

from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from openai import OpenAI

from app.agent.client import openai_client, parse_response
from app.agent.prompts import reader_header
from app.agent.schemas import ItemSummaryOut
from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.db.models import RawItemRow
from app.db.queries import insert_summaries, list_unsummarized

SUMMARIZE_WORKERS = 5
HEARTBEAT_S = 30

INSTRUCTIONS = """\
You summarize one news item or SEC filing for a long-term fundamental investor.

Return JSON only, matching the schema.
- summary: 1 sentence. What happened. Copy figures only if they appear in the text.
- why_it_matters: 1 sentence on the investment thesis (quality, cash flow, valuation, durability).
- item_type: earnings | 8-k | form-4 | 10-q | 10-k | product | news | other
- key_numbers: short strings copied from the text. Empty list if none.

If the excerpt is incomplete (typical for 10-Q / 10-K), say so and do not invent numbers.
For a Form 4, copy the owner, role, transaction code, shares, and price. Say whether
it is a discretionary open-market buy or sale. Do not treat RSU, tax-withholding, or
planned-sale language as thesis-changing.
Do not interpret tone. Do not pad. Skip market-sentiment language.
"""


def _user_input(item: RawItemRow, settings: Settings) -> str:
    profile = settings.profile
    return (
        f"{reader_header(profile, f'Background: {profile.background}')}\n"
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
    items = list_unsummarized(settings.window_start())
    candidates = len(items)
    if not items:
        log.debug("done candidates=0 written=0")
        return 0

    client = openai_client(settings)
    pending: list[tuple] = []
    workers = min(SUMMARIZE_WORKERS, candidates)
    completed = 0
    log.info("started candidates=%d workers=%d", candidates, workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_summarize_one, item, settings, client): item
            for item in items
        }
        outstanding = set(futures)
        last_beat = time.monotonic()
        while outstanding:
            finished, outstanding = wait(
                outstanding,
                timeout=HEARTBEAT_S,
                return_when=FIRST_COMPLETED,
            )
            now = time.monotonic()
            if not finished:
                log.info("progress %d/%d", completed, candidates)
                last_beat = now
                continue
            for future in finished:
                item = futures[future]
                completed += 1
                try:
                    out = future.result()
                except Exception:
                    log.exception(
                        "summarize failed ticker=%s id=%s",
                        item.ticker,
                        item.id,
                    )
                    continue
                pending.append(
                    (
                        item.id,
                        out.summary,
                        out.why_it_matters,
                        out.item_type,
                        out.key_numbers,
                        settings.summarize_model,
                    )
                )
                log.debug("summarized ticker=%s id=%s", item.ticker, item.id)
            if now - last_beat >= HEARTBEAT_S:
                log.info("progress %d/%d", completed, candidates)
                last_beat = now

    written = insert_summaries(pending)
    log.debug("done candidates=%d written=%d", candidates, written)
    return written


def _summarize_one(
    item: RawItemRow, settings: Settings, client: OpenAI
) -> ItemSummaryOut:
    return parse_response(
        model=settings.summarize_model,
        instructions=INSTRUCTIONS,
        user_input=_user_input(item, settings),
        schema=ItemSummaryOut,
        client=client,
    )
