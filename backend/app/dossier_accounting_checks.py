"""Narrow deterministic claim guards; passing is not a semantic audit."""
import re
from decimal import Decimal

def gross_margin_checks(ledger):
 checks=[]
 for g in ledger.get('comparisons',[]):
  if g['concept']!='GrossProfit':continue
  revenues=[r for r in ledger['comparisons'] if r['concept'] in {'Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet'} and r['unit']==g['unit'] and all((r[k].get('period_start'),r[k]['period_end'])==(g[k].get('period_start'),g[k]['period_end']) for k in ['current','previous'])]
  if len(revenues)!=1:continue
  r=revenues[0];values=[]
  for k in ['current','previous']:
   numerator=Decimal(str(g[k]['value']));denominator=Decimal(str(r[k]['value']))
   if not numerator.is_finite() or not denominator.is_finite() or denominator<=0:break
   values.append(numerator/denominator*100)
  if len(values)!=2:continue
  checks.append({'metric':'gross_margin','periodType':g['periodType'],'currentPercent':str(values[0]),'previousPercent':str(values[1]),'changePercentagePoints':str(values[0]-values[1]),'direction':'increase' if values[0]>values[1] else 'decrease' if values[0]<values[1] else 'unchanged','evidence_refs':list(dict.fromkeys(g['evidence_refs']+r['evidence_refs']))})
 return checks

def guard_prose(section,ratios):
 directions={r['direction'] for r in ratios if r['metric']=='gross_margin'}
 if directions!={'decrease'}:return
 for field in ['analysis','mechanism']:
  pair=getattr(section,field)
  # Deliberately narrow assertions only. Other causal claims still need review.
  if re.search(r'毛利率(?:同比|较上年同期)?(?:增长|上升|提高|改善)',pair.zh) or re.search(r'gross margin(?: has| had|s have| rate has)?(?: grown| increased| improved| risen)',pair.en,re.I):
   raise ValueError('Gross-margin assertion contradicts matching-period arithmetic')

def guard_expense_claims(section,ledger):
 patterns={
  'ResearchAndDevelopmentExpense':(r'研发(?:支出|费用)(?:的)?(?:减少|下降|降低)',r'(?:reductions? in R&D|R&D (?:expenditures|expenses) (?:have )?(?:decreased|declined))'),
  'SellingGeneralAndAdministrativeExpense':(r'(?:销售及管理|管理)(?:费用|支出)(?:的)?(?:减少|下降|降低)',r'(?:reductions? in .*administrative costs|administrative (?:costs|expenses) (?:have )?(?:decreased|declined))')}
 for concept,(zh,en) in patterns.items():
  directions={c['direction'] for c in ledger.get('comparisons',[]) if c['concept']==concept}
  if directions!={'increase'}:continue
  for field in ['analysis','mechanism']:
   pair=getattr(section,field)
   if re.search(zh,pair.zh) or re.search(en,pair.en,re.I):raise ValueError('Expense direction contradicts financial ledger: '+concept)

def mask_financial_numbers(text):
 # Preserve alphanumeric product identifiers (H20, GB200, MI300) rather than
 # silently turning an export-controlled product name into a placeholder.
 return re.sub(r'(?<![A-Za-z0-9])\d[\d,.%/-]*','[value in source table]',text)

def disclosed_product_terms(excerpts):
 return sorted(set(re.findall(r'\b(?:H|B|GB|MI)\d{2,4}[A-Z]?\b',' '.join(e['text'] for e in excerpts))))
