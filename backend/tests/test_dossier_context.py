import json
import pytest
from app.company_history_dossier import chapter_packet,chapter_allowed_ids,Section
from app.dossier_passages import check_claims,selection_schema
from app.research import _compatible_json_schema
from app.dossier_prompt import bounded_messages


def test_chapter_does_not_copy_other_chapters_or_full_text():
    packet={'ticker':'TEST','filing_ref':'SEC:0000000000-00-000001','facts':[],
            'financial_ledger':{'comparisons':[],'accountingRules':[]},
            'excerpts':[{'text':'x'*100000}], 'private_unused':'x'*100000,
            'chapter_passages':{'business':[{'id':'PASSAGE:1111111111111111','text':'Source paragraph'}], 'macro':[{'text':'x'*100000}]}}
    evidence=chapter_packet(packet,'business')
    assert len(json.dumps(evidence))<1000
    assert 'excerpts' not in evidence and 'chapter_passages' not in evidence
    assert chapter_allowed_ids(evidence)=={packet['filing_ref'],'PASSAGE:1111111111111111'}


def test_comparison_schema_pins_direction_and_period_together():
    schema=selection_schema(_compatible_json_schema(Section),[],set(),['CMP:a'],{'comparisons':[{'id':'CMP:a','direction':'decrease','periodType':'quarter'}]})
    props=schema['properties']['comparison_checks']['items']['oneOf'][0]['properties']
    assert props['direction']['const']=='decrease'
    assert props['period_type']['const']=='quarter'


def test_duplicate_claims_do_not_satisfy_minimum_sources():
    c={'passage_id':'p','quote':'Archived original paragraph of adequate length.','statement':{'zh':'这是原文披露。','en':'This is disclosed.'}}
    with pytest.raises(ValueError,match='distinct'):
        check_claims([c,c],[{'id':'p','text':c['quote']}],required=True)


def test_prompt_has_no_fake_ids_or_long_repair_history():
    messages=bounded_messages(json.dumps({'evidence':{},'previous_validation_error':'x'*50000}),'bad'*2000)
    assert len(messages)==2
    assert 'FACT:7996' not in messages[0]['content']
    assert len(json.loads(messages[1]['content'])['previous_validation_error'])==1800
