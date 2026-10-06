"""Keep accounting periods separate from later events known at the cutoff."""
from datetime import date


def validate_timeline(events, packet):
    seen=set();cutoff=date.fromisoformat(packet['as_of_date']);end=date.fromisoformat(packet['period_end'])
    for e in events:
        event=date.fromisoformat(e['eventDate']);filed=date.fromisoformat(e['sourceFiledAt'])
        expected='post_period_known_at_cutoff' if event>end else 'within_report_period'
        if e['id'] in seen or event>filed or filed>cutoff or e.get('periodRelation')!=expected:
            raise ValueError('Timeline date/period mismatch')
        if e.get('evidenceRef')!=packet['filing_ref'] or e.get('sourceUrl')!=packet['source_url']:
            raise ValueError('Timeline source mismatch')
        if e.get('recognition') not in {'disclosed_transaction','expected_charge','expected_benefit'}:
            raise ValueError('Timeline recognition status required')
        for field in ['title','interpretation']:
            if not all(e.get(field,{}).get(lang,'').strip() for lang in ['zh','en']):raise ValueError('Bilingual timeline required')
        seen.add(e['id'])
    return events
