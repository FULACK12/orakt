"""Exercise local CLI without opening production connections."""

import json
from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app import earnings_tasks_cli
from app.db.models.earnings_task import EarningsResearchTask


@pytest.fixture
def request_file(tmp_path):
    values = {
        "event": {
            "issuer_id": "test",
            "security_id": "test",
            "ticker": "TEST",
            "exchange": "TEST",
            "event_id": "e1",
            "fiscal_period": "2025Q1",
            "actual_release_at": "2025-04-01T20:00:00Z",
            "release_time_precision": "exact",
        },
        "cutoffs": {
            "pre_earnings_at": "2025-04-01T19:00:00Z",
            "release_at": "2025-04-01T20:00:00Z",
            "post_earnings_validation_at": "2025-04-02T20:00:00Z",
            "post_session_verified": True,
        },
        "versions": {"model_version": "m1", "template_version": "t1", "factor_version": "f1"},
        "evidence": [
            {
                "id": "d1",
                "available_at": "2025-04-01T18:00:00Z",
                "version": "v1",
                "content_sha256": sha256(b"synthetic").hexdigest(),
                "kind": "fixture",
            }
        ],
        "documents": [{"id": "d1", "text": "synthetic", "source_url": "https://example.com/doc"}],
        "release_source_url": "https://example.com/release",
    }
    path = tmp_path / "synthetic-request.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_cli_enqueue_status_cancel(monkeypatch, request_file, capsys):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    EarningsResearchTask.__table__.create(engine)
    monkeypatch.setattr(earnings_tasks_cli, "get_session_factory", lambda: sessionmaker(engine))
    assert earnings_tasks_cli.main(["--enqueue", str(request_file)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output["task_ids"]) == 3
    assert output["execution_permitted"] is False
    assert earnings_tasks_cli.main(["--status"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 3
    assert earnings_tasks_cli.main(["--cancel", str(output["task_ids"][0])]) == 0
    assert json.loads(capsys.readouterr().out)["cancelled"] is True
    engine.dispose()


def test_cli_redacts_connection_error(monkeypatch, capsys):
    def unavailable():
        raise OperationalError("secret_connection_url", {}, Exception("password"))

    monkeypatch.setattr(earnings_tasks_cli, "get_session_factory", unavailable)
    assert earnings_tasks_cli.main(["--status"]) == 2
    output = capsys.readouterr().out
    assert "secret_connection_url" not in output and "password" not in output
    assert "database_unavailable_or_migration_required" in output


def test_cli_rejects_unknown_fields_before_database(monkeypatch, request_file, capsys):
    payload = json.loads(request_file.read_text())
    payload["now"] = "2099-01-01T00:00:00Z"
    request_file.write_text(json.dumps(payload))

    def forbidden():
        pytest.fail("invalid input must not open database")

    monkeypatch.setattr(earnings_tasks_cli, "get_session_factory", forbidden)
    assert earnings_tasks_cli.main(["--enqueue", str(request_file)]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_input"


def test_duplicate_json_fields_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"event": {}, "event": {}}')
    with pytest.raises(ValueError, match="duplicate_field"):
        earnings_tasks_cli.load_request(path)
