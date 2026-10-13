import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('holdout_driver', Path(__file__).resolve().parents[2]/'scripts/run_frozen_holdout.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def setup_case(tmp_path, monkeypatch):
    source = tmp_path/'source.json'
    source.write_text('{}')
    case = {'id': 'EOG/accession', 'groupId': 'EOG', 'split': 'holdout',
            'sourcePath': str(source), 'sourceSha256': driver.file_hash(source),
            'usedForTuning': False, 'synthetic': False}
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'cases': [case]}))
    baseline = tmp_path/'baseline.json'
    baseline.write_text(json.dumps({'manifestSha256': driver.file_hash(manifest),
        'codeSnapshot': {'sha256': 'frozen'}, 'knownDevelopmentGroups': ['CVX']}))
    monkeypatch.setattr(driver, 'code_snapshot', lambda: {'sha256': 'frozen'})
    return source, manifest, baseline


def test_freeze_and_source_tampering_rejected(tmp_path, monkeypatch):
    source, manifest, baseline = setup_case(tmp_path, monkeypatch)
    assert driver.verify_baseline(manifest, baseline, 'EOG')[0]['groupId'] == 'EOG'
    monkeypatch.setattr(driver, 'code_snapshot', lambda: {'sha256': 'changed'})
    with pytest.raises(ValueError, match='code changed'):
        driver.verify_baseline(manifest, baseline, 'EOG')
    monkeypatch.setattr(driver, 'code_snapshot', lambda: {'sha256': 'frozen'})
    source.write_text('changed')
    with pytest.raises(ValueError, match='evidence changed'):
        driver.verify_baseline(manifest, baseline, 'EOG')


def test_development_issuer_and_existing_output_rejected(tmp_path, monkeypatch):
    source, manifest, baseline = setup_case(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='Development issuer'):
        driver.verify_baseline(manifest, baseline, 'CVX')
    with pytest.raises(ValueError, match='Output exists'):
        driver.run(manifest, baseline, 'EOG', tmp_path)


@pytest.mark.parametrize('reject_first', [True, False])
def test_single_attempt_shared_lock_finance_first_stop_on_rejection(tmp_path, monkeypatch, reject_first):
    source, manifest, baseline = setup_case(tmp_path, monkeypatch)
    monkeypatch.setattr(driver, 'get_settings', lambda: SimpleNamespace(
        llm_provider='ollama', llm_model='orakt-14b:latest',
        llm_base_url='http://127.0.0.1:11434', cold_data_root=tmp_path))
    monkeypatch.setattr(driver, 'load_frozen_packet', lambda *a: (
        {'packet': {'ticker': 'EOG', 'accession': 'accession'}, 'fingerprint': 'frozen'}, b''))
    monkeypatch.setattr(driver.httpx, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'models': [{'name': 'orakt-14b:latest', 'digest': 'model-hash'}]}))
    monkeypatch.setattr(driver, 'cool_down', lambda *a, **k: None)
    monkeypatch.setattr(driver, 'CHAPTERS', ('business', 'financial'))
    acquired, released, calls = [], [], []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def scalar(self, sql, params): acquired.append(params['key']); return True
        def execute(self, sql, params): released.append(params['key'])
    connection = Connection()
    monkeypatch.setattr(driver, 'get_session_factory', lambda: lambda: SimpleNamespace(
        get_bind=lambda: SimpleNamespace(connect=lambda: connection)))
    def writer(source, target, chapter, **kw):
        assert kw['model_connection'] is connection and kw['max_attempts'] == 1
        calls.append(chapter)
        driver.save(target/'progress.json', {'stage': 'repair_required' if reject_first else 'content_review_pending'})
        if not reject_first: driver.save(target/'chapter.json', {'chapter': chapter})
    monkeypatch.setattr(driver, 'write_chapter', writer)
    out = tmp_path/'output'
    result = driver.run(manifest, baseline, 'EOG', out)
    assert calls == (['financial'] if reject_first else ['financial', 'business'])
    assert len(acquired) == 3 and released == list(reversed(acquired[:2]))
    assert not result['published']
    assert ('rejected' in result['state']) == reject_first
    usage = json.loads((out/'usage-summary.json').read_text())
    assert usage['codexInputTokens'] is None
