from app.disclosure_reports import make_review

def test_native_units_and_one_filing_identity():
    facts=[dict(evidence_id=f'FACT:{i}',concept='Revenues',value=v,unit='USD',period_start=f'{year}-01-01',period_end=f'{year}-03-31',filed_at='2009-04-30') for i,(year,v) in enumerate([(2008,1943000000),(2009,1552000000)])]
    packet=dict(ticker='T',accession='a',as_of_date='2009-04-30',period_end='2009-03-31',source_url='https://www.sec.gov',raw_sha256='hash',facts=facts)
    r=make_review(packet,'Test','10-Q')
    assert r['comparisons'][0]['current']['value']==1552000000
    assert r['comparisons'][0]['periodType']=='quarter'
    assert r['comparisons'][0]['comparisonBasis']=='same_duration_year_over_year'
    assert r['predictiveConfidence'] is None
    assert r['type']=='disclosure_evidence_review'
