import hashlib
import json
import pytest
from app.leader_latest_queue import project_packet


def source():
    return {'version': 'test', 'packet': {'ticker': 'AMZN',
        'period_end': '2026-06-30', 'as_of_date': '2026-07-30',
        'facts': [{'filed_at': '2026-07-30', 'period_end': '2026-06-30'}],
        'market_evidence': [{'id': 'unknown-vintage'}]}}


def test_projection_preserves_original_and_rehashes():
    original = source()
    result, excluded = project_packet(original)
    assert excluded == 1
    assert original['packet']['market_evidence'] == [{'id': 'unknown-vintage'}]
    assert result['packet']['market_evidence'] == []
    assert result['packet']['facts'] == original['packet']['facts']
    assert result['fingerprint'] == hashlib.sha256(json.dumps(
        {'version': result['version'], 'packet': result['packet']}, sort_keys=True).encode()).hexdigest()


def test_future_facts_still_fail_closed():
    original = source()
    original['packet']['facts'][0]['filed_at'] = '2026-08-01'
    with pytest.raises(ValueError, match='future fact'):
        project_packet(original)
