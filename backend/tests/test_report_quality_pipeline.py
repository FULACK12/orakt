import copy
import json
import pytest
from app.financial_period_ledger import build_ledger
from app.report_quality import (check, worklist, units, accept_receipts, repair, FIELDS,
                                CHAPTERS, RULESET, SEMANTIC_PROTOCOL)
from app.report_usage import collect_usage, digest
from app.report_quality_evaluation import evaluate, split

PID = 'PASSAGE:0123456789abcdef'


def fixture():
    packet = {'ticker':'TEST', 'accession':'test-filing', 'as_of_date':'2025-04-30',
              'period_end':'2025-03-31', 'raw_sha256':'original',
              'facts':[{'evidence_id':'FACT:1','concept':'Revenues','unit':'USD','value':'100',
                        'period_start':'2025-01-01','period_end':'2025-03-31','filed_at':'2025-04-30',
                        'dimensions':{}}],
              'chapter_passages':{k:[{'id':PID,'text':'Revenue was 100 dollars in the first quarter.'}] for k in CHAPTERS}}
    packet['financial_ledger'] = build_ledger(packet)
    section = {f:{'zh':'收入为100美元。 ['+PID+']','en':'Revenue was 100 dollars. ['+PID+']'} for f in FIELDS}
    section['grounded_claims'] = [{'passage_id':PID,'quote':packet['chapter_passages']['business'][0]['text'],
                                 'statement':{'zh':'收入事实。','en':'Revenue fact.'}}]
    docs = [{'ticker':'TEST','chapter':k,'section':copy.deepcopy(section)} for k in CHAPTERS]
    return packet, docs


def receipts(plan):
    return accept_receipts(plan, [{k:u[k] for k in ('id','fingerprint','sourceIds','evidenceSha256')} |
                         {'reviewer':'codex_assistant','rationale':'Fixture explicit judgment','verdict':'supported'}
                         for u in plan['units']])


def test_good_structure_still_needs_semantic_review():
    packet, docs = fixture()
    c = check(packet,docs,complete=True)
    assert c['deterministicPassed'] and not c['semanticApproval']
    assert not worklist(packet,docs)['automaticApprovalEnabled']


def test_identical_source_rows_are_not_false_errors_but_conflicts_block():
    packet,docs=fixture()
    packet['facts'].append(copy.deepcopy(packet['facts'][0]))
    assert check(packet,docs)['deterministicPassed']
    assert check(packet,docs)['identicalDuplicateFacts']==1
    packet['facts'][-1]['value']='999'
    assert 'conflicting_fact_identity' in {f['code'] for f in check(packet,docs)['findings']}


@pytest.mark.parametrize('mutation,code',[
    (lambda p,d:d[0].update(ticker='WRONG'),'company_mismatch'),
    (lambda p,d:p['facts'][0].update(filed_at='2026-01-01'),'fact_period'),
    (lambda p,d:p['facts'][0].update(unit=''),'missing_unit'),
    (lambda p,d:p['facts'][0].update(value='NaN'),'invalid_number'),
    (lambda p,d:p['financial_ledger'].update(comparisons=[{}]),'ledger_not_reproducible'),
    (lambda p,d:d[0]['section']['analysis'].update(en='No reference.'),'source_binding'),
    (lambda p,d:d[0]['section']['grounded_claims'][0].update(quote='Invented source'),'quote_binding'),
    (lambda p,d:d[0].update(generationResponse={'done':True,'done_reason':'length'}),'truncation'),
    (lambda p,d:d.pop(),'missing_chapters'),
    (lambda p,d:d[0]['section'].pop('analysis'),'missing_text'),
])
def test_explicit_bad_cases(mutation,code):
    packet,docs=fixture(); mutation(packet,docs)
    assert code in {f['code'] for f in check(packet,docs,complete=True)['findings']}


