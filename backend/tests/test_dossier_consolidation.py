import copy
import hashlib
import json
import pytest
from app.dossier_consolidation import financial_tables, validate_chapters, register
from app.dossier_backfill_pilot import ready_packet
from app.company_history_dossier import CHAPTERS, write_json
from app.company_completion import connect, mark


def docs():
    passage='PASSAGE:1111111111111111';second='PASSAGE:2222222222222222'
    pair={'zh':'公司披露经营数据，但不代表股价方向已经得到验证。'*15+' ['+passage+']',
          'en':'Company disclosures describe operations, not verified future stock performance. '*12+' ['+passage+']'}
    section={k:copy.deepcopy(pair) for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')}
    quote='This original source passage is sufficiently long for the source check.'
    section.update(evidence_refs=[passage,second],grounded_claims=[{'passage_id':p,'quote':quote,'statement':pair} for p in [passage,second]])
    packet={'ticker':'TEST','accession':'acc','as_of_date':'2020-02-01','period_end':'2019-12-31','source_url':'https://www.sec.gov/test','raw_sha256':'a'*64,
            'filing_ref':'SEC:0000000001-20-000001','financial_ledger':{'comparisons':[]},
            'chapter_passages':{key:[{'id':p,'text':quote} for p in (passage,second)] for key,*_ in CHAPTERS}}
    records=[{'ticker':'TEST','chapter':key,'sourceFingerprint':'frozen','state':'assistant_reviewed','published':False,'completeDossier':False,
              'section':copy.deepcopy(section),'review':{'reviewer':'codex_assistant','state':'accepted_with_revisions','findings':['reviewed'],
                  'parentSha256':'a'*64,'reviewSha256':'b'*64}} for key,*_ in CHAPTERS]
    return {'packet':packet,'fingerprint':'frozen'},records


def test_legacy_metadata_bound_to_same_frozen_packet(monkeypatch):
    import app.dossier_consolidation as m
    monkeypatch.setattr(m,'guard_cash_narrative',lambda *a:None)
    monkeypatch.setattr(m,'cash_bridge',lambda p:{'state':'missing'})
    original,records=docs();r=validate_chapters(original,records)
    assert len(r)==9 and r[0]['sourceMetadata']['accession']=='acc'
    assert 'sourceMetadata' not in records[0]  # no mutation of archived chapter


@pytest.mark.parametrize('mutation',['missing','duplicate','source','review','metadata','citation'])
def test_invalid_assembly_fails_closed(monkeypatch,mutation):
    import app.dossier_consolidation as m
    monkeypatch.setattr(m,'guard_cash_narrative',lambda *a:None)
    monkeypatch.setattr(m,'cash_bridge',lambda p:{'state':'missing'})
    original,records=docs()
    if mutation=='missing':records.pop()
    if mutation=='duplicate':records[1]=records[0]
    if mutation=='source':records[0]['sourceFingerprint']='another'
    if mutation=='review':records[0]['state']='content_review_pending'
    if mutation=='metadata':records[0]['sourceMetadata']={'ticker':'OTHER'}
    if mutation=='citation':records[0]['section']['analysis']['en']+=' PASSAGE:9999999999999999'
    with pytest.raises(ValueError):validate_chapters(original,records)


def test_financial_values_and_periods_are_not_relabelled():
    c={'concept':'NetIncomeLoss','unit':'USD','periodType':'nine_month_cumulative','comparisonBasis':'year_over_year',
       'current':{'value':'-5000000','period_start':'2020-01-01','period_end':'2020-09-30','evidence_id':'IX:a'},
       'previous':{'value':'0','period_start':'2019-01-01','period_end':'2019-09-30','evidence_id':'IX:b'},
       'changePercent':None,'id':'CMP:test'}
    html=financial_tables({'comparisons':[c]})
    assert '-5,000,000' in html and 'nine_month_cumulative' in html and '2019-09-30' in html
    assert '—' in html and 'None%' not in html
    c['concept']='<script>bad()</script>';html=financial_tables({'comparisons':[c]})
    assert '<script>' not in html and '&lt;script&gt;' in html


def artifact(tmp_path):
    out=tmp_path/'artifact'
    write_json(out/'dossier.json',{'ticker':'TEST','accession':'a','structureComplete':True,'published':False,
        'dataCoverage':'partial_with_explicit_gaps','review':{'state':'whole_report_review_pending'}})
    digest=hashlib.sha256((out/'dossier.json').read_bytes()).hexdigest()
    write_json(out/'manifest.json',{'dossierSha256':digest})
    return out


def test_queue_handoff_keeps_failure_and_never_approves(tmp_path):
    root=tmp_path/'queue';out=artifact(tmp_path)
    with connect(root) as db:mark(db,'reports','a','TEST','repair_required',{'reason':'old failure'})
    assert register(root,out) and register(root,out) is False
    with connect(root) as db:
        row=db.execute('select * from jobs').fetchone()
        assert row['state']=='assembled_review_pending'
        assert not json.loads(row['detail'])['published']
        old=db.execute('select * from report_transitions').fetchall()
        assert len(old)==1 and json.loads(old[0]['old_detail'])['reason']=='old failure'


@pytest.mark.parametrize('state',['running','published_reviewed'])
def test_queue_cannot_overwrite_active_or_published(tmp_path,state):
    root=tmp_path/'queue';out=artifact(tmp_path)
    with connect(root) as db:mark(db,'reports','a','TEST',state)
    with pytest.raises(ValueError):register(root,out)


def test_preflight_keeps_future_fact_and_passage_gaps_out():
    original,_=docs();p=original['packet'];p['facts']=[{'filed_at':'2020-02-01','period_end':'2019-12-31'}]
    p['financial_ledger']['comparisons']=[{}]
    assert ready_packet(p)['facts']==1
    p['facts'][0]['filed_at']='2021-01-01'
    with pytest.raises(ValueError,match='Future'):ready_packet(p)
    p['facts'][0]['filed_at']='2020-02-01';p['chapter_passages']['business']=[]
    with pytest.raises(ValueError,match='Insufficient'):ready_packet(p)


def test_compact_writer_keeps_archives_and_uses_only_selected_sources(monkeypatch):
    import app.dossier_compact_writer as m
    original,_=docs();p=original['packet']
    p['facts']=[];p['market_evidence']=[]
    p['financial_ledger']['accountingRules']=[]
    p['chapter_passages']['business'][0]['text']='Revenue was 500 million in 2009. This does not establish a causal return.'
    before=copy.deepcopy(p)
    view=m.writer_view(p,'business')
    assert '500' not in view['passages'][0]['qualitative_view']
    assert '2009' not in view['passages'][0]['qualitative_view']
    assert p==before and view['viewOnly']
    schema=m.schema_for(view)
    assert schema['properties']['analysis']['properties']['en']['minLength']>=800
    assert schema['properties']['mechanism']['properties']['en'].get('minLength',0)<800
    assert schema['properties']['claims']['minItems']==2


def test_repetitive_paragraph_cannot_pass_by_padding():
    from app.dossier_compact_writer import check_repetition
    from app.company_history_dossier import Section
    _,records=docs()
    records[0]['section']['counterEvidence']['en']=('This independently testable alternative explanation must not be repeated to artificially lengthen the research report. '*3)
    with pytest.raises(ValueError,match='Repeated substantive sentence'):check_repetition(Section.model_validate(records[0]['section']))


def test_negative_failure_budget_rejected_before_resources():
    from app.company_history_dossier import run
    with pytest.raises(ValueError,match='failure budget'):run('TEST','a',None,max_failed_chapters=0)


def test_unattested_platform_translation_is_rejected():
    from app.dossier_compact_writer import check_platform_names
    from app.company_history_dossier import Section
    _,records=docs();s=Section.model_validate(records[0]['section']);s.analysis.zh+=' UNIX平台'
    view={'passages':[{'qualitative_view':'Customers use Windows and Macintosh.'}]}
    with pytest.raises(ValueError,match='UNIX'):check_platform_names(s,view)
    s.analysis.zh=s.analysis.zh.replace('UNIX','Macintosh');check_platform_names(s,view)
