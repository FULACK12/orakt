"""Run only migration 0047 against a disposable in-memory database."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from app.db.models.earnings_task import EarningsResearchTask


def test_upgrade_matches_model_and_downgrade_is_scoped(monkeypatch):
    path = (
        Path(__file__).parents[1] / "alembic/versions/20261005_0047_add_earnings_research_tasks.py"
    )
    spec = importlib.util.spec_from_file_location("earnings_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE preserved_test_table (id INTEGER PRIMARY KEY)")
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        module.upgrade()
        inspector = inspect(connection)
        assert {c["name"] for c in inspector.get_columns("earnings_research_tasks")} == set(
            EarningsResearchTask.__table__.columns.keys()
        )
        assert {c["name"] for c in inspector.get_indexes("earnings_research_tasks")} == {
            index.name for index in EarningsResearchTask.__table__.indexes
        }
        assert inspector.get_unique_constraints("earnings_research_tasks")[0]["column_names"] == [
            "fingerprint"
        ]
        module.downgrade()
        assert inspect(connection).get_table_names() == ["preserved_test_table"]
    engine.dispose()