def test_unit_currency_scale_and_narrative_span():
    packet,docs=fixture()
    b={'factId':'FACT:1','location':'section/analysis/en','start':12,'end':15,'surface':'100',
       'value':'100','scale':'1','currency':'USD', 'unit':'USD','concept':'Revenues',
       'period_start':'2025-01-01','period_end':'2025-03-31','dimensions':{}}
    docs[0]['factBindings']=[b]
    assert check(packet,docs)['deterministicPassed']
    b.update(currency='CNY',unit='shares',period_start='2024-01-01',value='1',start=0)
    codes={f['code'] for f in check(packet,docs)['findings']}
    assert {'fact_currency','fact_unit','fact_period_start','fact_value','fact_span'} <= codes
    assert 'fact_surface_value' in codes


def test_unchanged_reviews_reused_but_change_invalidates_twin_and_conclusions():
    packet,docs=fixture();plan=worklist(packet,docs);cached=receipts(plan)
    assert worklist(packet,docs,receipts=cached)['reuseCount']==len(plan['units'])
    docs[0]['section']['analysis']['en']+=' Revised.'
    newer=worklist(packet,docs,receipts=cached)
    states={u['id']:u['state'] for u in newer['units']}
    assert states['business/section/analysis/zh']=='pending'
    assert states['financial/section/analysis/en']=='review_reused'
    assert states['conclusion/section/analysis/en']=='pending'
    packet['raw_sha256']='new-original'
    assert worklist(packet,docs,receipts=cached)['reuseCount']==0


def test_changed_rule_code_invalidates_all(monkeypatch):
    import app.report_quality as module
    packet,docs=fixture();cached=receipts(worklist(packet,docs))
    monkeypatch.setattr(module,'rules_digest',lambda:'changed')
    assert worklist(packet,docs,receipts=cached)['reuseCount']==0


def test_model_cannot_self_approve_or_use_wrong_sources():
    packet,docs=fixture();plan=worklist(packet,docs);r=receipts(plan)[0]
    r['reviewer']='local_model'
    with pytest.raises(ValueError,match='Explicit'):accept_receipts(plan,[r])
    assert worklist(packet,docs,receipts=[r])['reuseCount']==0
    r.update(reviewer='codex_assistant',evidenceSha256='wrong')
    with pytest.raises(ValueError):accept_receipts(plan,[r])


def test_repairs_immutable_local_pending_and_evidence_preserved():
    packet,docs=fixture();original=copy.deepcopy(docs);u=units(docs,packet)[0]
    p={'id':u['id'],'fingerprint':u['fingerprint'],'reason':'Explicit correction',
       'replacement':'收入事实的局部修订。 ['+PID+']'}
    result=repair(packet,docs,[p])
    assert docs==original and result['state']=='pending_semantic_recheck'
    assert result['documents'][0]['section']['grounded_claims']==docs[0]['section']['grounded_claims']
    p['fingerprint']='stale'
    with pytest.raises(ValueError,match='stale'):repair(packet,docs,[p])
    p.update(fingerprint=u['fingerprint'],replacement='No source.')
    with pytest.raises(ValueError,match='Evidence'):repair(packet,docs,[p])


def test_usage_missing_is_not_zero_and_retries_not_hash_deduplicated(tmp_path):
    raw={'message':{'content':'same'},'done':True,'done_reason':'stop',
         'prompt_eval_count':10,'eval_count':20,'total_duration':1_000_000_000}
    for name in ('attempt-1.json','attempt-2.json'):(tmp_path/name).write_text(json.dumps(raw))
    (tmp_path/'attempt-2-partial.json').write_text(json.dumps({'message':{'content':'part'}}))
    (tmp_path/'attempt-3-partial.json').write_text(json.dumps({'message':{'content':'part'},'elapsedSeconds':2}))
    result=collect_usage(tmp_path)
    assert result['callCount']==3 and result['missingTokenCounters']==1
    assert result['inputTokensKnown']==20 and result['codexInputTokens'] is None


