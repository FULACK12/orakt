"""Evidence-addressable checks and incremental review. Fail closed, no AI verdicts.

Existing domain/ledger validators remain authoritative. These checks bind prose
to evidence; they do not prove that the prose follows from its citations.
"""
import copy
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from app.report_usage import digest, save

RULESET = 'report-quality/2'
SEMANTIC_PROTOCOL = 'evidence-entailment/1'
FIELDS = ('analysis', 'mechanism', 'counterEvidence', 'evidenceGaps', 'validationPlan')
CHAPTERS = ('business', 'financial', 'capital', 'competition', 'supply', 'macro', 'valuation', 'factors', 'conclusion')
REF = re.compile(r'PASSAGE:[a-f0-9]{16}')


def rules_digest():
    # Code changes invalidate receipts even if a version label was not bumped.
    files = ('report_quality.py', 'financial_period_ledger.py', 'dossier_semantic_guards.py',
             'dossier_accounting_checks.py', 'company_history_dossier.py', 'report_numeric_guards.py')
    return digest([Path(__file__).with_name(name).read_text(encoding='utf-8') for name in files])


def passages(packet):
    out = {}
    for group in packet.get('chapter_passages', {}).values():
        for p in group:
            if p['id'] in out and out[p['id']]['text'] != p['text']:
                raise ValueError('Conflicting passage identity')
            out[p['id']] = p
    return out


def units(documents, packet):
    """Stable JSON-pointer-like locations, bilingual spans and exact sources."""
    ps = passages(packet)
    out = []
    rules = rules_digest()
    shared = digest([RULESET, rules, SEMANTIC_PROTOCOL, packet.get('ticker'),
                     packet.get('accession'), packet.get('as_of_date'), packet.get('period_end'),
                     packet.get('raw_sha256'), packet.get('financial_ledger'), packet.get('facts')])
    for doc in documents:
        key = doc['chapter']
        section = doc.get('section', {})
        pairs = [(f'section/{f}', section.get(f, {})) for f in FIELDS]
        pairs += [(f'section/grounded_claims/{i}/statement', c.get('statement', {}))
                  for i, c in enumerate(section.get('grounded_claims', []))]
        for pointer, pair in pairs:
            for lang in ('zh', 'en'):
                text = pair.get(lang, '')
                refs = set(REF.findall(text))
                if 'grounded_claims' in pointer:
                    refs.add(section['grounded_claims'][int(pointer.split('/')[2])]['passage_id'])
                source = [{'id': pid, 'text': ps[pid]['text']} for pid in sorted(refs) if pid in ps]
                location = key + '/' + pointer + '/' + lang
                evidence_hash = digest(source)
                # Include fact ledger and raw document: a changed table or original
                # source invalidates prior acceptance, even if selected quotes match.
                fingerprint = digest([shared,
                    doc.get('factBindings'), doc.get('sourceMetadata'), text, source, pointer, lang])
                out.append({'id': location, 'chapter': key, 'pointer': pointer + '/' + lang,
                            'text': text, 'textSha256': digest(text), 'fingerprint': fingerprint,
                            'evidenceSha256': evidence_hash, 'sourceIds': sorted(refs),
                            'originalEvidence': source, 'language': lang})
    return out


def decimal(value):
    v = Decimal(str(value))
    if not v.is_finite():
        raise ValueError('Nonfinite number')
    return v


