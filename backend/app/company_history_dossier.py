"""Checkpointed, bilingual full company research; no automatic investment claims.

Each chapter is a separate local-model call. A completed dossier remains a draft
until an operator reviews it. Checkpoints and source packets stay on the cold disk.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import date, datetime, UTC
from pathlib import Path
import httpx
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import MarketSeries, MarketObservation
from app.db.session import get_session_factory
from app.historical_earnings_report import build_packet, validate_citations
from app.model_workload import local_model_workload_lock
from app.research import _compatible_json_schema
from app.financial_period_ledger import build_ledger
from app.inline_filing_facts import monetary_facts
from urllib.parse import urlsplit, unquote
from app.dossier_model_stream import generate as generate_stream
from app.dossier_prompt import bounded_messages
from app.dossier_passages import add_passages, check_claims, bind_selected_passages, selection_schema
from app.dossier_accounting_checks import gross_margin_checks, guard_prose, guard_expense_claims, mask_financial_numbers, disclosed_product_terms, disclosed_reference_terms, balance_narrative_errors, methodological_errors

VERSION = "company-dossier/v13-bounded-evidence"
GENERATION_VERSION = 'passage-selection-v13'
CHAPTERS = [
    ("business", "公司业务、产品与收入驱动", "Business, products and revenue drivers"),
    ("financial", "财务质量、利润与现金流", "Financial quality, earnings and cash flow"),
    ("capital", "资产负债、资本配置与股东回报", "Balance sheet, capital allocation and shareholder returns"),
    ("competition", "竞争格局、技术替代与护城河", "Competition, substitution and competitive advantage"),
    ("supply", "供应链、生产资源与地缘风险", "Supply chain, production resources and geopolitical risk"),
    ("macro", "宏观周期、政策与流动性传导", "Macro cycles, policy and liquidity transmission"),
    ("valuation", "估值框架与多期限情景", "Valuation framework and multi-horizon scenarios"),
    ("factors", "线性与非线性因子、双基准验证设计", "Linear/nonlinear factors and dual-benchmark validation"),
    ("conclusion", "综合判断、反证与后续观察清单", "Synthesis, counter-evidence and monitoring checklist"),
]

class Bilingual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zh: str = Field(min_length=5, max_length=6000)
    en: str = Field(min_length=5, max_length=10000)

class ComparisonCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: str
    direction: str
    period_type: str

class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis: Bilingual
    mechanism: Bilingual
    counterEvidence: Bilingual
    evidenceGaps: Bilingual
    validationPlan: Bilingual
    evidence_refs: list[str] = Field(min_length=1, max_length=40)
    comparison_checks: list[ComparisonCheck] = Field(default_factory=list)
    grounded_claims: list['GroundedClaim'] = Field(default_factory=list, max_length=6)

class GroundedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passage_id: str
    quote: str = Field(min_length=30,max_length=2200)
    statement: Bilingual

Section.model_rebuild()

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(path)

def enrich_market(session, packet):
    cutoff=date.fromisoformat(packet["as_of_date"])
    ticker=packet["ticker"]
    series=session.scalars(select(MarketSeries).where(MarketSeries.series_id.in_([f"EQ:{ticker}",f"US:{ticker}",ticker,"DGS2","DGS10","NFCI","FRED:DGS2","FRED:DGS10","FRED:NFCI","TD:SPY","SPY","US:SPY"]))).all()
    evidence=[]
    for s in series:
        rows=session.scalars(select(MarketObservation).where(MarketObservation.series_id==s.series_id,MarketObservation.observed_on<=cutoff).order_by(MarketObservation.observed_on.desc()).limit(252)).all()
        if not rows: continue
        evidence.append({"id":f"MARKET:{s.series_id}","name":s.name,"unit":s.unit,"source_url":s.source_url,"observations":[{"date":str(r.observed_on),"value":r.value} for r in reversed(rows)],"vintage":"Latest retained series truncated by observation date; original release vintage not guaranteed."})
    packet["market_evidence"]=evidence
    return packet

def chapter_packet(packet, key):
    # Fixed period facts, not arbitrary latest metrics. Select relevant concepts
    # to keep every chapter inside the context budget and preserve source IDs.
    patterns={"business":"Revenue|Sales|Segment", "financial":"Revenue|Income|Profit|Operating|CashFlow|CashFlows", "capital":"Asset|Liabil|Debt|Cash|Dividend|Repurch|Stock|Share", "valuation":"Earnings|Income|Revenue|Share|Cash", "supply":"Inventor|Purchas|Cost|Property"}
    import re
    facts=packet["facts"]
    preferred=[f for f in facts if re.search(patterns.get(key,"Revenue|Income|Cash|Debt|Share"),f["concept"],re.I)]
    relevant=re.compile(patterns.get(key,"Revenue|Income|Cash|Debt|Share"),re.I)
    def compact(f):return {k:f.get(k) for k in ['evidence_id','concept','value','unit','period_start','period_end']}
    comparisons=[c for c in packet['financial_ledger']['comparisons'] if relevant.search(c['concept'])]
    # Consolidated figures first, then the dimensional operating breakdown.
    core=['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet','Revenues',
          'GrossProfit','OperatingIncomeLoss','NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities',
          'CashAndCashEquivalentsAtCarryingValue','Assets','Liabilities','StockholdersEquity']
    comparisons.sort(key=lambda c:(' [' in c['concept'],core.index(c['concept']) if c['concept'] in core else len(core),c['concept'],c['periodType']))
    ledger={"accountingRules":packet['financial_ledger']['accountingRules'],"comparisons":[{**{k:c[k] for k in ['id','concept','unit','periodType','comparisonBasis','direction','change','changePercent','evidence_refs']},"current":compact(c['current']),"previous":compact(c['previous'])} for c in comparisons[:8]]}
    # An explicit allow-list avoids copying the entire filing, all chapters and
    # duplicate excerpts into every request. The immutable source retains them.
    return {k:packet[k] for k in ('ticker','accession','as_of_date','period_end','filing_ref','source_url') if k in packet} | {
        "financial_ledger":ledger,
        "input_scope":"Selected chapter evidence, not the entire filing. Omitted material is not proof of absence. Distinct passages are not independent sources.",
        "facts":[compact(f) for f in (preferred or facts)[:12]],
        "market_evidence":[{k:s[k] for k in ('id','name','unit','vintage') if k in s} | {"observations":s['observations'][-8:]} for s in packet.get('market_evidence',[])[:4]],
        "original_passages":[{'id':p['id'],'text':p['text']} for p in packet.get('chapter_passages',{}).get(key,[])[:6]],
    }


def chapter_allowed_ids(evidence):
    allowed={evidence['filing_ref'],*(f['evidence_id'] for f in evidence['facts']),*(s['id'] for s in evidence['market_evidence']),*(p['id'] for p in evidence['original_passages'])}
    for c in evidence['financial_ledger']['comparisons']:
        allowed.update(c['evidence_refs'])
        allowed.update(f['evidence_id'] for f in (c['current'],c['previous']) if f.get('evidence_id'))
    return allowed

def enrich_inline(packet,cold_root):
    base=(cold_root/'raw/sec/company-filings'/packet['ticker']).resolve()
    path=(base/packet['accession'].replace('-','')/unquote(urlsplit(packet['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not path.is_relative_to(base):raise ValueError('Filing path escaped archive')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=packet['raw_sha256']:raise ValueError('Filing changed during extraction')
    facts,coverage=monetary_facts(raw.decode('utf-8',errors='replace'),filed_at=packet['as_of_date'],source_url=packet['source_url'])
    packet['facts'] += [f for f in facts if f.get('period_end') and f['period_end']<=packet['period_end']]
    packet['inline_coverage']=coverage
    return packet

def validate_section(section, allowed, ledger=None, required_comparisons=(), technical_terms=()):
    import re
    validate_citations(section.model_dump(),allowed)
    known={c["id"]:c for c in (ledger or {}).get("comparisons",[])}
    seen=set()
    for checked in section.comparison_checks:
        expected=known.get(checked.comparison_id)
        if not expected or checked.direction!=expected["direction"] or checked.period_type!=expected["periodType"]:
            raise ValueError(f"Comparison direction/period mismatch: {checked.comparison_id}")
        seen.add(checked.comparison_id)
    if set(required_comparisons)-seen:
        raise ValueError("Missing required financial comparison checks")
    guard_prose(section,gross_margin_checks(ledger or {}))
    guard_expense_claims(section,ledger or {})
    contradictions=balance_narrative_errors(section,ledger or {})+methodological_errors(section)
    if contradictions:raise ValueError('; '.join(contradictions))
    pairs=[(key,getattr(section,key)) for key in ["analysis","mechanism","counterEvidence","evidenceGaps","validationPlan"]]
    pairs.extend((f'grounded_claims[{i}].statement',claim.statement) for i,claim in enumerate(section.grounded_claims))
    for field,pair in pairs:
        for language,value in [('zh',pair.zh),('en',pair.en)]:
            if '[value in source table]' in value:
                raise ValueError('Internal evidence masking placeholder leaked into report prose')
            narrative=re.sub(r"PASSAGE:[a-f0-9]{16}|BULK:[a-f0-9]{64}|FACT:\d+|IX:[A-Za-z0-9_.-]+|SEC:\d{10}-\d{2}-\d{6}|MARKET:[A-Za-z0-9:._-]+","",value)
            narrative=re.sub(r"\b10-[QK](?:/A)?\b","",narrative)  # SEC form names are not numerical claims
            # Explicit source-quoted year labels preserve period attribution.
            # A bare number, amount or percentage is still not permitted prose.
            years=set(re.findall(r'\b(?:19|20)\d{2}\b',' '.join(c.quote for c in section.grounded_claims)))
            for comparison in (ledger or {}).get('comparisons',[]):
                for side in ('current','previous'):
                    row=comparison.get(side,{})
                    years.update(str(row[k])[:4] for k in ('period_start','period_end') if row.get(k) and re.match(r'^(?:19|20)\d{2}-\d{2}-\d{2}$',str(row[k])))
            if years:
                alternatives='|'.join(sorted(years))
                def year_label(match):
                    before=narrative[max(0,match.start()-35):match.start()]
                    after=narrative[match.end():match.end()+22]
                    if re.search(r'(?:[$€£¥]|USD|CNY|EUR)\s*$',before,re.I) or re.match(r'\s*(?:%|[.,]\d|dollars\b|USD\b|million\b|billion\b|美元|元|股|万元|亿元)',after,re.I):
                        return match.group()
                    if (re.search(r'(?:price|amount|revenue|income|profit|EPS)\s+(?:was|is|of|at)\s*$',before,re.I)
                        or re.search(r'(?:价格|金额|销售额|收入|利润)(?:为|是|达到)\s*$',before)) and not after.startswith('年'):
                        return match.group()
                    # Evidence-quoted years can coordinate (2008 and 2009 / 2008、2009年).
                    # This is a lexical exception, NOT source entailment approval.
                    return ''
                narrative=re.sub(r'(?<![\d.])(?:'+alternatives+r')(?!\d)',year_label,narrative)
            for term in sorted(technical_terms,key=len,reverse=True):narrative=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(term)+r'(?![A-Za-z0-9_%])','',narrative)
            narrative=re.sub(r"(?<![\d.])\b[1-9][）)]", "", narrative)  # list ordinals are not financial quantities
            if re.search(r"\d",narrative):
                raise ValueError(f"Numerical claims belong in deterministic source tables, not bilingual model prose: {field}.{language}. For necessary source-quoted year labels only, use YYYY年 / in YYYY; other amounts stay in tables.")
        if not re.search(r"[\u4e00-\u9fff]",pair.zh) or re.search(r"[\u4e00-\u9fff]",pair.en):
            raise ValueError(f"Both Chinese and English text are required: {field}. zh must contain Chinese; en must be fully English without untranslated Chinese terms.")
    # Citation identifiers must never pad a thin paragraph past the quality gate.
    def prose_length(value):
        clean=re.sub(r'PASSAGE:[a-f0-9]{16}|BULK:[a-f0-9]{64}|FACT:\d+|IX:[A-Za-z0-9_.-]+|SEC:\d{10}-\d{2}-\d{6}|MARKET:[A-Za-z0-9:._-]+','',value)
        return len(re.sub(r'[\[\],\s]','',clean))
    if prose_length(section.analysis.zh)<200 or prose_length(section.analysis.en)<500:
        raise ValueError("Chapter analysis is too brief")

def run(ticker, accession, output_dir, review_overrides=None, chapter_keys=None, frozen_source=None, max_failed_chapters=None):
    if max_failed_chapters is not None and max_failed_chapters<1:raise ValueError('Invalid chapter failure budget')
    selected=set(chapter_keys or [c[0] for c in CHAPTERS])
    if selected-{c[0] for c in CHAPTERS}:raise ValueError('Unknown requested chapter')
    settings=get_settings()
    with get_session_factory()() as session, local_model_workload_lock(session) as acquired:
        if not acquired: raise RuntimeError("Local model busy; no concurrent generation")
        if frozen_source:
            from app.review_frozen_dossier import load_frozen_packet
            original,_=load_frozen_packet(frozen_source,settings.cold_data_root)
            packet=original['packet']
            if packet['ticker']!=ticker or packet['accession']!=accession:raise ValueError('Frozen source does not match requested filing')
            if frozen_source.resolve()==(output_dir/ticker/accession/'source.json').resolve():raise ValueError('Frozen replay requires a separate revision folder')
        else:
            packet=enrich_inline(enrich_market(session,build_packet(session,ticker=ticker,cold_root=settings.cold_data_root,accession=accession)),settings.cold_data_root)
            packet=add_passages(packet,settings.cold_data_root)
            packet["financial_ledger"]=build_ledger(packet)
        fingerprint=hashlib.sha256(json.dumps({"version":VERSION,"packet":packet},sort_keys=True).encode()).hexdigest()
        folder=output_dir/ticker/accession
        source=folder/"source.json"
        if source.exists() and json.loads(source.read_text(encoding="utf-8"))["fingerprint"]!=fingerprint:
            raise ValueError("Evidence changed; use a new revision folder, do not overwrite prior checkpoints")
        write_json(source,{"fingerprint":fingerprint,"packet":packet,"version":VERSION})
        revisions={};review_hash=None
        if review_overrides:
            reviewed=json.loads(review_overrides.read_text(encoding='utf-8'))
            if reviewed.get('reviewer')!='codex_assistant' or reviewed.get('ticker')!=ticker or reviewed.get('asOf')!=packet['as_of_date'] or not reviewed.get('corrections'):
                raise ValueError('Explicit matching assistant review required')
            review_hash=hashlib.sha256(review_overrides.read_bytes()).hexdigest();revisions=reviewed['chapters']
            write_json(folder/f'assistant-review-{review_hash}.json',reviewed)
        chapters=[];chapter_failures=[]
        for index,(key,zh,en) in enumerate(CHAPTERS):
            if key not in selected:continue
            if (output_dir.parent/'pause').exists():raise InterruptedError('Safe pause requested')
            checkpoint=folder/f"{index+1:02d}-{key}.json"
            write_json(output_dir.parent/"chapter-progress.json",{"ticker":ticker,"accession":accession,"chapter":index+1,"totalChapters":len(CHAPTERS),"stage":key,"checkedAt":datetime.now(UTC).isoformat()})
            evidence=chapter_packet(packet,key)
            evidence.pop('chapter_passages',None)
            passages=evidence['original_passages']
            if len(passages)<2:raise ValueError(f'Insufficient original prose passages for chapter {key}; retrieve sources before generation')
            allowed=chapter_allowed_ids(evidence)
            required=[c['id'] for c in evidence['financial_ledger']['comparisons'] if c['concept'] in {'NetCashProvidedByUsedInOperatingActivities','OperatingIncomeLoss','RevenueFromContractWithCustomerExcludingAssessedTax','PaymentsToAcquirePropertyPlantAndEquipment','SimplifiedFreeCashFlow'} or (key=='business' and 'RevenueFromContract' in c['concept'])] if key in {'business','financial','capital','conclusion'} else []
            required=required[:6]
            technical_terms=disclosed_reference_terms(packet)
            # Preserve source values and dates so the model can reason about
            # periods. The validator still rejects generated numerical claims.
            import re
            prose_evidence=evidence
            attempt=folder/f"{index+1:02d}-{key}-{GENERATION_VERSION}-attempt.json"
            if key in revisions:
                original=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
                section=Section.model_validate({**original,**revisions[key]})
                validate_section(section,allowed,packet['financial_ledger'],required,technical_terms)
                write_json(folder/f'{index+1:02d}-{key}.assistant-reviewed.json',section.model_dump())
            elif checkpoint.exists():
                section=Section.model_validate(json.loads(checkpoint.read_text(encoding="utf-8")))
            else:
                error=""; section=None
                for retry in range(3):
                    if (output_dir.parent/'pause').exists():raise InterruptedError('Safe pause requested')
                    retained=attempt if retry==0 else folder/f"{index+1:02d}-{key}-{GENERATION_VERSION}-repair-{retry}.json"
                    if retained.exists():
                        raw=json.loads(retained.read_text(encoding="utf-8"))
                    else:
                        request={
                            "chapter":zh,"company":ticker,"evidence":prose_evidence,
                            "primary_reference":packet['filing_ref'],
                            "allowed_evidence_ids":sorted(allowed),
                            "verified_ratio_checks":gross_margin_checks(evidence['financial_ledger']),
                            "disclosed_product_identifiers":technical_terms,
                            "required_comparison_ids":required,
                        }
                        # Retry against frozen evidence, not hallucinated draft text.
                        messages=bounded_messages(json.dumps(request,ensure_ascii=False),error)
                        try:
                            def progress(p):
                                if (output_dir.parent/'pause').exists():raise InterruptedError('Safe pause requested')
                                write_json(output_dir.parent/'chapter-progress.json',{'ticker':ticker,'accession':accession,'chapter':index+1,'totalChapters':len(CHAPTERS),'attempt':retry+1,'checkedAt':datetime.now(UTC).isoformat(),**p})
                            schema=selection_schema(_compatible_json_schema(Section),passages,allowed,required,packet['financial_ledger'])
                            raw=generate_stream(str(settings.llm_base_url).rstrip('/')+'/api/chat',{'model':settings.llm_model,'think':True,'format':schema,'options':{'temperature':0.1,'repeat_penalty':1.15,'repeat_last_n':512,'num_ctx':32768,'num_predict':18000},'messages':messages},progress,lambda partial:write_json(retained.with_suffix('.partial.json'),partial))
                            raw['oraktGeneration']={'reasoningEnabled':True,'requiredGroundedClaims':True,'version':VERSION,'protocol':GENERATION_VERSION,'quoteOrigin':'frozen_archive_not_model'}
                        except (ValueError,httpx.HTTPError) as exc:
                            error=str(exc);print(json.dumps({'ticker':ticker,'chapter':key,'generation_failed':error,'attempt':retry+1}),flush=True);continue
                        write_json(retained,raw)
                    try:
                        if raw.get("done_reason")=="length": raise ValueError("Output truncated; produce complete JSON")
                        draft=json.loads(raw['message']['content'])
                        if raw.get('oraktGeneration',{}).get('protocol')!=GENERATION_VERSION:
                            raise ValueError('Unsupported generation protocol; do not reinterpret legacy quotations')
                        candidate=Section.model_validate(bind_selected_passages(draft,passages))
                        validate_section(candidate,allowed,packet['financial_ledger'],required,technical_terms)
                        check_claims(candidate.grounded_claims,passages,required=True)
                        section=candidate
                        write_json(checkpoint,section.model_dump())
                        break
                    except ValueError as exc:
                        error=str(exc)
                        print(json.dumps({"ticker":ticker,"chapter":key,"validation_failed":error,"attempt":retry+1}),flush=True)
                if section is None:
                    chapter_failures.append({'chapter':key,'error':error})
                    write_json(folder/'quality-summary.json',{'state':'chapter_repair_required','failed':chapter_failures,'validatedChapters':len(chapters),'published':False})
                    if max_failed_chapters is not None and len(chapter_failures)>=max_failed_chapters:break
                    continue
            validate_section(section,allowed,packet['financial_ledger'],required,technical_terms)
            check_claims(section.grounded_claims,passages,required=True)
            chapters.append({"key":key,"title":{"zh":zh,"en":en},"authorship":"assistant_revised" if key in revisions else "local_model",**section.model_dump()})
            print(json.dumps({"ticker":ticker,"chapter":key,"completed":len(chapters),"attempted":index+1,"failed":len(chapter_failures),"total":len(CHAPTERS),"state":"structure_checked_content_pending"}),flush=True)
        if chapter_failures:
            write_json(folder/'partial-dossier.json',{'version':VERSION,'fingerprint':fingerprint,'ticker':ticker,'asOf':packet['as_of_date'],'chapters':chapters,'failedChapters':chapter_failures,'review':{'state':'partial_content_review_pending','humanAccepted':False},'complete':False,'eligibleForPredictiveBacktest':False})
            raise ValueError('Retained all chapter attempts; explicit content repair required: '+','.join(f['chapter'] for f in chapter_failures))
        if len(chapters)!=len(CHAPTERS):
            write_json(folder/'partial-dossier.json',{'version':VERSION,'fingerprint':fingerprint,'ticker':ticker,'asOf':packet['as_of_date'],'chapters':chapters,'review':{'state':'partial_content_review_pending','humanAccepted':False},'complete':False,'eligibleForPredictiveBacktest':False})
            write_json(output_dir.parent/'chapter-progress.json',{'ticker':ticker,'accession':accession,'stage':'partial_content_review_pending','completedChapters':len(chapters),'totalChapters':len(CHAPTERS),'checkedAt':datetime.now(UTC).isoformat(),'published':False})
            return
        write_json(folder/"dossier.json",{"version":VERSION,"fingerprint":fingerprint,"ticker":ticker,"asOf":packet["as_of_date"],"periodEnd":packet["period_end"],"createdAt":datetime.now(UTC).isoformat(),"model":settings.llm_model,"chapters":chapters,"facts":packet["facts"],"financialLedger":packet['financial_ledger'],"originalPassages":packet['chapter_passages'],"sources":[{"id":packet["filing_ref"],"url":packet["source_url"]}],"marketEvidence":packet["market_evidence"],"review":{"state":"content_review_pending","citationCheck":"passed","humanAccepted":False,"assistantRevisionHash":review_hash},"eligibleForPredictiveBacktest":False})
        write_json(output_dir.parent/"chapter-progress.json",{"ticker":ticker,"accession":accession,"stage":"content_review_pending","completedChapters":len(chapters),"totalChapters":len(CHAPTERS),"checkedAt":datetime.now(UTC).isoformat(),"published":False})

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--ticker",required=True);parser.add_argument("--accession",required=True);parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument('--review-overrides',type=Path)
    parser.add_argument('--frozen-source',type=Path,help='Replay immutable evidence in a new revision folder')
    parser.add_argument('--chapters',nargs='+',choices=[c[0] for c in CHAPTERS],help='Bounded quality pilot; never produces a complete dossier')
    args=parser.parse_args()
    try:
        run(args.ticker,args.accession,args.output_dir,args.review_overrides,args.chapters,args.frozen_source)
    except InterruptedError as exc:
        write_json(args.output_dir.parent/"chapter-progress.json",{"ticker":args.ticker,"accession":args.accession,"stage":"safely_paused","reason":str(exc),"checkedAt":datetime.now(UTC).isoformat(),"published":False})
    except Exception as exc:
        write_json(args.output_dir.parent/"chapter-progress.json",{"ticker":args.ticker,"accession":args.accession,"stage":"failed_quality_or_generation","error":str(exc)[:1200],"checkedAt":datetime.now(UTC).isoformat(),"published":False})
        raise
