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