def check(packet, documents, *, complete=False):
    findings = []
    def add(code, location, actual=None, expected=None, severity='error'):
        findings.append({'code': code, 'location': location, 'actual': actual,
                         'expected': expected, 'severity': severity})
    keys = [d.get('chapter') for d in documents]
    if len(keys) != len(set(keys)) or set(keys) - set(CHAPTERS):
        add('chapter_identity', 'chapters', keys, list(CHAPTERS))
    if complete and set(keys) != set(CHAPTERS):
        add('missing_chapters', 'chapters', keys, list(CHAPTERS))
    ps = passages(packet)
    fact_index, ambiguous = {}, set()
    identical_duplicates = 0
    for f in packet.get('facts', []):
        old = fact_index.get(f['evidence_id'])
        if old is not None:
            if old == f:
                identical_duplicates += 1
            else:
                ambiguous.add(f['evidence_id'])
        fact_index[f['evidence_id']] = f
    for fid in sorted(ambiguous):
        add('conflicting_fact_identity', 'facts/' + fid)
    if packet.get('period_end', '') > packet.get('as_of_date', ''):
        add('future_period', 'packet/period_end')
    for f in packet.get('facts', []):
        location = 'facts/' + f['evidence_id']
        if (not f.get('filed_at') or f['filed_at'] > packet.get('as_of_date', '')
                or f.get('period_end', '') > packet.get('period_end', '')):
            add('fact_period', location)
        if f.get('period_start') and f['period_start'] > f.get('period_end', ''):
            add('period_order', location)
        if not f.get('unit'):
            add('missing_unit', location)
        try:
            decimal(f.get('value'))
        except (InvalidOperation, ValueError):
            add('invalid_number', location)
    from app.financial_period_ledger import build_ledger
    try:
        if build_ledger(packet) != packet.get('financial_ledger'):
            add('ledger_not_reproducible', 'financial_ledger')
    except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
        add('ledger_not_reproducible', 'financial_ledger', str(exc))
    for doc in documents:
        key = doc.get('chapter', '')
        if doc.get('ticker') != packet.get('ticker'):
            add('company_mismatch', key + '/ticker', doc.get('ticker'), packet.get('ticker'))
        meta = doc.get('sourceMetadata', {})
        for name in ('ticker', 'accession', 'as_of_date', 'period_end', 'raw_sha256'):
            if name in meta and meta[name] != packet.get(name):
                add('source_identity', key + '/sourceMetadata/' + name, meta[name], packet.get(name))
        for f in FIELDS:
            for lang in ('zh', 'en'):
                text = doc.get('section', {}).get(f, {}).get(lang)
                if not isinstance(text, str) or not text.strip():
                    add('missing_text', key + '/section/' + f + '/' + lang)
        for i, c in enumerate(doc.get('section', {}).get('grounded_claims', [])):
            p = ps.get(c.get('passage_id'))
            if not p or c.get('quote') != p['text']:
                add('quote_binding', key + '/section/grounded_claims/' + str(i))
        response = doc.get('generationResponse')
        if response is not None and (response.get('done') is not True or response.get('done_reason') == 'length'):
            add('truncation', key + '/generationResponse')
        # Optional explicit factual assertions: never treat missing annotations
        # as correct prose. Unannotated content stays in the semantic worklist.
        for b in doc.get('factBindings', []):
            loc = key + '/' + b.get('location', '')
            fact = fact_index.get(b.get('factId'))
            if not fact or b.get('factId') in ambiguous:
                add('unknown_fact', loc, b.get('factId')); continue
            for prop in ('unit', 'period_start', 'period_end', 'concept', 'dimensions'):
                if prop not in b or b[prop] != fact.get(prop):
                    add('fact_' + prop, loc, b.get(prop), fact.get(prop))
            if 'currency' in b and b['currency'] != fact.get('unit', '').split('/')[0]:
                add('fact_currency', loc, b['currency'], fact.get('unit'))
            try:
                # unit remains original (USD, shares, USD/shares); scale is
                # an explicit rendering multiplier, not a silent currency conversion.
                if decimal(b['value']) * decimal(b.get('scale', 1)) != decimal(fact['value']):
                    add('fact_value', loc, b.get('value'), fact['value'])
                surface = str(b.get('surface', '')).replace(',', '').replace('−', '-')
                if decimal(surface) != decimal(b['value']):
                    add('fact_surface_value', loc, surface, b['value'])
            except (KeyError, ValueError, InvalidOperation):
                add('invalid_number', loc)
    all_units = units(documents, packet)
    locations = {u['id']: u for u in all_units}
    for doc in documents:
        for b in doc.get('factBindings', []):
            loc = doc['chapter'] + '/' + b.get('location', '')
            u = locations.get(loc)
            start, end = b.get('start'), b.get('end')
            if (not u or not isinstance(start, int) or not isinstance(end, int)
                    or not 0 <= start < end <= len(u['text']) or u['text'][start:end] != b.get('surface')):
                add('fact_span', loc)
            scales = {'thousand':1000,'million':1000000,'billion':1000000000,'千':1000,'万':10000,'百万':1000000,'亿':100000000}
            if str(b.get('scale', 1)) != '1':
                label=b.get('scaleSurface')
                if (not u or label not in scales or label not in u['text']
                        or str(scales[label]) != str(b.get('scale'))):
                    add('fact_scale_label', loc)
    for u in all_units:
        if not u['sourceIds'] or set(u['sourceIds']) - ps.keys():
            add('source_binding', u['id'], u['sourceIds'])
        if '[NUMBER]' in u['text'] or 'PLACEHOLDER' in u['text']:
            add('placeholder', u['id'])
    from app.report_numeric_guards import check as numeric_checks
    findings.extend(numeric_checks(packet, documents))
    return {'version': RULESET, 'findings': findings, 'identicalDuplicateFacts':identical_duplicates,
            'deterministicPassed': not findings,
            'semanticApproval': False, 'state': 'checks_failed' if findings else 'semantic_review_pending'}


