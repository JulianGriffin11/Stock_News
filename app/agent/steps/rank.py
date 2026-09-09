"""Agent 2: rank this week's summaries into a digest_run."""

from __future__ import annotations

import json

from app.agent.client import parse_response
from app.agent.prompts import pack_summary
from app.agent.schemas import RankOut
from app.config.context import PipelineContext, make_context
from app.config.logging import step_logger
from app.config.settings import Settings
from app.database.digest_runs import upsert_run
from app.database.models import ItemSummaryRow
from app.database.summaries import list_week_summaries

INSTRUCTIONS = """\
You rank this week's item summaries for one investor digest.

Pick the 5–10 most material items. If fewer than 5 exist, rank all of them.
Return picks in priority order. summary_id must be copied exactly from the input.
reason: one line, specific to this investor's ranking criteria.
rationale: one short paragraph covering the set.

Prefer material filings, earnings, guidance, cash-flow or thesis changes, M&A,
capital allocation, and durable competitive shifts.
Deprioritize recaps, rumor, and short-term price commentary.
Do not invent items. Do not pad the list.
"""


def _user_input(summaries: list[ItemSummaryRow], settings: Settings) -> str:
    profile = settings.profile
    prefs = ", ".join(f"{key}={value}" for key, value in profile.preferences.items())
    rows = [pack_summary(row) for row in summaries]
    return (
        f"Reader: {profile.name}, {profile.title} ({profile.expertise_level}).\n"
        f"Interests: {', '.join(profile.interests)}\n"
        f"Preferences: {prefs}\n"
        f"Ranking criteria:\n{profile.ranking_criteria}\n\n"
        f"Candidates ({len(rows)}):\n{json.dumps(rows, indent=2)}"
    )


def _valid_picks(out: RankOut, allowed: set[str]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    picks: list[tuple[str, str]] = []
    for pick in out.picks:
        if pick.summary_id not in allowed or pick.summary_id in seen:
            continue
        seen.add(pick.summary_id)
        picks.append((pick.summary_id, pick.reason))
    return picks[:10]


def run_rank(
    ctx: PipelineContext | None = None,
    force: bool = False,
) -> int:
    ctx = ctx or make_context()
    log = step_logger("rank", ctx)
    settings = ctx.settings
    week = ctx.week_start
    existing = ctx.resolve_digest_run()
    if existing is not None and not force:
        log.warning(
            "skipped digest already exists — pass --force to replace",
        )
        return 0

    summaries = list_week_summaries(settings)
    candidates = len(summaries)
    if not summaries:
        log.warning("skipped no summaries in 7-day window — run summarize first")
        return 0

    out = parse_response(
        model=settings.rank_model,
        instructions=INSTRUCTIONS,
        user_input=_user_input(summaries, settings),
        schema=RankOut,
        settings=settings,
    )
    allowed = {str(row.id) for row in summaries}
    picks = _valid_picks(out, allowed)
    if not picks:
        raise RuntimeError("rank model returned no valid summary_id values")

    upsert_run(
        week_start=week,
        ranked_item_ids=[item_id for item_id, _reason in picks],
        rank_rationale=out.rationale
        + "\n"
        + "\n".join(f"- {item_id}: {reason}" for item_id, reason in picks),
        status="ranked",
        settings=settings,
    )
    ctx.resolve_digest_run(refresh=True)
    log.debug("done candidates=%d picks=%d", candidates, len(picks))
    return len(picks)
