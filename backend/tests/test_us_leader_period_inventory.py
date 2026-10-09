from datetime import date
from types import SimpleNamespace as NS
from app.us_leader_period_inventory import period_groups


def f(form,accession,end='2025-12-31',filed='2026-02-01'):
    return NS(ticker='TEST',form=form,accession_number=accession,report_date=date.fromisoformat(end) if end else None,
        filed_at=date.fromisoformat(filed),source_url='https://www.sec.gov/file',primary_document='file.htm')


def test_amendment_is_provenance_not_extra_report():
    groups,_=period_groups([f('10-K','a'),f('10-K/A','b',filed='2026-03-01')],date(2026,10,7))
    assert len(groups)==1 and len(groups[0]['versions'])==2
    assert groups[0]['requiresAmendmentMerge'] and groups[0]['primaryAccession']=='a'


def test_annual_does_not_fabricate_fourth_quarter():
    groups,_=period_groups([f('10-K','a'),f('10-Q','b',end='2025-09-30')],date(2026,10,7))
    assert len(groups)==2
    assert {g['reportKind'] for g in groups}=={'annual','quarterly'}


def test_foreign_annual_and_undated_and_future():
    groups,undated=period_groups([f('20-F','a'),f('40-F/A','b',end=None),f('10-K','c',filed='2027-02-01')],date(2026,10,7))
    assert len(groups)==1 and groups[0]['reportKind']=='annual' and undated==['b']
