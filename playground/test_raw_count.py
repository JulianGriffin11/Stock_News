"""Count raw_items in Postgres. Does not hit Yahoo or SEC:

uv run python playground/test_raw_count.py
"""

from sqlalchemy import func, select

from app.db.models import RawItemRow
from app.db.session import session_scope


def run() -> None:
    with session_scope() as session:
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