def worklist(packet, documents, *, receipts=(), complete=False):
    """Cache decisions only for exact content/evidence/protocol fingerprints.

    Receipt import is an explicit reviewer operation, not output the local model
    is allowed to auto-author. Every changed chapter invalidates its mechanisms,
    alternatives and validation; changes anywhere invalidate high-level conclusions.
    """
    current = units(documents, packet)
    cache = {r['id']: r for r in receipts}
    reusable = {u['id'] for u in current if (r := cache.get(u['id']))
                and r.get('fingerprint') == u['fingerprint'] and r.get('verdict') == 'supported'
                and r.get('reviewer') == 'codex_assistant' and r.get('rationale')
                and r.get('protocol') == SEMANTIC_PROTOCOL and r.get('ruleset') == RULESET
                and r.get('evidenceSha256') == u['evidenceSha256']
                and set(r.get('sourceIds', [])) == set(u['sourceIds'])}
    dirty = {u['id'] for u in current if u['id'] not in reusable}
    for uid in list(reusable):
        if uid.rsplit('/', 1)[0] + ('/en' if uid.endswith('/zh') else '/zh') in dirty:
            reusable.discard(uid)
    changed = {u['chapter'] for u in current if u['id'] not in reusable}
    # Deletions also invalidate downstream interpretation.
    changed |= {r['id'].split('/')[0] for r in receipts if r['id'] not in {u['id'] for u in current}}
    for u in current:
        if changed and u['chapter'] in ('valuation', 'factors', 'conclusion'):
            reusable.discard(u['id'])
        if u['chapter'] in changed and any('/' + f + '/' in u['id'] for f in FIELDS[1:]):
            reusable.discard(u['id'])
    checked = check(packet, documents, complete=complete)
    requested_facts = {b.get('factId') for d in documents for b in d.get('factBindings', [])}
    requested_comparisons = {c.get('comparison_id') for d in documents
                             for c in d.get('section', {}).get('comparison_checks', [])}
    return {'version': RULESET, 'rulesetSha256':rules_digest(), 'protocol': SEMANTIC_PROTOCOL,
            'identity': {k: packet.get(k) for k in ('ticker', 'accession', 'as_of_date', 'period_end', 'raw_sha256')},
            'checks': checked, 'reuseCount': len(reusable),
            'units': [{**u, 'state': 'review_reused' if u['id'] in reusable else 'pending',
                       'affectedBy': sorted(changed) if u['id'] not in reusable else []} for u in current],
            'reviewInstructions': 'Compare each statement with exact original evidence, context, period and fact table. Label supported/contradicted/insufficient. Check bilingual equivalence and downstream conclusions. Citation presence alone is not entailment. Never invent missing evidence.',
            'facts': [f for f in packet.get('facts', []) if f['evidence_id'] in requested_facts],
            'comparisons': [c for c in packet.get('financial_ledger', {}).get('comparisons', []) if c['id'] in requested_comparisons],
            'factTableSha256': digest(packet.get('facts', [])),
            'financialLedgerSha256': digest(packet.get('financial_ledger')),
            'contextPolicy': 'Original quotations are included per unit. Fetch additional facts/context from the frozen source when needed; unbound quantitative prose requires review. Do not resend the entire fact table per paragraph.',
            'autoPublish': False, 'automaticApprovalEnabled': False,
            'state': 'pending_review', 'unknownDependencies': 'conservative chapter and conclusion invalidation'}


