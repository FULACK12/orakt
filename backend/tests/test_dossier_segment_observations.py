from copy import deepcopy
from app.dossier_compact_writer import segment_observations


def ledger():
    fact={'base_concept':'OperatingIncomeLoss','unit':'USD','value':'20',
          'dimensions':{'us-gaap:StatementBusinessSegmentsAxis':'amzn:AmazonWebServicesMember'}}
    old=deepcopy(fact);old['value']='10'
    return {'comparisons':[{'current':fact,'previous':old,'comparisonBasis':'same_duration_year_over_year',
        'periodType':'quarter','direction':'increase','evidence_refs':['IX:a','IX:b']}]}


def test_disclosed_segment_table_available_outside_prose_selection():
    result=segment_observations(ledger())
    assert result[0]['segment']=='amzn:AmazonWebServicesMember'
    assert result[0]['concept']=='OperatingIncomeLoss'
    assert result[0]['periodType']=='quarter'
    assert result[0]['evidenceIds']==['IX:a','IX:b']


def test_scope_currency_and_comparison_must_match():
    for mutate in (
        lambda c:c['previous'].update(dimensions={}),
        lambda c:c['current'].update(unit='EUR'),
        lambda c:c.update(comparisonBasis='prior_reported_balance'),
        lambda c:c['current']['dimensions'].update({'other:Axis':'other:Member'}),
    ):
        data=ledger();mutate(data['comparisons'][0])
        assert segment_observations(data)==[]


def test_loss_narrowing_is_not_profitability():
    data=ledger();data['comparisons'][0]['current']['value']='-10'
    data['comparisons'][0]['previous']['value']='-20'
    row=segment_observations(data)[0]
    assert row['direction']=='increase' and row['currentSign']==row['comparisonSign']=='negative'
