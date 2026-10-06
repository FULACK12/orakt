from copy import deepcopy
from datetime import date,timedelta
import pytest
from app.quarter_peer_study import unique_quarter,financial_summary,diagnose

def fact(concept,value,start,end,id):
    return {'evidence_id':id,'concept':concept,'dimensions':{},'unit':'USD','value':str(value),'period_start':start,'period_end':end,'filed_at':'2025-05-07'}

def test_financial_ratios_require_matching_quarters_not_segments_or_ytd():
    fs=[fact('Revenues',200,'2024-12-29','2025-03-29','r'),fact('GrossProfit',100,'2024-12-29','2025-03-29','g'),fact('Revenues',100,'2023-12-31','2024-03-30','rp'),fact('GrossProfit',40,'2023-12-31','2024-03-30','gp')]
    p={'facts':fs,'period_end':'2025-03-29','as_of_date':'2025-05-07'}
    s=financial_summary(p);assert s['grossMarginPercent']==50 and s['grossMarginYoYPoints']==10 and s['revenueYoYPercent']==100
    changed=deepcopy(fs);changed[1]['period_start']='2024-09-29'
    assert financial_summary({**p,'facts':changed})['grossMarginPercent'] is None
    changed=deepcopy(fs);changed[0]['dimensions']={'segment':'test'}
    assert unique_quarter(changed,['Revenues'],'2025-03-29') is None
    assert unique_quarter(fs+[fact('Revenues',201,'2024-12-29','2025-03-29','conflict')],['Revenues'],'2025-03-29') is None

def inputs():
    ds=[str(date(2025,1,1)+timedelta(days=i)) for i in range(40)]
    prices={k:{d:100+i for i,d in enumerate(ds)} for k in ['EQ:AMD','TD:SPY','TD:SOXX']}
    e={'accession':'1','filedAt':ds[0],'summary':{'revenueYoYPercent':10,'grossMarginYoYPoints':2}}
    return [e],prices,ds[-1]

def test_entry_after_filing_dual_benchmark_and_cost():
    e,p,end=inputs();d=diagnose(e,p,end);r=d['rows'][0]
    assert r['entryDate']>e[0]['filedAt'] and r['exitDate']=='2025-01-07'
    assert r['marketExcess']==pytest.approx(-.0025) and r['industryExcess']==pytest.approx(-.0025)
    assert d['groups'][0]['dualBenchmarkEvents']==1 and d['groups'][0]['confidenceInterval'] is None
    assert d['prospectiveValidation'] is False

def test_missing_industry_never_counts_as_dual_pass():
    e,p,end=inputs();del p['TD:SOXX'];d=diagnose(e,p,end)
    assert d['rows'][0]['state']=='industry_benchmark_missing' and d['groups'][0]['dualBenchmarkEvents']==0

def test_overlap_and_bad_observations_not_forward_filled():
    e,p,end=inputs();e.append({**e[0],'accession':'2','filedAt':'2025-01-03'})
    assert diagnose(e,p,end)['rows'][3]['state']=='overlap_excluded'
    p['EQ:AMD'].pop('2025-01-04')
    assert diagnose(e,p,end)['rows'][0]['state']=='price_window_missing'

def test_no_signal_and_incomplete_outcomes_are_not_wins():
    e,p,end=inputs();e[0]['summary']['revenueYoYPercent']=-1
    assert diagnose(e,p,end)['rows'][0]['state']=='no_signal'
    e[0]['summary']['revenueYoYPercent']=1
    assert diagnose(e,p,'2025-01-03')['rows'][0]['state']=='outcome_window_incomplete'
