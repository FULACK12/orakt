from datetime import date,timedelta
from app.research_lab_export import momentum_study,event_window

def test_no_future_signal_and_disjoint_holdings():
    rows=[(date(2020,1,1)+timedelta(days=i),100+i) for i in range(130)]
    r=momentum_study(rows,rows,rows)
    assert r['validatedAlpha'] is False
    assert r['points'][0]['strategy']==100
    assert all(t['signalDate']<t['entryDate']<t['exitDate'] for t in r['trades'])
    assert all(a['exitDate']<=b['entryDate'] for a,b in zip(r['trades'],r['trades'][1:]))
    assert r['points'][-1]['strategy']<r['points'][-1]['market']

def test_event_percent_vs_yield_bp_and_missing():
    rows=[(date(2020,1,1),2),(date(2020,1,2),2.1)]
    assert round(event_window(rows,date(2020,1,2),1,True)['change'])==10
    assert round(event_window(rows,date(2020,1,2),1)['change'])==5
    assert event_window(rows,date(2020,1,2),5) is None
