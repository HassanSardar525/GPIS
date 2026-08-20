"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@lru_cache(maxsize=4)
def engine_for(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, future=True)


def session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(engine_for(database_url), expire_on_commit=False)
