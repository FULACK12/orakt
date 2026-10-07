import pytest
from app.dossier_claim_pilot import extraction_messages,validate_extract


def test_extraction_uses_only_single_passage():
    messages=extraction_messages('NKE',{'text':'Wholesale increased while direct revenue decreased.','id':'p'})
    assert len(messages)==2
    assert 'Wholesale increased' in messages[1]['content']
    assert 'financial_ledger' not in messages[1]['content']


def test_numerical_extraction_is_not_silently_accepted():
    pair={'zh':'公司披露渠道表现不同。','en':'The company disclosed different channel performance.'}
    assert validate_extract({'disclosed_fact':pair,'not_established':pair})
    with pytest.raises(ValueError,match='numerical'):
        validate_extract({'disclosed_fact':{**pair,'en':'Sales increased 9%.'},'not_established':pair})

def test_number_abstraction_changes_only_prompt_not_evidence():
    import json
    passage={'id':'source-123','text':'Client revenue decreased 65% while embedded revenue increased 163%.'}
    before=dict(passage)
    prompt=json.loads(extraction_messages('AMD',passage,{'as_of_date':'2023-05-03'},abstract_numbers=True)[1]['content'])
    assert passage==before
    assert '65' not in prompt['paragraph_for_qualitative_summary']
    assert 'decreased' in prompt['paragraph_for_qualitative_summary']
    assert prompt['numeric_spans_abstracted'] is True
    assert '2023' not in json.dumps(prompt['source_contract'])

def test_placeholder_leakage_and_channel_scope_are_blocked():
    pair={'zh':'收入下降。','en':'Revenue declined.'}
    with pytest.raises(ValueError,match='placeholders'):
        validate_extract({'disclosed_fact':{**pair,'en':'Sales fell [number retained in original]%.'},'not_established':pair})
    with pytest.raises(ValueError,match='consumption'):
        validate_extract({'disclosed_fact':{**pair,'zh':'公司发货量低于需求。'},'not_established':pair},{'text':'shipping below consumption to reduce downstream inventory'})
