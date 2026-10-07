import json
from types import SimpleNamespace
import httpx
import pytest
from app.company_completion import connect,mark,done,filing_target,download_body,validate_cn_page,status,profile_candidate

def test_universe_excludes_unclassified_funds_and_nonperiodic_issuers():
 p={'cik':'1','entityType':'operating','name':'Example','tickers':['TEST'],'exchanges':['Nasdaq'],'filings':{'recent':{'form':['10-K']}}}
 assert profile_candidate(p)['cik']=='0000000001'
 for changes in [{'entityType':'investment'},{'exchanges':['OTC']},{'filings':{'recent':{'form':['N-PORT']}}},{'tickers':['../bad']}]:
  assert profile_candidate({**p,**changes}) is None

def filing(**changes):
 return SimpleNamespace(**{'ticker':'TEST','accession_number':'0000000001-26-000001','primary_document':'report.htm','source_url':'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/report.htm','filed_at':'2026-10-06','form':'10-Q',**changes})

def test_job_completion_is_independent_and_not_report_approval(tmp_path):
 with connect(tmp_path) as db:
  mark(db,'us-bodies','one','TEST','complete',{'bytes':1000})
  mark(db,'reports','one','TEST','content_review_pending')
  assert done(db,'us-bodies','one') and not done(db,'reports','one')
 assert status(tmp_path)['complete'] is False

def test_cn_no_silent_truncation_or_malformed_response():
 assert validate_cn_page({'announcements':None,'hasMore':False})==([],False)
 assert validate_cn_page({'announcements':[{}],'hasMore':True})==([{}],True)
 for p in [{},{'announcements':[],'hasMore':True},{'announcements':[],'hasMore':'false'}]:
  with pytest.raises(ValueError):validate_cn_page(p)

def test_archive_rejects_escape_or_wrong_host(tmp_path):
 for f in [filing(primary_document='../../../../../../escape.htm'),filing(source_url='https://evil.test/Archives/edgar/data/1/a.htm'),filing(primary_document=None)]:
  with pytest.raises(ValueError):filing_target(f,tmp_path)

def test_body_retained_with_hash_and_dedup_without_claiming_exhibits(tmp_path):
 raw=b'<html>'+b'original disclosure '*100+b'</html>'
 with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=raw))) as client:
  assert download_body(client,filing(),tmp_path)=='downloaded'
  assert download_body(client,filing(),tmp_path)=='existing'
 path=filing_target(filing(),tmp_path)
 meta=json.loads(path.with_suffix('.htm.manifest.json').read_text())
 assert meta['exhibitsComplete'] is False and len(meta['sha256'])==64

def test_denied_document_never_marked_archived(tmp_path):
 with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'Access Denied'+b' '*600))) as client:
  with pytest.raises(ValueError):download_body(client,filing(),tmp_path)
 assert not filing_target(filing(),tmp_path).exists()
