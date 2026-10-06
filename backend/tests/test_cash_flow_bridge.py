from copy import deepcopy
import pytest
from app.cash_flow_bridge import bridge,AAPL_LINES
from app.peer_evidence_completion import comparable_quarter

def packet():
 current=[84544,8571,9680,1748,-5685,-13555,-1223,6116,-18479,-15161]
 prior=[79000,8534,8830,1964,-6697,-11100,-41,5626,-15171,2]
 facts=[]
 for i,(concept,_,_,_) in enumerate(AAPL_LINES):
  for j,(values,start,end) in enumerate([(current,'2024-09-29','2025-06-28'),(prior,'2023-10-01','2024-06-29')]):
   facts.append(dict(evidence_id=f'IX:f-{i}-{j}',concept=concept,unit='USD',value=str(values[i]*1000000),period_start=start,period_end=end,filed_at='2025-08-01'))
 for j,(value,start,end) in enumerate([(81754,'2024-09-29','2025-06-28'),(91443,'2023-10-01','2024-06-29')]):
  facts.append(dict(evidence_id=f'IX:total{j}',concept='NetCashProvidedByUsedInOperatingActivities',unit='USD',value=str(value*1000000),period_start=start,period_end=end,filed_at='2025-08-01'))
 return dict(ticker='AAPL',accession='0000320193-25-000073',as_of_date='2025-08-01',source_url='https://www.sec.gov/example',raw_sha256='a'*64,facts=facts)

def test_reviewed_signs_reconcile_both_periods_and_asset_sign_is_inverted():
 b=bridge(packet());assert b['residuals']==['0','0']
 assert b['rows'][4]['current']=='5685000000'
 assert b['rows'][-1]['contributionChange']=='-15163000000'
 assert sum(int(r['contributionChange']) for r in b['rows'])==-9689000000

@pytest.mark.parametrize('change',['missing','conflict','future','unit','unreviewed','wrong_total'])
def test_no_guessing_or_silent_zero_fill(change):
 p=packet()
 if change=='missing':p['facts'].pop(0)
 if change=='conflict':p['facts'].append({**p['facts'][0],'value':'1'})
 if change=='future':p['facts'][0]['filed_at']='2025-08-02'
 if change=='unit':p['facts'][0]['unit']='EUR'
 if change=='unreviewed':p['ticker']='AMD'
 if change=='wrong_total':p['facts'][-1]['value']='1'
 with pytest.raises(ValueError):bridge(p)

def test_quarter_extraction_rejects_annual_cumulative_dimension_and_conflict():
 f=dict(evidence_id='IX:x',concept='OperatingIncomeLoss',unit='USD',value='20',period_start='2025-03-30',period_end='2025-06-28')
 assert len(comparable_quarter([f],f['period_end']))==1
 for other in [{**f,'period_start':'2024-09-29'},{**f,'concept':'OperatingIncomeLoss [segment=x]'},{**f,'unit':'EUR'}]:assert comparable_quarter([other],f['period_end'])==[]
 assert comparable_quarter([f,{**f,'value':'21'}],f['period_end'])==[]
