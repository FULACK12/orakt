import hashlib
import pytest
from app.dossier_operating_scope import operating_scope


def packet(chapter):
    texts = {
        'business': {
            'derivative_income_effect_table': 'Consolidated Statement of Income: The Effect of Derivatives\nGain / (Loss)\nThree Months Ended\nJune 30 Gain / (Loss)\nSix Months Ended\nJune 30\nType of 2026 2025 2026 2025\nContract Statement of Income Classification (Millions of dollars)',
            'income_eps_periods': 'CONSOLIDATED STATEMENT OF INCOME\nOriginal company income.'},
        'competition': {'annual_run_rate_savings': 'Management reported capturing $3 billion in annual run-rate savings.'},
        'supply': {'supply_contracts_complete': 'demand planning, volume commitments; fixed, indexed and performance-based contracts; lag before the company’s costs reflect changes in market trends',
                   'supply_purchase_commitments': 'pipeline and storage capacity, utilities, and petroleum products'},
        'macro': {'future_environment_standard': 'It becomes effective for fiscal years beginning after December 15, 2027. The company is evaluating the effect of the standard.',
                  'derivative_instruments_and_realized_impacts': 'Commodity volatility resulted in significant mark-to-market earnings and cash flow impacts.'},
    }[chapter]
    p={'ticker':'CVX','as_of_date':'2026-08-06','period_end':'2026-06-30','raw_sha256':'raw',
       'chapter_passages':{chapter:[{'text':t,'start':100,'sourceHash':'raw','contextRole':r} for r,t in texts.items()]}}
    rehash(p,chapter);return p


def rehash(p,k):
    for s in p['chapter_passages'][k]:s['id']='PASSAGE:'+hashlib.sha256(('raw:100:'+s['text']).encode()).hexdigest()[:16]
    p['review_chapter_selection']={k:[s['id'] for s in p['chapter_passages'][k]]}


@pytest.mark.parametrize('chapter',['business','competition','supply','macro'])
def test_original_scope_is_not_semantic_approval(chapter):
    r=operating_scope(packet(chapter),chapter)
    assert r['state']=='scope_checked_not_semantic_approval' and r['sourceIds'] and r['boundaries']


def test_run_rate_not_realized_and_standard_not_adoption():
    r=operating_scope(packet('competition'),'competition')
    assert r['facts']['managementReportedSavings']=='3'
    assert r['facts']['measurementBasis']=='annual_run_rate_not_cash_saved_during_reporting_period'
    r=operating_scope(packet('macro'),'macro')
    assert r['facts']['fiscalYearsBeginningAfter']=='2027-12-15'
    assert 'not_evidence_of_adoption' in r['facts']['statusAtCutoff']


@pytest.mark.parametrize('chapter,old,new',[
    ('business','The Effect of Derivatives','Total Company Revenue'),
    ('business','2026 2025 2026 2025','2026 2026 2025 2025'),
    ('business','Millions','Billions'),
    ('competition','annual run-rate','quarterly realized'),
    ('supply','fixed, indexed and performance-based','unspecified'),
    ('macro','is evaluating','has adopted'),
])
def test_scope_mutations_fail(chapter,old,new):
    p=packet(chapter)
    for s in p['chapter_passages'][chapter]:s['text']=s['text'].replace(old,new)
    rehash(p,chapter)
    with pytest.raises(ValueError):operating_scope(p,chapter)


def test_renew_review_at_later_cutoff():
    p=packet('macro');p['as_of_date']='2028-01-01'
    with pytest.raises(ValueError,match='reassessed'):operating_scope(p,'macro')


def test_mutated_hash_and_incomplete_context_fail():
    p=packet('supply');p['chapter_passages']['supply'][0]['text']+=' altered'
    with pytest.raises(ValueError,match='changed'):operating_scope(p,'supply')
    p=packet('macro');p['review_chapter_selection']['macro'].pop()
    with pytest.raises(ValueError,match='Missing'):operating_scope(p,'macro')
