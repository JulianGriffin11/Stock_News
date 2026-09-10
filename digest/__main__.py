"""CLI: python -m digest ingest | summarize | rank | write-email | send | run-weekly"""

from __future__ import annotations

import argparse

from app.agent import run_rank, run_summarize, run_write_email
from app.config.context import make_context
from app.config.logging import configure_logging, run_timed_step
from app.services import run_ingest, run_send, run_weekly


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digest")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (step details, per-item progress, DB totals)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ingest",
        help="Fetch Yahoo RSS + SEC filings and upsert to Postgres",
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
    send_parser = sub.add_parser(
        "send",
        help="Send this week's stored email via Resend",
    )
    send_parser.add_argument(
        "--force",
        action="store_true",
        help="Send again even if this week already went out",
    )
    run_parser = sub.add_parser(
        "run-weekly",
        help="Ingest → summarize → rank → write-email → send",
    )
    run_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace this week's digest and send again",
    )
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    ctx = make_context()

    if args.command == "ingest":
        run_timed_step(ctx, "ingest", run_ingest)
        return 0
    if args.command == "summarize":
        run_timed_step(ctx, "summarize", run_summarize)
        return 0
    if args.command == "rank":
        run_timed_step(ctx, "rank", run_rank, force=args.force)
        return 0
    if args.command == "write-email":
        run_timed_step(ctx, "write-email", run_write_email, force=args.force)
        return 0
    if args.command == "send":
        run_timed_step(ctx, "send", run_send, force=args.force)
        return 0
    if args.command == "run-weekly":
        run_weekly(ctx, force=args.force)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
