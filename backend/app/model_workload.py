"""Cross-process ownership for the single local-model runtime."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# Stable signed-bigint advisory-lock key for "NEWSMAP".
MODEL_WORKLOAD_LOCK_ID = 22_047_625_517_944_144


@contextmanager
def local_model_workload_lock(session: Session) -> Iterator[bool]:
    """Try to own Ollama work without blocking the database connection."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        yield True
        return

    lock_connection = bind.connect() if isinstance(bind, Engine) else bind
    transaction = lock_connection.begin() if isinstance(bind, Engine) else None
    acquired = bool(
        lock_connection.scalar(select(func.pg_try_advisory_xact_lock(MODEL_WORKLOAD_LOCK_ID)))
    )
    try:
        yield acquired
    finally:
        # A transaction-scoped advisory lock is released by commit/rollback even
        # if a worker is interrupted before it can explicitly unlock. This avoids
        # a pooled PostgreSQL connection retaining a stale session lock and making
        # every later research item appear to wait forever.
        if transaction is not None:
            transaction.rollback()
        if isinstance(bind, Engine):
            lock_connection.close()
