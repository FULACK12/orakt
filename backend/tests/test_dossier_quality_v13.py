import pytest
from app.company_history_dossier import validate_section
from app.dossier_accounting_checks import disclosed_reference_terms,balance_narrative_errors,methodological_errors
from app.company_history_dossier import Section

def section():
 pair={'zh':'本财季收入增长与现金流并非同向，产品结构的贡献需要进一步验证。'*12,'en':'Revenue and cash flow do not move together. Product mix remains a hypothesis requiring evidence. '*10}
 return Section(**{k:pair.copy() for k in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']},evidence_refs=['FACT:1'])

def ledger(concept='LiabilitiesCurrent',direction='decrease'):
 return {'comparisons':[{'concept':concept,'periodType':'instant','comparisonBasis':'prior_reported_balance','direction':direction,'current':{'period_end':'2009-03-31'},'previous':{'period_end':'2008-12-31'}}]}

def test_only_disclosed_named_codes_bypass_number_guard():
 packet={'excerpts':[{'text':'FSP APB 14-1 and H20; revenue 500 million.'}],'market_evidence':[{'id':'MARKET:DGS2'}]}
 terms=disclosed_reference_terms(packet)
 assert terms==['FSP APB 14-1','DGS2','H20'] and '500' not in terms
 s=section();s.mechanism.zh+='FSP APB 14-1会计准则影响非现金利息。';s.mechanism.en+=' FSP APB 14-1 affects noncash interest.'
 validate_section(s,{'FACT:1'},technical_terms=terms)
 for extra in ['实际利息14.1%。','FSP APB 14-1%','ASC 820适用。']:
  other=s.model_copy(deep=True);other.mechanism.zh+=extra
  with pytest.raises(ValueError,match='Numerical'):validate_section(other,{'FACT:1'},technical_terms=terms)

def test_balance_basis_and_direction_are_not_cashflow_yoy():
 s=section();s.analysis.zh+='流动负债水平上升。'
 assert balance_narrative_errors(s,ledger())
 s.analysis.zh='流动负债水平下降。';assert not balance_narrative_errors(s,ledger())
 s.analysis.zh='现金及等价物余额同比增长。'
 assert balance_narrative_errors(s,ledger('CashAndCashEquivalentsAtCarryingValue','increase'))
 s.analysis.zh='现金及等价物余额较上年末增长。'
 assert not balance_narrative_errors(s,ledger('CashAndCashEquivalentsAtCarryingValue','increase'))

def test_no_false_flags_for_negation_hypotheses_or_valid_methodology():
 s=section();s.analysis.zh='不能据此推断流动负债上升。若流动负债上升，需要另行分析。'
 assert not balance_narrative_errors(s,ledger())
 s.validationPlan.zh='使用NFCI进行季节性调整。';assert methodological_errors(s)
 s.validationPlan.zh='NFCI是金融状况指标，不能用于季节性调整。';assert not methodological_errors(s)

def test_english_direct_balance_contradiction():
 s=section();s.analysis.en+=' Current liabilities increased.'
 assert balance_narrative_errors(s,ledger())
