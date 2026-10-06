from datetime import date,timedelta
import pytest
from app.company_chart_export import chart_facts
from app.lab_expansion_export import basket_study,multifactor,interval

def fact(**kwargs):
    return dict(concept='Revenues',value=100,unit='USD',period_start='2024-01-01',period_end='2024-03-31',filed_at='2024-05-01',source_url='https://www.sec.gov/example',**kwargs)

def test_chart_separates_duration_and_omits_future():
    q=fact();y={**q,'period_end':'2024-06-30','filed_at':'2024-08-01'}
    a={**q,'period_end':'2024-12-31','filed_at':'2025-02-01'}
    metrics,conflicts=chart_facts([q,y,a],'2024-12-31')
    assert [p['basis'] for p in metrics['revenue']]==['quarter','ytd']
    assert conflicts==0

def test_chart_conflicts_and_latest_version():
    q=fact();metrics,n=chart_facts([q,{**q,'value':200}],'2025-01-01')
    assert n==1 and not metrics['revenue']
    metrics,n=chart_facts([q,{**q,'value':200,'filed_at':'2024-06-01'}],'2025-01-01')
    assert metrics['revenue'][0]['value']==200

def prices(n=180,rate=.001):
    return [(date(2024,1,1)+timedelta(days=i),100*(1+rate)**i) for i in range(n)]

def test_basket_constant_prices_fees_not_fake_returns():
    p=prices(90,0);r=basket_study({'EQ:A':p,'TD:SPY':p},{'EQ:A':.8,'CASH:USD':.2},90)
    assert r['returnPercent']==pytest.approx(-.15992)
    assert r['annualizedReturn'] is None
    assert r['points'][0]['nav']==100

def test_basket_missing_data_not_zero_filled():
    assert basket_study({'TD:SPY':prices()},{'EQ:A':1},30)['state']=='insufficient_data'

def test_factor_decision_precedes_entry_and_holdings_disjoint():
    p=prices();r=multifactor(p,p,p,'linear');trades=r['trades']
    assert all(t['signal']<t['entry']<t['exit'] for t in trades)
    assert all(a['exit']<=b['entry'] for a,b in zip(trades,trades[1:]))
    assert all(t['net']<t['market'] for t in trades)
    changed=p[:90]+[(d,v*3) for d,v in p[90:]]
    r2=multifactor(changed,p,p,'linear')
    assert [t for t in trades if t['exit']<str(p[90][0])]==[t for t in r2['trades'] if t['exit']<str(p[90][0])]
    assert r['validatedAlpha'] is False

def test_interval_needs_samples():
    assert interval([1]*19) is None
    assert interval([0]*30)['lower']==0
