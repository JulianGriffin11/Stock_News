"""CLI: python -m digest ingest"""

from __future__ import annotations

import argparse

from app.config.settings import Settings
from app.ingest import run_ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "ingest",
        help="Fetch Yahoo RSS + SEC filings into data/raw_items.json",
    )
    args = parser.parse_args(argv)

    if args.command == "ingest":
        run_ingest(Settings())
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
