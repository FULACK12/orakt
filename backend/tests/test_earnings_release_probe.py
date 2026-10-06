"""Publication extraction must not confuse dates, clocks, or modification time."""

from app.earnings_release_probe import publication_candidates, retain_release


def test_visible_explicit_timezone_retains_minute_precision():
    result = publication_candidates(
        '<time datetime="2026-08-04T16:15:00">August 04, 2026 4:15 pm EDT</time>'
    )[0]
    assert result["precision"] == "minute"
    assert result["window_start_utc"] == "2026-08-04T20:15:00+00:00"
    assert result["window_end_exclusive_utc"] == "2026-08-04T20:16:00+00:00"


def test_date_and_naive_time_never_become_midnight_or_utc():
    values = publication_candidates(
        '<time datetime="2026-08-04">Aug 4</time>'
        '<time datetime="2026-08-04T16:15:00">4:15</time>'
        '<time datetime="2026">2026</time>'
    )
    assert len(values) == 2
    assert all(value["window_start_utc"] is None for value in values)


def test_modified_and_event_dates_are_not_publication():
    values = publication_candidates(
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"NewsArticle","dateModified":"2026-08-05T12:00:00Z",'
        '"datePublished":"2026-08-04T20:15:00Z"},'
        '{"@type":"Event","datePublished":"2026-08-06T00:00:00Z"}]}</script>'
    )
    assert len(values) == 1
    assert values[0]["window_start_utc"] == "2026-08-04T20:15:00+00:00"


def test_archive_is_not_claimed_to_be_original_version(tmp_path):
    result = retain_release(tmp_path, "TEST", "https://example.com/release", b"fixture")
    assert (tmp_path / result["archive_path"]).read_bytes() == b"fixture"
    assert result["original_historical_version_verified"] is False
    assert result["execution_permitted"] is False
