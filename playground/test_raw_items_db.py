"""Count raw_items in Postgres. Does not hit Yahoo or SEC.

Run from the repo root after `uv run alembic upgrade head`:

    uv run python playground/test_raw_items_db.py
"""

from sqlalchemy import func, select

from app.config.settings import Settings
from app.database.models import RawItemRow
from app.database.session import session_scope


def run() -> None:
    settings = Settings()
    with session_scope(settings) as session:
        total = session.scalar(select(func.count()).select_from(RawItemRow)) or 0
        by_source = session.execute(
            select(RawItemRow.source, func.count())
            .group_by(RawItemRow.source)
            .order_by(RawItemRow.source)
        ).all()
    print(f"raw_items: {total}")
    for source, count in by_source:
        print(f"  {source}: {count}")


if __name__ == "__main__":
    run()
