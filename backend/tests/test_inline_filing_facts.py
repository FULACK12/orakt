from app.inline_filing_facts import monetary_facts

HEADER='''<xbrli:context id="c"><xbrli:entity><xbrli:segment><xbrldi:explicitMember dimension="a:RegionAxis">a:GreaterChinaMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2025-03-30</xbrli:startDate><xbrli:endDate>2025-06-28</xbrli:endDate></xbrli:period></xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'''

def parse(s):return monetary_facts(HEADER+s,filed_at='2025-08-01',source_url='https://www.sec.gov/filing.htm')

def test_scale_sign_period_dimension_and_source_anchor():
    facts,coverage=parse('<ix:nonFraction id="f-1" name="us-gaap:Revenue" unitRef="usd" contextRef="c" scale="6" sign="-" format="ixt:num-dot-decimal">15,369</ix:nonFraction>')
    f=facts[0]
    assert f['value']=='-15369000000' and f['period_start']=='2025-03-30'
    assert 'GreaterChinaMember' in f['concept'] and f['source_url'].endswith('#f-1')
    assert coverage['monetaryFacts']==1

def test_unsupported_transform_and_nil_are_not_guessed():
    facts,coverage=parse('<ix:nonFraction id="f-1" name="us-gaap:Revenue" unitRef="usd" contextRef="c" format="ixt:num-comma-decimal">15.369,1</ix:nonFraction><ix:nonFraction id="f-2" unitRef="usd" contextRef="c" xsi:nil="true">0</ix:nonFraction>')
    assert facts==[] and coverage['unsupportedOrNonMonetaryFacts']==2

def test_nested_formatting_and_explicit_exclusion():
    facts,_=parse('<ix:nonFraction id="f-3" name="us-gaap:Revenue" unitRef="usd" contextRef="c" format="ixt:num-dot-decimal"><span>1,234</span><ix:exclude>not a number</ix:exclude></ix:nonFraction>')
    assert facts[0]['value']=='1234'
