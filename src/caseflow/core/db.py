from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from caseflow.core.settings import Settings, get_settings


def get_engine(settings: Settings | None = None) -> str:
    active_settings = settings or get_settings()
    return active_settings.postgres_dsn


@contextmanager
def get_conn(settings: Settings | None = None) -> Generator[Connection, None, None]:
    dsn = get_engine(settings)
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield conn
