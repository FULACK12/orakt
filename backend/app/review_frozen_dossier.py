"""Explicit assistant revision against immutable historical inputs, without re-generation.

Changing generator versions never overwrites old checkpoints or silently refreshes
historical evidence. Every original attempt is hashed into the revision manifest.
"""
import argparse
import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import urlsplit, unquote
from app.company_history_dossier import CHAPTERS, Section, VERSION, validate_section, write_json
from app.dossier_accounting_checks import disclosed_product_terms, gross_margin_checks
from app.financial_period_ledger import build_ledger
from app.dossier_event_timeline import validate_timeline


def load_frozen_packet(source_path, cold_root):
    raw = source_path.read_bytes()
    original = json.loads(raw)
    packet = original['packet']
    expected = hashlib.sha256(json.dumps({'version': original['version'], 'packet': packet}, sort_keys=True).encode()).hexdigest()
    if original.get('fingerprint') != expected:
        raise ValueError('Frozen packet fingerprint mismatch')
    base = (cold_root / 'raw/sec/company-filings' / packet['ticker']).resolve()
    filing = (base / packet['accession'].replace('-', '') / unquote(urlsplit(packet['source_url']).path.rsplit('/', 1)[-1])).resolve()
    if not filing.is_relative_to(base) or hashlib.sha256(filing.read_bytes()).hexdigest() != packet['raw_sha256']:
        raise ValueError('Archived filing hash mismatch')
    if build_ledger(packet) != packet['financial_ledger']:
        raise ValueError('Frozen ledger no longer reproduces; review the evidence revision separately')
    return original, raw


def assemble(source_path, review_path, cold_root):
    original, raw = load_frozen_packet(source_path, cold_root)
    packet, expected = original['packet'], original['fingerprint']
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if review.get('reviewer') != 'codex_assistant' or review.get('ticker') != packet['ticker'] or review.get('asOf') != packet['as_of_date'] or not review.get('corrections'):
        raise ValueError('Explicit matching assistant review required')
    if set(review.get('chapters', {})) != {c[0] for c in CHAPTERS}:
        raise ValueError('Every chapter must be explicitly reviewed')
    allowed = {packet['filing_ref'], *(f['evidence_id'] for f in packet['facts']), *(s['id'] for s in packet.get('market_evidence', []))}
    required = [c['id'] for c in packet['financial_ledger']['comparisons'] if c['concept'] in {'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'GrossProfit', 'OperatingIncomeLoss', 'NetCashProvidedByUsedInOperatingActivities'} and c['periodType'] != 'instant']
    chapters, attempts = [], []
    for i, (key, zh, en) in enumerate(CHAPTERS, 1):
        paths = sorted(source_path.parent.glob(f'{i:02d}-{key}*.json'))
        paths = [p for p in paths if '.assistant-reviewed.' not in p.name]
        if not paths:
            raise ValueError(f'No retained local-model draft for {key}; do not misattribute assistant-only work')
        attempts.extend({'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths)
        section = Section.model_validate(review['chapters'][key])
        validate_section(section, allowed, packet['financial_ledger'], required if key in {'financial', 'conclusion'} else (), disclosed_product_terms(packet['excerpts']))
        chapters.append({'key': key, 'title': {'zh': zh, 'en': en}, 'authorship': 'assistant_revised', **section.model_dump()})
    return {'version': VERSION, 'fingerprint': expected, 'ticker': packet['ticker'], 'asOf': packet['as_of_date'], 'periodEnd': packet['period_end'], 'createdAt': datetime.now(UTC).isoformat(),
        'model': review['localModel'], 'chapters': chapters, 'facts': packet['facts'], 'financialLedger': packet['financial_ledger'], 'ratioChecks': gross_margin_checks(packet['financial_ledger']),
        'sources': [{'id': packet['filing_ref'], 'url': packet['source_url']}], 'marketEvidence': packet.get('market_evidence', []), 'eventTimeline':validate_timeline(review.get('eventTimeline',[]),packet),
        'provenance': {'parentVersion': original['version'], 'continuation': original.get('continuation'), 'sourcePacketHash': hashlib.sha256(raw).hexdigest(), 'sourceDocumentHash': packet['raw_sha256'], 'retainedDrafts': attempts, 'method': 'explicit_assistant_revision_of_frozen_local_drafts'},
        'review': {'state': 'content_review_pending', 'citationCheck': 'passed', 'humanAccepted': False, 'assistantRevisionHash': hashlib.sha256(review_bytes).hexdigest()}, 'eligibleForPredictiveBacktest': False}


def run(source, review, cold_root, output):
    if output.exists():
        raise ValueError('Revision output already exists; preserve it and use a new revision path')
    dossier = assemble(source, review, cold_root)
    write_json(output, dossier)
    print(json.dumps({'ticker': dossier['ticker'], 'chapters': len(dossier['chapters']), 'state': dossier['review']['state'], 'output': str(output)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ['source', 'review', 'cold-root', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.source, a.review, a.cold_root, a.output)
