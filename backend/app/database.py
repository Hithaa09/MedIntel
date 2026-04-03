from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

from .config import settings

_pool: pool.SimpleConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = pool.SimpleConnectionPool(
        settings.db_pool_min,
        settings.db_pool_max,
        settings.database_url,
    )


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
