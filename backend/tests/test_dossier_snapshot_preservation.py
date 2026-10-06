import importlib.util
import hashlib
import json
from pathlib import Path
import pytest


def exporter():
    path=Path(__file__).resolve().parents[2]/'pilot-site/scripts/export_local_snapshot.py'
    spec=importlib.util.spec_from_file_location('snapshot_preservation_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('tamper',[False,True])
def test_snapshot_keeps_file_backed_history_or_stops_before_deleting(tmp_path,tamper):
    module=exporter();base=tmp_path/'private-data';folder=base/'research-reports';folder.mkdir(parents=True)
    (base/'company-dossiers').mkdir();(base/'dossier-reviews').mkdir()
    name='dossier-NVDA-20250528.json';review=b'{"reviewer":"fixture"}'
    report={'id':name[:-5],'ticker':'NVDA','dataCutoff':'2025-05-28','historical':{'asOf':'2025-05-28'},'questionEn':'English title'}
    dossier={'ticker':'NVDA','asOf':'2025-05-28','review':{'state':'assistant_reviewed','assistantRevisionHash':hashlib.sha256(review).hexdigest()}}
    (folder/name).write_text(json.dumps({'report':report}));(base/'company-dossiers'/name).write_text(json.dumps(dossier));(base/'dossier-reviews'/name).write_bytes(review if not tamper else b'changed')
    module.REPORT_DETAIL_OUTPUT=folder;exports={};module.dump=lambda name,value:exports.update({name:value})
    reports=[]
    if tamper:
        with pytest.raises(ValueError,match='unverified'):module.dump_research_report_assets(reports,generated_at='now')
        assert (folder/name).exists()
    else:
        module.dump_research_report_assets(reports,generated_at='now')
        assert reports==[report] and (folder/name).exists()
        item=exports['research-report-index.json']['reports'][0]
        assert item['historical']==report['historical'] and item['questionEn']=='English title'
