"""Coverage diagnostics, never a valuation or an alpha-performance certificate.

Inspect immutable packet observations without silently fetching later prices.
Observation-date truncation is not a point-in-time vintage guarantee.
"""
from datetime import date
from math import isfinite


def market_readiness(packet):
    cutoff = date.fromisoformat(packet['as_of_date'])
    rows = []
    for series in packet.get('market_evidence', []):
        valid = {}; invalid = 0; future = 0; duplicates = 0
        for obs in series.get('observations', []):
            try:
                day = date.fromisoformat(obs['date'])
                value = float(obs['value'])
                if isinstance(obs['value'], bool) or not isfinite(value):
                    raise ValueError('Invalid value')
            except (ValueError, TypeError, KeyError):
                invalid += 1
                continue
            if day > cutoff:
                future += 1
                continue
            if day in valid:
                duplicates += 1
            valid[day] = value
        dates = sorted(valid)
        rows.append({'id': series['id'], 'name': series.get('name', series['id']),
                     'unit': series.get('unit'), 'count': len(dates),
                     'firstDate': str(dates[0]) if dates else None,
                     'lastDate': str(dates[-1]) if dates else None,
                     'calendarLagDays': (cutoff-dates[-1]).days if dates else None,
                     'invalidRows': invalid, 'futureRowsExcluded': future,
                     'duplicateDates': duplicates,
                     'vintage': series.get('vintage', 'unverified'),
                     'pointInTimeVerified': False})
    ids = {r['id'] for r in rows if r['count']}
    ticker = packet['ticker']
    equity = next((r for r in rows if r['id'] in
                   {f'MARKET:EQ:{ticker}', f'MARKET:US:{ticker}', f'MARKET:{ticker}'} and r['count']), None)
    # A diagnostic threshold, not an exchange-calendar completeness check.
    stale = equity is not None and equity['calendarLagDays'] > 7
    return {'version': 'market-readiness/v1', 'asOf': str(cutoff), 'series': rows,
            'equitySeriesId': equity['id'] if equity else None,
            'equityPriceState': 'missing' if equity is None else 'stale' if stale else 'recent_observation_only',
            'broadBenchmarkPresent': bool(ids & {'MARKET:TD:SPY', 'MARKET:SPY', 'MARKET:US:SPY'}),
            'sectorBenchmarkState': 'not_attested',
            'priceBasisComparable': False, 'filingReleaseTimeVerified': False,
            'valuationState': 'framework_only', 'factorState': 'hypothesis_only',
            'eligibleForPredictiveBacktest': False,
            'blockers': ['Exchange-session and corporate-action coverage not verified.',
                         'Sector benchmark and common total-return basis not attested.',
                         'Original release vintages and filing release time not attested.',
                         'No reviewed valuation model or out-of-sample factor experiment in this chapter packet.'],
            'rule': 'Recent observations alone do not establish completeness, contemporaneous availability, fair value or predictive alpha.'}
