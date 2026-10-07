from types import SimpleNamespace
from app.dossier_semantic_guards import known_semantic_errors

def section(text):
    pair=SimpleNamespace(zh='经核对的描述。',en=text)
    return SimpleNamespace(**{k:pair for k in ['analysis','mechanism','counterEvidence','evidenceGaps','validationPlan']},grounded_claims=[])

def test_distinct_subjects_in_contrast_are_not_dilution_accretion():
    assert not known_semantic_errors(section('Weaker earnings or new dilution can offset fewer shares, while operations can improve EPS without repurchases.'),{})

def test_actual_dilution_accretion_is_still_rejected():
    assert known_semantic_errors(section('New dilution increases EPS.'),{})
    assert known_semantic_errors(section('Operations are stable, but dilution increases EPS.'),{})
