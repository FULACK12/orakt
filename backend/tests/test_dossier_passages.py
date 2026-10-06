import pytest
from app.dossier_passages import retrieve_passages,check_claims,bind_selected_passages,selection_schema

def test_passage_quotes_bind_exact_source_offsets():
    text='Contents\nThe company reports revenue from product sales, but changing prices and customer demand can affect future results. These risks do not establish a causal conclusion.\n'
    p=retrieve_passages(text,'business','a'*64)[0]
    assert text[p['start']:p['end']]==p['text']
    assert p==retrieve_passages(text,'business','a'*64)[0]
    c={'passage_id':p['id'],'quote':p['text'],'statement':{'zh':'产品价格与客户需求是需要验证的风险。','en':'Product prices and customer demand are risks requiring verification.'}}
    check_claims([c],[p])
    with pytest.raises(ValueError):check_claims([{**c,'quote':'The market demand certainly declined.'}],[p])
    with pytest.raises(ValueError):check_claims([c],[p],required=True)
    assert retrieve_passages(text,'business','b'*64)[0]['id']!=p['id']


def test_archive_binds_quotes_without_rewriting_model_claims():
    passages=[{'id':'PASSAGE:'+str(i)*16,'text':'Original archived evidence paragraph with sufficient text '+str(i)} for i in (1,2)]
    draft={'grounded_claims':[{'passage_id':p['id'],'statement':{'zh':'原文披露的风险尚需核验。','en':'The disclosed risk still requires review.'}} for p in passages]}
    bound=bind_selected_passages(draft,passages)
    assert bound['grounded_claims'][0]['quote']==passages[0]['text']
    assert 'quote' not in draft['grounded_claims'][0]
    with pytest.raises(ValueError,match='model-written'):bind_selected_passages(bound,passages)
    with pytest.raises(ValueError,match='distinct'):bind_selected_passages({'grounded_claims':[draft['grounded_claims'][0]]*2},passages)
    draft['grounded_claims'][1]['passage_id']='PASSAGE:ffffffffffffffff'
    with pytest.raises(ValueError,match='outside'):bind_selected_passages(draft,passages)


def test_generation_schema_limits_ids_and_removes_model_quote():
    from app.company_history_dossier import Section
    from app.research import _compatible_json_schema
    schema=selection_schema(_compatible_json_schema(Section),[{'id':'PASSAGE:1111111111111111'}],{'SEC:0000000000-00-000001'})
    item=schema['properties']['grounded_claims']['items']
    if '$ref' in item:item=schema['$defs'][item['$ref'].rsplit('/',1)[-1]]
    assert 'quote' not in item['properties']
    assert 'quote' not in item['required']
    assert item['properties']['passage_id']['enum']==['PASSAGE:1111111111111111']
    assert schema['properties']['evidence_refs']['items']['enum']==['SEC:0000000000-00-000001']
