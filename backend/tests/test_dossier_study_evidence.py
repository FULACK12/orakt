from datetime import date
import pytest
from app.dossier_study_evidence import validate_prices,filing_events


def payload():
    return {'meta':{'symbol':'TEST','currency':'USD','interval':'1day'},
            'values':[{'datetime':f'2026-10-0{i}','close':'10'} for i in range(1,6)]}


def test_sorted_bounded_price_validation():
    p=payload();p['values'].reverse()
    assert validate_prices(p,'TEST',date(2026,10,1),date(2026,10,5))[0]['date']=='2026-10-01'


@pytest.mark.parametrize('bad',['symbol','currency','interval','duplicate','nan','negative','future','empty'])
def test_provider_response_fail_closed(bad):
    p=payload()
    if bad in ['symbol','currency','interval']:p['meta'][bad]='wrong'
    elif bad=='duplicate':p['values'].append(p['values'][0])
    elif bad in ['nan','negative']:p['values'][0]['close']='NaN' if bad=='nan' else '-1'
    elif bad=='future':p['values'][0]['datetime']='2026-10-06'
    else:p['values']=[]
    with pytest.raises(ValueError):validate_prices(p,'TEST',date(2026,10,1),date(2026,10,5))


def test_no_invented_timestamp_and_no_amendment_reentry():
    c={'form':['10-Q','10-Q/A','10-K'],'filingDate':['2026-10-02']*3,
       'reportDate':['2026-08-31']*3,'accessionNumber':['a','b','c'],
       'acceptanceDateTime':['2026-10-03T00:15:00Z','2026-10-03T01:00:00Z','2026-10-02T17:00:00']}
    es=filing_events(c,'TEST',date(2026,1,1),date(2026,10,5),'hash')
    assert len(es)==2
    assert es[0]['acceptedAt'].startswith('2026-10-03')
    assert es[1]['acceptedAt'] is None
    assert es[0]['timestampState']=='sec_acceptance_not_first_news'
