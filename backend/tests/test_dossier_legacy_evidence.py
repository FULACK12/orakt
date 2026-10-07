import copy
import hashlib
from decimal import Decimal
import pytest
from app.dossier_legacy_evidence import tables,number,extract_table,reconcile,subtotal_checks,recover_context


@pytest.mark.parametrize('cells,expected',[
    (['$','1,234',''],'1234000'),(['','(349,314',')'],'-349314000'),
    (['','—',''],'0'),(['12.5'],'12500.0')])
def test_split_numeric_cells(cells,expected):assert number(cells,1000)==expected


@pytest.mark.parametrize('cells',[[''],['N/A'],['(123',''],['2','4%'],['NaN'],['1','—']])
def test_no_guessing_missing_or_ambiguous_values(cells):
    with pytest.raises(ValueError):number(cells,1000)


def mapping():
    html='<table><tr><td>Six Months Ended</td><td>2009</td><td>2008</td></tr><tr><td>Investing</td><td>(13</td><td>)</td><td>20</td><td></td></tr></table>'
    sha=hashlib.sha256(html.encode()).hexdigest()
    m={'sourceHash':sha,'reviewer':'codex_assistant','tableIndex':0,'unit':'USD','scale':1000,
       'anchors':[{'row':0,'cells':['Six Months Ended','2009','2008']}],
       'columns':{'2009':[1,3],'2008':[3,5]},'rows':{'investing':{'row':1,'label':'Investing'}}}
    return html,sha,m


def test_table_mapping_provenance_and_negative_sign():
    html,sha,m=mapping();f=extract_table(html,sha,m)
    assert f['investing']['2009']['value']=='-13000'
    assert f['investing']['2008']['value']=='20000'
    assert f['investing']['2009']['rawCells']==['(13',')']
    assert f['investing']['2009']['sourceHash']==sha
    assert f['investing']['2009']['evidence_id']!=f['investing']['2008']['evidence_id']


def test_ascii_zero_dash_requires_reviewed_mapping_and_keeps_raw_cells():
    html,_,m=mapping();html=html.replace('(13',' $-').replace('<td>)</td>','<td></td>')
    sha=hashlib.sha256(html.encode()).hexdigest();m['sourceHash']=sha
    with pytest.raises(ValueError):extract_table(html,sha,m)
    m['reviewedZeroDash']='-';f=extract_table(html,sha,m)
    assert f['investing']['2009']['value']=='0' and '$-' in f['investing']['2009']['rawCells'][0]


@pytest.mark.parametrize('bad',['hash','label','header','currency','scale','column','reviewer'])
def test_changed_mapping_fails_closed(bad):
    html,sha,m=mapping()
    if bad=='hash':sha='a'*64
    if bad=='label':m['rows']['investing']['label']='Revenue'
    if bad=='header':m['anchors'][0]['cells']=['Year Ended']
    if bad=='currency':m['unit']='EUR'
    if bad=='scale':m['scale']=100
    if bad=='column':m['columns']['2009']=[1,99]
    if bad=='reviewer':m['reviewer']='model_automatic'
    with pytest.raises(ValueError):extract_table(html,sha,m)


def test_nested_tables_not_silently_flattened():
    ts=tables('<table><tr><td>outer<table><tr><td>inner</td></tr></table></td></tr></table>')
    assert ts[0]['nested'] and not ts[1]['nested']
    assert ts[1]['rows']==[['inner']]


def cash():
    return {k:{'p':{'value':str(v),'unit':'USD'}} for k,v in
            {'operating':100,'investing':-50,'financing':-30,'fx':5,'netChange':25,'opening':70,'closing':95}.items()}


def test_cash_identity_uses_reported_net_and_balances():
    f=cash();assert reconcile(f,'p')['state']=='matched'
    f['netChange']['p']['value']='24';assert reconcile(f,'p')['state']=='mismatch'
    f=cash();f['closing']['p']['value']='96';assert reconcile(f,'p')['state']=='mismatch'
    f=cash();f['fx']['p']['value']='NaN'
    with pytest.raises(ValueError):reconcile(f,'p')


def test_no_separate_fx_line_is_not_an_invented_zero_fact():
    f=cash();del f['fx'];f['netChange']['p']['value']='20';f['closing']['p']['value']='90'
    r=reconcile(f,'p',('operating','investing','financing'))
    assert r['state']=='matched' and not r['separateFxLineDisclosed'] and 'fx' not in r['facts']
    with pytest.raises(KeyError):reconcile(f,'p')
    with pytest.raises(ValueError):reconcile(f,'p',('operating','investing'))


def test_subtotal_rejects_duplicate_components_and_detects_disagreement():
    f=cash();f.update({'a':{'p':{'value':'30'}},'b':{'p':{'value':'70'}}})
    assert subtotal_checks(f,{'operating':['a','b']},'p')['operating']['state']=='matched'
    f['b']['p']['value']='69'
    assert subtotal_checks(f,{'operating':['a','b']},'p')['operating']['state']=='mismatch'
    with pytest.raises(ValueError):subtotal_checks(f,{'operating':['a','a']},'p')


def test_context_exact_offsets_not_fabricated_or_ambiguous():
    text='The former Mobile business was integrated into Platform. Prior periods restated.'
    c=recover_context(text,'Mobile','hash',11,50)
    assert text[c['start']:c['end']]==c['text'] and 'former Mobile' in c['text']
    with pytest.raises(ValueError):recover_context(text+' Mobile','Mobile','hash')
    with pytest.raises(ValueError):recover_context(text,'absent','hash')


def test_render_addendum_escapes_external_source_text():
    from app.dossier_evidence_addendum import panel
    f=cash()
    for k in f:f[k]['p'].update(rawLabel='<script>bad</script>',tableIndex=0,rowIndex=0,evidence_id='TABLE:1')
    r={'facts':f,'cashReconciliations':{'p':{}},'contexts':[]}
    html=panel(r)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'superseded' in html and '未对外发布' in html
