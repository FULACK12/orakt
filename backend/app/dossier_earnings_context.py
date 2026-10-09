"""Exact same-filing supplements for earnings bridges and standard effective dates.

Applied only when making a new packet or an explicit new immutable revision.
Never refresh evidence while loading a frozen report or approve model prose.
"""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from copy import deepcopy
from pathlib import Path
from urllib.parse import unquote, urlsplit
from app.historical_earnings_report import FilingText


def earnings_observations(packet):
    """Narrow verified table layout. Unknown layouts return no inferred columns."""
    result=[];seen=set()
    for rows in packet.get('chapter_passages',{}).values():
        for p in rows:
            if p.get('contextRole')!='non_operating_earnings_bridge' or p['id'] in seen:continue
            seen.add(p['id']);body=p['text']
            header=re.search(r'Three Months Ended Six Months Ended\n([^\n]+)\n(20\d{2}) (20\d{2}) (20\d{2}) (20\d{2})\n',body)
            if not header:continue
            y1,y2,y3,y4=header.groups()[1:]
            if y1!=y3 or y2!=y4 or int(y2)!=int(y1)+1 or not packet.get('period_end','').startswith(y2):continue
            from datetime import date
            end=date.fromisoformat(packet['period_end'])
            label=f'{end:%B} {end.day},'
            if header.group(1)!=f'{label} {label}':continue
            for concept,caption in [('equity_security_gains','Gain (loss) on equity securities, net'),('other_income_net','Other income (expense), net')]:
                line=next((s for s in body.splitlines() if s.startswith(caption+' ')),None)
                if not line:continue
                raw=line[len(caption):].replace('$','').strip()
                token=r'(?:\(\s*\d[\d,]*(?:\.\d+)?\s*\)|-?\d[\d,]*(?:\.\d+)?)'
                if not re.fullmatch(token+r'(?:\s+'+token+r'){3}',raw):continue
                values=[Decimal(v.replace(',','').replace('(','-').replace(')','').replace(' ','')) for v in re.findall(token,raw)]
                for period,a,b in [('quarter',0,1),('half_year',2,3)]:
                    result.append({'concept':concept,'periodType':period,'periodEnd':packet['period_end'],
                        'comparisonBasis':'same_duration_year_over_year',
                        'direction':'increase' if values[b]>values[a] else 'decrease' if values[b]<values[a] else 'unchanged',
                        'currentSign':'negative' if values[b]<0 else 'positive' if values[b]>0 else 'zero',
                        'evidenceId':p['id'],
                        'scope':'Non-operating income; not operating revenue, realized cash or proof of recurrence.'})
    return result


def context_span(text, start, stop, source_hash, role):
    raw=text[start:stop];value=raw.strip();start+=len(raw)-len(raw.lstrip())
    if not value:return None
    digest=hashlib.sha256((source_hash+':'+str(start)+':'+value).encode()).hexdigest()
    return {'id':'PASSAGE:'+digest[:16], 'start':start, 'end':start+len(value),
            'text':value, 'sourceHash':source_hash, 'score':0, 'contextRole':role}


def extract_contexts(text, source_hash):
    contexts=[]
    # Numeric tables deliberately bypass the prose filter; they are context,
    # not inferred numbers. Stop at the next note/section, never combine spans.
    headings=list(re.finditer(r'(?im)^Other Income \(Expense\),? Net\s*$',text))
    for match in headings[:2]:
        tail=text[match.end():match.end()+4000]
        if not re.search(r'Components of.{0,40}(?:OI&E|other income)|Gain \(loss\) on equity',tail,re.I):continue
        boundary=re.search(r'(?im)^(?:Note \d+[.\s]|ITEM \d+[.\s])',tail)
        stop=match.end()+(boundary.start() if boundary else len(tail))
        contexts.append(context_span(text,match.start(),stop,source_hash,'non_operating_earnings_bridge'))
    # Include both the requirement and its nearby effective-date sentence.
    for match in list(re.finditer(r'Accounting Standards Update \(ASU\)',text))[:10]:
        start=text.rfind('\n',0,match.start())+1
        tail=text[start:start+2600]
        effective=re.search(r'The standard is effective[^\n]*',tail,re.I)
        if not effective:continue
        next_rule=re.search(r'\n(?:In [A-Z][a-z]+ \d{4},|Note \d+\.)',tail[effective.end():])
        stop=start+effective.end()+(next_rule.start() if next_rule else 0)
        contexts.append(context_span(text,start,stop,source_hash,'accounting_effective_date'))
    return [p for p in contexts if p]


def add_context(packet, text):
    contexts=extract_contexts(text,packet['raw_sha256'])
    packet['earnings_context_ids']=[p['id'] for p in contexts]
    for key in ('financial','valuation','conclusion'):
        rows=packet['chapter_passages'].setdefault(key,[])
        known={p['id'] for p in rows}
        rows.extend(dict(p) for p in contexts if p['id'] not in known)
    validate_context(packet,text)
    return packet


def validate_context(packet,text):
    for pid in packet.get('earnings_context_ids',[]):
        spans=[p for rows in packet['chapter_passages'].values() for p in rows if p['id']==pid]
        if not spans:raise ValueError('Missing earnings context')
        for p in spans:
            digest=hashlib.sha256((packet['raw_sha256']+':'+str(p['start'])+':'+p['text']).encode()).hexdigest()
            if p['sourceHash']!=packet['raw_sha256'] or text[p['start']:p['end']]!=p['text'] or pid!='PASSAGE:'+digest[:16]:
                raise ValueError('Earnings context differs from original')


def revise_packet(source,cold_root,output):
    from app.review_frozen_dossier import load_frozen_packet
    from app.company_history_dossier import write_json
    if output.exists():raise ValueError('Preserve prior source revisions')
    original,raw=load_frozen_packet(source,cold_root)
    p=original['packet'];base=(cold_root/'raw/sec/company-filings'/p['ticker']).resolve()
    filing=(base/p['accession'].replace('-','')/unquote(urlsplit(p['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not filing.is_relative_to(base):raise ValueError('Source outside archive')
    parser=FilingText();parser.feed(filing.read_bytes().decode('utf-8'));text=parser.clean()
    revised=deepcopy(original);add_context(revised['packet'],text)
    if not revised['packet']['earnings_context_ids']:raise ValueError('No matching original context; review manually')
    revised['fingerprint']=hashlib.sha256(json.dumps({'version':revised['version'],'packet':revised['packet']},sort_keys=True).encode()).hexdigest()
    revised['evidenceRevision']={'kind':'same_filing_earnings_context/v1','parentPath':str(source),
        'parentSha256':hashlib.sha256(raw).hexdigest(),'parentFingerprint':original['fingerprint'],
        'modelCalls':0,'automaticApproval':False,'queueChanged':False,
        'note':'Prior chapters require explicit migration/review against this new fingerprint.'}
    write_json(output,revised)
    load_frozen_packet(output,cold_root)
    return {'ticker':p['ticker'],'contexts':len(revised['packet']['earnings_context_ids']),
            'fingerprint':revised['fingerprint'],'output':str(output),'queueChanged':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('source','cold-root','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(revise_packet(a.source,a.cold_root,a.output)))
