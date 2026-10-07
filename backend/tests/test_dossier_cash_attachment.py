import copy
import hashlib
import pytest
from app.dossier_cash_attachment import validate_attachment
from app.dossier_legacy_evidence import extract_table,reconcile,subtotal_checks


def packet():
    vals={'operating':10,'investing':-8,'financing':1,'netChange':3,'opening':20,'closing':23}
    html='USD millions<table><tr><td>Nine Months Ended</td><td>2009-06-27</td></tr>'+''.join('<tr><td>'+k+'</td><td>'+str(v)+'</td></tr>' for k,v in vals.items())+'</table>'
    sha=hashlib.sha256(html.encode()).hexdigest()
    m={'tableIndex':0,'sourceHash':sha,'reviewer':'codex_assistant','scale':1000000,'unit':'USD','scaleEvidence':'USD millions',
       'columns':{'2009-06-27':[1,2]},'anchors':[{'row':0,'cells':['Nine Months Ended','2009-06-27']}],
       'rows':{k:{'row':i,'label':k} for i,k in enumerate(vals,1)},'subtotalGroups':{},'flowComponents':['operating','investing','financing']}
    f=extract_table(html,sha,m);b={'2009-06-27':reconcile(f,'2009-06-27',m['flowComponents'])}
    p={'ticker':'TEST','accession':'acc','period_end':'2009-06-27','raw_sha256':sha,
       'facts':[{'concept':'NetCashProvidedByUsedInOperatingActivities','period_end':'2009-06-27','unit':'USD','value':'10000000'}],
       'verified_cash_source':{'ticker':'TEST','accession':'acc','sourceHash':sha,'mapping':m,'facts':f,'cashReconciliations':b,'subtotalChecks':{'2009-06-27':{}}}}
    return p,html


def test_cash_attachment_reproduces_original_not_authored_flags():
    p,h=packet();a=validate_attachment(p,h)
    assert a['cashReconciliations']['2009-06-27']['state']=='matched'
    assert 'fx' not in a['facts']


@pytest.mark.parametrize('bad',['value','claim','identity','unit','period','structured'])
def test_tampered_attachment_fails(bad):
    p,h=packet();a=p['verified_cash_source']
    if bad=='value':a['facts']['operating']['2009-06-27']['value']='999'
    if bad=='claim':a['cashReconciliations']['2009-06-27']['computedNetChange']='999'
    if bad=='identity':a['ticker']='OTHER'
    if bad=='unit':a['mapping']['scaleEvidence']='USD thousands'
    if bad=='period':p['period_end']='2009-03-31'
    if bad=='structured':p['facts'][0]['value']='1'
    with pytest.raises(ValueError):validate_attachment(p,h)


def test_writer_receives_reconciliation_not_a_missing_cash_flag(monkeypatch):
    import app.dossier_compact_writer as m
    p,h=packet();p['financial_ledger']={'comparisons':[{'concept':'NetCashProvidedByUsedInOperatingActivities','periodType':'nine_month_cumulative','current':{'period_start':'2008-09-28','period_end':'2009-06-27'}}]}
    monkeypatch.setattr(m,'chapter_packet',lambda *a:{'original_passages':[],'financial_ledger':{'comparisons':[]}})
    monkeypatch.setattr(m,'disclosed_reference_terms',lambda p:[])
    v=m.writer_view(p,'financial')['verifiedCashReconciliation']
    assert v['state']=='matched' and v['periodType']=='nine_month_cumulative'
    assert not v['separateFxLineDisclosed'] and 'fx' not in v['componentSigns']
    assert 'do not list them as missing' in v['scope']


def test_reconciliation_cannot_be_ignored_by_financial_writer():
    from types import SimpleNamespace
    from app.dossier_compact_writer import check_cash_evidence_use
    p,_=packet();s=SimpleNamespace(analysis=SimpleNamespace(zh='公司披露套保收益。',en='The company disclosed hedge gains.'))
    for key in ('financial','capital','conclusion'):
        with pytest.raises(ValueError,match='ignored'):check_cash_evidence_use(s,p,key)
    s.analysis.zh='累计现金表已核对，不能将余额与经营现金增长混同。'
    s.analysis.en='Cumulative cash flows reconcile to the balance change; this does not validate earnings quality.'
    check_cash_evidence_use(s,p,'financial')


def test_original_cash_rows_are_visible_in_both_language_modes():
    from app.dossier_cash_attachment import render_cash_source
    p,_=packet();html=render_cash_source(p['verified_cash_source'])
    assert '经营现金净流量' in html and 'Original cash-flow components' in html
    # Sign-neutral labels remain correct when a later issuer reports outflows.
    assert '融资现金净流入' not in html
    assert '-8.000' in html and 'TABLE:' in html and '0:2' in html
