"""Read legacy HTML tables and recover context without rewriting frozen packets.

Explicit table/column mappings must be reviewed. Nothing here invents missing
cells, infers trading eligibility, or treats a balanced total as causal proof.
"""
import hashlib
import re
from decimal import Decimal
from html.parser import HTMLParser


class FilingTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[]
        self.stack=[]

    def handle_starttag(self,tag,attrs):
        if tag=='table':
            table={'index':len(self.tables),'rows':[],'nested':False}
            if self.stack:self.stack[-1]['table']['nested']=True
            self.tables.append(table);self.stack.append({'table':table,'row':None,'cell':None})
        elif self.stack:
            frame=self.stack[-1]
            if tag=='tr':frame['row']=[];frame['table']['rows'].append(frame['row'])
            elif tag in ('td','th') and frame['row'] is not None:
                frame['cell']=[];frame['row'].append(frame['cell'])
            elif tag=='br' and frame['cell'] is not None:frame['cell'].append(' ')

    def handle_endtag(self,tag):
        if not self.stack:return
        if tag=='table':self.stack.pop()
        elif tag in ('td','th'):self.stack[-1]['cell']=None
        elif tag=='tr':self.stack[-1]['row']=None;self.stack[-1]['cell']=None

    def handle_data(self,data):
        if self.stack and self.stack[-1]['cell'] is not None:self.stack[-1]['cell'].append(data)

    def result(self):
        return [{**t,'rows':[[' '.join(''.join(c).split()) for c in row] for row in t['rows']]} for t in self.tables]


def tables(html):
    p=FilingTables();p.feed(html);return p.result()


def number(cells,scale):
    """Reviewed column slices include split currency/sign cells; blanks aren't zero."""
    text=''.join(cells).replace(' ','').replace(',','').replace('$','')
    if text in ('—','–'):text='0'
    if not re.fullmatch(r'-?\d+(?:\.\d+)?|\(\d+(?:\.\d+)?\)',text):
        raise ValueError('Missing or ambiguous numeric column')
    value=-Decimal(text[1:-1]) if text.startswith('(') else Decimal(text)
    if scale not in (1,1000,1000000):raise ValueError('Unreviewed monetary scale')
    return str(value*scale)


def extract_table(html,source_hash,mapping):
    if hashlib.sha256(html.encode()).hexdigest()!=source_hash:
        raise ValueError('Source hash mismatch; decode without replacing original bytes')
    if mapping.get('sourceHash')!=source_hash or mapping.get('reviewer')!='codex_assistant':
        raise ValueError('Explicit matching source mapping required')
    if mapping['unit']!='USD':raise ValueError('Only reviewed USD statement mapping supported')
    candidates=tables(html)
    table=candidates[mapping['tableIndex']]
    if table['nested']:raise ValueError('Nested table requires separate review')
    for anchor in mapping['anchors']:
        if table['rows'][anchor['row']]!=anchor['cells']:raise ValueError('Table header/period anchor changed')
    facts={}
    for key,spec in mapping['rows'].items():
        row=table['rows'][spec['row']]
        if row[0]!=spec['label']:raise ValueError('Mapped row label changed')
        facts[key]={}
        for period,span in mapping['columns'].items():
            cells=row[span[0]:span[1]]
            if len(cells)!=span[1]-span[0]:raise ValueError('Column outside row')
            parse_cells=['0'] if mapping.get('reviewedZeroDash')=='-' and ''.join(cells).replace('$','').strip()=='-' else cells
            identity=hashlib.sha256((source_hash+':'+str(table['index'])+':'+str(spec['row'])+':'+period).encode()).hexdigest()
            facts[key][period]={'value':number(parse_cells,mapping['scale']),'unit':mapping['unit'],
                'evidence_id':'TABLE:'+identity,'tableIndex':table['index'],'rowIndex':spec['row'],
                'rawLabel':row[0],'rawCells':cells,'sourceHash':source_hash}
    return facts


def subtotal_checks(facts,groups,period):
    result={}
    for total,components in groups.items():
        if not components or len(set(components))!=len(components):raise ValueError('Duplicate/empty subtotal components')
        value=sum(Decimal(facts[k][period]['value']) for k in components)
        residual=value-Decimal(facts[total][period]['value'])
        result[total]={'state':'matched' if residual==0 else 'mismatch','computed':str(value),
                       'residual':str(residual),'components':components}
    return result


