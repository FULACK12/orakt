from datetime import date,timedelta
import copy
import pytest
from app.dossier_factor_pilot import margin_feature,evaluate_event,independent_trades,interval,summarize,render


def event():
    return {'ticker':'NKE','accession':'original','periodEnd':'2026-08-31','filedAt':'2026-10-02','acceptedAt':'2026-10-03T00:15:53+00:00'}


def facts():
    def rows(vals):
        return [{'start':y+'-06-01','end':y+'-08-31','val':v,'accn':'original','filed':'2026-10-02'} for y,v in zip(['2025','2026'],vals)]
    return {'facts':{'us-gaap':{'Revenues':{'units':{'USD':rows([100,100])}},'GrossProfit':{'units':{'USD':rows([30,40])}}}}}


def test_exact_accession_feature_and_period_pair():
    f=margin_feature(facts(),event())
    assert f['delta']==pytest.approx(.1)
    assert f['positive']


@pytest.mark.parametrize('bad',['later_revision','conflict','ytd','missing_prior','filed_after'])
def test_no_later_restatement_or_ambiguous_period_feature(bad):
    fs=facts();rows=fs['facts']['us-gaap']['GrossProfit']['units']['USD']
    if bad=='later_revision':rows[1]['accn']='later'
    elif bad=='conflict':rows.append({**rows[1],'val':99})
    elif bad=='ytd':rows[1]['start']='2026-01-01'
    elif bad=='missing_prior':rows.pop(0)
    else:rows[1]['filed']='2026-11-01'
    assert margin_feature(fs,event())['state']!='available'


def prices():
    days=[str(date(2026,10,5)+timedelta(days=i)) for i in range(30)]
    return {s:{d:100+i for i,d in enumerate(days)} for s in ('NKE','SPY','XLY')}


def test_after_hours_utc_uses_new_york_date_then_next_session_close():
    e=evaluate_event(event(),margin_feature(facts(),event()),prices())
    assert e['signalDayNY']=='2026-10-02'
    assert e['entry']=='2026-10-05'
    assert e['marketExcess']==pytest.approx(-.0025)


def test_does_not_compress_missing_stock_days_into_shorter_window():
    ps=prices();del ps['NKE']['2026-10-09']
    assert evaluate_event(event(),margin_feature(facts(),event()),ps)['state']=='price_window_gap'


def test_unmatured_event_not_fabricated():
    assert evaluate_event(event(),margin_feature(facts(),event()),prices(),horizon=40)['state']=='forward_window_not_mature'


def test_same_day_entry_never_allowed_even_for_premarket():
    e=event();e['acceptedAt']='2026-10-05T10:04:00+00:00'
    assert evaluate_event(e,margin_feature(facts(),e),prices())['entry']=='2026-10-06'


def test_no_overlap_and_negative_signal_not_taken():
    e=evaluate_event(event(),margin_feature(facts(),event()),prices())
    b={**e,'accession':'b','entry':'2026-10-08'}
    c={**e,'accession':'c','feature':{**e['feature'],'positive':False}}
    kept,removed=independent_trades([e,b,c],'2024-01-01')
    assert len(kept)==1 and len(removed)==1


def test_small_sample_and_no_false_validated_alpha():
    assert interval([.1]*7) is None
    assert interval([.1]*8)==pytest.approx([.1,.1])
    s=summarize([])
    assert s['netPriceReturn']['mean'] is None
    assert not s['validatedAlpha'] and not s['eligibleForPredictiveBacktest']


def test_readable_report_shows_actual_coverage_and_sample_status():
    e=evaluate_event(event(),margin_feature(facts(),event()),prices())
    e['sampleStatus']='included_evaluation_trade'
    result={'priceCoverage':{'NKE':{'first':'2020-01-02','last':'2026-10-02','requestedEnd':'2026-10-05','count':1697}},
            'companies':{'NKE':{'summary':summarize([e]),'events':[e]}}}
    html=render(result)
    assert '2026-10-02' in html and '2026-10-05' in html
    assert 'Insufficient sample' in html
    assert 'included_evaluation_trade' in html
    assert 'not an ex-ante prediction' in html


def test_even_negative_margin_signal_keeps_observed_outcome_for_audit():
    f=margin_feature(facts(),event());f['positive']=False
    e=evaluate_event(event(),f,prices())
    assert e['state']=='observed'
    assert independent_trades([e],'2024-01-01')[0]==[]
