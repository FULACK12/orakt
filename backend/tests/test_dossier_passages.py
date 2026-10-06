import pytest
from app.dossier_passages import retrieve_passages,check_claims

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
