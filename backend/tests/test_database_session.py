"""Database engine and request-session tests."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.db import session as session_module


def test_session_factory_uses_configured_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'session.sqlite3').as_posix()}"
    test_settings = SimpleNamespace(database_url=database_url, database_echo=False)
    monkeypatch.setattr(session_module, "get_settings", lambda: test_settings)
    session_module.get_engine.cache_clear()
    session_module.get_session_factory.cache_clear()

    engine = session_module.get_engine()
    dependency = session_module.get_db_session()
    database_session = next(dependency)

    try:
        assert engine.dialect.name == "sqlite"
        assert isinstance(database_session, Session)
        assert database_session.bind is engine
    finally:
        dependency.close()
        engine.dispose()
        session_module.get_session_factory.cache_clear()
        session_module.get_engine.cache_clear()

