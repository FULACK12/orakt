import hashlib
import json
import pytest
import app.dossier_report_review as m
from app.company_history_dossier import write_json


def fixture(tmp_path,monkeypatch):
    p=tmp_path/'parent';out=tmp_path/'reviewed';r=tmp_path/'audit.json'
    packet={'ticker':'TEST','accession':'acc','as_of_date':'2009-06-26','period_end':'2009-05-29','facts':[],'financial_ledger':{}}
    original={'fingerprint':'frozen','packet':packet};write_json(p/'source.json',original)
    source_raw=(p/'source.json').read_bytes()
    d={'ticker':'TEST','accession':'acc','asOf':packet['as_of_date'],'periodEnd':packet['period_end'],
       'sourceFingerprint':'frozen','sourcePacketSha256':hashlib.sha256(source_raw).hexdigest(),
       'facts':[],'financialLedger':{},'chapters':[], 'structureComplete':True,
       'published':False,'eligibleForPredictiveBacktest':False,'validatedAlpha':False,
       'review':{'state':'whole_report_review_pending'}}
    write_json(p/'dossier.json',d);(p/'readable.html').write_text('pending')
    sha=hashlib.sha256((p/'dossier.json').read_bytes()).hexdigest()
    write_json(p/'manifest.json',{'dossierSha256':sha,'readableSha256':hashlib.sha256((p/'readable.html').read_bytes()).hexdigest()})
    review={'reviewer':'codex_assistant','state':m.STATE,'parentSha256':sha,'sourceFingerprint':'frozen',
            'checks':{k:'Explicit audit of source, scope and limitations performed.' for k in m.CHECKS}}
    write_json(r,review)
    monkeypatch.setattr(m,'load_frozen_packet',lambda *a:(original,source_raw))
    monkeypatch.setattr(m,'validate_chapters',lambda *a:[])
    monkeypatch.setattr(m,'render',lambda *a:'reviewed limited research')
    return p,r,out,review


def test_finalization_retains_parent_and_never_enables_trading(tmp_path,monkeypatch):
    p,r,out,_=fixture(tmp_path,monkeypatch);old=(p/'dossier.json').read_bytes()
    result=m.finalize(p,r,tmp_path,out)
    assert result['review']['state']==m.STATE and not result['review']['humanAccepted']
    assert not result['published'] and not result['eligibleForPredictiveBacktest'] and not result['validatedAlpha']
    assert (p/'dossier.json').read_bytes()==old
    assert result['wholeReportAudit']['checks']
    with pytest.raises(ValueError,match='Preserve'):m.finalize(p,r,tmp_path,out)


@pytest.mark.parametrize('bad',['parent','html','review_hash','checks','source','facts','eligibility'])
def test_finalization_fails_closed(tmp_path,monkeypatch,bad):
    p,r,out,review=fixture(tmp_path,monkeypatch)
    if bad=='parent':(p/'dossier.json').write_text('{}')
    elif bad=='html':(p/'readable.html').write_text('changed')
    elif bad=='review_hash':review['parentSha256']='wrong';write_json(r,review)
    elif bad=='checks':review['checks']={};write_json(r,review)
    else:
        d=json.loads((p/'dossier.json').read_text(encoding='utf-8'))
        if bad=='source':d['sourcePacketSha256']='wrong'
        if bad=='facts':d['facts']=[{'invented':1}]
        if bad=='eligibility':d['validatedAlpha']=True
        write_json(p/'dossier.json',d)
        sha=hashlib.sha256((p/'dossier.json').read_bytes()).hexdigest()
        manifest=json.loads((p/'manifest.json').read_text(encoding='utf-8'));manifest['dossierSha256']=sha
        write_json(p/'manifest.json',manifest);review['parentSha256']=sha;write_json(r,review)
    with pytest.raises(ValueError):m.finalize(p,r,tmp_path,out)
    assert not out.exists()


def test_queue_links_exact_parent_and_preserves_prior_state(tmp_path,monkeypatch):
    from app.company_completion import connect, mark
    p,r,out,_=fixture(tmp_path,monkeypatch);d=m.finalize(p,r,tmp_path,out);root=tmp_path/'queue'
    with connect(root) as db:
        mark(db,'reports','acc','TEST','assembled_review_pending',{'dossierSha256':'wrong'})
    with pytest.raises(ValueError,match='parent changed'):m.register(root,out)
    with connect(root) as db:
        mark(db,'reports','acc','TEST','assembled_review_pending',{'dossierSha256':d['review']['parentSha256']})
    assert m.register(root,out) and not m.register(root,out)
    with connect(root) as db:
        row=db.execute('SELECT * FROM jobs').fetchone()
        assert row['state']==m.STATE and not json.loads(row['detail'])['published']
        assert db.execute('SELECT count(*) FROM report_transitions').fetchone()[0]==1
