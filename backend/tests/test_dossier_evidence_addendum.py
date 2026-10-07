import json
import hashlib
import pytest
from app.company_history_dossier import write_json
from app.company_completion import connect,mark
from app.dossier_evidence_addendum import register


def artifacts(tmp_path):
    out=tmp_path/'evidence';root=tmp_path/'queue'
    d={'ticker':'TEST','accession':'acc','parentSha256':'parent','review':{'state':'assistant_reviewed_source_addendum'},
       'published':False,'eligibleForPredictiveBacktest':False,'validatedAlpha':False,'facts':{'cash':{'a':{},'b':{}}}}
    write_json(out/'addendum.json',d);(out/'readable.html').write_text('review')
    write_json(out/'manifest.json',{'addendumSha256':hashlib.sha256((out/'addendum.json').read_bytes()).hexdigest(),
        'readableSha256':hashlib.sha256((out/'readable.html').read_bytes()).hexdigest()})
    with connect(root) as db:mark(db,'reports','acc','TEST','assistant_reviewed_research_only',{'dossierSha256':'parent','published':False})
    return root,out


def test_attachment_is_idempotent_not_new_completed_report(tmp_path):
    root,out=artifacts(tmp_path)
    assert register(root,out) and not register(root,out)
    with connect(root) as db:
        rows=db.execute('SELECT * FROM jobs').fetchall();assert len(rows)==1
        assert rows[0]['state']=='assistant_reviewed_research_only'
        d=json.loads(rows[0]['detail']);assert not d['published'] and d['evidenceAddendum']['cashSourceCells']==2
        assert db.execute('SELECT count(*) FROM report_transitions').fetchone()[0]==1


@pytest.mark.parametrize('bad',['hash','html','parent','state'])
def test_attachment_does_not_replace_changed_parent(tmp_path,bad):
    root,out=artifacts(tmp_path)
    if bad=='hash':(out/'addendum.json').write_text('{}')
    elif bad=='html':(out/'readable.html').write_text('changed')
    else:
        with connect(root) as db:
            mark(db,'reports','acc','TEST','running' if bad=='state' else 'assistant_reviewed_research_only',{'dossierSha256':'wrong' if bad=='parent' else 'parent'})
    with pytest.raises(ValueError):register(root,out)
