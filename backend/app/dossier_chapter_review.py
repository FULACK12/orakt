"""Explicit content revision of one pilot chapter; never a full-dossier approval."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import UTC,datetime
from app.company_history_dossier import Section,validate_section,write_json
from app.dossier_passages import check_claims
from app.core.config import get_settings
from app.review_frozen_dossier import load_frozen_packet
from app.dossier_cash_bridge import packet_passages,cash_bridge,guard_cash_narrative
from app.dossier_market_readiness import market_readiness
from copy import deepcopy
from app.dossier_accounting_checks import disclosed_reference_terms


def apply_claim_corrections(section, changes):
    """Revise interpretation only; original quote and passage identity stay fixed."""
    result=deepcopy(section)
    known={c['passage_id']:c for c in result.get('grounded_claims',[])}
    if len(known)!=len(result.get('grounded_claims',[])):raise ValueError('Duplicate claim identity')
    if not isinstance(changes,dict) or set(changes)-set(known):raise ValueError('Claim correction outside existing evidence')
    for pid,statement in changes.items():
        if not isinstance(statement,dict) or set(statement)!={'zh','en'}:raise ValueError('Only bilingual claim statements may be revised')
        known[pid]['statement']=statement
    return result


def revise(chapter_path,review_path,source_path,output):
    if output.exists():raise ValueError('Reviewed chapter already exists; preserve revision')
    raw=chapter_path.read_bytes();chapter=json.loads(raw)
    review_raw=review_path.read_bytes();review=json.loads(review_raw)
    original,_=load_frozen_packet(source_path,get_settings().cold_data_root);packet=original['packet']
    if review.get('reviewer')!='codex_assistant' or review.get('state')!='accepted_with_revisions' or not review.get('findings'):
        raise ValueError('Explicit content audit required')
    if review.get('parentSha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('Reviewed draft changed')
    if chapter['sourceFingerprint']!=original['fingerprint'] or chapter['ticker']!=packet['ticker']:raise ValueError('Frozen source mismatch')
    corrections=review['corrections']
    permitted={'analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'}
    if not corrections or set(corrections)-permitted:raise ValueError('Only explicit bilingual narrative corrections allowed')
    corrected=apply_claim_corrections(chapter['section'],review.get('claimCorrections',{}))
    section=Section.model_validate({**corrected,**corrections})
    from app.dossier_compact_writer import check_cash_evidence_use
    check_cash_evidence_use(section,packet,chapter['chapter'])
    from app.dossier_semantic_guards import guard_known_semantics
    guard_known_semantics(section,packet)
    ps=list(packet_passages(packet).values())
    validate_section(section,{packet['filing_ref'],*(p['id'] for p in ps)},packet['financial_ledger'],technical_terms=disclosed_reference_terms(packet))
    if chapter['chapter'] in {'financial','capital'}:guard_cash_narrative(section,packet)
    check_claims(section.grounded_claims,ps,required=True)
    for pair in (section.analysis,section.mechanism,section.counterEvidence,section.evidenceGaps,section.validationPlan):
        if 'PASSAGE:' not in pair.zh or 'PASSAGE:' not in pair.en:raise ValueError('Each bilingual paragraph requires evidence context')
    result={**chapter,'section':section.model_dump(),'authorship':{'narrative':'assistant_revised_local_model_draft','groundedClaims':'assistant_revised'},
        'state':'assistant_reviewed','completeDossier':False,'published':False,
        'sourceMetadata':{k:packet.get(k) for k in ('ticker','accession','as_of_date','period_end','source_url','raw_sha256')},
        'reviewDocument':review,
        'review':{'reviewer':'codex_assistant','state':'accepted_with_revisions','reviewedAt':datetime.now(UTC).isoformat(),
                  'parentSha256':review['parentSha256'],'reviewSha256':hashlib.sha256(review_raw).hexdigest(),'findings':review['findings'],
                  'scope':chapter['chapter']+' chapter only; not a full-company, valuation or investment recommendation approval.'}}
    if chapter['chapter'] in {'financial','capital'}:result['cashBridge']=cash_bridge(packet)
    if chapter['chapter'] in {'valuation','factors','conclusion'}:
        # Recompute from frozen evidence, not model/user-authored readiness flags.
        result['marketReadiness']=market_readiness(packet)
    # Paragraph references are authoritative after the reviewer edits prose;
    # retain model context separately rather than silently mislabel it current.
    result['modelEvidenceContext']=result.pop('evidenceContext',{})
    # New reviews can supply pinpoint semantic decisions. Old reviews remain
    # intact and are never silently upgraded to per-statement acceptance.
    from app.report_quality import worklist, accept_receipts
    from app.report_usage import save
    plan=worklist(packet,[result])
    receipts=accept_receipts(plan,review['semanticDecisions']) if review.get('semanticDecisions') else None
    write_json(output,result)
    save(output.with_name(output.stem+'-semantic-worklist.json'),plan)
    if receipts is not None:
        save(output.with_name(output.stem+'-semantic-receipts.json'),receipts)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('chapter','review','source','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();revise(args.chapter,args.review,args.source,args.output)
