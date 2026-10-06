from app.us_history_backfill import classify,connect,snapshot

def test_coverage_stages_do_not_confuse_index_body_draft_and_publication():
 assert classify('10-Q','2020-03-31',False,100)=='body_missing'
 assert classify('10-Q','2020-03-31',True,0)=='facts_missing'
 assert classify('10-Q','2020-03-31',True,100)=='ready_preflight'
 assert classify('10-K',None,True,100)=='period_missing'
 assert classify('10-Q/A','2020-03-31',True,100)=='adapter_required'
 assert classify('20-F','2020-03-31',True,100)=='adapter_required'
 assert classify('10-Q','2020-03-31',True,100,draft=True)=='draft_retained'
 assert classify('10-Q','2020-03-31',True,100,reviewed=True,draft=True)=='published_reviewed'

def test_snapshot_reports_actual_counts_and_never_claims_live_progress(tmp_path):
 with connect(tmp_path) as db:
  for i,state in enumerate(['body_missing','facts_missing','draft_retained','published_reviewed']):
   db.execute('INSERT INTO filings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(i),'TEST','10-Q',f'2020-0{i+1}-01','2019-12-31','https://www.sec.gov/test','doc.htm',0,0,state,None,'now'))
 d=snapshot(tmp_path)
 assert d['indexedFilings']==4 and d['counts']['published_reviewed']==1
 assert d['live'] is False and d['workerObservation']['state']=='not_started'
 assert d['companies'][0]['periods']==4
 (tmp_path/'pause').touch();assert snapshot(tmp_path)['pauseRequested'] is True
