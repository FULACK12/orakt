"""Narrow development regressions, not a general semantic approval oracle.

Unbound prose is still reviewed against originals. A bilingual discrepancy is
triage, not proof which language is correct. Never infer totals from fragments.
"""
import re
from decimal import Decimal

NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
REF = re.compile(r'PASSAGE:[a-f0-9]{16}')


def money(text, lang):
    pattern = (rf'({NUM})\s*(亿|百万|千万|万)\s*美元' if lang == 'zh'
               else rf'\$\s*({NUM})\s*(billion|million|thousand|B\b|M\b)')
    scale = {'亿':8,'百万':6,'千万':7,'万':4,'billion':9,'million':6,'thousand':3,'b':9,'m':6}
    return [(m.group(0), Decimal(m.group(1).replace(',', '')) * 10**scale[m.group(2).lower()])
            for m in re.finditer(pattern, text, re.I)]


def check(packet, documents):
    ps = {p['id']: p['text'] for group in packet.get('chapter_passages', {}).values() for p in group}
    result = []
    def add(code, loc, actual, expected, refs, severity='error'):
        result.append({'code':code,'location':loc,'actual':actual,'expected':expected,
                       'sourceIds':sorted(refs),'severity':severity})
    for doc in documents:
        chapter = doc['chapter']; section = doc.get('section', {})
        pairs = [(f'section/{k}',section.get(k,{})) for k in
                 ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')]
        pairs += [(f'section/grounded_claims/{i}/statement',c.get('statement',{}))
                  for i,c in enumerate(section.get('grounded_claims',[]))]
        for pointer, pair in pairs:
            zh, en = pair.get('zh',''), pair.get('en','')
            refs = set(REF.findall(zh+en))
            if 'grounded_claims' in pointer:
                refs.add(section['grounded_claims'][int(pointer.split('/')[2])].get('passage_id',''))
            # Only compare unmatched values. Legitimate omission/extra detail is
            # not called wrong. An exact tenfold mismatch requires human review.
            z, e = money(zh,'zh'),money(en,'en')
            zs, es = {v for _,v in z},{v for _,v in e}
            for surface,value in e:
                if value in zs or not value: continue
                alternatives = [(s,v) for s,v in z if v not in es and v and value/v in (Decimal(10),Decimal('0.1'))]
                if alternatives:
                    add('bilingual_money_scale',chapter+'/'+pointer+'/en',surface,
                        [s for s,_ in alternatives],refs,'review_required')
            # Two-column cash payments only: do not use tax expense, an annual
            # table, ambiguous multiple rows, or rounded narrative endpoints.
            rows = []
            for pid in refs & ps.keys():
                source = ps[pid]
                if not all(s in source for s in ('Six Months Ended','Millions of dollars','cash payments')):continue
                years = re.search(r'\b(20\d{2})\s+(20\d{2})\s*\n\(Millions of dollars\)',source)
                row = re.findall(rf'^Income taxes\s+\$?\s*({NUM})\s+\$?\s*({NUM})\s*$',source,re.M)
                if years and int(years[1])>int(years[2]) and len(row)==1:
                    a,b = (Decimal(v.replace(',','')) for v in row[0])
                    rows.append((a-b,pid,years[1],years[2]))
            if rows and len({r[0] for r in rows})==1:
                delta,pid,current,prior = rows[0]
                for lang,body in [('zh',zh),('en',en)]:
                    for sentence in re.split(r'(?<=[。!?])|(?<=\.)\s+(?=[A-Z])',body):
                        if not (current in sentence and prior in sentence):continue
                        if lang=='zh':
                            if '所得税支付' not in sentence or not re.search(r'上半年|六个月',sentence):continue
                            changes = re.findall(rf'(增加|减少)\s*({NUM})\s*百万美元',sentence)
                        else:
                            if 'income tax payments' not in sentence.lower() or 'first half' not in sentence.lower():continue
                            changes = re.findall(rf'\b(up|down)\s+\$({NUM})\s+million',sentence,re.I)
                        for direction,value in changes:
                            actual=Decimal(value.replace(',','')) * (-1 if direction.lower() in ('down','减少') else 1)
                            if actual != delta:
                                add('cash_tax_change_arithmetic',chapter+'/'+pointer+'/'+lang,
                                    str(actual),str(delta),[pid])
            # Negated cash-reconciliation row reverses balance direction. This
            # guard is deliberately confined to prepaid assets and the exact
            # accounting row, not all negative values in financial statements.
            negative = [pid for pid in refs & ps.keys() if re.search(
                r'Decrease\s*\(increase\)\s*in prepaid expenses and other current assets\s+\$?\s*\(\s*[\d,]+\s*\)',ps[pid],re.I)]
            for lang,body in [('zh',zh),('en',en)]:
                if negative and (re.search(r'预付费用减少\s*\d',body) if lang=='zh' else
                                 re.search(r'\$[\d,.]+\s+million decrease in prepaid expenses',body,re.I)):
                    add('working_capital_sign_direction',chapter+'/'+pointer+'/'+lang,
                        'prepaid balance described as decreasing',
                        'negative Decrease (increase) row means an increase/cash outflow; verify column period',negative,'review_required')
            # Compare signed CASH totals only, never infer causes. A smaller
            # negative investing total means less cash used, not lower signed
            # cash flow. Ambiguous qualitative wording is triaged, not approved.
            labels={'investing':r'Net Cash Used for Investing Activities',
                    'financing':r'Net Cash Provided by \(Used for\) Financing Activities'}
            amount=rf'(\(?\s*-?{NUM}\s*\)?)'
            for category,label in labels.items():
                observations=[]
                for pid in refs & ps.keys():
                    source=ps[pid]
                    if not re.search(r'Six Months Ended.{0,40}(20\d{2})\s+(20\d{2})\s*\n\(Millions of dollars\)',source,re.S):continue
                    years=re.search(r'(20\d{2})\s+(20\d{2})\s*\n\(Millions of dollars\)',source)
                    if int(years[1])<=int(years[2]) or not str(packet.get('period_end','')).startswith(years[1]+'-'):continue
                    rows=re.findall(r'^'+label+r'\s+'+amount+r'\s+'+amount+r'\s*$',source,re.M)
                    if len(rows)!=1:continue
                    def signed(s):
                        return Decimal(re.sub(r'[(),\s]','',s))*(-1 if '(' in s else 1)
                    a,b=map(signed,rows[0]);observations.append((a-b,pid))
                if not observations or len({v for v,_ in observations})!=1:continue
                delta=observations[0][0]
                for lang,body in [('zh',zh),('en',en)]:
                    word='投资' if category=='investing' else '融资'
                    pattern=(word+r'活动现金流(?:同比)?(改善|增加|减少|下降)' if lang=='zh' else
                             category+r' cash flow (improved|increased|declined|decreased)')
                    for sentence in re.split(r'[。;；]|(?<=[.!?])\s+',body):
                        if re.search(r'如果|若|不应|不能|并非|\bif\b|must not|does not|incorrect',sentence,re.I):continue
                        m=re.search(pattern,sentence,re.I)
                        if not m:continue
                        asserted=1 if m[1].lower() in ('改善','增加','improved','increased') else -1
                        if delta*asserted<0:
                            add('signed_cash_flow_direction',chapter+'/'+pointer+'/'+lang,m[0],
                                {'category':category,'signedChangeMillions':str(delta),
                                 'scope':'Cumulative signed cash total; describe outflow magnitude separately, not as company health'},
                                [p for _,p in observations],'review_required')
    return result
