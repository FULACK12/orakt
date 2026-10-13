"""Development-derived metric identity triage, NOT general entailment checking.

Motivation: retained AMD financial review (operating income mistranslated as
revenue). Short assertion and exact claim citation only; mixed metrics, ratios,
negations and conditional research questions abstain. No holdout-specific rules.
"""
import re

OP = r'\boperating (?:income|profit|loss)\b'
REVENUE = r'\b(?:net sales|(?:net |operating )?revenue[s]?)\b'
NET = r'\bnet (?:income|profit|loss)\b'
OP_SOURCE = OP + r'|\b(?:income|loss|earnings) from operations\b|\boperating earnings\b'
NET_SOURCE = NET + r'|\bnet earnings\b'
ASSERTION = r'\s+(?:(?:has|had)\s+)?(?:increased|decreased|improved|declined|rose|fell|grew|was|were|is|turns|turned)\b'
CAUTION = re.compile(r'\b(?:if|whether|would|could|might|not|no|without|unknown|undisclosed|missing|lacks?|verify|retrieve)\b|如果|假如|并非|不是|不等于|未披露|未说明|没有|尚未|无法|核实|检索', re.I)


def check(packet, documents):
    ps = {p['id']: p['text'] for group in packet.get('chapter_passages', {}).values() for p in group}
    findings = []

    def add(code, location, body, start, end, refs, expected, related=None):
        findings.append({'code': code, 'location': location, 'severity': 'review_required',
                         'actual': body[start:end], 'span': {'start': start, 'end': end},
                         'expected': expected, 'sourceIds': sorted(refs),
                         'originalEvidence': [{'id': pid, 'text': ps[pid]} for pid in sorted(refs) if pid in ps],
                         'relatedLocation': related,
                         'scope': 'Narrow metric-identity triage; does not determine factual truth or approve a report.'})

    for doc in documents:
        section = doc.get('section', {})
        # Development AMD business draft: a cash-flow improvement asserted in
        # a paragraph citing manufacturing risks only. This is citation triage,
        # not an entailment verdict. An explicit fact binding stays with the
        # ledger validator. Restrict to English result assertions, not questions,
        # forecasts or hypotheses; other languages still need semantic review.
        body = section.get('analysis', {}).get('en', '')
        refs = set(re.findall(r'PASSAGE:[a-f0-9]{16}', body))
        source = ' '.join(ps.get(pid, '') for pid in refs)
        bound = any(b.get('location') == 'section/analysis/en' for b in doc.get('factBindings', []))
        if refs and refs <= ps.keys() and not bound:
            for sentence in re.finditer(r'[^.!?]+[.!?]?', body):
                value = sentence.group()
                if CAUTION.search(value) or '?' in value:
                    continue
                asserted = re.search(r'\b(?:improved|increased|decreased|higher|lower) (?:operating )?cash flow\b|\b(?:operating )?cash flow (?:improved|increased|decreased|rose|fell)\b', value, re.I)
                if asserted and not re.search(r'\bcash (?:flows?|provided|used|generated)\b', source, re.I):
                    add('narrative_result_source_mismatch', doc['chapter']+'/section/analysis/en', body,
                        sentence.start()+asserted.start(), sentence.start()+asserted.end(), refs,
                        'Cash-flow result asserted but not named in the cited evidence; bind its original statement or remove the unsupported result. This is not proof the result is false.')
        # Grounded claims are short, explicitly paired and have a single exact
        # source. Whole-paragraph keyword comparison would mix unrelated metrics.
        for index, claim in enumerate(section.get('grounded_claims', [])):
            pair = claim.get('statement', {})
            zh, en = pair.get('zh', ''), pair.get('en', '')
            if not isinstance(zh, str) or not isinstance(en, str):
                continue
            pid = claim.get('passage_id')
            if pid not in ps:
                continue  # Existing quote/source validator reports this.
            loc = f"{doc['chapter']}/section/grounded_claims/{index}/statement"
            source = ps[pid]
            retired = re.search(r'\bretired\s+(?:\d[\d,.]*\s+)?(?:(?:million|billion)\s+)?(?:of\s+)?(?:its\s+)?treasury shares\b', source, re.I)
            repurchased = re.search(r'\brepurchased treasury shares\b', en, re.I)
            if (retired and repurchased and not CAUTION.search(en[:repurchased.end()])
                    and not re.search(r'\brepurchased\b', source, re.I)):
                add('treasury_retirement_not_repurchase', loc+'/en', en,
                    repurchased.start(), repurchased.end(), {pid},
                    'The cited event retires existing treasury shares, not a new repurchase. Preserve both languages and do not deduct cash twice.', loc+'/zh')
            # Rejecting a proposition is not asserting it. Abstaining here is
            # deliberate; these units remain in the semantic review worklist.
            if CAUTION.search(zh + ' ' + en):
                continue
            op = re.search(OP + ASSERTION, en, re.I)
            wrong = re.search(r'(?:运营|营业)收入', zh)
            if (op and wrong and not re.search(REVENUE, en, re.I)
                    and not re.search(r'(?:营业|经营|运营)(?:利润|亏损)', zh)
                    and re.search(OP_SOURCE, source, re.I)):
                add('bilingual_operating_profit_identity', loc+'/zh', zh,
                    wrong.start(), wrong.end(), {pid},
                    'Operating income/profit/loss refers to 营业利润/亏损, not revenue. Verify both languages against the original.', loc+'/en')
            # Only an assertive metric absent from its own source while a
            # different accounting metric is explicitly present. Absence alone
            # is not proof of a false claim; point to the binding for review.
            for name, pattern, source_pattern, other in (
                ('operating_profit', OP, OP_SOURCE, REVENUE+'|'+NET),
                ('net_income', NET, NET_SOURCE, REVENUE+'|'+OP),
            ):
                asserted = re.search(pattern + ASSERTION, en, re.I)
                if not asserted or re.search(source_pattern, source, re.I) or not re.search(other, source, re.I):
                    continue
                # Revenue-to-income calculations/ratios require a separate
                # computation binding; don't misclassify such comparisons here.
                if re.search(r'\b(?:ratio|margin|divided|difference|minus|calculated|derived|estimate)\b', en, re.I):
                    continue
                add('claim_metric_source_mismatch', loc+'/en', en,
                    asserted.start(), asserted.end(), {pid},
                    {'assertedMetric': name,
                     'action': 'This claim source does not name the asserted metric. Bind the correct source or retain pending semantic review; another paragraph elsewhere is not support for this citation.'})
    return findings
