"""Small PostgreSQL transaction locks for cross-service queue scheduling."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Stable signed-bigint keys. These protect only queue creation; the model runtime
# has its own independent lock in ``model_workload.py``.
CLUSTER_QUEUE_LOCK_ID = 22_047_625_517_944_145
RESEARCH_BATCH_QUEUE_LOCK_ID = 22_047_625_517_944_146
DAILY_EQUITY_QUEUE_LOCK_ID = 22_047_625_517_944_147


def acquire_queue_transaction_lock(session: Session, lock_id: int) -> None:
    """Serialize one scheduler transaction across all Docker services.

    SQLite is used by unit tests and local fixtures, where there is only one
    caller. PostgreSQL holds this lock until the surrounding transaction ends.
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    session.scalar(select(func.pg_advisory_xact_lock(lock_id)))
