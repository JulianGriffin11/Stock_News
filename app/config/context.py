"""Shared state for one pipeline run (CLI command or run-weekly)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.config.settings import Settings

if TYPE_CHECKING:
    from app.db.models import DigestRunRow


@dataclass
class PipelineContext:
    settings: Settings
    week_start: date
    digest_run: DigestRunRow | None = None

    def resolve_digest_run(self, *, refresh: bool = False) -> DigestRunRow | None:
        """Return the in-memory digest_run, or load it from Postgres once."""
        if refresh or self.digest_run is None:
            from app.db.queries import get_run_for_week

            self.digest_run = get_run_for_week(self.week_start)
        return self.digest_run


def make_context(settings: Settings | None = None) -> PipelineContext:
    settings = settings or Settings()
    return PipelineContext(settings=settings, week_start=settings.week_start())
