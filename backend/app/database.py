import oracledb
from .config import settings

_pool: oracledb.ConnectionPool | None = None


def init_pool() -> None:
    global _pool
    _pool = oracledb.create_pool(
        user=settings.db_user,
        password=settings.db_pass,
        dsn=settings.db_dsn,
        min=settings.db_pool_min,
        max=settings.db_pool_max,
    )


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.close()
        _pool = None


def get_conn() -> oracledb.Connection:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool.acquire()
