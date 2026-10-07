"""Exact-period cash reconciliation, never an inferred cash-flow statement."""
from datetime import date,timedelta
from decimal import Decimal
import re

CONCEPTS={
 'operating':'NetCashProvidedByUsedInOperatingActivities',
 'investing':'NetCashProvidedByUsedInInvestingActivities',
 'financing':'NetCashProvidedByUsedInFinancingActivities',
 'fx':'EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
 'netChange':'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect',
 'balance':'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
}


def packet_passages(packet):
    known={}
    for ps in packet['chapter_passages'].values():
        for p in ps:
            if p['id'] in known and known[p['id']]['text']!=p['text']:raise ValueError('Conflicting passage identity')
            known[p['id']]=p
    return known


def cash_bridge(packet):
    candidates=[c for c in packet['financial_ledger']['comparisons'] if c['concept']==CONCEPTS['operating'] and c['current']['period_end']==packet['period_end']]
    if len(candidates)!=1:return {'state':'unavailable','reason':'Missing or ambiguous operating cash-flow period'}
    comparison=candidates[0];start=comparison['current']['period_start'];end=comparison['current']['period_end']
    if packet.get('verified_cash_source'):
        # Attachment is reproduced against original HTML by load_frozen_packet.
        a=packet['verified_cash_source'];b=a['cashReconciliations'][end]
        return {'state':b['state'],'periodStart':start,'periodEnd':end,'periodType':comparison['periodType'],'unit':'USD',
                'basis':b['basis'],'separateFxLineDisclosed':b['separateFxLineDisclosed'],
                'values':{k:{'value':f['value'],'evidence_refs':[f['evidence_id']]} for k,f in b['facts'].items()},
                'computedNetChange':b['computedNetChange'],'balanceChange':b['balanceChange'],'residual':b['flowResidual'],
                'meaning':b['meaning'],'source':'reviewed_original_html_table'}
    beginning=str(date.fromisoformat(start)-timedelta(days=1))
    def find(concept,lo,hi):
        rows=[f for f in packet['facts'] if f['concept']==concept and f.get('unit')=='USD' and f.get('period_start')==lo and f.get('period_end')==hi and f.get('filed_at',packet['as_of_date'])<=packet['as_of_date']]
        values={Decimal(str(f['value'])) for f in rows}
        if len(values)!=1 or not all(v.is_finite() for v in values):raise ValueError('Missing/conflicting exact-period fact: '+concept)
        return {'value':str(next(iter(values))),'evidence_refs':sorted({f['evidence_id'] for f in rows})}
    try:
        values={k:find(c,start,end) for k,c in CONCEPTS.items() if k!='balance'}
        values['opening']=find(CONCEPTS['balance'],None,beginning)
        values['closing']=find(CONCEPTS['balance'],None,end)
    except ValueError as exc:return {'state':'unavailable','reason':str(exc),'periodStart':start,'periodEnd':end,'periodType':comparison['periodType']}
    flow=sum(Decimal(values[k]['value']) for k in ('operating','investing','financing','fx'))
    reported=Decimal(values['netChange']['value'])
    delta=Decimal(values['closing']['value'])-Decimal(values['opening']['value'])
    matched=flow==reported==delta
    return {'state':'matched' if matched else 'mismatch','periodStart':start,'periodEnd':end,'periodType':comparison['periodType'],'unit':'USD',
            'values':values,'computedNetChange':str(flow),'balanceChange':str(delta),'residual':str(flow-reported),
            'meaning':'Arithmetic reconciliation only; not a conclusion about earnings quality, solvency or investment value.'}


def guard_cash_narrative(section, packet):
    """Known accounting regressions only; does not replace content review."""
    directions={c['direction'] for c in packet['financial_ledger']['comparisons'] if c['concept']==CONCEPTS['operating']}
    for key in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan'):
        pair=getattr(section,key);zh=pair.zh;en=pair.en
        if directions=={'decrease'} and (re.search(r'本财季(?:的)?经营现金流增长',zh) or re.search(r"(?:current quarter.s operating cash flow growth|operating cash flow growth in the current quarter)",en,re.I)):
            raise ValueError('Current operating cash flow decreased; do not describe current-quarter cash-flow growth')
        if re.search(r'递延收入.{0,70}(?:从而|进而|直接).{0,12}(?:提升|增加|改善).{0,12}现金流',zh) or re.search(r'deferred revenue.{0,110}(?:thereby|directly).{0,30}(?:improv|increas).{0,35}cash flow',en,re.I):
            raise ValueError('Recognizing deferred revenue does not itself generate a new cash receipt')
        if re.search(r'非现金项目增加.{0,12}(?:削弱|减少)现金流',zh) or re.search(r'non.cash items increase.{0,20}(?:weaken|reduce).{0,12}cash flow',en,re.I):
            raise ValueError('Non-cash adjustments have different signs; increases do not automatically weaken cash flow')