def test_no_auto_approval_from_empty_or_reused_evaluation_data():
    manifest={'rulesFrozenBeforeHoldout':False,'cases':[]}
    result=evaluate(manifest,[])
    assert not result['eligibleForEnablementReview'] and not result['automaticApprovalEnabled']
    assert split('aapl')==split('AAPL')
    case={'id':'a','split':'holdout','groupId':'AAPL','stratum':'us_annual_historical',
          'labelStatus':'independently_adjudicated','usedForTuning':True,'synthetic':False}
    manifest.update(cases=[case],rulesFrozenBeforeHoldout=True)
    result=evaluate(manifest,[{'id':'a','caseSha256':digest(case)}])
    assert 'unqualified_case:a' in result['failures']


def test_preflight_rejection_is_not_a_model_call(tmp_path):
    raw={'message':{'content':''},'oraktInput':{'networkStarted':False}}
    (tmp_path/'attempt-1-partial.json').write_text(json.dumps(raw))
    result=collect_usage(tmp_path)
    assert result['callCount']==0 and len(result['preflightRejections'])==1
    assert result['missingTokenCounters']==0 and result['codexInputTokens'] is None


def test_known_bad_semantics_not_falsely_auto_approved():
    packet,docs=fixture()
    docs[0]['section']['analysis']['en']='This revenue guarantees tomorrow stock profit. ['+PID+']'
    plan=worklist(packet,docs)
    assert all(u['state']=='pending' for u in plan['units'])
    assert plan['state']=='pending_review' and not plan['automaticApprovalEnabled']


def test_legacy_generator_records_real_counters_for_retries(monkeypatch):
    import httpx
    from types import SimpleNamespace
    import app.research as m
    settings=SimpleNamespace(llm_provider='ollama',llm_model='test-local',llm_max_input_chars=10000,
                             llm_base_url='http://local.test',llm_max_attempts=2,research_llm_timeout_seconds=10)
    count=0
    def validate(text):
        nonlocal count
        count+=1
        if count==1:raise ValueError('First malformed attempt')
        return 'result'
    monkeypatch.setattr(m,'_compact_evidence',lambda *a,**k:{})
    monkeypatch.setattr(m,'_compatible_json_schema',lambda *a:{})
    monkeypatch.setattr(m,'_validated_research_content',validate)
    monkeypatch.setattr(m,'_sanitize_research_result',lambda result,**kw:result)
    transport=httpx.MockTransport(lambda r:httpx.Response(200,json={
        'message':{'content':'{}'},'prompt_eval_count':11,'eval_count':7,'total_duration':2000000000}))
    evidence={}
    assert m._call_local_research_model(question='test',mode='user_question',evidence=evidence,
                                       settings=settings,transport=transport)=='result'
    calls=evidence['_reportUsage']['localCalls']
    assert len(calls)==2 and sum(c['inputTokens'] for c in calls)==22
    assert calls[0]['outcome']=='failed' and calls[1]['outcome']=='validated_local_draft'


def test_evaluation_rejects_development_issuer_leakage():
    case={'id':'hold','split':'holdout','groupId':'AAPL'}
    manifest={'rulesFrozenBeforeHoldout':True,'rulesetSha256':'locked','cases':[
        case,{'id':'train','split':'development','groupId':'AAPL','usedForTuning':True}]}
    assert 'issuer_leakage_from_development' in evaluate(manifest,[])['failures']


def test_changed_derived_cash_table_invalidates_semantic_cache():
    packet,docs=fixture()
    docs[0]['deterministicTables']={'cashComponentsSha256':'old'}
    cached=receipts(worklist(packet,docs))
    docs[0]['deterministicTables']['cashComponentsSha256']='new'
    revised=worklist(packet,docs,receipts=cached)
    affected={docs[0]['chapter'],'valuation','factors','conclusion'}
    assert all(u['state']=='pending' for u in revised['units'] if u['chapter'] in affected)
    assert all(u['state']=='review_reused' for u in revised['units'] if u['chapter'] not in affected)
    assert revised['reuseCount']>0  # Unchanged evidence must not trigger full re-review.
