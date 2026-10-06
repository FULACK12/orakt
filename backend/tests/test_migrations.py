"""Alembic migration smoke tests."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.db import models  # noqa: F401
from app.db.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "sources",
    "documents",
    "events",
    "event_documents",
    "rss_feeds",
    "cluster_jobs",
    "cluster_review_decisions",
    "document_analyses",
    "economic_indicators",
    "country_profiles",
    "economic_observations",
    "economic_sync_states",
    "administrative_areas",
    "regional_indicators",
    "regional_observations",
    "event_relation_candidates",
    "logic_chain_hypotheses",
    "logic_chain_review_signals",
    "energy_series",
    "energy_observations",
    "energy_sync_states",
    "conflict_aggregate_observations",
    "conflict_aggregate_sync_states",
    "conflict_country_indicator_observations",
    "research_inquiries",
    "research_review_signals",
    "research_batches",
    "research_batch_items",
    "research_report_audit_jobs",
    "market_series",
    "market_observations",
    "market_daily_bars",
    "market_sync_states",
    "market_asset_lifecycles",
    "market_price_backfill_states",
    "market_asset_identifiers",
    "market_delisting_outcomes",
    "market_delisting_evidence_states",
    "market_delisting_evidence_candidates",
    "market_lifecycle_resolutions",
    "market_terminal_cashflows",
    "company_profiles",
    "company_filings",
    "company_financial_facts",
    "company_sync_states",
    "china_disclosure_sync_states",
    "gdelt_archive_states",
    "gdelt_event_aggregates",
    "company_institutional_holdings",
    "institutional_archive_states",
    "company_insider_filing_states",
    "company_insider_transactions",
    "company_supply_chain_edges",
    "company_supply_chain_coverage",
    "company_supply_chain_sites",
    "entry_calibration_runs",
    "entry_horizon_forecasts",
    "entry_horizon_outcomes",
    "entry_outcome_evaluations",
    "entry_parameter_candidates",
    "entry_parameter_candidate_reviews",
    "external_training_examples",
    "factor_experiments",
    "factor_experiment_outcomes",
    "task_control_records",
}


def test_initial_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-test.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    for table_name in EXPECTED_TABLES - {"alembic_version"}:
        migrated_columns = {column["name"] for column in inspector.get_columns(table_name)}
        model_columns = set(Base.metadata.tables[table_name].columns.keys())
        assert migrated_columns == model_columns

    command.downgrade(config, "base")

    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
