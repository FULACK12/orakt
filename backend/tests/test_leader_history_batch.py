import json
from pathlib import Path
import pytest
from app.leader_history_batch import temporal_check, reviewed_index, summarize


def packet():
    return {'as_of_date':'2010-02-01','period_end':'2009-12-31','facts':[
        {'filed_at':'2010-02-01','period_end':'2009-12-31'}],'market_evidence':[]}


def test_same_filing_boundary():
    temporal_check(packet())


@pytest.mark.parametrize('key,value',[('filed_at','2010-02-02'),('period_end','2010-01-01'),('filed_at',None)])
def test_future_and_undated_facts_rejected(key,value):
    p=packet();p['facts'][0][key]=value
    with pytest.raises(ValueError):temporal_check(p)


def test_latest_market_series_not_treated_as_point_in_time():
    p=packet();p['market_evidence']=[{'date':'2009-01-01','vintage':'latest'}]
    with pytest.raises(ValueError,match='vintages'):temporal_check(p)


def test_existing_review_records_only_skip_full_reviewed_reports(tmp_path):
    d={'ticker':'AAPL','sources':[{'id':'SEC:one'}],'chapters':[{}]*9,'review':{'state':'assistant_reviewed_research_only'}}
    (tmp_path/'accepted.json').write_text(json.dumps(d))
    d['sources']=[{'id':'SEC:two'}];d['review']['state']='content_review_pending'
    (tmp_path/'draft.json').write_text(json.dumps(d))
    index=reviewed_index(tmp_path)
    assert set(index)=={('AAPL','one')}
    assert index[('AAPL','one')]['state']=='existing_review_record'


def test_summary_never_upgrades_drafts():
    s=summarize([{'state':'ready_for_generation','filedAt':'2010-01-01'}])
    assert s['reportsApprovedByThisQueue']==s['publishedByThisQueue']==0
