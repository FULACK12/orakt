import pytest
from app.report_metric_guards import check

PID = 'PASSAGE:2f4d9e5f9b5539d2'
SOURCE = ('Operating income for the three months ended June 27, 2026 was $2.0 billion '
          'compared to operating loss of $134 million for the prior year period. '
          'The increase in operating income was due to higher gross profit, partially offset by higher operating expenses.')


@pytest.mark.parametrize('sentence,source,count', [
    ('Improved cash flow links to operational efficiency.', 'We rely on external manufacturers.', 1),
    ('Operating cash flow increased.', 'We rely on external manufacturers.', 1),
    ('If operating cash flow increased, test the cause.', 'We rely on external manufacturers.', 0),
    ('Verify whether operating cash flow increased.', 'We rely on external manufacturers.', 0),
    ('Operating cash flow increased.', 'Cash provided by operations increased.', 0),
])
def test_narrative_result_needs_own_source(sentence, source, count):
    packet={'chapter_passages':{'business':[{'id':PID,'text':source},
             {'id':'PASSAGE:0000000000000001','text':'Operating cash flow increased.'}]}}
    body=sentence+' ['+PID+']'
    doc={'chapter':'business','section':{'analysis':{'en':body}}}
    result=check(packet,[doc])
    assert len(result)==count
    if count:
        f=result[0]
        assert f['code']=='narrative_result_source_mismatch'
        assert body[f['span']['start']:f['span']['end']]==f['actual']
        assert f['sourceIds']==[PID]
    doc['factBindings']=[{'location':'section/analysis/en'}]
    assert not check(packet,[doc])  # Binding validity is checked by the ledger layer.


def run(zh, en, source=SOURCE, extras=()):
    packet = {'chapter_passages': {'financial': [{'id': PID, 'text': source}, *extras]}}
    doc = {'chapter': 'financial', 'section': {'grounded_claims': [
        {'passage_id': PID, 'quote': source, 'statement': {'zh': zh, 'en': en}}]}}
    return check(packet, [doc])


def test_retained_amd_operating_income_translation_located():
    zh = '2026年第二季度运营收入同比改善，主要由于毛利增长，但运营费用增加部分抵消了这一趋势。'
    en = 'Q2 2026 operating income improved year-over-year, primarily due to higher gross profit, partially offset by increased operating expenses.'
    findings = run(zh, en)
    assert [f['code'] for f in findings] == ['bilingual_operating_profit_identity']
    f = findings[0]
    assert zh[f['span']['start']:f['span']['end']] == f['actual'] == '运营收入'
    assert f['sourceIds'] == [PID] and f['originalEvidence'][0]['text'] == SOURCE
    assert f['relatedLocation'].endswith('/en')


@pytest.mark.parametrize('quantity',['','66.9 million of ','1,200 of its '])
def test_treasury_retirement_is_not_a_new_repurchase(quantity):
    source='During the quarter the company retired '+quantity+'treasury shares. Stock Repurchase Program: total authority remains available.'
    result=run('公司回购库存股。','The company repurchased treasury shares but did not explain why.',source)
    assert [f['code'] for f in result]==['treasury_retirement_not_repurchase']
    assert not run('公司注销库存股。','The company retired treasury shares.',source)
    assert not run('注销不是回购。','The company retired, not repurchased treasury shares.',source)


def test_retained_amd_corrected_translation_not_flagged():
    assert not run('本季度集团营业利润由上年同期亏损转为盈利，毛利增加被营业费用增长部分抵消，净利润也改善。',
                   'Quarterly consolidated operating income turns positive from the prior-year loss as higher gross profit is partly offset by increased operating expenses; net income also improves.')


@pytest.mark.parametrize('zh,en', [
    ('营业收入和营业利润均增加。', 'Revenue and operating income increased.'),
    ('运营收入增长，营业利润改善。', 'Revenue increased and operating income improved.'),
    ('如果运营收入增加，则营业利润可能改善。', 'If revenue increases, operating income could improve.'),
    ('不是营业收入增加。', 'Operating income was not higher.'),
    ('尚未核实营业利润。', 'Verify whether operating income was higher.'),
    ('本期营业收入增加。', 'Operating revenue increased.'),
])
def test_negation_hypothesis_and_mixed_metrics_abstain(zh, en):
    assert not run(zh, en)


@pytest.mark.parametrize('metric', ['Operating income', 'Net income'])
def test_wrong_claim_source_not_repaired_by_unrelated_paragraph(metric):
    en = metric + ' increased.'
    findings = run('利润增加。', en, 'Net revenue increased with unit shipments.',
                   [{'id': 'PASSAGE:0000000000000001', 'text': metric + ' increased.'}])
    assert len(findings) == 1 and findings[0]['code'] == 'claim_metric_source_mismatch'
    assert findings[0]['sourceIds'] == [PID]
    assert findings[0]['actual'] in en


@pytest.mark.parametrize('en', [
    'Operating income was not disclosed.',
    'If operating income increased, the mechanism would need testing.',
    'Operating income was derived as revenue minus expenses.',
    'Operating income was estimated using the margin ratio.',
    'The source does not specify whether operating income increased.',
])
def test_absence_research_and_calculation_not_false_assertions(en):
    assert not run('研究限制。', en, 'Net revenue increased.')


def test_silent_source_not_treated_as_contradiction():
    assert not run('营业利润增加。', 'Operating income increased.', 'The company sells processors.')


def test_matching_metric_not_flagged():
    assert not run('营业利润改善。', 'Operating income improved.')


@pytest.mark.parametrize('source,en', [
    ('Revenue increased and income from operations improved.', 'Operating income improved.'),
    ('Revenue increased and operating earnings improved.', 'Operating income improved.'),
    ('Revenue increased and net earnings improved.', 'Net income improved.'),
])
def test_source_metric_aliases_are_not_false_binding_mismatches(source, en):
    assert not run('利润改善。', en, source)


def test_quality_worklist_integrates_triage_without_semantic_approval():
    from app.report_quality import check as quality_check, rules_digest
    from app.financial_period_ledger import build_ledger
    packet = {'ticker': 'TEST', 'period_end': '2026-06-30', 'as_of_date': '2026-08-01',
              'facts': [], 'chapter_passages': {'financial': [{'id': PID, 'text': SOURCE}]}}
    packet['financial_ledger'] = build_ledger(packet)
    doc = {'ticker': 'TEST', 'chapter': 'financial', 'section': {'grounded_claims': [
        {'passage_id': PID, 'quote': SOURCE,
         'statement': {'zh': '运营收入改善。', 'en': 'Operating income improved.'}}]}}
    result = quality_check(packet, [doc])
    assert 'bilingual_operating_profit_identity' in {f['code'] for f in result['findings']}
    assert not result['deterministicPassed'] and not result['semanticApproval']
    assert len(rules_digest()) == 64
