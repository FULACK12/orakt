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
 text=' '.join(e['text'] for e in excerpts)
 terms=set(re.findall(r'\b(?:H|B|GB|MI)\d{2,4}[A-Z]?\b',text))
 # Source-attested product identifiers are not financial quantities. In
 # particular, masking Microsoft 365 makes the writer reconstruct its name.
 terms.update(re.findall(r'\b(?:Microsoft|Office|Dynamics) 365\b',text))
 # Exact disclosed aircraft program names, not arbitrary hyphenated numbers.
 # These otherwise become "MQ-[value in source table]" in redacted views.
 terms.update(re.findall(r'\b(?:MQ-25|T-7A|KC-46A?|VC-25B)\b',text))
 # Retain the full source-attested program label, never a bare numeric name
 # that could also be a revenue, delivery quantity or percentage.
 terms.update(re.findall(r'\b(?:737|777X|787) program\b',text))
 if re.search(r'\bMicrosoft\b',text):
  terms.update(re.findall(r'\bE[35]\b',text))
 return sorted(terms)


def disclosed_reference_terms(packet):
 """Only source-attested named identifiers, never dates or standalone numbers."""
 excerpts=list(packet.get('excerpts',[]))
 excerpts += [p for ps in packet.get('chapter_passages',{}).values() for p in ps]
 text=' '.join(e['text'] for e in excerpts)
 terms=set(disclosed_product_terms(excerpts))
 pattern=r'\b(?:FSP(?: No\.)? APB \d{1,3}-\d{1,2}|EITF \d{2}-\d{1,2}|(?:FAS|SFAS)(?: No\.)? \d{1,3}|(?:ASC|IFRS|IAS) \d{1,3}(?:-\d{1,3})?)\b'
 terms.update(re.findall(pattern,text))
 # A code supplied in the frozen market packet is a label, not a yield value.
 for series in packet.get('market_evidence',[]):
  code=series.get('id','').removeprefix('MARKET:')
  if re.fullmatch(r'DGS\d{1,2}',code):terms.add(code)
 return sorted(terms,key=lambda t:(-len(t),t))


def balance_narrative_errors(section, ledger):
 """Narrow contradiction flags. Never a replacement for semantic review."""
 patterns={
  'CashAndCashEquivalentsAtCarryingValue':r'现金及等价物(?:余额|规模)?|现金及现金等价物(?:余额)?|货币资金(?:余额|规模)?|cash and cash equivalents(?: balance)?',
  'LiabilitiesCurrent':r'流动负债(?:水平|余额|规模)?|current liabilities',
  'AssetsCurrent':r'流动资产(?:水平|余额|规模)?|current assets',
  'LongTermDebtNoncurrent':r'长期债务非流动部分(?:余额|规模)?|非流动长债(?:余额)?|noncurrent (?:long.term )?debt',
 }
 errors=[]
 for field in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']:
  pair=getattr(section,field)
  for lang,text in [('zh',pair.zh),('en',pair.en)]:
   for concept,pattern in patterns.items():
    comparisons=[c for c in ledger.get('comparisons',[]) if c['concept']==concept and c['periodType']=='instant']
    if len(comparisons)!=1:continue
    c=comparisons[0]
    for sentence in re.split(r'[。！？;；\n]|(?<=[.!?])\s+',text):
     for match in re.finditer(pattern,sentence,re.I):
      prefix=sentence[max(0,match.start()-22):match.start()]
      tail=sentence[match.end():match.end()+20]
      # Restrict flags to direct assertions. Hypothetical language still needs review.
      if re.search(r'不能|不应|并非|无法|如果|假设|若|not |cannot |\bif\b|whether',prefix,re.I):continue
      if re.search(r'^(?:可能|或许|may| might| could)',tail,re.I):continue
      if c['comparisonBasis']=='prior_reported_balance':
       from datetime import date
       gap=(date.fromisoformat(c['current']['period_end'])-date.fromisoformat(c['previous']['period_end'])).days
       if not 350<=gap<=380 and re.search(r'^[^，,。;；]{0,6}同比|^.{0,10}(?:year.over.year|YoY)',tail,re.I):
        errors.append(f'{field}.{lang}: {concept} compares prior reported balance, not YoY')
      direction='increase' if re.search(r'^(?:同比|较上年末|较期初|较前期|的|显著|明显|大幅|却|仍|呈现| has| have| had| is| materially| substantially| significantly| sharply| year.over.year| YoY| )*(?:上升|增加|增长|扩张|increased|rose|grew)',tail,re.I) else 'decrease' if re.search(r'^(?:同比|较上年末|较期初|较前期|的|显著|明显|大幅|却|仍|呈现| has| have| had| is| materially| substantially| significantly| sharply| year.over.year| YoY| )*(?:下降|减少|收缩|decreased|declined|fell)',tail,re.I) else None
      if direction and direction!=c['direction']:errors.append(f'{field}.{lang}: {concept} direction contradicts frozen balance comparison')
 return errors


def methodological_errors(section):
 errors=[]
 for field in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']:
  pair=getattr(section,field)
  for lang,text in [('zh',pair.zh),('en',pair.en)]:
   for sentence in re.split(r'[。！？;；\n]|(?<=[.!?])\s+',text):
    # Narrow regressions observed in reviewed local drafts, not a semantic verifier.
    negated = re.search(r'不等于|不能|不意味着|并非|不是|不能据此|not |cannot|does not|neither',sentence,re.I)
    if not negated:
     if re.search(r'递延收入.{0,35}(?:等同于|接近于|就是).{0,12}(?:已实现的?利润|利润)',sentence) or re.search(r'deferred revenue.{0,75}(?:equivalent to|closer to|equals).{0,20}(?:realized profit|earned profit)',sentence,re.I):
      errors.append(f'{field}.{lang}: deferred revenue is not realized profit; correlation does not change recognition rules')
     if ((re.search(r'回购价格.{0,25}(?:高于|低于).{0,20}(?:累计|历史).*平均',sentence) and re.search(r'每股收益.{0,12}(?:正面|负面|提高|降低)',sentence)) or
         (re.search(r'repurchase.{0,45}price.{0,20}(?:higher|lower).{0,45}(?:average|historical)',sentence,re.I) and re.search(r'(?:positiv|negativ).{0,30}earnings per share|earnings per share.{0,30}(?:positiv|negativ)',sentence,re.I))):
      errors.append(f'{field}.{lang}: historical repurchase average does not determine EPS accretion')
    if 'NFCI' not in sentence or not re.search(r'季节性调整|seasonal.{0,15}adjust',sentence,re.I):continue
    if not re.search(r'不能|不可|不用于|不得|not |cannot|must not',sentence,re.I):
     errors.append(f'{field}.{lang}: NFCI is not a seasonal-adjustment procedure')
 return errors
