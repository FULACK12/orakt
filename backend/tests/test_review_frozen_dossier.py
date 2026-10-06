import hashlib
import json
import pytest
from app.review_frozen_dossier import assemble, run
from app.company_history_dossier import CHAPTERS, Section, validate_section
from app.financial_period_ledger import build_ledger

def section():
    pair={'zh':'本财季收入增长与现金流并非同向，产品结构的贡献需要进一步验证。'*12,'en':'Revenue and cash flow do not move together. Product mix requires further evidence. '*12}
    return Section(**{k:pair.copy() for k in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']},evidence_refs=['FACT:1'])


@pytest.fixture
def frozen(tmp_path):
    raw=b'archived filing fixture'
    archive=tmp_path/'raw/sec/company-filings/TEST/123'
    archive.mkdir(parents=True);(archive/'test.htm').write_bytes(raw)
    packet={'ticker':'TEST','accession':'123','as_of_date':'2025-05-28','period_end':'2025-04-27','filing_ref':'SEC:123','source_url':'https://example.test/test.htm','raw_sha256':hashlib.sha256(raw).hexdigest(),'facts':[{'evidence_id':'FACT:1','concept':'InventoryNet','value':1,'unit':'USD','period_start':None,'period_end':'2025-04-27','filed_at':'2025-05-28'}],'market_evidence':[],'excerpts':[{'text':'H20 products'}]}
    packet['financial_ledger']=build_ledger(packet)
    original={'version':'old-generator','packet':packet}
    original['fingerprint']=hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
    source=tmp_path/'source.json';source.write_text(json.dumps(original))
    reviewed={'reviewer':'codex_assistant','ticker':'TEST','asOf':'2025-05-28','localModel':'fixture','corrections':['Reviewed fixture'],'chapters':{k:section().model_dump() for k,*_ in CHAPTERS}}
    for i,(key,*_) in enumerate(CHAPTERS,1):(tmp_path/f'{i:02d}-{key}-attempt.json').write_text('{}')
    review=tmp_path/'review.json';review.write_text(json.dumps(reviewed))
    return source,review,tmp_path


def test_frozen_revision_preserves_parent_and_all_attempts(frozen):
    source,review,root=frozen;before=source.read_bytes();d=assemble(*frozen)
    assert len(d['chapters'])==9 and len(d['provenance']['retainedDrafts'])==9
    assert d['provenance']['parentVersion']=='old-generator'
    assert d['review']['humanAccepted'] is False and d['eligibleForPredictiveBacktest'] is False
    assert source.read_bytes()==before


def test_tampered_packet_and_raw_filing_rejected(frozen):
    source,review,root=frozen;original=source.read_text();o=json.loads(original);o['packet']['ticker']='BAD';source.write_text(json.dumps(o))
    with pytest.raises(ValueError,match='fingerprint'):assemble(*frozen)
    source.write_text(original);(root/'raw/sec/company-filings/TEST/123/test.htm').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash'):assemble(*frozen)


def test_incomplete_review_and_missing_original_draft_rejected(frozen):
    source,review,root=frozen;original=review.read_text();o=json.loads(original);del o['chapters']['capital'];review.write_text(json.dumps(o))
    with pytest.raises(ValueError,match='Every chapter'):assemble(*frozen)
    review.write_text(original);(root/'09-conclusion-attempt.json').unlink()
    with pytest.raises(ValueError,match='No retained'):assemble(*frozen)


def test_output_never_overwrites_revision(frozen):
    output=frozen[2]/'dossier.json';output.write_text('preserve')
    with pytest.raises(ValueError,match='already exists'):run(*frozen,output)
    assert output.read_text()=='preserve'


def test_product_identifiers_next_to_chinese_text_are_not_numbers():
    s=section();s.analysis.zh+='H20产品受到限制。';s.analysis.en+=' H20 products face restrictions.'
    validate_section(s,{'FACT:1'},technical_terms=['H20'])
    s.analysis.en+=' H20000 products.'
    with pytest.raises(ValueError,match='Numerical'):validate_section(s,{'FACT:1'},technical_terms=['H20'])
