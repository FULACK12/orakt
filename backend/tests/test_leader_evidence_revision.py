import copy
import pytest
from app.leader_evidence_revision import check_additive


def packets():
    old={'packet':{'ticker':'TEST','raw_sha256':'a','financial_ledger':{},
        'chapter_passages':{'business':[{'id':'a','text':'Business'}],'financial':[{'id':'b','text':'Cash'}]}}}
    new=copy.deepcopy(old)
    new['packet']['chapter_passages']['financial'].append({'id':'c','text':'Earnings bridge'})
    new['packet']['earnings_context_ids']=['c']
    return old,new


def test_only_unchanged_chapters_are_migratable():
    old,new=packets()
    assert check_additive(old,new)=={'business'}
    assert len(old['packet']['chapter_passages']['financial'])==1


@pytest.mark.parametrize('kind',['ledger','original','quote','duplicate'])
def test_reject_non_additive_changes(kind):
    old,new=packets();p=new['packet']
    if kind=='ledger':p['financial_ledger']={'changed':True}
    if kind=='original':p['raw_sha256']='b'
    if kind=='quote':p['chapter_passages']['business'][0]['text']='Altered'
    if kind=='duplicate':p['chapter_passages']['business'].append(p['chapter_passages']['business'][0])
    with pytest.raises(ValueError):check_additive(old,new)
