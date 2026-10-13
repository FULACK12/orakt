"""Exact two-column cash-statement decomposition, not economic attribution.

Supports an explicitly selected June half-year USD-million statement. Unknown
layouts, ambiguous rows, changed evidence or mismatches fail closed. No model.
"""
import hashlib
import re
from decimal import Decimal
from app.dossier_cash_bridge import cash_bridge

# An explicit source-layout adapter, not an inferred universal company schema.
CVX_GROUPS={
    'operating':[
        'Net Income (Loss)','Depreciation, depletion and amortization','Dry hole expense',
        'Distributions more (less) than income from equity affiliates',
        'Net before-tax losses (gains) on asset retirements and sales','Net foreign currency effects',
        'Deferred income tax provision','Net decrease (increase) in operating working capital',
        'Decrease (increase) in long-term receivables','Net decrease (increase) in other deferred charges',
        'Cash contributions to employee pension plans','Other'],
    'investing':[
        'Acquisition of Hess Corporation common stock','Capital expenditures',
        'Proceeds and deposits related to asset sales and returns of investment',
        'Net maturities of (investments in) time deposits','Net repayment (borrowing) of loans by equity affiliates'],
    'financing':[
        'Net borrowings (repayments) of short-term obligations','Proceeds from issuances of long-term debt',
        'Repayments of long-term debt and other financing obligations','Cash dividends - common stock',
        'Net contributions from (distributions to) noncontrolling interests','Net sales (purchases) of treasury shares'],
}
TOTALS={'operating':'Net Cash Provided by Operating Activities',
        'investing':'Net Cash Used for Investing Activities',
        'financing':'Net Cash Provided by (Used for) Financing Activities',
        'fx':'Effect of Exchange Rate Changes on Cash, Cash Equivalents and Restricted Cash',
        'netChange':'Net Change in Cash, Cash Equivalents and Restricted Cash',
        'opening':'Cash, Cash Equivalents and Restricted Cash at January 1',
        'closing':'Cash, Cash Equivalents and Restricted Cash at June 30'}
WORKING_CAPITAL=[
    'Decrease (increase) in accounts and notes receivable','Decrease (increase) in inventories',
    'Decrease (increase) in prepaid expenses and other current assets',
    'Increase (decrease) in accounts payable and accrued liabilities',
    'Increase (decrease) in income and other taxes payable']


def two_column_rows(passage, labels, *, period_end):
    """Exact row surface + offsets; em dash is explicit zero, never missing."""
    source=passage['text'];year=int(period_end[:4])
    if not period_end.endswith('-06-30'):raise ValueError('Unsupported cash statement period')
    header=f'Six Months Ended\nJune 30\n{year} {year-1}\n(Millions of dollars)'
    if header not in source:raise ValueError('Missing exact period/unit header')
    expected=hashlib.sha256((passage['sourceHash']+':'+str(passage['start'])+':'+source).encode()).hexdigest()
    if passage['id']!='PASSAGE:'+expected[:16]:raise ValueError('Changed passage identity')
    atom=r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    number=rf'(—|-?{atom}|\(\s*{atom}\s*\))'
    def decimal(s):
        if s=='—':return Decimal(0)
        return Decimal(re.sub(r'[(),\s]','',s))*(-1 if '(' in s else 1)
    result={}
    for label in labels:
        matches=list(re.finditer(r'^'+re.escape(label)+r'[ \t]+\$?[ \t]*'+number+r'[ \t]+\$?[ \t]*'+number+r'[ \t]*$',source,re.M))
        if len(matches)!=1:raise ValueError('Missing/ambiguous cash row: '+label)
        m=matches[0]
        if m.start()<source.index(header)+len(header):raise ValueError('Row precedes period context')
        a,b=map(decimal,m.groups())
        result[label]={'label':label,'current':str(a),'previous':str(b),'signedChange':str(a-b),
                       'sourceId':passage['id'],'sourceHash':passage['sourceHash'],
                       'surface':m[0],'start':passage['start']+m.start(),'end':passage['start']+m.end()}
    return result


