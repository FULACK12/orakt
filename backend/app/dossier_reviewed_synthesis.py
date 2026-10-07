"""Generate a bounded chapter from explicitly reviewed claims, not raw tables.

This pilot produces no publishable full dossier. Archive quotations and reviewer
changes remain separate from the local model's narrative authorship.
"""
import argparse
import hashlib
import json
import re
from datetime import UTC,datetime
from pathlib import Path
from app.company_history_dossier import Section,validate_section,write_json
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.model_workload import local_model_workload_lock
from app.dossier_claim_pilot import validate_extract
from app.dossier_model_stream import generate
from app.dossier_passages import check_claims
from app.dossier_prompt import INSTRUCTIONS
from app.dossier_source_contract import source_contract
from app.research import _compatible_json_schema
from app.review_frozen_dossier import load_frozen_packet
from app.dossier_cash_bridge import packet_passages,cash_bridge,guard_cash_narrative
from app.dossier_market_readiness import market_readiness


def review_claims(packet, fingerprint, review):
    if review.get('reviewer')!='codex_assistant' or review.get('state')!='accepted_with_revisions':
        raise ValueError('Explicit content review with revisions required')
    if review.get('sourceFingerprint')!=fingerprint or review.get('ticker')!=packet['ticker']:
        raise ValueError('Review does not match frozen source')
    chapter=review['chapter']
    if chapter not in packet['chapter_passages']:raise ValueError('Unknown chapter')
    known=packet_passages(packet)
    claims=[];seen=set()
    for item in review['claims']:
        if item['passageId'] in seen:raise ValueError('Duplicate reviewed passage')
        p=known.get(item['passageId'])
        if not p:raise ValueError('Reviewed claim outside frozen source')
        if hashlib.sha256(p['text'].encode()).hexdigest()!=item['quoteSha256']:raise ValueError('Reviewed quote hash mismatch')
        if not item.get('revisionNote'):raise ValueError('Missing review rationale')
        value=validate_extract(item['extract'],p)
        claims.append({'passageId':p['id'],'extract':value.model_dump(),'sourceContract':source_contract(p,packet)})
        seen.add(p['id'])
    if len(claims)<2:raise ValueError('At least two reviewed passages required')
    return claims


