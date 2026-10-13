import copy
import json

import pytest

from app.report_quality_evaluation import evaluate
from app.report_quality_holdout_audit import audit, code_snapshot, file_hash
from app.report_usage import digest


def labeled_fixture():
    # Synthetic unit fixture, deliberately NOT an independently labeled report.
    case = {'id': 'fixture', 'groupId': 'TEST', 'split': 'holdout',
            'stratum': 'us_quarter_recent', 'usedForTuning': False,
            'synthetic': False, 'labelStatus': 'independently_adjudicated'}
    manifest = {'rulesFrozenBeforeHoldout': True, 'rulesetSha256': 'frozen', 'cases': [case]}
    row = {'id': case['id'], 'caseSha256': digest(case), 'rulesetSha256': 'frozen',
           'severeErrorPresent': True, 'severeErrorDetected': False,
           'correctContent': False, 'blocked': False,
           'repairAttempted': False, 'repairIntroducedError': False}
    return manifest, row


def test_empty_evaluation_has_unknown_rates():
    result = evaluate({'cases': []}, [])
    assert result['measurementState'] == 'not_measured'
    assert all(result[key] is None for key in
               ('severeMissRate', 'falseBlockRate', 'repairRegressionRate'))
    assert not result['automaticApprovalEnabled']


@pytest.mark.parametrize('changes', [
    {'correctContent': True},
    {'severeErrorPresent': False, 'severeErrorDetected': True},
    {'repairIntroducedError': True},
])
def test_contradictory_labels_are_excluded(changes):
    manifest, row = labeled_fixture()
    row.update(changes)
    result = evaluate(manifest, [row])
    assert result['independentCases'] == 0
    assert result['unqualifiedCases'] == 1
    assert 'contradictory_labels:fixture' in result['failures']


def test_miss_and_false_block_denominators_are_separate():
    manifest, row = labeled_fixture()
    result = evaluate(manifest, [row])
    assert result['severeMissRate'] == 1
    assert result['falseBlockRate'] is None
    assert result['repairRegressionRate'] is None
    assert not result['eligibleForEnablementReview']


def test_normalized_issuer_blocks_leakage_and_duplicate_groups():
    manifest, row = labeled_fixture()
    other = copy.deepcopy(manifest['cases'][0])
    other.update(id='other', groupId=' test ')
    manifest['cases'].append(other)
    second = dict(row, id='other', caseSha256=digest(other))
    result = evaluate(manifest, [row, second])
    assert 'non_independent_report_groups' in result['failures']
    assert result['independentCases'] == 0 and result['severeMissRate'] is None
    other['split'] = 'development'
    result = evaluate(manifest, [row])
    assert 'issuer_leakage_from_development' in result['failures']
    assert result['independentCases'] == 0


@pytest.mark.parametrize('duplicate', ['case', 'result'])
def test_duplicates_cannot_contribute_quality_metrics(duplicate):
    manifest, row = labeled_fixture()
    rows = [row]
    if duplicate == 'case':
        manifest['cases'].append(copy.deepcopy(manifest['cases'][0]))
    else:
        rows.append(copy.deepcopy(row))
    result = evaluate(manifest, rows)
    assert result['independentCases'] == 0
    assert result['severeMissRate'] is None


def test_missing_group_cannot_count_as_qualified():
    manifest, row = labeled_fixture()
    manifest['cases'][0]['groupId'] = ' '
    row['caseSha256'] = digest(manifest['cases'][0])
    result = evaluate(manifest, [row])
    assert result['independentCases'] == 0
    assert 'missing_report_group:fixture' in result['failures']


def audit_fixture(tmp_path):
    cold = tmp_path/'cold'
    cold.mkdir()
    source = cold/'source.json'
    source.write_text('private evidence bytes, not opened as prose', encoding='utf-8')
    case = {'id': 'EOG/0000821189-26-000149', 'groupId': 'EOG', 'split': 'holdout',
            'stratum': 'us_quarter_recent', 'sourcePath': str(source),
            'sourceSha256': file_hash(source), 'labelStatus': 'candidate_unseen_prose_not_adjudicated',
            'usedForTuning': False, 'synthetic': False}
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'cases': [case]}), encoding='utf-8')
    return cold, source, manifest, case


def test_readiness_is_not_semantic_evaluation_and_preserves_inputs(tmp_path):
    cold, source, manifest, case = audit_fixture(tmp_path)
    before = source.read_bytes(), manifest.read_bytes()
    out = tmp_path/'audit'
    audit(manifest, cold, out, ['CVX'])
    result = json.loads((out/'summary.json').read_text())
    assert result['verifiedSourceFiles'] == 1
    assert result['candidatesWithChapterDrafts'] == 0
    assert result['measurement']['severeMissRate'] is None
    assert result['codexTokens'] is None and result['localModelCalls'] == 0
    assert not result['candidates'][0]['proseOpened']
    assert not result['automaticApprovalEnabled']
    assert before == (source.read_bytes(), manifest.read_bytes())
    with pytest.raises(ValueError, match='Preserve'):
        audit(manifest, cold, out)


def test_source_tampering_exposure_and_draft_discovery(tmp_path):
    cold, source, manifest, case = audit_fixture(tmp_path)
    source.write_text('changed')
    draft = cold/'leader-one'/'drafts'/case['id']/'financial'/'chapter.json'
    draft.parent.mkdir(parents=True)
    draft.write_text('Do not parse this draft; inventory only.')
    out = tmp_path/'audit'
    audit(manifest, cold, out, ['eog'])
    result = json.loads((out/'summary.json').read_text())
    candidate = result['candidates'][0]
    assert candidate['chapterDraftCount'] == 1
    assert candidate['knownDevelopmentExposure']
    assert not candidate['sourceHashMatches']
    assert 'source_missing_or_hash_mismatch' in candidate['blockers']
    assert not candidate['eligibleForQualityMeasurement']


@pytest.mark.parametrize('identity', ['../outside', 'EOG/../../secret', 'OTHER/0000821189-26-000149'])
def test_candidate_path_traversal_and_identity_mismatch_rejected(tmp_path, identity):
    cold, source, manifest, case = audit_fixture(tmp_path)
    case['id'] = identity
    manifest.write_text(json.dumps({'cases': [case]}))
    with pytest.raises(ValueError, match='Invalid candidate identity'):
        audit(manifest, cold, tmp_path/'audit')


def test_snapshot_tracks_adapter_and_evaluator_changes(tmp_path):
    module = tmp_path/'adapter.py'
    module.write_text('value = 1')
    before = code_snapshot(tmp_path)
    assert before == code_snapshot(tmp_path)
    module.write_text('value = 2')
    assert before['sha256'] != code_snapshot(tmp_path)['sha256']
