import pytest
from app.derived_fiscal_quarter import derive
from app.dossier_accounting_checks import mask_financial_numbers,gross_margin_checks,guard_prose,guard_expense_claims
from types import SimpleNamespace

def operands():
 a=dict(issuer='MSFT',concept='OperatingIncomeLoss',unit='USD',value='128528000000',period_start='2024-07-01',period_end='2025-06-30',filed_at='2025-07-30',source_url='https://www.sec.gov/annual')
 y={**a,'value':'94205000000','period_end':'2025-03-31','filed_at':'2025-04-30','source_url':'https://www.sec.gov/ytd'}
 return a,y

def test_reviewed_quarter_is_reproducible():
 r=derive(*operands(),issuer='MSFT',cutoff='2025-08-01',reviewed_basis=True)
 assert r['value']=='34323000000' and r['period_start']=='2025-04-01'

@pytest.mark.parametrize('key,value',[('unit','EUR'),('issuer','AAPL'),('period_start','2024-01-01'),('period_end','2025-01-31'),('filed_at','2025-08-02'),('concept','EarningsPerShareDiluted'),('value','NaN'),('dimensions',{'segment':'x'})])
def test_mismatched_inputs_cannot_be_derived(key,value):
 a,y=operands();y[key]=value
 with pytest.raises(ValueError):derive(a,y,issuer='MSFT',cutoff='2025-08-01',reviewed_basis=True)

def test_no_unreviewed_basis_or_product_corruption():
 with pytest.raises(ValueError):derive(*operands(),issuer='MSFT',cutoff='2025-08-01')
 assert mask_financial_numbers('H20 and GB200 cost 44062 dollars')=='H20 and GB200 cost [value in source table] dollars'

def test_profit_growth_is_not_margin_growth():
 def row(c,a,b):return {'concept':c,'unit':'USD','periodType':'quarter','current':{'value':a,'period_start':'2025-01-27','period_end':'2025-04-27'},'previous':{'value':b,'period_start':'2024-01-29','period_end':'2024-04-28'},'evidence_refs':[c]}
 checks=gross_margin_checks({'comparisons':[row('GrossProfit',26668,20406),row('Revenues',44062,26044)]})
 assert checks[0]['direction']=='decrease'
 s=SimpleNamespace(analysis=SimpleNamespace(zh='公司的毛利率同比增长',en=''),mechanism=SimpleNamespace(zh='',en=''))
 with pytest.raises(ValueError):guard_prose(s,checks)

def test_expense_direction_claim_is_checked():
 s=SimpleNamespace(analysis=SimpleNamespace(zh='',en=''),mechanism=SimpleNamespace(zh='研发支出和管理费用的减少',en='reductions in R&D expenditures and administrative costs'))
 with pytest.raises(ValueError):guard_expense_claims(s,{'comparisons':[{'concept':'ResearchAndDevelopmentExpense','direction':'increase'}]})
