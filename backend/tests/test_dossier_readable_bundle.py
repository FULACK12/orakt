import copy
import pytest
from app.dossier_readable_bundle import render


def chapter():
    pair={'zh':'复审正文 <script>alert(1)</script>','en':'Reviewed bilingual content'}
    return {'ticker':'TEST','sourceFingerprint':'frozen','state':'assistant_reviewed','completeDossier':False,'published':False,'chapter':'business',
        'sourceMetadata':{'as_of_date':'2026-10-02','period_end':'2026-08-31','source_url':'https://www.sec.gov/Archives/example'},
        'section':{**{k:pair for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')},'grounded_claims':[{'passage_id':'PASSAGE:abc','quote':'Original <unsafe> text','statement':pair}]},
        'review':{'findings':['Scope corrected.'],'parentSha256':'parent','reviewSha256':'review'}}


def test_offline_bilingual_report_preserves_quotes_and_escapes_text():
    html=render([chapter()])
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'Original &lt;unsafe&gt; text' in html
    assert '1 / 9' in html and 'unpublished' in html
    assert 'id="zh"' in html and 'id="en"' in html
    assert 'Reviewed bilingual content' in html


def test_unsafe_source_link_not_rendered():
    d=chapter();d['sourceMetadata']['source_url']='javascript:alert(1)'
    assert 'javascript:' not in render([d])


def test_full_chapter_layout_does_not_claim_validated_alpha():
    from app.dossier_readable_bundle import LABELS
    from app.dossier_market_readiness import market_readiness
    items=[]
    for key in list(LABELS)[:9]:
        d=chapter();d['chapter']=key;items.append(d)
    items[-1]['marketReadiness']=market_readiness({'ticker':'TEST','as_of_date':'2026-10-02'})
    html=render(items)
    assert '9 / 9' in html
    assert 'factors are untested' in html
    assert 'Sector' not in html or 'sector' in html
    assert 'Not a complete company report' in html


def test_conflicting_coverage_is_rejected():
    a=chapter();b=chapter();b['chapter']='valuation'
    a['marketReadiness']={'version':'one'};b['marketReadiness']={'version':'two'}
    with pytest.raises(ValueError,match='Conflicting market readiness'):render([a,b])


@pytest.mark.parametrize('change',['company','fingerprint','state','duplicate'])
def test_no_mixed_or_unreviewed_bundle(change):
    a=chapter();b=copy.deepcopy(a);b['chapter']='capital'
    if change=='company':b['ticker']='OTHER'
    elif change=='fingerprint':b['sourceFingerprint']='new'
    elif change=='state':b['state']='content_review_pending'
    else:b['chapter']='business'
    with pytest.raises(ValueError):render([a,b])