def accept_receipts(plan, decisions):
    """Reject stale, missing or fabricated source bindings; no whole-report pass."""
    known = {u['id']: u for u in plan['units']}
    result = []
    seen = set()
    for r in decisions:
        u = known.get(r.get('id'))
        if not u or r['id'] in seen or r.get('fingerprint') != u['fingerprint']:
            raise ValueError('Unknown, duplicate or stale review location')
        seen.add(r['id'])
        if (r.get('reviewer') != 'codex_assistant' or not r.get('rationale')
                or r.get('verdict') not in ('supported', 'contradicted', 'insufficient')
                or set(r.get('sourceIds', [])) != set(u['sourceIds'])
                or r.get('evidenceSha256') != u['evidenceSha256']):
            raise ValueError('Explicit evidence-grounded semantic decision required')
        result.append({**r, 'protocol': SEMANTIC_PROTOCOL, 'ruleset': RULESET})
    return result


def repair(packet, documents, patches):
    """Only exact-span bilingual prose replacements; originals never mutated.

    A repair is a pending draft, even when all mechanical checks succeed.
    """
    before = {u['id']: u for u in units(documents, packet)}
    output = copy.deepcopy(documents)
    docs = {d['chapter']: d for d in output}
    seen = set()
    for p in patches:
        u = before.get(p.get('id'))
        if not u or p['id'] in seen or p.get('fingerprint') != u['fingerprint']:
            raise ValueError('Unknown, duplicate or stale repair target')
        seen.add(p['id'])
        if not isinstance(p.get('replacement'), str) or not p['replacement'].strip() or not p.get('reason'):
            raise ValueError('Repair needs replacement and reason')
        if set(REF.findall(p['replacement'])) != set(REF.findall(u['text'])):
            raise ValueError('Evidence changes require a new frozen source review')
        node = docs[u['chapter']]
        path = u['pointer'].split('/')
        for part in path[:-1]:
            node = node[int(part)] if isinstance(node, list) else node[part]
        node[path[-1]] = p['replacement']
        docs[u['chapter']]['state'] = 'content_review_pending'
        docs[u['chapter']]['published'] = False
        docs[u['chapter']].pop('review', None)
        docs[u['chapter']].pop('reviewDocument', None)
    old = {(f['code'], f['location']) for f in check(packet, documents)['findings']}
    new = check(packet, output)
    if {(f['code'], f['location']) for f in new['findings']} - old:
        raise ValueError('Repair introduced a new deterministic error')
    return {'documents': output, 'state': 'pending_semantic_recheck', 'published': False,
            'patches': patches, 'parentSha256': digest(documents), 'checks': new,
            'affectedReview': worklist(packet, output)}


def write_worklist(output, packet, documents, **kwargs):
    plan = worklist(packet, documents, **kwargs)
    save(Path(output), plan)
    return plan
