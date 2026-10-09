import pytest
from app.dossier_earnings_context import context_span
from app.dossier_review_context import validate_context

def fixture():
    text='A current annual operating result and liquidity explanation.'
    span=context_span(text,0,len(text),'original','annual_results')
    return text,{'raw_sha256':'original','review_context_ids':[span['id']],
        'chapter_passages':{'financial':[span]}}

def test_exact_review_context_is_bound_to_original():
    text,p=fixture();validate_context(p,text)

@pytest.mark.parametrize('kind',['text','hash','bounds','missing','duplicate'])
def test_tampered_review_context_fails(kind):
    text,p=fixture();r=p['chapter_passages']['financial'][0]
    if kind=='text':r['text']='Changed interpretation instead of exact source'
    if kind=='hash':r['sourceHash']='different'
    if kind=='bounds':r['start']=-1
    if kind=='missing':p['chapter_passages']['financial']=[]
    if kind=='duplicate':p['review_context_ids']*=2
    with pytest.raises(ValueError):validate_context(p,text)

@pytest.mark.parametrize('required_count',[1,5])
def test_review_context_replaces_redundant_keyword_hits(monkeypatch,required_count):
    import app.dossier_compact_writer as m
    rows=[{'id':str(i),'text':f'Annual source paragraph number {i} with a disclosed result.'} for i in range(9)]
    required=[p['id'] for p in rows[-required_count:]]
    packet={'ticker':'TEST','chapter_passages':{'financial':rows},'review_context_ids':required,'financial_ledger':{'comparisons':[]}}
    monkeypatch.setattr(m,'chapter_packet',lambda p,k:{'original_passages':rows,'financial_ledger':{'comparisons':[]}})
    monkeypatch.setattr(m,'disclosed_reference_terms',lambda p:[])
    monkeypatch.setattr(m,'gross_margin_checks',lambda p:[])
    view=m.writer_view(packet,'financial',False)
    ids=[p['id'] for p in view['passages']]
    assert set(required)<=set(ids)
    assert len(ids)==len(set(ids))
    assert required_count<=len(ids)<=max(4,required_count)
