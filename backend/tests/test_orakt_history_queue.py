from app.orakt_history_queue import connect, snapshot


def test_queue_insert_is_idempotent_and_status_is_not_fake_percentage(tmp_path):
    with connect(tmp_path) as db:
        for _ in range(2):
            db.execute("INSERT OR IGNORE INTO jobs(accession,ticker,as_of,period_end) VALUES(?,?,?,?)", ("fixture", "TEST", "2020-01-01", "2019-12-31"))
    status = snapshot(tmp_path)
    assert status["counts"] == {"queued": 1}
    assert status["active"] == []
    assert status["worker"] == {}
    assert status["pauseRequested"] is False
    (tmp_path / "pause").touch()
    assert snapshot(tmp_path)["pauseRequested"] is True
