import copy
from datetime import date,timedelta
import pytest
from app.dossier_extended_study import inventory_feature,subscription_feature,calendar_sessions,cohort
from app.dossier_factor_pilot import evaluate_event
from app.dossier_corporate_actions import classify


def event():return {'ticker':'NKE','accession':'a','filedAt':'2026-10-02','acceptedAt':'2026-10-03T00:15:00+00:00','periodEnd':'2026-08-31'}
def margin():return {'state':'available','positive':True,'delta':.01,'current':{'revenue':110,'end':'2026-08-31'},'prior':{'revenue':100,'end':'2025-08-31'}}
def stock(val,end,accn='a',filed='2026-10-02'):return {'val':val,'end':end,'accn':accn,'filed':filed}
def facts():return {'facts':{'us-gaap':{'InventoryNet':{'units':{'USD':[stock(55,'2026-08-31'),stock(50,'2025-08-31','prior','2025-10-01')]}}}}}


def test_inventory_uses_only_asof_vintage():
    f=facts();f['facts']['us-gaap']['InventoryNet']['units']['USD'].append(stock(1,'2025-08-31','future','2027-01-01'))
    r=inventory_feature(f,event(),margin())
    assert r['state']=='available' and r['pressure']==pytest.approx(0)
    assert all(v['filed']<='2026-10-02' for v in r['priorReferences'])


def test_inventory_does_not_mix_total_and_finished_goods():
    f=facts();prev=f['facts']['us-gaap']['InventoryNet']['units']['USD'].pop()
    f['facts']['us-gaap']['InventoryFinishedGoodsNetOfReserves']={'units':{'USD':[prev]}}
    assert inventory_feature(f,event(),margin())['state']!='available'


def test_inventory_conflicts_fail_closed():
    f=facts();f['facts']['us-gaap']['InventoryFinishedGoodsNetOfReserves']={'units':{'USD':[stock(99,'2026-08-31'),stock(20,'2025-08-31')]}}
    assert inventory_feature(f,event(),margin())['state']=='conflicting_inventory_concepts'


def test_subscription_uses_exact_paired_costs_not_consolidated():
    def r(y,v):return {'start':str(y)+'-06-01','end':str(y)+'-08-31','accn':'a','filed':'2026-10-02','val':v}
    f={'facts':{'us-gaap':{'SubscriptionRevenue':{'units':{'USD':[r(2025,100),r(2026,110)]}},
        'CostOfGoodsSoldSubscription':{'units':{'USD':[r(2025,30),r(2026,22)]}},
        'GrossProfit':{'units':{'USD':[r(2025,1),r(2026,1)]}}}}}
    result=subscription_feature(f,event())
    assert result['delta']==pytest.approx(.1)
    assert {r['concept'] for r in result['sourceReferences']}=={'SubscriptionRevenue','CostOfGoodsSoldSubscription'}
    f['facts']['us-gaap']['CostOfGoodsSoldSubscription']['units']['USD'][1]['start']='2026-01-01'
    assert subscription_feature(f,event())['state']!='available'


def test_calendar_cannot_skip_missing_spy_observation():
    days=[str(date(2026,10,5)+timedelta(days=i)) for i in range(30)]
    prices={s:{d:100 for d in days} for s in ['NKE','SPY','XLY']}
    del prices['SPY'][days[3]]
    r=evaluate_event(event(),margin(),prices,sessions=days)
    assert r['state']=='price_window_gap' and r['missingSymbol']=='SPY'


def test_calendar_special_closures_and_current_missing_monday():
    pytest.importorskip('exchange_calendars')
    days,_=calendar_sessions('2012-10-26','2012-11-02')
    assert '2012-10-29' not in days and '2012-10-30' not in days
    days,_=calendar_sessions('2026-10-02','2026-10-05')
    assert days==['2026-10-02','2026-10-05']
    days,_=calendar_sessions('2010-01-01','2010-01-05')
    assert days==['2010-01-04','2010-01-05']


def test_entitlement_is_not_zero_dividends():
    r=classify({'status':'error','code':403},'NKE','dividends')
    assert r['state']=='provider_unavailable' and 'records' not in r
    r=classify({'meta':{'symbol':'NKE'},'dividends':[]},'NKE','dividends')
    assert r['state']=='retained_unreconciled' and not r['completeCoverage']


def test_subscription_dimension_excludes_customer_subtotals():
    from app.dossier_subscription_evidence import subscription_rows
    r={'concept':'Revenues [subscription]','base_concept':'Revenues','dimensions':{'srt:ProductOrServiceAxis':'adbe:SubscriptionRevenueMember'},
       'unit':'USD','period_start':'2026-06-01','period_end':'2026-08-31','value':'100','evidence_id':'IX:one','filed_at':'2026-10-02','source_url':'https://www.sec.gov/example'}
    customer={**r,'dimensions':{**r['dimensions'],'srt:MajorCustomersAxis':'adbe:CustomerGroupMember'}}
    whole={**r,'dimensions':{}}
    selected=subscription_rows([r,customer,whole],'a')
    assert len(selected)==1 and selected[0]['concept']=='SubscriptionRevenue'
    legacy={**r,'base_concept':'SubscriptionRevenues','concept':'SubscriptionRevenues','dimensions':{}}
    selected=subscription_rows([legacy],'a')
    assert selected[0]['concept']=='SubscriptionRevenue' and selected[0]['originalConcept']=='SubscriptionRevenues'
    old={**legacy,'base_concept':'SubscriptionandCirculationRevenue','concept':'SubscriptionandCirculationRevenue'}
    assert subscription_rows([old],'a')[0]['concept']=='SubscriptionRevenue'
    oldcost={**legacy,'base_concept':'CostofSubscriptionRevenue','concept':'CostofSubscriptionRevenue'}
    assert subscription_rows([oldcost],'a')[0]['concept']=='CostOfGoodsSoldSubscription'


def test_gap_patch_selects_requested_day_not_extra_day():
    from app.dossier_price_gap_repair import select_missing
    p={'meta':{'symbol':'NKE','currency':'USD','interval':'1day'},'values':[
       {'datetime':'2026-10-05','close':'10'},{'datetime':'2026-10-06','close':'12'}]}
    assert select_missing(p,'NKE','2026-10-05')=={'date':'2026-10-05','close':10}
    with pytest.raises(ValueError):select_missing(p,'NKE','2026-10-02')


def test_subscription_inline_facts_never_masquerade_as_reported_gross_profit():
    def r(tag,y,v):return {'concept':tag,'originalConcept':tag,'start':str(y)+'-06-01','end':str(y)+'-08-31','val':v,'accn':'a','filed':'2026-10-02','evidence_id':'IX:test'}
    f={'facts':{'us-gaap':{'SubscriptionRevenue':{'units':{'USD':[r('SubscriptionRevenue',2025,100),r('SubscriptionRevenue',2026,110)]}},
        'CostOfGoodsSoldSubscription':{'units':{'USD':[r('CostOfGoodsSoldSubscription',2025,30),r('CostOfGoodsSoldSubscription',2026,22)]}}}}}
    answer=subscription_feature(f,event())
    assert answer['state']=='available'
    assert all(x['concept']!='GrossProfit' for x in answer['current']['references'])
