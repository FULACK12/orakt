"""Finite, resumable original-document collection for the frozen US leaders.

No model requests, no report approval, no automatic retry of access denials.
"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from app.company_completion import check_pause
from app.company_history_dossier import write_json
from app.legacy_sec_originals import run as collect
from app.leader_report_batch import now


def selected_companies(inventory):
    companies=inventory['companies']
    if any(c['marketRegion']!='us' for c in companies):raise ValueError('US leaders only')
    tickers=[c['ticker'] for c in companies]
    if len(tickers)!=len(set(tickers)):raise ValueError('Duplicate company')
    return tickers


def run(inventory_path,root,limit=108):
    raw=inventory_path.read_bytes();inventory=json.loads(raw);tickers=selected_companies(inventory)
    fingerprint=hashlib.sha256(raw).hexdigest();path=root/'progress.json'
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'inventorySha256':fingerprint,'cutoff':inventory['cutoff'],'companies':{},'published':False,'modelRequests':0}
    if state['inventorySha256']!=fingerprint:raise ValueError('Frozen source collection scope changed')
    def save(stage,**extra):
        state.update(stage=stage,checkedAt=now(),**extra)
        state['summary']=dict(Counter(c['stage'] for c in state['companies'].values()))
        write_json(path,state)
    try:
        count=0
        for ticker in tickers:
            if state['companies'].get(ticker,{}).get('stage')=='pass_finished':continue
            if count>=limit:break
            check_pause(root,'reports');count+=1;save('retrieving',activeTicker=ticker)
            # One issuer at a time, already bounded to this original inventory.
            r=collect(root/ticker,ticker,date.fromisoformat(inventory['cutoff']),include_named=True,
                accessions={v['accession'] for g in inventory['periods'] if g['ticker']==ticker for v in g['versions']},pause_root=root)
            state['companies'][ticker]={'stage':r['stage'],'documents':len(r['results']),
                'byState':dict(Counter(x['state'] for x in r['results']))}
            save('between_companies')
            if r['stage']=='source_access_backoff':save('source_access_backoff');return state
        save('pass_finished',activeTicker=None)
    except InterruptedError:
        save('safely_paused');return state
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--limit',type=int,default=108);a=p.parse_args()
    if not 1<=a.limit<=108:p.error('Use a bounded 1..108 company pass')
    r=run(a.inventory,a.root,a.limit);print(json.dumps({'stage':r['stage'],'summary':r['summary']}))
