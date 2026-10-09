import pytest
from app.us_leader_source_batch import selected_companies


def test_scope_does_not_expand_to_ashares():
    assert selected_companies({'companies':[{'ticker':'AAPL','marketRegion':'us'}]})==['AAPL']
    with pytest.raises(ValueError):selected_companies({'companies':[{'ticker':'000001','marketRegion':'china'}]})
    with pytest.raises(ValueError):selected_companies({'companies':[{'ticker':'AAPL','marketRegion':'us'}]*2})