def reconcile(facts,period,flow_components=('operating','investing','financing','fx')):
    if tuple(flow_components) not in (('operating','investing','financing','fx'),('operating','investing','financing')):
        raise ValueError('Unsupported statement flow components')
    required=(*flow_components,'netChange','opening','closing')
    selected={k:facts[k][period] for k in required}
    if {f['unit'] for f in selected.values()}!={'USD'}:raise ValueError('Cash statement currency mismatch')
    values={k:Decimal(f['value']) for k,f in selected.items()}
    if not all(v.is_finite() for v in values.values()):raise ValueError('Non-finite cash fact')
    flow=sum(values[k] for k in flow_components)
    balance=values['closing']-values['opening']
    return {'state':'matched' if flow==balance==values['netChange'] else 'mismatch',
        'period':period,'basis':'cash_and_cash_equivalents_as_labelled_in_original_statement',
        'flowComponents':list(flow_components),'separateFxLineDisclosed':'fx' in flow_components,
        'computedNetChange':str(flow),'reportedNetChange':str(values['netChange']),
        'balanceChange':str(balance),'flowResidual':str(flow-values['netChange']),
        'balanceResidual':str(balance-values['netChange']),'facts':selected,
        'meaning':'Arithmetic only; not an assessment of earnings quality or solvency.'}


def recover_context(text,needle,source_hash,before=350,after=500):
    hits=list(re.finditer(re.escape(needle),text,re.I))
    if len(hits)!=1:raise ValueError('Context anchor must be unique')
    hit=hits[0];lo=max(0,hit.start()-before);hi=min(len(text),hit.end()+after)
    value=text[lo:hi]
    return {'id':'CONTEXT:'+hashlib.sha256((source_hash+':'+str(lo)+':'+value).encode()).hexdigest(),
            'start':lo,'end':hi,'text':value,'sourceHash':source_hash,
            'scope':'Exact contiguous filing text; window edges may be truncated.'}


def prepare_cash_source(source_path,mapping_path,cold_root,output):
    """Check a second issuer before model work; source-ready is not report-ready."""
    import json
    from pathlib import Path
    from urllib.parse import unquote,urlsplit
    from app.company_history_dossier import write_json
    from app.historical_earnings_report import FilingText
    from app.review_frozen_dossier import load_frozen_packet
    if output.exists():raise ValueError('Preserve previous prepared source')
    original,_=load_frozen_packet(source_path,cold_root);packet=original['packet']
    mapping_raw=mapping_path.read_bytes();mapping=json.loads(mapping_raw)
    if mapping['ticker']!=packet['ticker'] or mapping['accession']!=packet['accession']:raise ValueError('Mapping identity mismatch')
    base=(cold_root/'raw/sec/company-filings'/packet['ticker']).resolve()
    path=(base/packet['accession'].replace('-','')/unquote(urlsplit(packet['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not path.is_relative_to(base):raise ValueError('Source escaped archive')
    html=path.read_bytes().decode('utf-8');p=FilingText();p.feed(html)
    if mapping['scaleEvidence'] not in p.clean():raise ValueError('Reviewed monetary scale context missing')
    facts=extract_table(html,packet['raw_sha256'],mapping)
    components=mapping.get('flowComponents',['operating','investing','financing','fx'])
    bridges={period:reconcile(facts,period,components) for period in mapping['columns']}
    checks={period:subtotal_checks(facts,mapping['subtotalGroups'],period) for period in mapping['columns']}
    if any(b['state']!='matched' for b in bridges.values()) or any(c['state']!='matched' for cs in checks.values() for c in cs.values()):
        raise ValueError('Unreconciled cash source requires review')
    # Independent original-table versus retained structured-data CFO cross-check.
    retained=[]
    for period in mapping['columns']:
        candidates=[f for f in packet['facts'] if f['concept']=='NetCashProvidedByUsedInOperatingActivities' and f['period_end']==period and f['unit']=='USD']
        values={Decimal(str(f['value'])) for f in candidates}
        if values!={Decimal(facts['operating'][period]['value'])}:raise ValueError('Original CFO conflicts with structured source')
        retained.append({'period':period,'state':'matched','evidence_refs':[f['evidence_id'] for f in candidates]})
    result={'state':'cash_source_ready_not_report_generated','ticker':packet['ticker'],'accession':packet['accession'],
        'sourceFingerprint':original['fingerprint'],'sourceHash':packet['raw_sha256'],'mapping':mapping,
        'mappingHash':hashlib.sha256(mapping_raw).hexdigest(),'facts':facts,'cashReconciliations':bridges,
        'subtotalChecks':checks,'structuredSourceChecks':retained,'sourcePath':str(source_path),
        'modelRequests':0,'reportGenerated':False,'published':False,'humanAccepted':False}
    write_json(output,result)
    return result
