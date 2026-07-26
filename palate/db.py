"""SQLite access. BASE — frozen. Do not edit on a feature branch."""

import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable

from . import config


class Connection(sqlite3.Connection):
    """Transaction context manager that also closes the file descriptor.

    sqlite3.Connection.__exit__ commits or rolls back but, unlike most resource
    context managers, does not close. Every Palate call is short-lived, so
    leaving those handles to the garbage collector leaks descriptors during a
    large inbox backfill.
    """

    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate() -> None:
    """Apply schema.sql. Idempotent — every statement is CREATE ... IF NOT EXISTS."""
    with connect() as conn:
        conn.executescript(config.SCHEMA_PATH.read_text())


def seed() -> int:
    """Load fake visits so B/C/D can work before A's pipeline lands."""
    if not config.SEED_PATH.exists():
        return 0
    with connect() as conn:
        conn.executescript(config.SEED_PATH.read_text())
        return conn.execute("SELECT COUNT(*) FROM visit").fetchone()[0]


def now() -> str:
    """ISO-8601 to the minute, local wall-clock, no timezone. See TRD 3.1."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def rows(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchone()


def scalar(sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
    row = one(sql, params)
    if row is None or row[0] is None:
        return default
    return row[0]


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    with connect() as conn:
        conn.execute(sql, tuple(params))


def executemany(sql: str, seq: Iterable[Iterable[Any]]) -> None:
    with connect() as conn:
        conn.executemany(sql, [tuple(p) for p in seq])


def upsert_visit(visit: dict) -> None:
    """INSERT OR REPLACE — ingest must be re-runnable without duplicating rows."""
    from . import contracts

    payload = dict(visit)
    payload.setdefault("created_at", now())
    if isinstance(payload.get("cuisine"), (list, tuple)):
        payload["cuisine"] = json.dumps(list(payload["cuisine"]))
    cols = contracts.VISIT_FIELDS
    placeholders = ",".join("?" for _ in cols)
    execute(
        f"INSERT OR REPLACE INTO visit ({','.join(cols)}) VALUES ({placeholders})",
        [payload.get(c) for c in cols],
    )


def log_llm_call(
    purpose: str,
    model: str,
    route: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    ok: bool = True,
    error: str | None = None,
) -> None:
    execute(
        "INSERT INTO llm_call (created_at, purpose, model, route, input_tokens,"
        " output_tokens, ok, error) VALUES (?,?,?,?,?,?,?,?)",
        (now(), purpose, model, route, input_tokens, output_tokens, int(ok), error),
    )
