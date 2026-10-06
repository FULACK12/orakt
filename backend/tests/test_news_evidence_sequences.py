"""Connected-news evidence sequence tests."""

from app.research_evidence import build_news_evidence_sequences


def test_related_dated_reports_are_linked_without_claiming_causality() -> None:
    sequences = build_news_evidence_sequences(
        [
            {
                "evidence_id": "document:1",
                "title": "Central bank raises policy rate after inflation report",
                "excerpt": "The central bank raised its policy rate as inflation persisted.",
                "published_at": "2026-01-10T10:00:00+00:00",
                "source": "Official bulletin",
                "source_url": "https://example.test/1",
                "can_verify_claims": True,
                "content_storage": "cold",
            },
            {
                "evidence_id": "document:2",
                "title": "Central bank policy rate decision lifts bond yields",
                "excerpt": "Bond yields rose after the central bank policy rate decision.",
                "published_at": "2026-01-11T12:00:00+00:00",
                "source": "Market report",
                "source_url": "https://example.test/2",
                "can_verify_claims": True,
                "content_storage": "hot",
            },
        ],
        focus="central bank policy rate bond yields",
    )

    assert len(sequences) == 1
    assert sequences[0]["causal_status"] == "chronology_only_until_validated"
    assert [item["relation"] for item in sequences[0]["entries"]] == [
        "initial_report",
        "latest_report",
    ]
    assert sequences[0]["entries"][0]["content_storage"] == "cold"
