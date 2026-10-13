"""Bounded, no-tuning holdout generation; never reuse the development runner.

Original request/response/diagnostics are retained; rejection stops the run.
Detector logs stay separate from the blind-review input. No publication or retry.
The driver lives outside app/ so it cannot silently change the frozen detector.
"""
import argparse
from contextlib import redirect_stdout
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.dossier_compact_writer import run as write_chapter
from app.leader_history_batch import cool_down
from app.model_workload import MODEL_WORKLOAD_LOCK_ID
from app.report_quality import CHAPTERS
from app.report_quality_holdout_audit import code_snapshot, file_hash
from app.report_rejections import DEFAULT_POLICY, guard
from app.report_usage import collect_usage, save
from app.review_frozen_dossier import load_frozen_packet


def verify_baseline(manifest_path, baseline_path, ticker):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    if file_hash(manifest_path) != baseline['manifestSha256']:
        raise ValueError('Manifest changed since freeze')
    if code_snapshot()['sha256'] != baseline['codeSnapshot']['sha256']:
        raise ValueError('Frozen application code changed; do not tune on holdout')
    ticker = ticker.strip().upper()
    if ticker in baseline['knownDevelopmentGroups']:
        raise ValueError('Development issuer cannot be used as holdout')
    matches = [c for c in manifest['cases'] if c.get('groupId') == ticker
               and c.get('split') == 'holdout']
    if len(matches) != 1:
        raise ValueError('Exactly one reserved case required')
    case = matches[0]
    if case.get('usedForTuning') is not False or case.get('synthetic') is not False:
        raise ValueError('Case is not an untuned real candidate')
    if file_hash(case['sourcePath']) != case['sourceSha256']:
        raise ValueError('Reserved evidence changed')
    return case, baseline


def run(manifest, baseline_path, ticker, output):
    if output.exists():
        raise ValueError('Output exists; no automatic retry or overwrite')
    case, baseline = verify_baseline(manifest, baseline_path, ticker)
    settings = get_settings()
    if (settings.llm_provider != 'ollama' or settings.llm_model != 'orakt-14b:latest'
            or urlsplit(str(settings.llm_base_url)).hostname not in ('127.0.0.1', 'localhost')):
        raise ValueError('Only the authorized local orakt-14b runtime is allowed')
    source = Path(case['sourcePath'])
    original, _ = load_frozen_packet(source, settings.cold_data_root)
    if original['packet']['ticker'] != case['groupId'] or case['id'] != (
            original['packet']['ticker'] + '/' + original['packet']['accession']):
        raise ValueError('Source identity does not match reserved case')
    endpoint = str(settings.llm_base_url).rstrip('/')
    response = httpx.get(endpoint+'/api/tags', timeout=10)
    response.raise_for_status()
    models = [m for m in response.json()['models'] if m['name'] == settings.llm_model]
    if len(models) != 1:
        raise ValueError('Installed local model not found')
    started = time.monotonic()
    policy = {**DEFAULT_POLICY, 'maxModelRequests': 9, 'maxKnownLocalTokens': 120000,
              'maxWallSeconds': 1800, 'maxAttemptsPerChapter': 1,
              'stopOnFirstRejectedChapter': True}
    state = {'ticker': case['groupId'], 'caseId': case['id'],
             'createdAt': datetime.now(UTC).isoformat(), 'policy': policy,
             'sourceSha256': case['sourceSha256'], 'baselineSha256': file_hash(baseline_path),
             'driverSha256': file_hash(__file__), 'model': settings.llm_model,
             'modelDigest': models[0]['digest'], 'chapters': {},
             'state': 'preparing', 'published': False, 'trainingEnabled': False,
             'independentReview': False, 'automaticApprovalEnabled': False,
             'holdoutCandidate': True, 'usedForTuning': False}
    output.mkdir(parents=True, exist_ok=False)
    save(output/'source.json', original)
    save(output/'frozen-baseline.json', baseline)
    documents = []

    def progress(stage, **extra):
        state.update(state=stage, checkedAt=datetime.now(UTC).isoformat(), **extra)
        save(output/'progress.json', state)

    try:
        with get_session_factory()().get_bind().connect() as connection:
            owned = []
            try:
                for lock_id in (624730015831, 624730015811):
                    if not connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': lock_id}):
                        raise RuntimeError('Existing report worker owns global lock')
                    owned.append(lock_id)
                if not connection.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': MODEL_WORKLOAD_LOCK_ID}):
                    raise RuntimeError('Local model busy')
                # Finance first: failed prerequisite stops before spending on
                # downstream interpretation. The rest retain the fixed template.
                order = ('financial', *(k for k in CHAPTERS if k != 'financial'))
                for index, chapter in enumerate(order):
                    usage = collect_usage(output/'drafts')
                    if (usage['callCount'] >= policy['maxModelRequests']
                            or usage['inputTokensKnown'] + usage['outputTokensKnown'] >= policy['maxKnownLocalTokens']
                            or time.monotonic() - started >= policy['maxWallSeconds']):
                        progress('budget_stopped'); break
                    guard(output, chapter)
                    def cooled(stage, **extra):
                        if time.monotonic() - started >= policy['maxWallSeconds']:
                            raise TimeoutError('Holdout wall budget exhausted during cooling')
                        progress(stage, **extra)
                    cool_down(output, cooled, seconds=15 if index else 0)
                    verify_baseline(manifest, baseline_path, ticker)
                    progress('generating', activeChapter=chapter)
                    target = output/'drafts'/chapter/'revision-1'
                    # Keep automated findings out of the blind reviewer context.
                    with (output/'detector-output.log').open('a', encoding='utf-8') as log, redirect_stdout(log):
                        write_chapter(source, target, chapter, redact_numbers=False,
                                      reasoning=True, max_attempts=1,
                                      rejection_root=output, model_connection=connection)
                    local = json.loads((target/'progress.json').read_text(encoding='utf-8'))
                    state['chapters'][chapter] = {'generationState': local['stage']}
                    accepted = target/'chapter.json'
                    if not accepted.exists():
                        progress('rejected_frozen_sample_pending_blind_review', activeChapter=None)
                        break
                    documents.append(json.loads(accepted.read_text(encoding='utf-8')))
                    progress('chapter_retained', activeChapter=None)
                else:
                    progress('frozen_draft_pending_blind_review', activeChapter=None)
            finally:
                for lock_id in reversed(owned):
                    connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': lock_id})
    except Exception as exc:
        progress('stopped', errorType=type(exc).__name__, error=str(exc)[:500])
    finally:
        save(output/'draft-report.json', {'caseId': case['id'], 'chapters': documents,
             'complete': len(documents) == len(CHAPTERS), 'published': False,
             'state': 'pending_blind_review', 'sourceFingerprint': original['fingerprint']})
        save(output/'usage-summary.json', {**collect_usage(output/'drafts'),
             'trialWallSeconds': round(time.monotonic()-started, 3),
             'scopeNote': 'Frozen evaluation generation only; Codex usage unknown. Rejected raw responses are retained, not approved chapters.'})
    return {'state': state['state'], 'retainedChapters': len(documents), 'published': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--ticker', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.baseline, args.ticker, args.output)))
