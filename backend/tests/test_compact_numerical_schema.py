import re
from app.dossier_compact_writer import schema_for


def test_qualitative_schema_preserves_identifiers_but_blocks_quantities():
    schema=schema_for({'passages':[{'id':'PASSAGE:0123456789abcdef'}],'technicalNames':['MI300','FAS 115']},constrain_numbers=True)
    for field in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']:
        pattern=schema['properties'][field]['properties']['en']['pattern']
        assert re.fullmatch(pattern,'MI300 and FAS 115 are named source terms.')
        assert not re.fullmatch(pattern,'Revenue fell 9% in 2023.')
        assert not re.fullmatch(pattern,'MI400 is not supplied.')
    claims=schema['properties']['claims']['items']['properties']['statement']['properties']['zh']['pattern']
    assert re.fullmatch(claims,'披露了MI300。') and not re.fullmatch(claims,'收入54亿美元。')


def test_unsuccessful_decoding_experiment_is_not_the_batch_default():
    schema=schema_for({'passages':[{'id':'PASSAGE:0123456789abcdef'}]})
    assert 'pattern' not in schema['properties']['analysis']['properties']['en']
