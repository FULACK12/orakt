from datetime import date
from types import SimpleNamespace
from app.company_report_inventory import summarize_company
from app.company_completion import DOCUMENT_ERRORS
from pypdf.errors import PdfReadError


def filing(**kw):
    return SimpleNamespace(**{'ticker':'TEST','accession_number':'0000000001-26-000001','primary_document':'report.htm',
        'source_url':'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/report.htm',
        'filed_at':date(2026,2,1),'report_date':date(2025,12,31),'form':'10-K',**kw})


def test_periods_do_not_count_old_narratives_or_amendments_twice(tmp_path):
    base=filing();amend=filing(accession_number='0000000001-26-000002',form='10-K/A')
    summary,jobs=summarize_company(SimpleNamespace(ticker='TEST',name='Company'),[base,amend],{('TEST',base.accession_number):['dossier-1','dossier-2']},tmp_path,date(2026,10,6))
    assert summary['indexedPeriods']==1 and summary['publishedPeriods']==1
    assert summary['publishedVersions']==2 and summary['waitingSource']==1
    assert not summary['complete'] and len(jobs)==2


def test_unknown_period_future_filings_and_missing_sources_remain_gaps(tmp_path):
    summary,jobs=summarize_company(SimpleNamespace(ticker='TEST',name='Company'),[filing(report_date=None),filing(filed_at=date(2027,1,1))],{},tmp_path,date(2026,10,6))
    assert len(jobs)==1 and jobs[0]['state']=='period_unknown'
    assert summary['indexedPeriods']==0 and summary['periodUnknown']==1
    assert summary['sourceArchived']==0 and summary['publishedPeriods']==0


def test_bad_pdf_is_an_isolated_document_failure_not_a_global_worker_crash():
    assert isinstance(PdfReadError('invalid PDF'),DOCUMENT_ERRORS)
    assert not isinstance(KeyboardInterrupt(),DOCUMENT_ERRORS)
    assert not isinstance(RuntimeError('programming failure'),DOCUMENT_ERRORS)
