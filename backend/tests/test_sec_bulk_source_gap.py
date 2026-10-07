import io,json,zipfile
import pytest
from app.sec_bulk_import import optional_facts,already_processed


def test_missing_member_is_not_fake_empty_facts():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('present.json','{}');z.writestr('broken.json','bad')
    with zipfile.ZipFile(data) as z:
        assert optional_facts(z,'missing.json') is None
        assert optional_facts(z,'present.json')=={}
        with pytest.raises(json.JSONDecodeError):optional_facts(z,'broken.json')


def test_gap_checkpoint_only_skips_same_archives():
    ids={'submissions.zip':'a','companyfacts.zip':'b'}
    prior=('source_gap',json.dumps({'archives':ids}))
    assert already_processed(prior,ids)
    assert not already_processed(prior,{**ids,'companyfacts.zip':'new'})
    assert not already_processed(('failed','{}'),ids)