def reconcile_components(packet, statement_id, note_id, *, groups=None):
    """Rows must be explicit; extra/missing components cannot balance silently."""
    if groups is None:
        if packet['ticker']!='CVX':raise ValueError('Explicit component adapter required for this issuer')
        groups=CVX_GROUPS
    ps={p['id']:p for rows in packet['chapter_passages'].values() for p in rows}
    statement,note=ps[statement_id],ps[note_id]
    if any(p['sourceHash']!=packet['raw_sha256'] for p in (statement,note)):
        raise ValueError('Statement and note must belong to this frozen original')
    labels=[v for rows in groups.values() for v in rows]+list(TOTALS.values())
    if len(labels)!=len(set(labels)):raise ValueError('Duplicate component labels')
    if set(groups)!={'operating','investing','financing'}:raise ValueError('All cash categories required')
    rows=two_column_rows(statement,labels,period_end=packet['period_end'])
    # Reject unmodelled numeric rows even when they net to zero. Matching a
    # subtotal is not sufficient evidence that every component was captured.
    numeric_line=re.compile(r'^[A-Za-z][^\n]*?[ \t]+\$?[ \t]*(?:—|-?\d[\d,.]*|\(\s*\d[\d,.]*\s*\))[ \t]+\$?[ \t]*(?:—|-?\d[\d,.]*|\(\s*\d[\d,.]*\s*\))[ \t]*$',re.M)
    known={r['surface'].strip() for r in rows.values()}
    if any(m[0].strip() not in known for m in numeric_line.finditer(statement['text'])):
        raise ValueError('Unmodelled statement component; adapter must be reviewed')
    ns=two_column_rows(note,WORKING_CAPITAL+['Net decrease (increase) in operating working capital','Income taxes'],period_end=packet['period_end'])
    for column in ('current','previous'):
        value=lambda label:Decimal(rows[label][column])
        for key,components in groups.items():
            if sum(value(s) for s in components)!=value(TOTALS[key]):raise ValueError('Component sum mismatch: '+key)
        if sum(value(TOTALS[k]) for k in ('operating','investing','financing','fx'))!=value(TOTALS['netChange']):
            raise ValueError('Cash flow reconciliation mismatch')
        if value(TOTALS['opening'])+value(TOTALS['netChange'])!=value(TOTALS['closing']):
            raise ValueError('Cash balance reconciliation mismatch')
        working=sum(Decimal(ns[s][column]) for s in WORKING_CAPITAL)
        if working!=Decimal(ns['Net decrease (increase) in operating working capital'][column]) or working!=value('Net decrease (increase) in operating working capital'):
            raise ValueError('Working capital reconciliation mismatch')
    bridge=cash_bridge(packet)
    if bridge['state']!='matched':raise ValueError('Structured fact bridge is not matched')
    if (bridge.get('unit')!='USD' or bridge.get('periodEnd')!=packet['period_end']
            or bridge['periodStart']!=packet['period_end'][:4]+'-01-01'):
        raise ValueError('Structured fact bridge period/currency mismatch')
    for key,label in TOTALS.items():
        if Decimal(rows[label]['current'])*1000000!=Decimal(bridge['values'][key]['value']):
            raise ValueError('Original table conflicts with structured facts: '+key)
    return {'state':'arithmetically_matched_not_semantic_approval','ticker':packet['ticker'],
            'periodStart':bridge['periodStart'],'periodEnd':packet['period_end'],
            'comparisonStart':str(int(packet['period_end'][:4])-1)+'-01-01',
            'comparisonEnd':str(int(packet['period_end'][:4])-1)+'-06-30',
            'unit':'USD','displayScale':1000000,'cashDefinition':'cash, cash equivalents and restricted cash',
            'sourceHash':packet['raw_sha256'],'totals':{key:rows[label] for key,label in TOTALS.items()},
            'components':{key:[rows[label] for label in labels] for key,labels in groups.items()},
            'workingCapital':[ns[label] for label in WORKING_CAPITAL],
            'cashTaxes':ns['Income taxes'],'structuredFactBridge':bridge,
            'meaning':'Exact signed arithmetic decomposition. Not causal proof, sustainable earnings, credit approval or investment advice.'}
