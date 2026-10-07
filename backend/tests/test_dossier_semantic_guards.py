import pytest
from app.company_history_dossier import Section
from app.dossier_semantic_guards import known_semantic_errors


def section(zh, en):
    pair={'zh':zh,'en':en}
    return Section(**{k:pair for k in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']},evidence_refs=['SEC:test'])


@pytest.mark.parametrize('zh,en',[
    ('稀释可能提高每股收益。','Dilution may increase earnings per share.'),
    ('非暂时性减值就是一次性损失。','Other-than-temporary impairment means a one-time loss.')])
def test_observed_accounting_errors_rejected(zh,en):
    assert known_semantic_errors(section(zh,en),{})


def test_missing_authority_is_source_dependent():
    s=section('剩余回购额度未披露。','Remaining repurchase authority is unknown.')
    assert not known_semantic_errors(s,{})
    packet={'chapter_passages':{'capital':[{'text':'We are authorized to repurchase shares up to an additional amount of $1 billion.'}]}}
    assert known_semantic_errors(s,packet)


def test_corrections_and_valid_direction_not_rejected():
    s=section('不能将稀释解释为提高每股收益。剩余回购额度已披露。','Dilution lowers EPS holding earnings constant. The draft incorrectly called remaining repurchase authority unknown.')
    assert not known_semantic_errors(s,{})
    assert not known_semantic_errors(section('若未来盈利且相关证券具有稀释性，增加分母会降低而非提高每股收益。','An increased denominator lowers EPS.'),{})