def synthesis_messages(ticker, claims, error='', chapter='business', bridge=None, readiness=None):
    # Only qualitative facts reach the writer. Exact originals remain bound in
    # the result and source hashes. No numeric values are deleted from archives.
    clean=[{'passageId':c['passageId'],'reviewedFact':c['extract']['disclosed_fact'],
            'evidenceBoundary':c['extract']['not_established'],
            'terms':c['sourceContract']['terms'],'eventTiming':c['sourceContract'].get('eventTiming',[])} for c in claims]
    focus={
        'competition':'Distinguish management positioning and R&D expenditure from measured competitive advantage. No competitor market-share rankings without comparable evidence. Litigation exposure is not a legal defeat.',
        'supply':'Distinguish announced plans from achieved savings and post-period developments from in-period results. For software, hosting, inference and training are distinct resources/accounting scopes; do not invent factories, mines, suppliers or outages.',
        'macro':'Separate disclosed exposures from realized market events. Do not invent rate decisions, yields, currencies or stock returns. Respect fixed-to-floating swap direction and debt fair value versus principal. No macro-stock causal conclusion without dated market evidence.',
        'valuation':'Framework only, no numerical targets or buy/sell recommendation. Repurchase averages and employee purchase prices are NOT fair value or institutional cost. Do not annualize a seasonal quarter. Require matched trailing cash flows, dilution, net debt, dated prices and explicit scenario assumptions. Separate short-term event risk from long-horizon valuation.',
        'factors':'Propose issuer-specific falsifiable linear signals and an interaction, NOT validated alpha. Specify disclosure-time lag, market AND sector benchmarks, fees/slippage, non-overlapping out-of-sample tests, confidence intervals and multiple-testing control. A newly reconstructed historical report is not an ex-ante prediction. Never report hypothetical returns as measured.',
        'conclusion':'Synthesize only reviewed disclosures. Separate observed operations, conditional mechanisms and unverified market conclusions. State what would reverse the interpretation and the priority data request. Do not convert a nine-chapter structure into proof of completeness, a price target or approval to trade.',
    }.get(chapter,'')
    return [{'role':'system','content':INSTRUCTIONS+
        '\nThis is a bounded '+chapter+' chapter, not a full company report. All factual statements must follow the reviewed facts. '
        'Do not emit grounded_claims, evidence_refs or comparison_checks: the program binds the reviewed claims. '
        'Do not infer omitted dates, fiscal quarters, regions or numbers. Cite PASSAGE IDs. '
        'Mechanism must be explicitly conditional; do not invent customer contracts, industry statistics or actual future performance. '
        'Do not invent numerical thresholds in the validation plan. Focus on supplied operating evidence, not generic macroeconomics. '
        'Each paragraph must first select support_ids as evidence context, then zh/en. These IDs are not proof of causality. '
        'analysis must contain at least 300 Chinese characters and 900 English characters of substantive prose, excluding IDs; explain basis, alternative interpretation and limits without repetition. '
        'A repurchase price above/below a historical average does not determine EPS accretion. Test shares retired, funding costs, dilution and earnings instead. '
        'Do not claim no material impact just because no quarterly repurchase occurred. Stock compensation may already affect earnings. '
        'Deferred revenue remains a liability until earned; correlation cannot turn it into realized profit. It includes billings OR advance receipts. '
        'A product mix change is not necessarily an optimization. Disclosure absence is not an economic cause of costs. '
        'mechanism must start 如果/If and specify a testable conditional mechanism, not repeat reported outcomes. '
        'counterEvidence must give an alternative interpretation or a condition that would falsify the hypothesis, not repeat missing data. '
        'evidenceGaps must say 本次所选摘录/selected excerpts: missing here is not missing from the entire filing. '
        'validationPlan must name the exact series or company disclosure to check and what would support or reject the mechanism. '
        'Keep apparel without stated regional scope explicitly region-unspecified. Never infer whole-company profitability from it. '
        'For financial/capital chapters distinguish operating, investing and financing cash flows, stocks versus flows, and quarter versus cumulative periods. '
        'Repurchases and dividends use cash, not generate operating cash. Authorization is not execution; debt fair value is not principal repayment. '
        'Recognizing already-collected deferred revenue does NOT cause new cash inflow. Non-cash adjustments have different signs; do not assume they reduce cash flow. '
        'Never apply the prior-year working-capital explanation to the current year. Do not assume a positive cash inflow grew year-over-year. '
        'An arithmetic cash bridge is not proof of earnings quality. Management liquidity forecasts are opinions, not guarantees. '+focus},
        {'role':'user','content':json.dumps({'company':ticker,'chapter':chapter,'reviewedClaims':clean,
            'cashFlowBasis':{'state':bridge.get('state'),'periodType':bridge.get('periodType')} if bridge else None,
            'marketReadiness':{k:v for k,v in (readiness or {}).items() if k!='series'},
            'previousError':error[:1200]},ensure_ascii=False)}]


def chapter_schema(claims):
    pair=_compatible_json_schema(Section)['$defs']['Bilingual']
    ids=[c['passageId'] for c in claims]
    props={}
    for key in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
        props[key]={'type':'object','additionalProperties':False,'required':['support_ids','zh','en'],
            'properties':{'support_ids':{'type':'array','items':{'type':'string','enum':ids},'minItems':1,'maxItems':4},**pair['properties']}}
    return {'type':'object','additionalProperties':False,'properties':props,'required':list(props)}


def bind_narrative_context(draft, allowed):
    """Append model-selected evidence context, not fabricated proof of causality."""
    text={};contexts={}
    for key in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
        pair=draft[key];ids=pair['support_ids']
        if not ids or len(set(ids))!=len(ids) or set(ids)-set(allowed):raise ValueError('Select distinct supplied support_ids for every paragraph')
        if set(pair)!={'support_ids','zh','en'}:raise ValueError('Unexpected narrative fields')
        suffix=' ['+', '.join(ids)+']'
        text[key]={'zh':pair['zh']+suffix,'en':pair['en']+suffix};contexts[key]=ids
    m=text['mechanism']
    if not re.search(r'如果|若|条件|假设',m['zh']) or not re.search(r'\bif\b|conditional|hypothes',m['en'],re.I):
        raise ValueError('mechanism must explicitly be a conditional hypothesis, not established issuer performance')
    g=text['evidenceGaps']
    if not re.search(r'本次|当前摘录|所选|这些摘录',g['zh']) or not re.search(r'selected|these excerpts|this packet|provided excerpts',g['en'],re.I):
        raise ValueError('evidenceGaps must refer to selected excerpts, not claim company-wide nondisclosure')
    from difflib import SequenceMatcher
    if SequenceMatcher(None,draft['counterEvidence']['en'],draft['evidenceGaps']['en']).ratio()>.8:
        raise ValueError('counterEvidence duplicates evidenceGaps: describe a competing interpretation or falsification condition instead')
    return text,contexts


