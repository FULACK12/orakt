from app.complete_frozen_chapters import prepare_evidence

def test_values_dates_and_comparison_periods_are_not_masked():
    packet={'facts':[], 'excerpts':[{'text':'Sales in 2009 were 1552 million vs 1943 million in 2008.'}], 'financial_ledger':{'accountingRules':[], 'comparisons':[]}, 'market_evidence':[]}
    evidence=prepare_evidence(packet,'financial')
    assert '1552 million' in evidence['excerpts'][0]['text']
    assert '2008' in evidence['excerpts'][0]['text']
    assert '[value in source table]' not in str(evidence)
    assert any('year-on-year' in s for s in evidence['research_constraints'])
