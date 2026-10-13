import hashlib
from decimal import Decimal
import pytest
from app.dossier_factor_candidate import candidate_observation


def packet():
    header = 'Three Months Ended\nJune 30 Six Months Ended\nJune 30\n2026 2025 2026 2025\n'
    texts = {
        'income_eps_periods': 'CONSOLIDATED STATEMENT OF INCOME\n' + header + '(Millions of dollars, except per-share amounts)\nSales and other operating revenues $ 67,199 $ 44,375 $ 114,755 $ 90,476',
        'comprehensive_income_periods': 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME\n' + header + '(Millions of dollars)\nIncome (taxes) benefit on defined benefit plans ( 98 ) ( 19 ) ( 120 ) ( 29 )\nComprehensive Income (Loss) Attributable to Chevron Corporation $ 12,552 $ 2,632 $ 14,633 $ 6,183',
        'complete_cash_statement_with_headers': 'CONSOLIDATED STATEMENT OF CASH FLOWS\nSix Months Ended\nJune 30\n2026 2025\n(Millions of dollars)\nNet Cash Provided by Operating Activities 25,147 13,765\nNet decrease (increase) in operating working capital ( 1,680 ) ( 2,130 )',
    }
    p = {'ticker': 'CVX', 'period_end': '2026-06-30', 'as_of_date': '2026-08-06', 'raw_sha256': 'raw',
         'chapter_passages': {'factors': [{'contextRole': r, 'text': t, 'start': 100, 'sourceHash': 'raw'} for r,t in texts.items()]}}
    rehash(p)
    return p


def rehash(p):
    for s in p['chapter_passages']['factors']:
        s['id'] = 'PASSAGE:' + hashlib.sha256(('raw:100:' + s['text']).encode()).hexdigest()[:16]
    p['review_chapter_selection'] = {'factors': [s['id'] for s in p['chapter_passages']['factors']]}


def test_matched_half_year_signal_is_not_a_return():
    p = packet(); r = candidate_observation(p)
    assert Decimal(r['linearSignal']['value']) == Decimal(25147)/Decimal(114755) - Decimal(13765)/Decimal(90476)
    assert r['linearSignal']['unit'] == 'ratio_difference_not_return'
    assert not r['backtest']['performed'] and r['backtest']['returns'] is None
    assert 'never period end' in r['availabilityRule']
    c = r['classificationChecks']
    assert c['pensionTaxEffect']['values'] == dict(quarterCurrent='-98',quarterPrevious='-19',halfYearCurrent='-120',halfYearPrevious='-29')
    assert 'not_tax_payable' in c['pensionTaxEffect']['metric']
    assert 'not_segment_operating_income' in c['comprehensiveIncome']['metric']
    for row in [r['inputs']['sales'], *c.values()]:
        s = next(s for s in p['chapter_passages']['factors'] if s['id']==row['sourceId'])
        assert s['text'][row['start']-100:row['end']-100] == row['surface']


@pytest.mark.parametrize('idx,old,new', [
    (0,'2026 2025 2026 2025','2025 2026 2025 2026'), (0,'Millions','Billions'),
    (0,'114,755','0'), (1,'COMPREHENSIVE INCOME','BALANCE SHEET'),
    (1,'Income (taxes) benefit on defined benefit plans','Tax-related accrued liabilities'),
    (2,'Six Months Ended','Three Months Ended'), (2,'Millions','Thousands'),
])
def test_wrong_period_units_and_metric_rows_fail(idx,old,new):
    p=packet();s=p['chapter_passages']['factors'][idx];s['text']=s['text'].replace(old,new);rehash(p)
    with pytest.raises(ValueError):candidate_observation(p)


def test_stale_source_and_duplicate_row_fail():
    p=packet();p['chapter_passages']['factors'][0]['text']+=' altered'
    with pytest.raises(ValueError,match='Changed'):candidate_observation(p)
    p=packet();p['chapter_passages']['factors'][0]['text']+='\nSales and other operating revenues $ 67,199 $ 44,375 $ 114,755 $ 90,476';rehash(p)
    with pytest.raises(ValueError,match='ambiguous'):candidate_observation(p)


def test_missing_source_or_future_period_fails():
    p=packet();p['review_chapter_selection']['factors'].pop()
    with pytest.raises(ValueError,match='Missing'):candidate_observation(p)
    p=packet();p['as_of_date']='2026-06-29'
    with pytest.raises(ValueError,match='precedes'):candidate_observation(p)


def test_cash_source_not_cash_use_has_zero_pressure_not_negative_gate():
    p=packet();p['chapter_passages']['factors'][2]['text']=p['chapter_passages']['factors'][2]['text'].replace('( 1,680 )','1,680');rehash(p)
    r=candidate_observation(p)
    assert Decimal(r['nonlinearCandidate']['currentCashUseToSales'])==0
    assert Decimal(r['nonlinearCandidate']['value'])==0
