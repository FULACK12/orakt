import hashlib
import pytest
from app.dossier_capital_ratio import capital_ratio

TEXT='''Financial Ratios and Metrics
At June 30,
2026 At December 31,
2025
Net Debt Ratio (2) 13.1 % 15.6 %
(2) Net Debt Ratio for June 30, 2026, is calculated as short-term debt of $0.4 billion plus long-term debt of $36.7 billion (together, “total debt”) less cash and cash equivalents, time deposits, and marketable securities of $8.5 billion as a percentage of total debt less cash and cash equivalents, time deposits, and marketable securities, plus Chevron Corporation Stockholders’ Equity of $189.9 billion. For the December 31, 2025, calculation, please refer to the prior annual filing.'''

def packet(text=TEXT):
    start=500;h=hashlib.sha256(('raw:'+str(start)+':'+text).encode()).hexdigest()
    p={'id':'PASSAGE:'+h[:16],'text':text,'start':start,'sourceHash':'raw'}
    return {'ticker':'CVX','period_end':'2026-06-30','raw_sha256':'raw','chapter_passages':{'capital':[p]}},p

def test_rounded_formula_and_source_offsets():
    p,s=packet();r=capital_ratio(p,s['id'])
    assert r['totalDebt']=='37.1' and r['netDebt']=='28.6' and r['denominator']=='218.5'
    assert r['reproducedPercentAtSourcePrecision']=='13.1'
    assert r['inputs']['shortTermDebt']['value']=='0.4'
    assert r['comparisonEnd']=='2025-12-31'
    for f in r['inputs'].values():assert s['text'][f['start']-s['start']:f['end']-s['start']]==f['surface']

@pytest.mark.parametrize('old,new', [('plus Chevron','minus Chevron'),('$0.4','$4'),('13.1 %','12.0 %'),
                                  ('2026 At December 31','2025 At December 31'),
                                  ('cash and cash equivalents, time deposits','cash including restricted cash, time deposits')])
def test_formula_scale_period_cash_scope_changes_fail(old,new):
    p,s=packet(TEXT.replace(old,new))
    with pytest.raises(ValueError):capital_ratio(p,s['id'])

def test_changed_or_ambiguous_source_fails():
    p,s=packet();s['text']+=' modified'
    with pytest.raises(ValueError,match='changed'):capital_ratio(p,s['id'])
    p,s=packet(TEXT+'\nNet Debt Ratio (2) 13.1 % 15.6 %')
    with pytest.raises(ValueError,match='ambiguous'):capital_ratio(p,s['id'])
