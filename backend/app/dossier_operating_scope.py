"""Source-bound scope checks for CVX operating chapters; no causal approval."""
import hashlib
import re
from datetime import date
from pathlib import Path


ROLES = {
    'business': ('derivative_income_effect_table', 'income_eps_periods'),
    'competition': ('annual_run_rate_savings',),
    'supply': ('supply_contracts_complete', 'supply_purchase_commitments'),
    'macro': ('future_environment_standard', 'derivative_instruments_and_realized_impacts'),
}


def operating_scope(packet, chapter):
    if packet.get('ticker') != 'CVX' or chapter not in ROLES:
        raise ValueError('Explicit CVX operating adapter required')
    selected = set(packet.get('review_chapter_selection', {}).get(chapter, []))
    rows = [p for p in packet['chapter_passages'][chapter] if p['id'] in selected]
    sources = {}
    for role in ROLES[chapter]:
        hits = [p for p in rows if p.get('contextRole') == role]
        if len(hits) != 1: raise ValueError('Missing/ambiguous operating context: ' + role)
        p = hits[0]
        h = hashlib.sha256((packet['raw_sha256'] + ':' + str(p['start']) + ':' + p['text']).encode()).hexdigest()
        if p['sourceHash'] != packet['raw_sha256'] or p['id'] != 'PASSAGE:' + h[:16]:
            raise ValueError('Operating source changed')
        sources[role] = p
    boundaries, facts = [], {}
    if chapter == 'business':
        text = sources['derivative_income_effect_table']['text']
        year = int(packet['period_end'][:4])
        if not packet['period_end'].endswith('-06-30') or not text.startswith('Consolidated Statement of Income: The Effect of Derivatives\n'):
            raise ValueError('Derivative income classification requires full title')
        header = f'Three Months Ended\nJune 30 Gain / (Loss)\nSix Months Ended\nJune 30\nType of {year} {year-1} {year} {year-1}'
        if header not in text or 'Contract Statement of Income Classification (Millions of dollars)' not in text:
            raise ValueError('Derivative periods and units required')
        if not sources['income_eps_periods']['text'].startswith('CONSOLIDATED STATEMENT OF INCOME\n'):
            raise ValueError('Consolidated comparison statement required')
        boundaries = ['Derivative gains/losses classified in sales are not total consolidated sales.',
                      'Keep quarterly versus cumulative half-year columns separate.',
                      'Existing hedge-accounting timing is not a new accounting-policy adoption.']
    elif chapter == 'competition':
        text = sources['annual_run_rate_savings']['text']
        match = re.search(r'capturing \$(\d+(?:\.\d+)?) billion in annual run-rate savings', text)
        if not match: raise ValueError('Annual run-rate basis must remain explicit')
        facts = {'managementReportedSavings': match[1], 'unit': 'USD', 'displayScale': 1000000000,
                 'measurementBasis': 'annual_run_rate_not_cash_saved_during_reporting_period'}
        boundaries = ['Management-reported annual run-rate savings are not realized quarter/half-year cash savings.',
                      'Cost-reduction plans and reported progress do not establish peer ranking, market share or a proven moat.']
    elif chapter == 'supply':
        text = sources['supply_contracts_complete']['text']
        for phrase in ('fixed, indexed and performance-based contracts', 'demand planning, volume commitments', 'lag before the company’s costs reflect changes in market trends'):
            if phrase not in text: raise ValueError('Complete disclosed procurement context required')
        if 'pipeline and storage capacity, utilities, and petroleum products' not in sources['supply_purchase_commitments']['text']:
            raise ValueError('Purchase-commitment resource scope required')
        boundaries = ['Procurement methods are disclosed; effectiveness and supplier-level exposures remain unverified.',
                      'Risk lists are not evidence of a realized outage at a named supplier or route.',
                      'Take-or-pay commitments may create obligations; they are not unconditional protection against disruption.']
    else:
        text = sources['future_environment_standard']['text']
        m = re.search(r'becomes effective for fiscal years beginning after December 15, (\d{4})', text)
        if not m or 'The company is evaluating the effect of the standard' not in text:
            raise ValueError('Effective-date and evaluation status required')
        threshold = date(int(m[1]), 12, 15)
        if date.fromisoformat(packet['as_of_date']) >= threshold:
            raise ValueError('Future-effective scope must be reassessed at this cutoff')
        actual = sources['derivative_instruments_and_realized_impacts']['text']
        if 'resulted in significant mark-to-market earnings and cash flow impacts' not in actual:
            raise ValueError('Preserve disclosed realized impacts, not only generic risks')
        facts = {'fiscalYearsBeginningAfter': threshold.isoformat(), 'statusAtCutoff': 'company_evaluating_not_evidence_of_adoption'}
        boundaries = ['A future-effective standard under evaluation is not evidence of adoption or hidden current reclassification.',
                      'Derivative instruments and management-attributed realized mark-to-market impacts are disclosed.',
                      'Pension funding arrangements do not establish a hedge against operating supply-chain costs.']
    return {'state': 'scope_checked_not_semantic_approval', 'chapter': chapter,
            'adapterCodeSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'sourceIds': [p['id'] for p in sources.values()], 'facts': facts, 'boundaries': boundaries}