def run(source,review_path,output):
    if output.exists():raise ValueError('Choose a new revision directory')
    settings=get_settings();original,_=load_frozen_packet(source,settings.cold_data_root);packet=original['packet']
    review=json.loads(review_path.read_text(encoding='utf-8'))
    claims=review_claims(packet,original['fingerprint'],review)
    chapter=review['chapter'];known=packet_passages(packet)
    bridge=cash_bridge(packet) if chapter in {'financial','capital'} else None
    readiness=market_readiness(packet) if chapter in {'valuation','factors','conclusion'} else None
    bound=[{'passage_id':c['passageId'],'quote':known[c['passageId']]['text'],'statement':c['extract']['disclosed_fact']} for c in claims]
    allowed={packet['filing_ref'],*(c['passageId'] for c in claims)}
    schema=chapter_schema(claims)
    with get_session_factory()() as session,local_model_workload_lock(session) as acquired:
        if not acquired:raise RuntimeError('Local model busy')
        write_json(output/'review-input.json',review)
        error=''
        for attempt in range(2):
            def progress(p):
                if (output/'pause').exists():raise InterruptedError('Safe pause requested')
                write_json(output/'progress.json',{'ticker':packet['ticker'],'chapter':chapter,'attempt':attempt+1,'checkedAt':datetime.now(UTC).isoformat(),**p})
            raw=generate(str(settings.llm_base_url).rstrip('/')+'/api/chat',{
                'model':settings.llm_model,'think':False,'format':schema,
                'options':{'num_ctx':32768,'num_predict':6500,'temperature':0.1},
                'messages':synthesis_messages(packet['ticker'],claims,error,chapter,bridge,readiness),
            },progress,lambda p:write_json(output/f'attempt-{attempt+1}-partial.json',p))
            write_json(output/f'attempt-{attempt+1}.json',raw)
            try:
                if raw.get('done_reason')=='length':raise ValueError('Truncated chapter')
                draft=json.loads(raw['message']['content'])
                if set(draft)-set(schema['properties']):raise ValueError('Model returned reserved evidence fields')
                narrative,contexts=bind_narrative_context(draft,{c['passageId'] for c in claims})
                section=Section.model_validate({**narrative,'evidence_refs':sorted(allowed),'comparison_checks':[],'grounded_claims':bound})
                validate_section(section,allowed,packet['financial_ledger'])
                if chapter in {'financial','capital'}:guard_cash_narrative(section,packet)
                check_claims(section.grounded_claims,list(known.values()),required=True)
                write_json(output/'chapter.json',{'ticker':packet['ticker'],'chapter':chapter,'sourceFingerprint':original['fingerprint'],
                    'reviewHash':hashlib.sha256(review_path.read_bytes()).hexdigest(),'authorship':{'narrative':'local_model','groundedClaims':'assistant_revised'},
                    'section':section.model_dump(),'cashBridge':bridge,'marketReadiness':readiness,'evidenceContext':contexts,'contextMeaning':'Model-selected source context; conditional mechanisms are not verified causal findings.',
                    'state':'content_review_pending','completeDossier':False,'published':False})
                write_json(output/'progress.json',{'stage':'content_review_pending','checkedAt':datetime.now(UTC).isoformat(),'published':False})
                return
            except ValueError as exc:error=str(exc)
        write_json(output/'progress.json',{'stage':'repair_required','error':error,'checkedAt':datetime.now(UTC).isoformat(),'published':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('source','review','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output already exists; preserve prior revision')
    try:run(args.source,args.review,args.output)
    except Exception as exc:
        if args.output.exists():write_json(args.output/'progress.json',{'stage':'failed','error':str(exc)[:1200],'checkedAt':datetime.now(UTC).isoformat(),'published':False})
        raise
