import copy
import pytest
from app.dossier_passages import add_accounting_transition_context,validate_transition_context,TOPICS
from app.dossier_semantic_guards import known_semantic_errors
from app.company_history_dossier import Section


def packet():
    return {'raw_sha256':'test','chapter_passages':{k:[] for k in TOPICS}}


def test_both_sides_are_exact_original_spans():
    text=('Preamble. Under the historical accounting principles, subscription accounting deferred revenue. '
          'The new accounting principles generally require two deliverables. The new accounting principles '
          'result in the recognition of substantially all revenue at sale. Software upgrade rights remain deferred. End.')
    p=packet();add_accounting_transition_context(p,text);validate_transition_context(p,text)
    assert len(p['accounting_transition_ids'])==2
    assert 'at sale' in p['chapter_passages']['business'][1]['text']
    before=copy.deepcopy(p)
    add_accounting_transition_context(p,text)
    assert p==before
    p['chapter_passages']['business'][1]['text']='invented'
    with pytest.raises(ValueError):validate_transition_context(p,text)


def test_no_transition_not_invented():
    p=packet();add_accounting_transition_context(p,'Company uses subscription accounting.')
    assert 'accounting_transition_ids' not in p


def test_observed_reversal_rejected_but_old_rule_description_allowed():
    p={'chapter_passages':{'business':[{'text':'The new accounting principles result in the recognition of substantially all revenue at sale.'}]}}
    def s(zh,en):
        return Section(**{k:{'zh':zh,'en':en} for k in ('analysis','mechanism','counterEvidence','evidenceGaps','validationPlan')},evidence_refs=['SEC:test'])
    assert known_semantic_errors(s('会计政策变更要求收入递延确认。','The accounting policy change required deferred revenue recognition.'),p)
    assert not known_semantic_errors(s('旧原则采用订阅会计；新原则主要在销售时确认硬件收入。','Historical principles deferred revenue; the new principles recognize most hardware revenue at sale.'),p)
