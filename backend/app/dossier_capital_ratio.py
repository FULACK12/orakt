"""Source-bound CVX net-debt ratio, rounded inputs not false precision.

This explicit layout adapter does not infer fair value, debt maturities or
available liquidity from a ratio. Other issuers/layouts require another adapter.
"""
import hashlib
import re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP


def capital_ratio(packet, passage_id):
    if packet['ticker']!='CVX' or not packet['period_end'].endswith('-06-30'):
        raise ValueError('Unsupported issuer/period for this capital adapter')
    rows=[p for ps in packet['chapter_passages'].values() for p in ps if p['id']==passage_id]
    if not rows or any(r!=rows[0] for r in rows):raise ValueError('Missing/conflicting ratio source')
    p=rows[0];text=p['text'];year=int(packet['period_end'][:4])
    h=hashlib.sha256((packet['raw_sha256']+':'+str(p['start'])+':'+text).encode()).hexdigest()
    if p['sourceHash']!=packet['raw_sha256'] or p['id']!='PASSAGE:'+h[:16]:raise ValueError('Ratio source changed')
    if f'At June 30,\n{year} At December 31,\n{year-1}' not in text:
        raise ValueError('Exact balance-sheet comparison dates required')
    note=re.search(r'\(2\) Net Debt Ratio for June 30, '+str(year)+r', is calculated as (.+?)(?: For the December|$)',text,re.S)
    if not note:raise ValueError('Missing complete net-debt definition')
    definition=note[1]
    formula=(r'short-term debt of \$(\d+(?:\.\d+)?) billion plus long-term debt of \$(\d+(?:\.\d+)?) billion '
             r'\(together, “total debt”\) less cash and cash equivalents, time deposits, and marketable securities of '
             r'\$(\d+(?:\.\d+)?) billion as a percentage of total debt less cash and cash equivalents, '
             r'time deposits, and marketable securities, plus Chevron Corporation Stockholders’ Equity of \$(\d+(?:\.\d+)?) billion\.')
    m=re.fullmatch(formula,definition.strip())
    if not m:raise ValueError('Unrecognized numerator/denominator definition')
    ratios=re.findall(r'^Net Debt Ratio \(2\) (\d+(?:\.\d+)?) % (\d+(?:\.\d+)?) %$',text,re.M)
    if len(ratios)!=1:raise ValueError('Missing/ambiguous disclosed ratio')
    short,long,cash,equity=map(Decimal,m.groups())
    net=short+long-cash;denominator=net+equity
    if any(v<0 for v in (short,long,cash,equity)) or denominator<=0:raise ValueError('Unsupported ratio values')
    # All source inputs are rounded billions. Match displayed precision only.
    reproduced=(net/denominator*100).quantize(Decimal('0.1'),rounding=ROUND_HALF_UP)
    if reproduced!=Decimal(ratios[0][0]):raise ValueError('Displayed ratio does not reconcile with rounded inputs')
    names=('shortTermDebt','longTermDebt','deductibleCashTimeDepositsSecurities','chevronStockholdersEquity')
    fields={}
    for i,name in enumerate(names,1):
        a=note.start(1)+m.start(i);b=note.start(1)+m.end(i)
        fields[name]={'value':m[i],'unit':'USD','displayScale':1000000000,
                      'sourceId':p['id'],'sourceHash':p['sourceHash'],
                      'start':p['start']+a,'end':p['start']+b,'surface':text[a:b]}
    return {'state':'rounded_formula_reconciled_not_semantic_approval','periodEnd':packet['period_end'],
            'adapterCodeSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'comparisonEnd':str(year-1)+'-12-31','sourceId':p['id'],'sourceHash':p['sourceHash'],
            'unit':'USD','displayScale':1000000000,'inputs':fields,
            'totalDebt':str(short+long),'netDebt':str(net),'denominator':str(denominator),
            'formula':'(shortTermDebt + longTermDebt - deductibleCashTimeDepositsSecurities) / (shortTermDebt + longTermDebt - deductibleCashTimeDepositsSecurities + chevronStockholdersEquity)',
            'reproducedPercentAtSourcePrecision':str(reproduced),
            'disclosedCurrentPercent':ratios[0][0],'disclosedPreviousPercent':ratios[0][1],
            'cashScope':'company-defined cash and cash equivalents, time deposits and marketable securities; do not replace with cash-flow balance including restricted cash',
            'limitation':'Computed from rounded disclosed billions; not exact unrounded debt or valuation. Previous-period ratio is quoted, not independently recomputed.'}
