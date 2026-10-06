import pytest
from app.company_history_dossier import Section, validate_section, CHAPTERS

def section():
    pair={"zh":"本财季收入增长与现金流并非同向，产品结构的贡献需要进一步验证。"*12,"en":"Revenue and cash flow do not move together. Product mix remains a hypothesis requiring evidence. "*10}
    return Section(**{k:pair.copy() for k in ["analysis","mechanism","counterEvidence","evidenceGaps","validationPlan"]},evidence_refs=["FACT:1"])

def test_full_bilingual_structure():
    assert len(CHAPTERS)==9
    validate_section(section(),{"FACT:1"})

def test_currency_conversion_and_missing_translation_fail_closed():
    s=section();s.analysis.en+=' $445.82 billion'
    with pytest.raises(ValueError):validate_section(s,{"FACT:1"})
    s=section();s.analysis.en=s.analysis.zh
    with pytest.raises(ValueError):validate_section(s,{"FACT:1"})
    s=section();s.analysis.zh='短文'
    with pytest.raises(ValueError):validate_section(s,{"FACT:1"})

def test_unknown_citation_rejected():
    s=section();s.evidence_refs=["FACT:999"]
    with pytest.raises(ValueError):validate_section(s,{"FACT:1"})


def test_malformed_inline_id_cannot_escape_validation():
    from app.historical_earnings_report import validate_citations
    for text in ['FACT:ca6697b3c229','PASSAGE:1111111111111111extra','SEC:madeup','BULK:wrong']:
        with pytest.raises(ValueError,match='Inline citation'):validate_citations(text,{'FACT:1'})
    validate_citations('Supported by FACT:1.',{'FACT:1'})


def test_claim_statements_cannot_bypass_numerical_prose_guard():
    from app.company_history_dossier import GroundedClaim
    s=section()
    s.grounded_claims=[GroundedClaim(passage_id='PASSAGE:1111111111111111',quote='An original statement long enough for citation.',statement={'zh':'公司净利润为189百万美元。','en':'Net income was 189 million dollars.'})]
    with pytest.raises(ValueError,match='Numerical claims'):validate_section(s,{'FACT:1','PASSAGE:1111111111111111'})
