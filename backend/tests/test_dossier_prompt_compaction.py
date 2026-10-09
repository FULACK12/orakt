import copy,json
from app.dossier_compact_writer import prompt_view

def test_segment_prompt_compaction_is_lossless_and_nonmutating():
    rows=[{'concept':'Revenue','segment':f'segment-{i}','periodType':p,'direction':'increase',
           'currentSign':'positive','comparisonSign':'negative','evidenceIds':[f'IX:{i}-{p}-now',f'IX:{i}-{p}-prior'],
           'scope':'Same-period disclosed segment table; not consolidated performance or independent causal evidence.'}
          for i in range(15) for p in ('quarter','six_month_cumulative')]
    view={'passages':[{'id':'p1','qualitative_view':'unaltered'}],'segmentFinancialObservations':rows}
    old=copy.deepcopy(view);result=prompt_view(view);table=result['segmentFinancialObservations']
    restored=[{**table['sharedFields'],**dict(zip(table['columns'],row))} for row in table['rows']]
    assert restored==rows and view==old
    assert result['passages']==view['passages']
    assert len(json.dumps(result))<len(json.dumps(view))*0.7

def test_irregular_or_single_segment_records_stay_intact():
    for rows in ([],[{'concept':'x'}],[{'concept':'x'},{'concept':'y','scope':'different'}]):
        v={'segmentFinancialObservations':rows}
        assert prompt_view(v)==v

def test_explicit_physical_volumes_do_not_trigger_revenue_only_guard():
    from types import SimpleNamespace
    from app.dossier_compact_writer import check_source_scope
    import pytest
    s=SimpleNamespace(grounded_claims=[SimpleNamespace(passage_id='p',statement=SimpleNamespace(zh='销量增加。'))])
    for text in ('Revenue increased due to higher volumes and prices.',
                 'Revenues rose while shipment volumes increased.',
                 'Revenue declined due to lower sales volumes.'):
        check_source_scope(s,{'passages':[{'id':'p','qualitative_view':text}]})
    for text in ('Net sales increased with favorable pricing.',
                 'Revenue rose; see volumes of the accounting handbook.'):
        with pytest.raises(ValueError,match='sales value'):
            check_source_scope(s,{'passages':[{'id':'p','qualitative_view':text}]})
