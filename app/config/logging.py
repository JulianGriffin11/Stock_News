"""Logging setup and helpers for the digest pipeline."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from app.config.context import PipelineContext

# Third-party loggers that emit one line per HTTP request at INFO.
_QUIET_LOGGERS = ("httpx", "httpx2", "httpcore", "openai", "urllib3")


def configure_logging(*, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
        force=True,
    )
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


class _ContextAdapter(logging.LoggerAdapter):
    def process(self, msg: object, kwargs: dict) -> tuple[object, dict]:
        extra = {**self.extra, **kwargs.pop("extra", {})}
        parts = []
        if week_start := extra.get("week_start"):
            parts.append(f"week_start={week_start}")
        if step := extra.get("step"):
            parts.append(f"step={step}")
        prefix = " ".join(parts)
        if prefix:
            msg = f"{prefix} {msg}"
        return msg, kwargs


def step_logger(step: str, ctx: PipelineContext | None = None) -> _ContextAdapter:
    base = logging.getLogger("digest")
    extra: dict[str, str] = {"step": step}
    if ctx is not None:
        extra["week_start"] = ctx.week_start.isoformat()
    return _ContextAdapter(base, extra)


def _step_summary(step: str, result: object) -> str:
    if step == "ingest" and isinstance(result, list):
        return f"items={len(result)}"
    if step == "summarize" and isinstance(result, int):
        return f"written={result}"
    if step == "rank" and isinstance(result, int):
        return f"picks={result}"
    if step == "write-email":
        return "stored" if result else "skipped"
    if step == "send":
        return "sent" if result else "skipped"
    return ""


def run_timed_step[R](
    ctx: PipelineContext,
    step: str,
    fn: Callable[..., R],
    *args: object,
    **kwargs: object,
) -> R:
    """Run a pipeline step and log one INFO line with duration (+ brief result)."""
    log = logging.getLogger("digest")
    week = ctx.week_start.isoformat()
    start = time.perf_counter()
    result = fn(ctx, *args, **kwargs)
    duration_s = time.perf_counter() - start
    summary = _step_summary(step, result)
    if summary:
        log.info(
            "week_start=%s %s done duration_s=%.1f %s",
            week,
            step,
            duration_s,
            summary,
        )
    else:
        log.info("week_start=%s %s done duration_s=%.1f", week, step, duration_s)
    return result
