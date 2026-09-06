"""CLI: python -m digest ingest | summarize | rank | write-email | run-weekly"""

from __future__ import annotations

import argparse

from app.agent.steps import run_rank, run_summarize, run_write_email
from app.config.settings import Settings
from app.ingest import run_ingest


def run_pipeline(settings: Settings, force: bool = False) -> None:
    print("=== ingest ===")
    run_ingest(settings)
    print("=== summarize ===")
    run_summarize(settings)
    print("=== rank ===")
    run_rank(settings, force=force)
    print("=== write-email ===")
    run_write_email(settings, force=force)
    print("=== done (email stored unsent; send is Phase 5) ===")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ingest",
        help="Fetch Yahoo RSS + SEC filings, write JSON, upsert to Postgres",
    )
    sub.add_parser(
        "summarize",
        help="Summarize unsummarized raw_items into item_summaries",
    )
    rank_parser = sub.add_parser(
        "rank",
        help="Rank this week's summaries onto digest_runs",
    )
    rank_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing digest_run for this week",
    )
    email_parser = sub.add_parser(
        "write-email",
        help="Write the ranked digest email and store it unsent",
    )
    email_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing unsent email for this week",
    )
    run_parser = sub.add_parser(
        "run-weekly",
        help="Ingest → summarize → rank → write-email (does not send)",
    )
    run_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace this week's digest_run and unsent email",
    )
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "ingest":
        run_ingest(settings)
        return 0
    if args.command == "summarize":
        run_summarize(settings)
        return 0
    if args.command == "rank":
        run_rank(settings, force=args.force)
        return 0
    if args.command == "write-email":
        run_write_email(settings, force=args.force)
        return 0
    if args.command == "run-weekly":
        run_pipeline(settings, force=args.force)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
