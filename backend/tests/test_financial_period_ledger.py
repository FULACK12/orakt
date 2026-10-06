from app.financial_period_ledger import build_ledger
from app.company_history_dossier import validate_section, ComparisonCheck, Section
import pytest

def section():
    pair={"zh":"财务期间必须保持一致并且说明已确认事实与解释性假设之间的区别。"*12,"en":"Financial periods must remain comparable. Separate verified facts from causal hypotheses. "*10}
    return Section(**{k:pair.copy() for k in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']},evidence_refs=['FACT:1'])


def fact(i,concept,value,start,end,unit="USD"):
    return dict(evidence_id=f"FACT:{i}",concept=concept,value=value,unit=unit,period_start=start,period_end=end,filed_at="2025-08-01")

def packet(facts):return dict(as_of_date="2025-08-01",period_end="2025-06-28",facts=facts)

def cash_facts():
    return [fact(1,"NetCashProvidedByUsedInOperatingActivities",91443,"2023-10-01","2024-06-29"),fact(2,"NetCashProvidedByUsedInOperatingActivities",81754,"2024-09-29","2025-06-28"),fact(3,"PaymentsToAcquirePropertyPlantAndEquipment",6539,"2023-10-01","2024-06-29"),fact(4,"PaymentsToAcquirePropertyPlantAndEquipment",9473,"2024-09-29","2025-06-28")]

def test_cash_flow_is_nine_month_cumulative_and_fcf_is_separate():
    ledger=build_ledger(packet(cash_facts()))
    rows={r['concept']:r for r in ledger['comparisons']}
    assert rows['NetCashProvidedByUsedInOperatingActivities']['periodType']=='nine_month_cumulative'
    assert rows['NetCashProvidedByUsedInOperatingActivities']['direction']=='decrease'
    assert rows['PaymentsToAcquirePropertyPlantAndEquipment']['direction']=='increase'
    fcf=rows['SimplifiedFreeCashFlow']
    assert fcf['previous']['value']=='84904' and fcf['current']['value']=='72281'
    assert set(fcf['evidence_refs'])=={'FACT:1','FACT:2','FACT:3','FACT:4'}

def test_quarter_vs_ytd_different_units_and_non_yoy_never_compare():
    for old in [fact(1,'Revenue',10,'2024-01-01','2024-06-29'),fact(1,'Revenue',10,'2024-03-31','2024-06-29','EUR'),fact(1,'Revenue',10,'2025-01-01','2025-03-29')]:
        assert build_ledger(packet([old,fact(2,'Revenue',12,'2025-03-30','2025-06-28')]))['comparisons']==[]

def test_conflicting_values_and_later_filings_are_excluded():
    rows=cash_facts();rows.append({**rows[1],'value':100,'evidence_id':'FACT:5'})
    ledger=build_ledger(packet(rows))
    assert any(r['reason']=='conflicting_same_period_values' for r in ledger['excluded'])
    assert not any(r['concept']=='NetCashProvidedByUsedInOperatingActivities' for r in ledger['comparisons'])
    rows=cash_facts();rows[1]['filed_at']='2026-01-01'
    assert build_ledger(packet(rows))['excluded'][0]['reason']=='after_cutoff'

def test_balance_change_not_labeled_yoy_and_negative_denominator_has_no_percentage():
    ledger=build_ledger(packet([fact(1,'InventoryNet',-5,None,'2024-09-28'),fact(2,'InventoryNet',-2,None,'2025-06-28')]))
    row=ledger['comparisons'][0]
    assert row['comparisonBasis']=='prior_reported_balance'
    assert row['changePercent'] is None and row['direction']=='increase'

def test_model_cannot_acknowledge_wrong_cash_flow_direction_or_period():
    ledger=build_ledger(packet(cash_facts())); row=ledger['comparisons'][0]
    s=section();s.comparison_checks=[ComparisonCheck(comparison_id=row['id'],direction='increase',period_type='quarter')]
    with pytest.raises(ValueError,match='mismatch'):validate_section(s,{'FACT:1'},ledger,[row['id']])
    s.comparison_checks=[ComparisonCheck(comparison_id=row['id'],direction=row['direction'],period_type=row['periodType'])]
    validate_section(s,{'FACT:1'},ledger,[row['id']])
