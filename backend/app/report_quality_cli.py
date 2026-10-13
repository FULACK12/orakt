"""Offline review handoff. No GPU, publication, approval or original overwrites.

python -m app.report_quality_cli --source source.json --chapters ... --output new-dir
Optional --receipts existing-receipts.json, --decisions explicit-decisions.json,
--patches scoped-patches.json. Existing frozen-source integrity checks run first.
"""
import argparse
import json
import time
from pathlib import Path
from app.report_quality import worklist, accept_receipts, repair
from app.report_usage import save, stage_event


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--chapters', type=Path, nargs='+', required=True)
    p.add_argument('--cold-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--receipts', type=Path)
    p.add_argument('--decisions', type=Path)
    p.add_argument('--patches', type=Path)
    p.add_argument('--complete', action='store_true')
    a = p.parse_args()
    if a.output.exists():
        p.error('Output must be new; preserve original drafts and audits')
    started = time.monotonic()
    from app.review_frozen_dossier import load_frozen_packet
    original, _ = load_frozen_packet(a.source, a.cold_root)
    read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
    docs = [read(path) for path in a.chapters]
    if any(d.get('sourceFingerprint') != original['fingerprint'] for d in docs):
        p.error('Chapter frozen-source fingerprint mismatch')
    receipts = read(a.receipts) if a.receipts else []
    plan = worklist(original['packet'], docs, receipts=receipts, complete=a.complete)
    if a.decisions:
        imported = accept_receipts(plan, read(a.decisions))
        retained = {r['id']: r for r in receipts}
        retained.update({r['id']: r for r in imported})
        receipts = list(retained.values())
        plan = worklist(original['packet'], docs, receipts=receipts, complete=a.complete)
    if a.patches:
        result = repair(original['packet'], docs, read(a.patches))
        save(a.output/'repair.json', result)
        plan = worklist(original['packet'], result['documents'], receipts=receipts, complete=a.complete)
        # The existing chapter validator still applies before any approval.
        from app.company_history_dossier import Section, validate_section
        from app.dossier_accounting_checks import disclosed_reference_terms
        from app.dossier_passages import check_claims
        from app.report_quality import passages
        packet = original['packet']; ps = list(passages(packet).values())
        for d in result['documents']:
            s = Section.model_validate(d['section'])
            validate_section(s,{packet['filing_ref'],*(p['id'] for p in ps)},packet['financial_ledger'],
                             technical_terms=disclosed_reference_terms(packet))
            check_claims(s.grounded_claims,ps,required=True)
    save(a.output/'semantic-worklist.json', plan)
    save(a.output/'receipts.json', receipts)
    save(a.output/'inputs.json', {'source':str(a.source),'chapters':[str(p) for p in a.chapters]})
    stage_event(a.output,'review_handoff',started,outcome='pending_review',identity=plan['identity'])
    print(json.dumps({'pending':sum(u['state']=='pending' for u in plan['units']),
                      'reused':plan['reuseCount'],'checks':plan['checks']['state'],
                      'automaticApprovalEnabled':False}))


if __name__ == '__main__':
    main()
