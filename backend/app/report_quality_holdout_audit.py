"""Metadata-only readiness audit. Never label, generate, tune, or approve reports.

The immutable receipt binds source bytes, evaluator policy and application code.
It is a prospective baseline, NOT proof that the candidates were never exposed.
Example: python -m app.report_quality_holdout_audit --manifest <manifest.json>
 --cold-root <archive> --output <new-directory> --development-group CVX
"""
import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.report_quality import rules_digest
from app.report_quality_evaluation import POLICY, evaluate, group_key
from app.report_usage import digest, save


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def code_snapshot(root=None):
    # Hash all app Python modules, not just the core checker: scoped guards and
    # adapters must not silently change between freezing and measured execution.
    root = Path(root) if root else Path(__file__).parent
    files = {p.relative_to(root).as_posix(): file_hash(p)
             for p in sorted(root.rglob('*.py'))}
    return {'files': files, 'sha256': digest(files)}


def audit(manifest_path, cold_root, output, development_groups=()):
    started = time.monotonic()
    manifest_path, cold_root, output = map(Path, (manifest_path, cold_root, output))
    if output.exists():
        raise ValueError('Preserve previous audit; output must be new')
    if not cold_root.is_dir():
        raise ValueError('Cold archive unavailable')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    candidates = [c for c in manifest['cases'] if c['split'] == 'holdout']
    development = {group_key(c) for c in manifest['cases']
                   if c['split'] != 'holdout' or c.get('usedForTuning')}
    development.update(g.strip().upper() for g in development_groups)
    queues = sorted(p for p in cold_root.glob('leader-*') if p.is_dir())
    rows = []
    for case in candidates:
        reasons = []
        issuer = group_key(case)
        parts = case['id'].split('/')
        # Identifiers enter path discovery; reject traversal instead of probing
        # paths outside the intended archive.
        if (len(parts) != 2 or parts[0].strip().upper() != issuer
                or not re.fullmatch(r'[A-Z0-9.\-]+', issuer)
                or not re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}', parts[-1])):
            raise ValueError('Invalid candidate identity: ' + case['id'])
        if issuer in development:
            reasons.append('development_issuer_exposure')
        path = Path(case['sourcePath'])
        actual = file_hash(path) if path.is_file() else None
        if actual != case.get('sourceSha256') or not actual:
            reasons.append('source_missing_or_hash_mismatch')
        # Inventory paths only; do not open holdout prose during rule development.
        artifacts = sorted({str(p) for queue in queues
                            for p in (queue/'drafts'/issuer).glob('**/*.json')})
        chapter_paths = [p for p in artifacts if Path(p).name in
                         ('chapter.json', 'reviewed-chapter.json')]
        if not chapter_paths:
            reasons.append('no_chapter_draft_in_scanned_queues')
        if case.get('labelStatus') != 'independently_adjudicated':
            reasons.append('independent_labels_missing')
        rows.append({'id': case['id'], 'groupId': issuer, 'stratum': case['stratum'],
                     'sourcePath': str(path), 'sourceSha256': actual,
                     'sourceHashMatches': bool(actual and actual == case.get('sourceSha256')),
                     'knownDevelopmentExposure': issuer in development,
                     'proseOpened': False, 'draftArtifactPaths': artifacts,
                     'chapterDraftCount': len(chapter_paths), 'blockers': reasons,
                     'eligibleForQualityMeasurement': False})
    snapshot = code_snapshot()
    baseline = {'createdAt': datetime.now(UTC).isoformat(),
                'manifestSha256': file_hash(manifest_path),
                'codeSnapshot': snapshot, 'policy': POLICY, 'policySha256': digest(POLICY),
                'rulesetSha256': rules_digest(),
                'oldManifestRulesetMatchesCurrent': manifest.get('rulesetSha256') == rules_digest(),
                'knownDevelopmentGroups': sorted(development),
                'scope': 'Prospective freeze only; old manifest and missing labels are not re-certified.'}
    summary = {'state': 'holdout_readiness_audited_not_quality_evaluated',
               'candidateCount': len(rows),
               'verifiedSourceFiles': sum(r['sourceHashMatches'] for r in rows),
               'candidatesWithChapterDrafts': sum(r['chapterDraftCount'] > 0 for r in rows),
               'strata': dict(Counter(r['stratum'] for r in rows)),
               'missingStrata': sorted(set(POLICY['requiredStrata']) - {r['stratum'] for r in rows}),
               'scannedQueues': [str(p) for p in queues],
               'discoveryLimit': 'Only drafts/<issuer> JSON paths in leader-* queues. Other archives and prior threads are not proven unexposed.',
               'baselineSha256': digest(baseline), 'candidates': rows,
               'measurement': evaluate(manifest, []),
               'localModelCalls': 0, 'localModelTokens': 0, 'codexTokens': None,
               'elapsedSeconds': round(time.monotonic() - started, 3),
               'automaticApprovalEnabled': False, 'published': False,
               'next': 'Generate frozen drafts with no tuning on these issuers; obtain evidence-bound labels without detector output, then measure against this baseline. If used to fix rules, retire the affected issuer from holdout.'}
    output.mkdir(parents=True, exist_ok=False)
    save(output/'baseline.json', baseline)
    save(output/'summary.json', summary)
    return {k: v for k, v in summary.items() if k not in ('candidates', 'scannedQueues', 'measurement')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--cold-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--development-group', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(audit(args.manifest, args.cold_root, args.output,
                           args.development_group), ensure_ascii=False))
