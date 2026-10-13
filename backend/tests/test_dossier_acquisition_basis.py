import hashlib
import pytest
from app.dossier_acquisition_basis import acquisition_basis


def packet():
    texts = {
        'acquisition_terms_and_accounting': 'The acquisition was accounted for as a business combination under ASC 805. The shares issued represented a proportion of the shares of Chevron common stock outstanding immediately after the transaction closed on July 18, 2025.',
        'acquisition_allocation_table': 'At July 18, 2025\n(Billions of dollars)\nTotal assets acquired 79.5\nTotal liabilities assumed 26.5\nNoncontrolling interest (2) 5.0\nNet assets acquired / purchase price $ 48.0',
        'acquired_debt_table': 'Hess Corporation (Millions of dollars)\nTotal Hess Corporation Debt $ 5,138\nTotal Hess Midstream Operations LP Debt $ 3,746\nUnamortized discounts and debt issuance costs ( 61 )\nTotal Long-Term Debt Assumed $ 8,823\nFair market value adjustment for debt acquired in the acquisition 247\nFair Market Value of Long-Term Debt Assumed $ 9,070',
    }
    p = {'ticker': 'CVX', 'as_of_date': '2026-08-06', 'raw_sha256': 'raw', 'chapter_passages': {'valuation': []}}
    for role, text in texts.items():
        p['chapter_passages']['valuation'].append({'contextRole': role, 'start': 100, 'text': text, 'sourceHash': 'raw'})
    rehash(p)
    return p


def rehash(p):
    for s in p['chapter_passages']['valuation']:
        s['id'] = 'PASSAGE:' + hashlib.sha256(('raw:100:' + s['text']).encode()).hexdigest()[:16]
    p['review_chapter_selection'] = {'valuation': [s['id'] for s in p['chapter_passages']['valuation']]}


def test_original_scopes_and_offsets():
    p = packet(); r = acquisition_basis(p)
    assert r['purchasePriceBillions'] == '48.0'
    assert r['debtCarryingMillions'] == '8823' and r['debtFairValueMillions'] == '9070'
    assert r['accountingStandard'] == 'ASC 805'
    assert any('not measured EPS dilution' in b for b in r['boundaries'])
    for f in r['inputs'].values():
        s = next(s for s in p['chapter_passages']['valuation'] if s['id'] == f['sourceId'])
        assert s['text'][f['start'] - 100:f['end'] - 100] == f['surface']


@pytest.mark.parametrize('index,old,new', [
    (0, 'ASC 805', 'IFRS 10'), (0, 'outstanding immediately after', 'weighted average during'),
    (1, 'Billions', 'Millions'), (1, '48.0', '53.0'), (1, '2025', '2026'),
    (2, '9,070', '90,700'), (2, '( 61 )', '61'), (2, 'Millions', 'Billions'),
])
def test_source_definition_unit_date_arithmetic_changes_fail(index, old, new):
    p = packet(); p['chapter_passages']['valuation'][index]['text'] = p['chapter_passages']['valuation'][index]['text'].replace(old, new)
    rehash(p)
    with pytest.raises(ValueError): acquisition_basis(p)


def test_source_mutation_and_missing_context_fail():
    p = packet(); p['chapter_passages']['valuation'][0]['text'] += 'mutation'
    with pytest.raises(ValueError, match='changed'): acquisition_basis(p)
    p = packet(); p['review_chapter_selection']['valuation'].pop()
    with pytest.raises(ValueError, match='Missing'): acquisition_basis(p)


def test_duplicate_row_and_pre_acquisition_cutoff_fail():
    p = packet(); p['chapter_passages']['valuation'][1]['text'] += '\nTotal assets acquired 79.5'
    rehash(p)
    with pytest.raises(ValueError, match='ambiguous'): acquisition_basis(p)
    p = packet(); p['as_of_date'] = '2025-07-17'
    with pytest.raises(ValueError, match='cutoff'): acquisition_basis(p)
