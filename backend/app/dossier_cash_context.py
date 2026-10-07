"""Create citable exact cash-table spans; preserve earlier frozen packet."""
import copy,hashlib,json
from urllib.parse import urlsplit,unquote
from app.historical_earnings_report import FilingText
from app.company_history_dossier import write_json
from app.review_frozen_dossier import load_frozen_packet


def validate_context(packet,text):
    for pid in packet.get('cash_context_ids',[]):
        records=[p for ps in packet['chapter_passages'].values() for p in ps if p['id']==pid]
        if not records:raise ValueError('Missing cash context')
        for p in records:
            if p['sourceHash']!=packet['raw_sha256'] or text[p['start']:p['end']]!=p['text']:raise ValueError('Cash context changed')
            digest=hashlib.sha256((p['sourceHash']+':'+str(p['start'])+':'+p['text']).encode()).hexdigest()
            if pid!='PASSAGE:'+digest[:16]:raise ValueError('Cash context identity changed')


def attach(source,cold,output):
    if output.exists():raise ValueError('Preserve prior packet')
    original,raw=load_frozen_packet(source,cold);r=copy.deepcopy(original);p=r['packet']
    base=(cold/'raw/sec/company-filings'/p['ticker']).resolve()
    f=(base/p['accession'].replace('-','')/unquote(urlsplit(p['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not f.is_relative_to(base):raise ValueError('Archive escape')
    parser=FilingText();parser.feed(f.read_bytes().decode('utf-8'));text=parser.clean()
    mapping=p['verified_cash_source']['mapping'];header=text.find('CONDENSED CONSOLIDATED STATEMENTS OF CASH FLOWS')
    if header<0:raise ValueError('Cash statement heading not found')
    positions={k:text.find(mapping['rows'][k]['label'],header) for k in ('netIncome','operating','closing')}
    if min(positions.values())<0 or not positions['netIncome']<positions['operating']<positions['closing']:raise ValueError('Cash rows cannot be located safely')
    end=text.find('Supplemental',positions['closing'])
    if end<0:raise ValueError('Cash statement end not found')
    spans=[(positions['netIncome'],positions['operating']),(positions['operating'],end)]
    contexts=[]
    for lo,hi in spans:
        value=text[lo:hi].rstrip();hi=lo+len(value)
        if not 30<len(value)<=2200:raise ValueError('Cash context exceeds quotation bound')
        digest=hashlib.sha256((p['raw_sha256']+':'+str(lo)+':'+value).encode()).hexdigest()
        contexts.append({'id':'PASSAGE:'+digest[:16],'start':lo,'end':hi,'text':value,'sourceHash':p['raw_sha256'],'score':0})
    p['cash_context_ids']=[c['id'] for c in contexts]
    for key in ('financial','capital','factors','conclusion'):p['chapter_passages'][key].extend(copy.deepcopy(contexts))
    validate_context(p,text)
    r['fingerprint']=hashlib.sha256(json.dumps({'version':r['version'],'packet':p},sort_keys=True).encode()).hexdigest()
    r['continuation']={'parentSourceSha256':hashlib.sha256(raw).hexdigest(),'method':'Added exact same-filing cash-table spans for model citations; unchanged numeric ledger'}
    write_json(output,r);return r
