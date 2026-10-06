"""Reviewed accounting signs, not inferred causality. Unsupported filings fail closed."""
from decimal import Decimal

# Signs reconciled to the displayed AAPL statement, not inferred from XBRL names.
# Asset increase/decrease tags and OtherNoncashIncomeExpense use the opposite
# sign to the cash contribution displayed in this particular statement.
AAPL_LINES = [
 ('NetIncomeLoss',1,'净利润','Net income'),
 ('DepreciationDepletionAndAmortization',1,'折旧与摊销','Depreciation and amortization'),
 ('ShareBasedCompensation',1,'股权激励费用','Share-based compensation'),
 ('OtherNoncashIncomeExpense',-1,'其他非现金调整','Other noncash adjustments'),
 ('IncreaseDecreaseInAccountsReceivable',-1,'应收账款变动','Accounts receivable movement'),
 ('IncreaseDecreaseInOtherReceivables',-1,'供应商非贸易应收款变动','Vendor non-trade receivables movement'),
 ('IncreaseDecreaseInInventories',-1,'存货变动','Inventory movement'),
 ('IncreaseDecreaseInOtherOperatingAssets',-1,'其他经营资产变动','Other operating assets movement'),
 ('IncreaseDecreaseInAccountsPayable',1,'应付账款变动','Accounts payable movement'),
 ('IncreaseDecreaseInOtherOperatingLiabilities',1,'其他经营负债变动','Other operating liabilities movement'),
]

def bridge(packet):
 if (packet['ticker'],packet['accession'])!=('AAPL','0000320193-25-000073'):
  raise ValueError('Statement sign mapping not reviewed for this filing')
 def fact(concept,start,end):
  matches=[f for f in packet['facts'] if f['concept']==concept and f['unit']=='USD' and f.get('period_start')==start and f['period_end']==end and f.get('filed_at',packet['as_of_date'])<=packet['as_of_date']]
  if not matches or len({Decimal(str(f['value'])) for f in matches})!=1:raise ValueError('Missing or conflicting bridge fact: '+concept)
  return matches[0]
 periods=[('2024-09-29','2025-06-28'),('2023-10-01','2024-06-29')]
 rows=[]
 for concept,sign,zh,en in AAPL_LINES:
  facts=[fact(concept,*p) for p in periods];values=[Decimal(str(f['value']))*sign for f in facts]
  rows.append({'concept':concept,'label':{'zh':zh,'en':en},'sign':sign,'current':str(values[0]),'previous':str(values[1]),'contributionChange':str(values[0]-values[1]),'facts':facts})
 totals=[fact('NetCashProvidedByUsedInOperatingActivities',*p) for p in periods]
 residuals=[Decimal(str(f['value']))-sum(Decimal(r[k]) for r in rows) for k,f in zip(['current','previous'],totals)]
 if any(residuals):raise ValueError('Cash flow statement does not reconcile; no attribution published')
 return {'version':'cash-flow-bridge/v1','ticker':packet['ticker'],'asOf':packet['as_of_date'],'unit':'USD','periodType':'nine_month_cumulative','sourceUrl':packet['source_url'],'sourceDocumentHash':packet['raw_sha256'],'rows':rows,'totals':totals,'residuals':[str(v) for v in residuals],'reconciled':True,'scope':'Accounting decomposition, not causal identification; tax payments are supplemental and must not be added again.'}
