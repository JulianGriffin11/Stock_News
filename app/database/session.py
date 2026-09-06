"""Postgres engine + session for Supabase."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = settings or Settings()
        _engine = create_engine(settings.require_database_url(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    get_engine(settings)
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
