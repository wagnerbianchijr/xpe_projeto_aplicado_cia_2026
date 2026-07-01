"""Read-only Tiger Cloud access: connection pool + a thin fetch helper."""
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def configure(conn) -> None:
    """Pool configure callback: force read-only + dict rows on every connection."""
    conn.read_only = True
    conn.row_factory = dict_row


def create_pool(database_url: str) -> ConnectionPool:
    """Open a small read-only pool. connect_timeout keeps startup from hanging."""
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        kwargs={"connect_timeout": 5},
        configure=configure,
        open=True,
    )


class SupportsFetch(Protocol):
    def fetch(self, query: Any, params: Any = None) -> list[dict]: ...


class Database:
    """Executes read-only queries against a pooled connection."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def fetch(self, query: Any, params: Any = None) -> list[dict]:
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


class FakeDatabase:
    """Test double: returns canned responses in call order."""

    def __init__(self, responses: list[list[dict]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple] = []

    def fetch(self, query: Any, params: Any = None) -> list[dict]:
        self.calls.append((query, params))
        return self._responses.pop(0)
