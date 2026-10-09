import pytest
from app.legacy_sec_originals import submission_name,verify_submission


def test_only_index_named_submission_selected():
    assert submission_name({'directory':{'item':[{'name':'0000320193-94-000002.txt'}]}},'0000320193-94-000002')=='0000320193-94-000002.txt'
    with pytest.raises(ValueError):submission_name({'directory':{'item':[{'name':'../secret.txt'}]}},'0000320193-94-000002')


def test_form_and_accession_required():
    body='ACCESSION NUMBER: 0000320193-94-000002\n<DOCUMENT>\n<TYPE>10-Q\n<TEXT>Original'
    verify_submission(body,'0000320193-94-000002','10-Q')
    with pytest.raises(ValueError):verify_submission(body,'0000320193-94-000003','10-Q')
    with pytest.raises(ValueError):verify_submission(body,'0000320193-94-000002','10-K')
