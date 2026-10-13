import copy
import hashlib
from decimal import Decimal
import pytest
import app.dossier_cash_components as m

HEADER='Six Months Ended\nJune 30\n2026 2025\n(Millions of dollars)\n'
WORK='Net decrease (increase) in operating working capital'


def span(text,start=0):
    raw='frozen-hash';h=hashlib.sha256((raw+':'+str(start)+':'+text).encode()).hexdigest()
    return {'id':'PASSAGE:'+h[:16],'text':text,'start':start,'sourceHash':raw,'end':start+len(text)}


def fixture(monkeypatch):
    rows={'Net Income (Loss)':('31','16'),WORK:('( 1 )','( 1 )'),
          'Capital expenditures':('( 10 )','( 8 )'),'Cash dividends - common stock':('( 4 )','( 3 )')}
    totals={'operating':('30','15'),'investing':('( 10 )','( 8 )'),'financing':('( 4 )','( 3 )'),
            'fx':('( 1 )','—'),'netChange':('15','4'),'opening':('10','6'),'closing':('25','10')}
    rows.update({m.TOTALS[k]:v for k,v in totals.items()})
    s=span(HEADER+'\n'.join(k+' '+a+' '+b for k,(a,b) in rows.items()))
    numbers=[('( 2 )','1'),('( 1 )','—'),('( 1 )','—'),('2','( 2 )'),('1','—')]
    n=span(HEADER+'\n'.join(k+' '+a+' '+b for k,(a,b) in zip(m.WORKING_CAPITAL,numbers))+'\n'+WORK+' ( 1 ) ( 1 )\nIncome taxes 5 3',2000)
    packet={'ticker':'TEST','period_end':'2026-06-30','raw_sha256':'frozen-hash',
            'chapter_passages':{'financial':[s,n]}}
    groups={'operating':['Net Income (Loss)',WORK],'investing':['Capital expenditures'],
            'financing':['Cash dividends - common stock']}
    fact_values={'operating':30,'investing':-10,'financing':-4,'fx':-1,'netChange':15,'opening':10,'closing':25}
    monkeypatch.setattr(m,'cash_bridge',lambda p:{'state':'matched','periodStart':'2026-01-01','periodEnd':'2026-06-30','unit':'USD',
        'values':{k:{'value':str(v*1000000)} for k,v in fact_values.items()}})
    return packet,s,n,groups,fact_values


def test_components_both_years_cash_scope_and_exact_offsets(monkeypatch):
    p,s,n,g,_=fixture(monkeypatch)
    result=m.reconcile_components(p,s['id'],n['id'],groups=g)
    assert result['cashTaxes']['signedChange']=='2'
    assert result['totals']['investing']['signedChange']=='-2'
    assert result['cashDefinition'].endswith('restricted cash')
    assert result['state']=='arithmetically_matched_not_semantic_approval'
    for row in result['workingCapital']:
        assert n['text'][row['start']-n['start']:row['end']-n['start']]==row['surface']


def test_table_fact_conflict_blocks(monkeypatch):
    p,s,n,g,f=fixture(monkeypatch);f['closing']=26
    with pytest.raises(ValueError,match='structured facts'):m.reconcile_components(p,s['id'],n['id'],groups=g)


@pytest.mark.parametrize('change', ['wrong_unit','wrong_year','duplicate','changed_hash'])
def test_rows_fail_closed(monkeypatch,change):
    p,s,n,g,_=fixture(monkeypatch)
    if change=='changed_hash':s['text']+=' altered'
    else:
        text=s['text']
        if change=='wrong_unit':text=text.replace('Millions','Billions')
        if change=='wrong_year':text=text.replace('2026 2025','2025 2026')
        if change=='duplicate':text+='\nNet Income (Loss) 31 16'
        s=span(text);p['chapter_passages']['financial'][0]=s
    with pytest.raises(ValueError):m.reconcile_components(p,s['id'],n['id'],groups=g)


def test_missing_component_and_wrong_template_block(monkeypatch):
    p,s,n,g,_=fixture(monkeypatch)
    with pytest.raises(ValueError,match='adapter'):m.reconcile_components(p,s['id'],n['id'])
    g['operating'].remove(WORK)
    with pytest.raises(ValueError,match='Unmodelled'):m.reconcile_components(p,s['id'],n['id'],groups=g)


def test_unmodelled_zero_row_is_not_silently_accepted(monkeypatch):
    p,s,n,g,_=fixture(monkeypatch)
    s=span(s['text']+'\nUnlisted cash adjustment — —')
    p['chapter_passages']['financial'][0]=s
    with pytest.raises(ValueError,match='Unmodelled'):m.reconcile_components(p,s['id'],n['id'],groups=g)
