import pytest
from app.company_history_dossier import Section,validate_section


def section(zh,en):
    pairs={k:{'zh':zh,'en':en} for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')}
    pairs['analysis']={'zh':zh+'原文资料用于描述历史比较范围，并不能独立证明经济传导已经发生。'*9,
        'en':en+' The original filing describes a historical comparison, not independent proof of a causal mechanism.'*9}
    return Section(**pairs,
        evidence_refs=['SEC:test'],grounded_claims=[{'passage_id':'p','quote':'Net sales during 2008 increased from the previous year.',
        'statement':{'zh':'比较期间的销售额有所增加。','en':'Sales increased in the comparison period.'}}])


def test_source_quoted_year_label_keeps_time_scope():
    validate_section(section('2008年是历史比较期间。','The comparison refers to sales in 2008.'),{'SEC:test','p'})
    validate_section(section('2008年是历史比较期间。','The 2008 Mac sales comparison describes an earlier period.'),{'SEC:test','p'})
    validate_section(section('核对2008年度比较期间。','Compare the disclosures for the year 2008'),{'SEC:test','p'})


def test_original_ledger_period_is_also_a_valid_year_label():
    ledger={'comparisons':[{'id':'x','concept':'Sales','current':{'period_end':'2009-12-31'},'previous':{'period_end':'2008-12-31'}}]}
    validate_section(section('报告期间为2009年。','The report period ended in 2009.'),{'SEC:test','p'},ledger)


@pytest.mark.parametrize('zh,en',[
    ('2010年销售额增加。','Sales increased in 2010.'),
    ('销售额为2008美元。','Revenue was 2008 dollars.'),
    ('销售额为2008美元。','Revenue increased from 2008 dollars.'),
    ('销售额为2008。','Revenue was 2008'),
    ('销售额增长2008%。','Revenue increased 2008%.')])
def test_unattested_year_or_quantity_not_whitelisted(zh,en):
    with pytest.raises(ValueError,match='Numerical claims'):validate_section(section(zh,en),{'SEC:test','p'})
