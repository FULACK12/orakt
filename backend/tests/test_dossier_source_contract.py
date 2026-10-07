import pytest
from app.dossier_source_contract import source_contract
from app.dossier_claim_pilot import validate_extract


def extract(zh,en='The source describes a specific reporting category.'):
    return {'disclosed_fact':{'zh':zh,'en':en},'not_established':{'zh':'该段没有证明相关因果关系。','en':'This paragraph does not establish causation.'}}


def test_corporate_segment_is_not_total_company_revenue():
    p={'text':'Corporate revenues primarily consisted of foreign currency gains and losses.'}
    with pytest.raises(ValueError,match='reporting category'):validate_extract(extract('公司收入主要由汇兑损益构成。'),p)
    validate_extract(extract('总部／未分配项收入主要由汇兑损益构成。'),p)


def test_converse_other_revenues_scope_is_preserved():
    p={'text':'Converse other revenues were primarily attributable to licensing businesses.'}
    with pytest.raises(ValueError,match='OTHER'):validate_extract(extract('匡威收入主要来自授权业务。'),p)
    validate_extract(extract('Converse 其他收入主要来自授权业务。'),p)


def test_regions_are_not_inferred_from_issuer():
    with pytest.raises(ValueError,match='Geographic'):validate_extract(extract('亚太地区收入下降。'),{'text':'Greater China revenues decreased.'})


def test_filing_date_is_not_fiscal_period():
    contract=source_contract({'text':'FIRST QUARTER OF FISCAL 2027 COMPARED TO FIRST QUARTER OF FISCAL 2026'}, {'as_of_date':'2026-10-02','period_end':'2026-08-31'})
    assert contract['filingDate']=='2026-10-02'
    assert contract['explicitFiscalLabels'][0].startswith('FIRST QUARTER OF FISCAL 2027')
    assert source_contract({'text':'Apparel revenue increased.'})['explicitFiscalLabels']==[]


def test_deferred_revenue_not_earned_revenue():
    with pytest.raises(ValueError,match='deferred'):validate_extract(extract('递延收入就是利润。'),{'text':'Deferred revenue is recognized when control transfers.'})


def test_post_period_month_does_not_invent_day_or_realized_savings():
    from app.dossier_source_contract import event_timing
    d=event_timing('In October 2026, NIKE announced a multi-year program.',{'period_end':'2026-08-31','as_of_date':'2026-10-02'})
    assert d[0]['afterPeriodEnd'] is True and d[0]['afterFilingMonth'] is False
    assert d[0]['eventMonth']=='2026-10' and d[0]['precision']=='month'
    assert 'eventDay' not in d[0]


def test_future_month_is_not_historically_known_without_review():
    from app.dossier_source_contract import event_timing
    d=event_timing('In November 2026, the issuer announced a plan.',{'period_end':'2026-08-31','as_of_date':'2026-10-02'})
    assert d[0]['afterFilingMonth'] is True


def test_fixed_to_floating_swap_direction_not_reversed():
    p={'text':'The swaps effectively convert the fixed interest rates on the notes to floating interest rates based on SOFR OIS.'}
    with pytest.raises(ValueError,match='direction reversed'):
        validate_extract(extract('公司把浮动利率转换为固定利率。','The swaps convert floating rates into fixed rates.'),p)
