"""Exact CVX/Hess acquisition table checks, not an equity valuation or approval."""
import hashlib
import re
from decimal import Decimal
from pathlib import Path


def acquisition_basis(packet):
    if packet.get('ticker') != 'CVX':
        raise ValueError('Unsupported acquisition adapter issuer')
    selected = set(packet.get('review_chapter_selection', {}).get('valuation', []))
    rows = [p for p in packet['chapter_passages']['valuation'] if p['id'] in selected]

    def source(role):
        hits = [p for p in rows if p.get('contextRole') == role]
        if len(hits) != 1:
            raise ValueError('Missing/ambiguous acquisition context: ' + role)
        p = hits[0]
        h = hashlib.sha256((packet['raw_sha256'] + ':' + str(p['start']) + ':' + p['text']).encode()).hexdigest()
        if p['sourceHash'] != packet['raw_sha256'] or p['id'] != 'PASSAGE:' + h[:16]:
            raise ValueError('Acquisition source changed')
        return p

    terms = source('acquisition_terms_and_accounting')
    allocation = source('acquisition_allocation_table')
    debt = source('acquired_debt_table')
    if ('accounted for as a business combination under ASC 805' not in terms['text'] or
        'shares of Chevron common stock outstanding immediately after the transaction closed' not in terms['text']):
        raise ValueError('Acquisition accounting/share-denominator definition changed')
    date = re.search(r'^At (July 18, 2025)\n\(Billions of dollars\)', allocation['text'])
    if not date or 'July 18, 2025' not in terms['text'] or packet['as_of_date'] < '2025-07-18':
        raise ValueError('Unsupported acquisition date/units/cutoff')
    if 'Hess Corporation (Millions of dollars)' not in debt['text']:
        raise ValueError('Acquired debt table requires million-dollar units')
    inputs = {}

    def amount(p, label, scale, negative=False):
        pattern = '^' + re.escape(label) + r'\s+\$?\s*' + (r'\(\s*([\d,.]+)\s*\)' if negative else r'([\d,.]+)') + r'\s*$'
        matches = list(re.finditer(pattern, p['text'], re.M))
        if len(matches) != 1:
            raise ValueError('Missing/ambiguous acquisition row: ' + label)
        m = matches[0]
        v = Decimal(m[1].replace(',', '')) * (-1 if negative else 1)
        inputs[label] = {'value': str(v), 'unit': 'USD', 'displayScale': scale,
                         'sourceId': p['id'], 'sourceHash': p['sourceHash'],
                         'start': p['start'] + m.start(1), 'end': p['start'] + m.end(1), 'surface': m[1]}
        return v

    assets = amount(allocation, 'Total assets acquired', 10**9)
    liabilities = amount(allocation, 'Total liabilities assumed', 10**9)
    nci = amount(allocation, 'Noncontrolling interest (2)', 10**9)
    price = amount(allocation, 'Net assets acquired / purchase price', 10**9)
    if assets - liabilities - nci != price:
        raise ValueError('Acquisition purchase-price allocation does not reconcile')
    hess = amount(debt, 'Total Hess Corporation Debt', 10**6)
    midstream = amount(debt, 'Total Hess Midstream Operations LP Debt', 10**6)
    discounts = amount(debt, 'Unamortized discounts and debt issuance costs', 10**6, True)
    carrying = amount(debt, 'Total Long-Term Debt Assumed', 10**6)
    adjustment = amount(debt, 'Fair market value adjustment for debt acquired in the acquisition', 10**6)
    fair = amount(debt, 'Fair Market Value of Long-Term Debt Assumed', 10**6)
    if hess + midstream + discounts != carrying or carrying + adjustment != fair:
        raise ValueError('Acquired debt bridge does not reconcile')
    return {'state': 'acquisition_basis_reconciled_not_valuation_approval', 'acquisitionDate': '2025-07-18',
            'adapterCodeSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'sourceIds': [p['id'] for p in (terms, allocation, debt)], 'inputs': inputs,
            'accountingStandard': 'ASC 805', 'purchasePriceBillions': str(price),
            'debtCarryingMillions': str(carrying), 'debtFairValueMillions': str(fair),
            'boundaries': [
                'Share consideration and assumed debt are distinct; issuance is not repayment of assumed debt.',
                'Issued-share ownership proportion immediately after closing is not measured EPS dilution.',
                'Acquisition-date fair values and provisional allocation are not current company equity value.',
                'Allocation long-term debt includes finance leases; do not equate it with the separate debt bridge.',
                'No stock price, target price, return, accretion or investment approval is computed.',
            ]}
