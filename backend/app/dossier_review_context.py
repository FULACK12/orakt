"""Exact reviewer-selected original spans, never new facts or model approval."""
import hashlib
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, unquote


def validate_context(packet,text):
    ids=packet.get('review_context_ids',[])
    if len(set(ids))!=len(ids):raise ValueError('Duplicate review context')
    for pid in ids:
        records=[p for rows in packet['chapter_passages'].values() for p in rows if p['id']==pid]
        if not records:raise ValueError('Missing review context')
        for p in records:
            digest=hashlib.sha256((packet['raw_sha256']+':'+str(p['start'])+':'+p['text']).encode()).hexdigest()
            if (not p['text'] or not 0<=p['start']<p['end']<=len(text)
                or p['sourceHash']!=packet['raw_sha256'] or text[p['start']:p['end']]!=p['text']
                or pid!='PASSAGE:'+digest[:16]):
                raise ValueError('Review context differs from original')


def additive_revision(source, cold_root, output, specifications, *, context_only_chapters=()):
    """Append full, exact table contexts without replacing failed inputs.

    Anchors must be unique in the archived filing. End markers are exclusive;
    table title, period, units and subtotal classification remain unmodified.
    This only prepares evidence, never transfers an earlier review verdict.
    """
    from app.review_frozen_dossier import load_frozen_packet
    from app.historical_earnings_report import FilingText
    from app.dossier_earnings_context import context_span
    from app.report_usage import save
    if output.exists():raise ValueError('Preserve existing evidence revision')
    original, raw=load_frozen_packet(source,cold_root)
    result=copy.deepcopy(original);packet=result['packet']
    base=(cold_root/'raw/sec/company-filings'/packet['ticker']).resolve()
    filing=(base/packet['accession'].replace('-','')/unquote(urlsplit(packet['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not filing.is_relative_to(base):raise ValueError('Source outside archive')
    parser=FilingText();parser.feed(filing.read_text(encoding='utf-8'));text=parser.clean()
    if not specifications:raise ValueError('Explicit source context specifications required')
    added=[]
    for spec in specifications:
        start,end=spec['start'],spec['end']
        if text.count(start)!=1:raise ValueError('Start anchor must be unique: '+start)
        a=text.index(start);b=text.find(end,a+len(start))
        if not a<b or not 30<=b-a<=16000:raise ValueError('Missing or unbounded source end')
        if not spec['chapters'] or set(spec['chapters'])-packet['chapter_passages'].keys():raise ValueError('Unknown chapter')
        span=context_span(text,a,b,packet['raw_sha256'],spec['role'])
        for key in spec['chapters']:
            if span['id'] not in {p['id'] for p in packet['chapter_passages'][key]}:
                packet['chapter_passages'][key].append(copy.deepcopy(span))
        if span['id'] not in packet.setdefault('review_context_ids',[]):packet['review_context_ids'].append(span['id'])
        added.append(span['id'])
    validate_context(packet,text)
    if set(context_only_chapters)-packet['chapter_passages'].keys():raise ValueError('Unknown context-only chapter')
    for key in context_only_chapters:
        selected=[p for p in packet['chapter_passages'][key] if p['id'] in added]
        if len({p['id'] for p in selected})<2:raise ValueError('Context-only chapters require two distinct original spans')
        packet.setdefault('review_chapter_selection',{})[key]=[p['id'] for p in selected]
    result['fingerprint']=hashlib.sha256(json.dumps({'version':result['version'],'packet':packet},sort_keys=True).encode()).hexdigest()
    result['evidenceRevision']={'kind':'complete-table-context/v1','createdAt':datetime.now(UTC).isoformat(),
        'parentPath':str(source),'parentSha256':hashlib.sha256(raw).hexdigest(),'parentFingerprint':original['fingerprint'],
        'newContextIds':added,'specifications':specifications,'contextOnlyChapters':list(context_only_chapters),
        'approvalTransferred':False,'oldEvidencePreserved':True}
    save(output,result)
    load_frozen_packet(output,cold_root)
    return result
