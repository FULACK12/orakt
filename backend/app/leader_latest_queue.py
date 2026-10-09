"""Adapt the frozen latest-leader plan to the cooled nine-chapter worker.

Never overwrite source packets or promote generated drafts to approved reports.
Unknown-vintage market observations stay in the parent archive, not in an
as-of report's evidence input.
"""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.company_history_dossier import write_json
from app.core.config import get_settings
from app.dossier_backfill_pilot import ready_packet
from app.leader_history_batch import temporal_check, sha
from app.leader_report_batch import now
from app.review_frozen_dossier import load_frozen_packet


def project_packet(original):
    result = copy.deepcopy(original)
    packet = result['packet']
    excluded = packet.pop('market_evidence', [])
    packet['market_evidence'] = []
    temporal_check(packet)
    result['fingerprint'] = hashlib.sha256(json.dumps(
        {'version': result['version'], 'packet': packet}, sort_keys=True).encode()).hexdigest()
    return result, len(excluded)


def prepare(plan_path, root):
    if root.exists():
        raise ValueError('Preserve previous queue; run/resume it instead')
    parent = json.loads(plan_path.read_text(encoding='utf-8'))
    items = []
    for item in parent['items']:
        # CN table reconciliation and already reviewed reports retain their
        # existing state outside this GPU queue.
        if item['marketRegion'] != 'us' or item['state'] != 'ready_for_generation':
            continue
        current = copy.deepcopy(item)
        source = Path(item['sourcePath'])
        try:
            if sha(source) != item['sourceSha256']:
                raise ValueError('Parent source hash changed')
            original, _ = load_frozen_packet(source, get_settings().cold_data_root)
            packet = original['packet']
            if (packet['ticker'], packet['accession'], packet['period_end']) != (
                    item['ticker'], item['accession'], item['periodEnd']):
                raise ValueError('Parent company/filing identity mismatch')
            projected, excluded = project_packet(original)
            current['readiness'] = ready_packet(projected['packet'])
            target = root/'packets'/item['ticker']/item['accession']/'source.json'
            write_json(target, projected)
            load_frozen_packet(target, get_settings().cold_data_root)
            current.update(sourcePath=str(target), sourceSha256=sha(target),
                parentSourcePath=str(source), parentSourceSha256=item['sourceSha256'],
                excludedUnknownVintageMarketSeries=excluded)
        except (ValueError, OSError) as exc:
            current.update(state='waiting_evidence', reason=str(exc)[:500])
        items.append(current)
    result = {'version': 'leader-latest-cooled/v1', 'createdAt': now(),
        'cutoff': parent['cutoff'], 'parentPlanPath': str(plan_path),
        'parentPlanSha256': sha(plan_path), 'items': items,
        'scope': 'Existing US leaders, latest frozen filing only; no new ranking',
        'sourcePolicy': 'Original filing unchanged; unknown-vintage market series excluded, not fabricated',
        'template': 'company-periodic/v1', 'published': False,
        'summary': dict(Counter(i['state'] for i in items))}
    write_json(root/'plan.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.plan, a.root)['summary']))
