"""Deterministic original-filing retrieval, with exact text offsets and hashes.

Matching a quotation proves attribution only, not that a model's interpretation
is entailed. Independent content review is still mandatory before publication.
"""
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote,urlsplit
from app.historical_earnings_report import FilingText

TOPICS={
 'business':r'product|business|revenue|sales|customer|gold|copper',
 'financial':r'cash flow|income|profit|margin|expense|revenue|sales',
 'capital':r'debt|borrow|dividend|repurchas|liquidity|capital|cash',
 'competition':r'compet|technology|patent|research|substitut|innovation',
 'supply':r'supplier|suppl|mine|production|manufactur|material|energy|cost|operat',
 'macro':r'interest rate|exchange rate|economic|inflation|commodity|credit|demand',
 'valuation':r'share|earnings|price|risk|outlook|uncertain|forecast',
 'factors':r'price|volume|cost|margin|revenue|risk|cash flow',
 'conclusion':r'outlook|risk|uncertain|cash flow|revenue|demand|sales',
}


def prose_fraction(text):
    """EDGAR table cells must not masquerade as narrative retrieval hits."""
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    if not lines:return 0.0
    # Older filings hard-wrap sentences. Genuine prose still has long lines;
    # a numeric table may contain many letters in labels but mostly short cells.
    return sum(len(line)>=45 and len(re.findall(r'[A-Za-z]+',line))>=6 for line in lines)/len(lines)

def retrieve_passages(text,chapter,source_hash,limit=8):
    matches=[]
    for m in re.finditer(r'[^\n]+',text):
        # Older EDGAR HTML wraps every line at about 100 characters. Retrieve
        # contiguous source spans, never concatenate unrelated paragraphs.
        if len(m.group())<45:continue
        stop=min(len(text),m.start()+1400)
        sentence=re.search(r'[.!?](?:\s|$)',text[m.start()+400:stop])
        end=m.start()+400+sentence.end() if sentence else stop
        raw=text[m.start():end];left=len(raw)-len(raw.lstrip());value=raw.strip()
        if not 100<=len(value)<=2200:continue
        if sum(c.isalpha() for c in value)<len(value)*.58:continue
        if prose_fraction(value)<.6:continue
        score=len(re.findall(TOPICS[chapter],value,re.I))
        if not score:continue
        digest=hashlib.sha256((source_hash+':'+str(m.start()+left)+':'+value).encode()).hexdigest()
        matches.append({'id':'PASSAGE:'+digest[:16],'start':m.start()+left,'end':m.start()+left+len(value),'text':value,'sourceHash':source_hash,'score':score})
    selected=[]
    for p in sorted(matches,key=lambda p:(-min(p['score'],8),p['start'])):
        if any(p['start']<q['end'] and q['start']<p['end'] for q in selected):continue
        selected.append(p)
        if len(selected)>=limit:break
    return sorted(selected,key=lambda p:p['start'])

def add_passages(packet,cold_root):
    base=(Path(cold_root)/'raw/sec/company-filings'/packet['ticker']).resolve()
    path=(base/packet['accession'].replace('-','')/unquote(urlsplit(packet['source_url']).path.rsplit('/',1)[-1])).resolve()
    if not path.is_relative_to(base):raise ValueError('Filing escaped archive')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=packet['raw_sha256']:raise ValueError('Original filing changed')
    parser=FilingText();parser.feed(raw.decode('utf-8',errors='replace'));text=parser.clean()
    packet['chapter_passages']={key:retrieve_passages(text,key,packet['raw_sha256']) for key in TOPICS}
    return packet

def check_claims(claims,passages,required=False):
    known={p['id']:p for p in passages}
    if required and len(claims)<2:raise ValueError('At least two source-grounded claims required')
    for claim in claims:
        c=claim.model_dump() if hasattr(claim,'model_dump') else claim
        p=known.get(c['passage_id'])
        # EDGAR hard line wraps are formatting, not changes to quoted words.
        if not p or len(c['quote'].strip())<30 or ' '.join(c['quote'].split()) not in ' '.join(p['text'].split()):
            raise ValueError('Claim quotation does not match its frozen original passage')
        if not re.search(r'[\u4e00-\u9fff]',c['statement']['zh']) or re.search(r'[\u4e00-\u9fff]',c['statement']['en']):
            raise ValueError('Grounded claims require Chinese and English statements')


def bind_selected_passages(draft, passages):
    """Attach original paragraphs to model-selected IDs, never repair quotations.

    This protocol deliberately does not ask a language model to copy source text.
    The statement remains unverified interpretation requiring content review.
    Legacy generated quotations must use check_claims, not this function.
    """
    import copy
    result=copy.deepcopy(draft)
    known={p['id']:p for p in passages}
    claims=result.get('grounded_claims',[])
    if len({c.get('passage_id') for c in claims})<2:
        raise ValueError('Select at least two distinct original passages')
    for c in claims:
        if 'quote' in c:
            raise ValueError('Selection protocol must not contain model-written quotes')
        p=known.get(c.get('passage_id'))
        if not p:raise ValueError('Selected passage is outside frozen chapter evidence')
        c['quote']=p['text']
    check_claims(claims,passages,required=True)
    return result


def selection_schema(schema, passages, allowed, required_comparisons=(), ledger=None):
    """Constrain IDs, with quotation text supplied only by the archive reader."""
    import copy
    schema=copy.deepcopy(schema)
    schema['required']=list(schema['properties'])
    schema['properties']['evidence_refs']['items']={'type':'string','enum':sorted(allowed)}
    claims=schema['properties']['grounded_claims']
    claims['minItems']=2
    item=claims['items']
    if '$ref' in item:
        item=schema['$defs'][item['$ref'].rsplit('/',1)[-1]]
    item['properties'].pop('quote',None)
    item['required']=[key for key in item.get('required',[]) if key!='quote']
    item['properties']['passage_id']={'type':'string','enum':[p['id'] for p in passages]}
    comparisons=schema['properties']['comparison_checks']
    comparisons['minItems']=len(required_comparisons)
    comparisons['maxItems']=len(required_comparisons)
    if required_comparisons:
        known={c['id']:c for c in (ledger or {}).get('comparisons',[])}
        if set(required_comparisons)-known.keys():raise ValueError('Required comparison missing from ledger')
        comparison=comparisons['items']
        if '$ref' in comparison:comparison=schema['$defs'][comparison['$ref'].rsplit('/',1)[-1]]
        comparison['properties']['comparison_id']={'type':'string','enum':list(required_comparisons)}
    return schema
