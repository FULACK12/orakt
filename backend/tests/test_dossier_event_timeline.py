from copy import deepcopy
import pytest
from app.dossier_event_timeline import validate_timeline

PACKET={'as_of_date':'2025-05-07','period_end':'2025-03-29','filing_ref':'SEC:1','source_url':'https://www.sec.gov/test'}
EVENT={'id':'export','eventDate':'2025-04-15','sourceFiledAt':'2025-05-07','periodRelation':'post_period_known_at_cutoff','evidenceRef':'SEC:1','sourceUrl':'https://www.sec.gov/test','recognition':'expected_charge','title':{'zh':'出口','en':'Exports'},'interpretation':{'zh':'预计费用并非已实现','en':'Expected, not realized'}}

def test_post_period_known_event_is_preserved():
    assert validate_timeline([deepcopy(EVENT)],PACKET)==[EVENT]

@pytest.mark.parametrize('field,value',[('eventDate','2025-05-08'),('sourceFiledAt','2025-05-08'),('periodRelation','within_report_period'),('sourceUrl','https://example.test'),('evidenceRef','SEC:2'),('recognition','realized_profit'),('title',{'zh':'出口','en':''})])
def test_inaccurate_period_or_source_fails_closed(field,value):
    e=deepcopy(EVENT);e[field]=value
    with pytest.raises(ValueError):validate_timeline([e],PACKET)

def test_duplicate_and_invalid_dates_rejected():
    with pytest.raises(ValueError):validate_timeline([EVENT,EVENT],PACKET)
    e=deepcopy(EVENT);e['eventDate']='2025-02-30'
    with pytest.raises(ValueError):validate_timeline([e],PACKET)
