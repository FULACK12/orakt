import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[2]/'scripts/replay_report_writer_gate.py'
spec=importlib.util.spec_from_file_location('writer_replay_test',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


@pytest.mark.parametrize('split,tuning',[('holdout',False),('development',False)])
def test_replay_refuses_unexposed_source_before_reading_prose(tmp_path,monkeypatch,split,tuning):
    root=tmp_path/'trial';root.mkdir();source=root/'source.json';source.write_text('reserved content')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'cases':[{
        'id':'TEST/a','groupId':'TEST','split':split,'usedForTuning':tuning,
        'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}))
    def forbidden(*a):raise AssertionError('Do not open reserved prose')
    monkeypatch.setattr(module,'load_frozen_packet',forbidden)
    with pytest.raises(ValueError,match='exposed development'):
        module.replay(root,tmp_path/'corrected.json',manifest,tmp_path,tmp_path/'out.json')
    assert not (tmp_path/'out.json').exists()


def test_replay_never_overwrites_an_audit(tmp_path):
    target=tmp_path/'old.json';target.write_text('preserve')
    with pytest.raises(ValueError,match='Preserve previous'):
        module.replay(tmp_path,tmp_path/'a',tmp_path/'b',tmp_path,target)
    assert target.read_text()=='preserve'
