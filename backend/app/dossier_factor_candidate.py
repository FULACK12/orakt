"""Source-bound CVX cash-margin observation, never a tested alpha or return.

Preserves quarter/half-year columns and the OCI-versus-liability distinction.
Only the explicitly reviewed June half-year layout is supported.
"""
import hashlib
import re
from decimal import Decimal
from pathlib import Path
from app.dossier_cash_components import two_column_rows


def candidate_observation(packet, key='factors'):
    if packet.get('ticker') != 'CVX' or not packet['period_end'].endswith('-06-30'):
        raise ValueError('Explicit CVX half-year adapter required')
    if packet['as_of_date'] < packet['period_end']:
        raise ValueError('Filing precedes observation period')
    ids = set(packet.get('review_chapter_selection', {}).get(key, []))
    passages = [p for p in packet['chapter_passages'][key] if p['id'] in ids]

    def source(role):
        hits = [p for p in passages if p.get('contextRole') == role]
        if len(hits) != 1: raise ValueError('Missing/ambiguous factor context: ' + role)
        p = hits[0]
        h = hashlib.sha256((packet['raw_sha256'] + ':' + str(p['start']) + ':' + p['text']).encode()).hexdigest()
        if p['sourceHash'] != packet['raw_sha256'] or p['id'] != 'PASSAGE:' + h[:16]:
            raise ValueError('Changed factor source')
        return p

    income = source('income_eps_periods')
    oci = source('comprehensive_income_periods')
    cash = source('complete_cash_statement_with_headers')
    year = int(packet['period_end'][:4])
    header = f'Three Months Ended\nJune 30 Six Months Ended\nJune 30\n{year} {year-1} {year} {year-1}'

    def four_columns(p, title, units, label, metric):
        text = p['text']
        if not text.startswith(title + '\n') or header + '\n' + units not in text:
            raise ValueError('Exact statement, periods and units required')
        atom = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
        number = rf'(—|-?{atom}|\(\s*{atom}\s*\))'
        pattern = '^' + re.escape(label) + ''.join(r'[ \t]+\$?[ \t]*' + number for _ in range(4)) + r'[ \t]*$'
        ms = list(re.finditer(pattern, text, re.M))
        if len(ms) != 1: raise ValueError('Missing/ambiguous four-column row: ' + label)
        m = ms[0]
        if m.start() < text.index(header) + len(header): raise ValueError('Row before header')
        def value(s):
            if s == '—': return Decimal(0)
            return Decimal(re.sub(r'[(),\s]', '', s)) * (-1 if '(' in s else 1)
        columns = ('quarterCurrent', 'quarterPrevious', 'halfYearCurrent', 'halfYearPrevious')
        return {'metric': metric, 'label': label, 'unit': 'USD', 'displayScale': 1000000,
                'sourceId': p['id'], 'sourceHash': p['sourceHash'],
                'start': p['start'] + m.start(), 'end': p['start'] + m.end(), 'surface': m[0],
                'values': {k: str(value(s)) for k, s in zip(columns, m.groups())}}

    revenue = four_columns(income, 'CONSOLIDATED STATEMENT OF INCOME',
                           '(Millions of dollars, except per-share amounts)',
                           'Sales and other operating revenues', 'sales_and_other_operating_revenues')
    pension = four_columns(oci, 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME', '(Millions of dollars)',
                           'Income (taxes) benefit on defined benefit plans', 'oci_defined_benefit_plan_tax_effect_not_tax_payable')
    comprehensive = four_columns(oci, 'CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME', '(Millions of dollars)',
                                 'Comprehensive Income (Loss) Attributable to Chevron Corporation',
                                 'comprehensive_income_attributable_not_segment_operating_income')
    cash_rows = two_column_rows(cash, ['Net Cash Provided by Operating Activities',
                                     'Net decrease (increase) in operating working capital'], period_end=packet['period_end'])
    cfo = cash_rows['Net Cash Provided by Operating Activities']
    wc = cash_rows['Net decrease (increase) in operating working capital']
    denominators = [Decimal(revenue['values'][k]) for k in ('halfYearCurrent', 'halfYearPrevious')]
    if any(x <= 0 for x in denominators): raise ValueError('Positive matched revenue denominator required')
    margins = [Decimal(cfo[k]) / den for k, den in zip(('current', 'previous'), denominators)]
    # Unitless ratios, not investment returns. Interaction is a research hypothesis.
    pressure = [max(Decimal(0), -Decimal(wc[k])) / den for k, den in zip(('current', 'previous'), denominators)]
    return {'state': 'candidate_observation_only_not_backtested', 'ticker': packet['ticker'],
            'adapterCodeSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'periodEnd': packet['period_end'], 'periodStart': f'{year}-01-01',
            'comparisonStart': f'{year-1}-01-01', 'comparisonEnd': f'{year-1}-06-30',
            'disclosureDate': packet['as_of_date'], 'inputs': {'sales': revenue, 'cfo': cfo, 'workingCapitalAdjustment': wc},
            'sourceIds': [p['id'] for p in (income, oci, cash)],
            'classificationChecks': {'pensionTaxEffect': pension, 'comprehensiveIncome': comprehensive},
            'linearSignal': {'formula': 'CFO_current / sales_current - CFO_previous / sales_previous',
                             'unit': 'ratio_difference_not_return', 'value': str(margins[0] - margins[1]),
                             'currentCashMargin': str(margins[0]), 'previousCashMargin': str(margins[1])},
            'nonlinearCandidate': {'formula': 'linearSignal * max(0, -workingCapitalCashAdjustment_current) / sales_current',
                                   'interpretation': 'Hypothesis: working-capital cash use may weaken persistence; not a proven return sign.',
                                   'currentCashUseToSales': str(pressure[0]), 'previousCashUseToSales': str(pressure[1]),
                                   'value': str((margins[0] - margins[1]) * pressure[0])},
            'availabilityRule': 'Use only after verified publication; conservative next full trading session, never period end. Exact release time/calendar not supplied.',
            'comparableScopeWarning': 'Hess closed after the comparison half-year; do not interpret consolidated year-on-year change as organic growth.',
            'backtest': {'performed': False, 'returns': None, 'marketBenchmark': 'required', 'sectorBenchmark': 'required',
                         'costs': 'required', 'outOfSample': 'non-overlapping holdout required', 'validatedAlpha': False},
            'meaning': 'Accounting ratios and proposed interaction only. No causal proof, trading eligibility or predictive performance.'}
