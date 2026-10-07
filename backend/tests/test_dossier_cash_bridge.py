import copy
from app.dossier_cash_bridge import CONCEPTS,cash_bridge,packet_passages
import pytest


def packet():
    start='2025-11-29';end='2026-08-28'
    p={'period_end':end,'as_of_date':'2026-09-22','facts':[],
       'financial_ledger':{'comparisons':[{'concept':CONCEPTS['operating'],'periodType':'nine_month_cumulative','current':{'period_start':start,'period_end':end}}]}}
    vals={'operating':100,'investing':-20,'financing':-95,'fx':5,'netChange':-10}
    for key,value in vals.items():p['facts'].append({'concept':CONCEPTS[key],'value':value,'unit':'USD','period_start':start,'period_end':end,'evidence_id':key})
    for d,v in [('2025-11-28',50),(end,40)]:p['facts'].append({'concept':CONCEPTS['balance'],'value':v,'unit':'USD','period_start':None,'period_end':d,'evidence_id':d})
    return p


def test_bridge_preserves_cumulative_period_and_balance_identity():
    b=cash_bridge(packet())
    assert b['state']=='matched' and b['periodType']=='nine_month_cumulative'
    assert b['computedNetChange']=='-10' and b['balanceChange']=='-10'
    assert b['values']['financing']['value']=='-95'


@pytest.mark.parametrize('problem',['missing','wrong_period','conflict','currency','future'])
def test_missing_or_incompatible_facts_fail_closed(problem):
    p=packet()
    if problem=='missing':p['facts'].pop(0)
    elif problem=='wrong_period':p['facts'][0]['period_start']='2026-05-30'
    elif problem=='currency':p['facts'][0]['unit']='EUR'
    elif problem=='future':p['facts'][0]['filed_at']='2026-10-01'
    else:p['facts'].append({**p['facts'][0],'value':200})
    assert cash_bridge(p)['state']=='unavailable'


def test_reconciliation_mismatch_never_marked_passed():
    p=packet();p['facts'][-1]['value']=60
    assert cash_bridge(p)['state']=='mismatch'


def test_duplicate_identical_facts_keep_all_provenance():
    p=packet();p['facts'].append({**p['facts'][0],'evidence_id':'other'})
    b=cash_bridge(p)
    assert b['state']=='matched' and len(b['values']['operating']['evidence_refs'])==2


def test_cross_chapter_retrieval_requires_consistent_original():
    p={'id':'p','text':'Original exact passage'}
    assert len(packet_passages({'chapter_passages':{'a':[p],'b':[p]}}))==1
    with pytest.raises(ValueError):packet_passages({'chapter_passages':{'a':[p],'b':[{**p,'text':'changed'}]}})


@pytest.mark.parametrize('zh,en',[
 ('本财季经营现金流增长。','Current quarter operating cash flow increased.'),
 ('递延收入确认从而提升利润和现金流。','Recognition generates cash.'),
 ('若非现金项目增加，可能削弱现金流。','Non-cash items increase and weaken cash flow.'),
])
def test_known_cash_accounting_errors_blocked(zh,en):
    from types import SimpleNamespace
    from app.dossier_cash_bridge import guard_cash_narrative
    s=SimpleNamespace(**{k:SimpleNamespace(zh=zh,en=en) for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')})
    p={'financial_ledger':{'comparisons':[{'concept':CONCEPTS['operating'],'direction':'decrease'}]}}
    with pytest.raises(ValueError):guard_cash_narrative(s,p)
