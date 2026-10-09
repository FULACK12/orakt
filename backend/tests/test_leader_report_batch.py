from datetime import date
from types import SimpleNamespace
import pytest
from app.leader_report_batch import leaders, latest_filing, summarize, cn_period


def filing(period, filed, form='10-Q', accession='a'):
    return SimpleNamespace(report_date=date.fromisoformat(period), filed_at=date.fromisoformat(filed), form=form, accession_number=accession)


def test_freezes_catalog_and_prioritizes_without_expanding_universe():
    result = leaders({'companies': [{'marketRegion': 'us', 'ticker': 'NKE'}, {'marketRegion': 'china', 'ticker': '000001'}, {'marketRegion': 'us', 'ticker': 'AAPL'}]})
    assert [r['ticker'] for r in result] == ['AAPL', '000001', 'NKE']
    assert len(result) == 3


def test_duplicates_fail_instead_of_inflating_company_count():
    with pytest.raises(ValueError, match='Duplicate'):
        leaders({'companies': [{'marketRegion': 'us', 'ticker': 'AAPL'}]*2})


def test_latest_period_not_latest_old_amendment_or_future():
    old = filing('2024-12-31', '2026-09-30', '10-K/A')
    current = filing('2026-06-30', '2026-08-01')
    future = filing('2026-09-30', '2026-11-01')
    assert latest_filing([old, current, future], date(2026,10,6)) is current


def test_latest_amendment_is_not_silently_ignored():
    base = filing('2026-06-30', '2026-08-01')
    amendment = filing('2026-06-30', '2026-08-10', '10-Q/A')
    assert latest_filing([base, amendment], date(2026,10,6)) is amendment


def test_readiness_and_drafts_are_not_completed_reports():
    result = summarize([{'marketRegion':'us','state':'ready_for_generation'}, {'marketRegion':'china','state':'waiting_cn_period_adapter'}])
    assert result['totalCompanies'] == 2
    assert result['completeReviewedReports'] == 0
    assert result['byState']['waiting_cn_period_adapter'] == 1


@pytest.mark.parametrize('title,expected',[
    ('贵州茅台：2026年半年度报告','2026-06-30'),
    ('2025年年度报告','2025-12-31'),
    ('2026年第一季度报告','2026-03-31'),
    ('2026年半年度报告摘要',None),('2025年度审计报告',None),
    ('关于2026年半年度报告的更正公告',None),('没有年份的年度报告',None)])
def test_cn_period_is_explicit_and_full_report_only(title,expected):
    result=cn_period(title)
    assert (str(result) if result else None)==expected
