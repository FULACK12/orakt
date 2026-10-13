"""Measured local usage, never inferred Codex billing. Rebuildable sidecars."""
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def collect_usage(directory):
    """Each path is a call, not each output hash: identical retries still cost.

    A retained partial + terminal response with the same attempt basename is
    one call. Missing counters are unknown, never zero. No cached-token guess.
    """
    directory = Path(directory)
    calls = []; preflight = []
    for path in sorted(directory.rglob('attempt-*.json')):
        if path.name.endswith('-partial.json') and path.with_name(path.name.replace('-partial', '')).exists():
            continue
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or 'message' not in raw:
            continue
        if raw.get('oraktInput',{}).get('networkStarted') is False:
            preflight.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                              'reason':'Stopped before network request; no model invocation'})
            continue
        measured = lambda k: raw[k] if isinstance(raw.get(k), int) and raw[k] >= 0 else None
        calls.append({
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'model': raw.get('model'), 'createdAt': raw.get('created_at'),
            'inputTokens': measured('prompt_eval_count'), 'outputTokens': measured('eval_count'),
            'modelSeconds': raw['total_duration'] / 1e9 if measured('total_duration') is not None else None,
            'requestWallSeconds': raw.get('oraktTiming', {}).get('wallSeconds', raw.get('elapsedSeconds')),
            'complete': raw.get('done') is True and raw.get('done_reason') != 'length',
            'validation': 'see retained chapter progress; completion is not quality approval',
        })
    known = lambda k: sum(c[k] for c in calls if c[k] is not None)
    return {
        'version': 'report-usage/v1', 'recordedAt': datetime.now(UTC).isoformat(),
        'calls': calls, 'callCount': len(calls), 'preflightRejections':preflight,
        'inputTokensKnown': known('inputTokens'), 'outputTokensKnown': known('outputTokens'),
        'missingTokenCounters': sum(c['inputTokens'] is None or c['outputTokens'] is None for c in calls),
        'modelSecondsKnown': round(known('modelSeconds'), 3),
        'requestWallSecondsKnown': round(known('requestWallSeconds'), 3),
        'codexInputTokens': None, 'codexOutputTokens': None, 'codexQuotaUsed': None,
        'reviewWallSeconds': None, 'publicationWallSeconds': None,
        'scope': 'Local calls under this directory only; cooling, review, publication and earlier revisions elsewhere excluded. Unknown is not zero.',
    }


def write_usage(directory, **identity):
    result = {**collect_usage(directory), **identity}
    save(Path(directory) / 'usage-summary.json', result)
    return result


def stage_event(directory, stage, started, *, outcome, identity=None, measured_tokens=None):
    """Unique, append-only stage receipt. Never insert model-estimated tokens."""
    row = {'version': 'report-stage/v1', 'stage': stage, 'outcome': outcome,
           'at': datetime.now(UTC).isoformat(), 'wallSeconds': round(time.monotonic() - started, 3),
           'identity': identity or {}, 'measuredTokens': measured_tokens,
           'scope': 'This instrumented operation only; excludes prior interactive review time.'}
    path = Path(directory) / 'usage-events' / (str(time.time_ns()) + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(row, f, ensure_ascii=False, indent=2)
    return row
